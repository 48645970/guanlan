# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 回测引擎（继承重写）

继承 VNPY BacktestingEngine，重写 DailyResult 使用真实手续费计算。

Author: 海山观澜
"""

from datetime import date as Date

from vnpy.trader.constant import Direction
from vnpy.trader.object import TradeData

from vnpy_ctastrategy.backtesting import (
    BacktestingEngine as _BacktestingEngine,
    DailyResult as _DailyResult,
)

from guanlan.core.setting.commission import calculate_commission


class DailyResult(_DailyResult):
    """每日盈亏结果 — 真实手续费

    重写 calculate_pnl()，将 `turnover * rate` 替换为
    按品种区分开仓/平今/平昨的真实手续费计算。
    """

    def calculate_pnl(
        self,
        pre_close: float,
        start_pos: float,
        size: float,
        rate: float,
        slippage: float,
    ) -> None:
        # 首日无昨收时用 1 避免除零
        if pre_close:
            self.pre_close = pre_close
        else:
            self.pre_close = 1

        # 持仓盈亏
        self.start_pos = start_pos
        self.end_pos = start_pos
        self.holding_pnl = self.start_pos * (self.close_price - self.pre_close) * size

        # 交易盈亏
        self.trade_count = len(self.trades)

        for trade in self.trades:
            if trade.direction == Direction.LONG:
                pos_change = trade.volume
            else:
                pos_change = -trade.volume

            self.end_pos += pos_change

            turnover: float = trade.volume * size * trade.price
            self.trading_pnl += pos_change * (self.close_price - trade.price) * size
            self.slippage += trade.volume * size * slippage

            self.turnover += turnover
            # 真实手续费（替代原版 turnover * rate）
            self.commission += calculate_commission(trade)

        # 净盈亏 = 总盈亏 - 手续费 - 滑点
        self.total_pnl = self.trading_pnl + self.holding_pnl
        self.net_pnl = self.total_pnl - self.commission - self.slippage


class BacktestingEngine(_BacktestingEngine):
    """CTA 回测引擎 — 使用自定义 DailyResult

    仅重写 update_daily_close()，使其创建自定义 DailyResult。
    其余方法（calculate_result/calculate_statistics 等）全部继承原版。
    """

    def update_daily_close(self, price: float) -> None:
        """更新每日收盘价（使用自定义 DailyResult）"""
        d: Date = self.datetime.date()

        daily_result: DailyResult | None = self.daily_results.get(d, None)
        if daily_result:
            daily_result.close_price = price
        else:
            self.daily_results[d] = DailyResult(d, price)
