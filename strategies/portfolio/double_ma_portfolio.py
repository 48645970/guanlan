# -*- coding: utf-8 -*-
"""
组合双均线策略（测试用）

每个合约独立计算双均线交叉信号，通过 set_target + rebalance_portfolio 调仓。
用于验证组合策略引擎的完整生命周期。

Author: 海山观澜
"""

from pydantic import Field

from guanlan.core.trader.cta.template import BaseParams, BaseState
from guanlan.core.trader.portfolio.template import PortfolioTemplate
from guanlan.core.trader.portfolio.utility import PortfolioBarGenerator
from vnpy.trader.constant import Direction
from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import ArrayManager


class PortfolioDoubleMaParams(BaseParams):
    """组合双均线参数"""

    fast_window: int = Field(default=10, title="快线周期", ge=1, le=200)
    slow_window: int = Field(default=20, title="慢线周期", ge=1, le=500)
    fixed_size: int = Field(default=1, title="固定手数", ge=1, le=100)
    price_add: int = Field(default=5, title="委托加点", ge=0, le=50)


class PortfolioDoubleMaState(BaseState):
    """组合双均线状态"""

    pos: int = Field(default=0, title="(未使用)")


class PortfolioDoubleMaStrategy(PortfolioTemplate):
    """组合双均线策略"""

    author = "海山观澜"
    params = PortfolioDoubleMaParams()
    state = PortfolioDoubleMaState()

    def __init__(self, portfolio_engine, strategy_name, vt_symbols, gateway_name):
        super().__init__(portfolio_engine, strategy_name, vt_symbols, gateway_name)

        # 每个合约一个 ArrayManager
        self.ams: dict[str, ArrayManager] = {}
        for vt_symbol in self.vt_symbols:
            self.ams[vt_symbol] = ArrayManager()

        # 组合K线生成器（Tick → 分钟K线）
        self.pbg = PortfolioBarGenerator(self.on_bars)

    def on_init(self):
        """策略初始化"""
        self.write_log("策略初始化")
        self.load_bars(10)

    def on_start(self):
        """策略启动"""
        self.write_log("策略启动")

    def on_stop(self):
        """策略停止"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """Tick 回调 → 合成分钟K线"""
        self.pbg.update_tick(tick)

    def on_bars(self, bars: dict[str, BarData]):
        """K线切片回调"""
        for vt_symbol, bar in bars.items():
            am: ArrayManager = self.ams[vt_symbol]
            am.update_bar(bar)

            if not am.inited:
                continue

            fast_ma = am.sma(self.params.fast_window, array=True)
            slow_ma = am.sma(self.params.slow_window, array=True)

            fast_ma0 = fast_ma[-1]
            fast_ma1 = fast_ma[-2]
            slow_ma0 = slow_ma[-1]
            slow_ma1 = slow_ma[-2]

            cross_over = fast_ma0 > slow_ma0 and fast_ma1 < slow_ma1
            cross_below = fast_ma0 < slow_ma0 and fast_ma1 > slow_ma1

            if cross_over:
                self.set_target(vt_symbol, self.params.fixed_size)
            elif cross_below:
                self.set_target(vt_symbol, -self.params.fixed_size)

        self.rebalance_portfolio(bars)
        self.put_event()

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
