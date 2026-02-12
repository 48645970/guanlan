# -*- coding: utf-8 -*-
"""
组合随机交易策略（测试用）

每隔 N 秒对每个合约随机设置目标仓位，通过 rebalance_portfolio 自动调仓。
用于验证组合策略引擎的发单、撤单、成交回调是否正常。

Author: 海山观澜
"""

import random
from datetime import datetime, timedelta

from pydantic import Field

from guanlan.core.trader.cta.template import BaseParams, BaseState
from guanlan.core.trader.portfolio.template import PortfolioTemplate
from guanlan.core.trader.portfolio.utility import PortfolioBarGenerator
from vnpy.trader.constant import Direction
from vnpy.trader.object import BarData, TickData, TradeData, OrderData


class RandomPortfolioParams(BaseParams):
    """组合随机策略参数"""

    interval: int = Field(default=15, title="交易间隔(秒)", ge=3, le=300)
    max_pos: int = Field(default=2, title="最大持仓手数", ge=1, le=10)
    price_add: int = Field(default=5, title="委托加点", ge=0, le=50)


class RandomPortfolioState(BaseState):
    """组合随机策略状态"""

    trade_count: int = Field(default=0, title="成交次数")
    rebalance_count: int = Field(default=0, title="调仓次数")


class RandomPortfolioStrategy(PortfolioTemplate):
    """组合随机交易策略"""

    author = "海山观澜"
    params = RandomPortfolioParams()
    state = RandomPortfolioState()

    def __init__(self, portfolio_engine, strategy_name, vt_symbols, gateway_name):
        super().__init__(portfolio_engine, strategy_name, vt_symbols, gateway_name)

        self._next_trade_time: datetime | None = None
        self._last_prices: dict[str, float] = {}

        # 组合K线生成器（Tick → 分钟K线）
        self.pbg = PortfolioBarGenerator(self.on_bars)

    def on_init(self):
        """策略初始化"""
        self.write_log("组合随机策略初始化")

    def on_start(self):
        """策略启动"""
        self.write_log("组合随机策略启动，准备疯狂交易")
        self._next_trade_time = None

    def on_stop(self):
        """策略停止"""
        self.write_log(
            f"组合随机策略停止，共调仓 {self.state.rebalance_count} 次，"
            f"成交 {self.state.trade_count} 次"
        )

    def on_reset(self):
        """重置策略状态"""
        self.write_log(
            f"组合随机策略重置，清零前：调仓 {self.state.rebalance_count} 次，"
            f"成交 {self.state.trade_count} 次"
        )
        self.state.trade_count = 0
        self.state.rebalance_count = 0
        self._next_trade_time = None
        self.put_event()

    def on_tick(self, tick: TickData):
        """Tick 回调：记录最新价，到时间就随机调仓"""
        self._last_prices[tick.vt_symbol] = tick.last_price

        # 同时合成K线（虽然 on_bars 里不做逻辑，但保持生成器运行）
        self.pbg.update_tick(tick)

        now = tick.datetime
        if not now:
            return

        if self._next_trade_time is None:
            self._next_trade_time = now + timedelta(seconds=self.params.interval)
            return

        if now < self._next_trade_time:
            return

        self._next_trade_time = now + timedelta(seconds=self.params.interval)
        self._random_rebalance()

    def _random_rebalance(self):
        """随机设置目标仓位并调仓"""
        max_pos = self.params.max_pos

        # 为每个合约随机设置目标仓位
        for vt_symbol in self.vt_symbols:
            target = random.randint(-max_pos, max_pos)
            self.set_target(vt_symbol, target)
            current = self.pos_data.get(vt_symbol, 0)
            if target != current:
                self.write_log(
                    f"{vt_symbol} 目标 {current} → {target}"
                )

        # 构造 bars 用于 rebalance（用最新价模拟）
        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            price = self._last_prices.get(vt_symbol, 0)
            if not price:
                continue

            # 用最新价构造一个简单的 BarData
            symbol, exchange_str = vt_symbol.rsplit(".", 1)
            from vnpy.trader.constant import Exchange, Interval
            bar = BarData(
                symbol=symbol,
                exchange=Exchange(exchange_str),
                datetime=datetime.now(),
                interval=Interval.MINUTE,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=0,
                gateway_name="",
            )
            bars[vt_symbol] = bar

        if bars:
            self.rebalance_portfolio(bars)
            self.state.rebalance_count += 1

        self.put_event()

    def on_bars(self, bars: dict[str, BarData]):
        """K线切片回调（随机策略不依赖K线信号）"""
        pass

    def calculate_price(
        self,
        vt_symbol: str,
        direction: Direction,
        reference: float,
    ) -> float:
        """加滑点"""
        if direction == Direction.LONG:
            return reference + self.params.price_add
        else:
            return reference - self.params.price_add

    def update_trade(self, trade: TradeData) -> None:
        """成交回调"""
        super().update_trade(trade)
        self.state.trade_count += 1
        self.write_log(
            f"成交：{trade.vt_symbol} {trade.direction.value} "
            f"{trade.offset.value} {trade.volume} 手 @ {trade.price}"
        )
        self.put_event()

    def update_order(self, order: OrderData) -> None:
        """委托回调"""
        super().update_order(order)
        self.put_event()
