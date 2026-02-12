# -*- coding: utf-8 -*-
"""
双均线策略

快线上穿慢线做多，快线下穿慢线做空。

Author: 海山观澜
"""

from pydantic import Field

from guanlan.core.trader.cta.template import BaseParams, BaseState, CtaTemplate
from vnpy.trader.object import BarData, TradeData, TickData
from vnpy.trader.utility import ArrayManager


class DoubleMaParams(BaseParams):
    """双均线策略参数"""

    fast_window: int = Field(default=10, title="快线周期", ge=1, le=200)
    slow_window: int = Field(default=20, title="慢线周期", ge=1, le=500)


class DoubleMaState(BaseState):
    """双均线策略状态"""

    fast_ma0: float = Field(default=0.0, title="快线当前")
    fast_ma1: float = Field(default=0.0, title="快线前值")
    slow_ma0: float = Field(default=0.0, title="慢线当前")
    slow_ma1: float = Field(default=0.0, title="慢线前值")


class DoubleMaStrategy(CtaTemplate):
    """双均线策略"""

    author = "海山观澜"
    params = DoubleMaParams()
    state = DoubleMaState()

    def __init__(self, cta_engine, strategy_name, vt_symbol, gateway_name):
        super().__init__(cta_engine, strategy_name, vt_symbol, gateway_name)

        self.am = ArrayManager()

    def on_init(self):
        """策略初始化"""
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self):
        """策略启动"""
        self.write_log("策略启动")

    def on_stop(self):
        """策略停止"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """Tick 回调"""
        pass

    def on_bar(self, bar: BarData):
        """K 线回调"""
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        fast_ma = am.sma(self.params.fast_window, array=True)
        self.state.fast_ma0 = fast_ma[-1]
        self.state.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.params.slow_window, array=True)
        self.state.slow_ma0 = slow_ma[-1]
        self.state.slow_ma1 = slow_ma[-2]

        cross_over = (
            self.state.fast_ma0 > self.state.slow_ma0
            and self.state.fast_ma1 < self.state.slow_ma1
        )
        cross_below = (
            self.state.fast_ma0 < self.state.slow_ma0
            and self.state.fast_ma1 > self.state.slow_ma1
        )

        # 信号输出（CTA 卡片展示 / 辅助模式按钮控制）
        if self.state.fast_ma0 > self.state.slow_ma0:
            spread = self.state.fast_ma0 - self.state.slow_ma0
            self.vars.direction = 1
            self.vars.strength = min(int(spread / self.state.slow_ma0 * 1000), 100)
            self.vars.tip = "均线金叉，建议做多"
            self.vars.suggest_price = bar.close_price
            self.vars.suggest_volume = 1
            self.vars.allow_open_long = True
            self.vars.allow_open_short = False
        elif self.state.fast_ma0 < self.state.slow_ma0:
            spread = self.state.slow_ma0 - self.state.fast_ma0
            self.vars.direction = -1
            self.vars.strength = min(int(spread / self.state.fast_ma0 * 1000), 100)
            self.vars.tip = "均线死叉，建议做空"
            self.vars.suggest_price = bar.close_price
            self.vars.suggest_volume = 1
            self.vars.allow_open_long = False
            self.vars.allow_open_short = True
        else:
            self.vars.direction = 0
            self.vars.strength = 0
            self.vars.tip = ""
            self.vars.allow_open_long = False
            self.vars.allow_open_short = False

        self.put_signal()

        if cross_over:
            if self.state.pos == 0:
                self.buy(bar.close_price, 1)
            elif self.state.pos < 0:
                self.cover(bar.close_price, 1)
                self.buy(bar.close_price, 1)

        elif cross_below:
            if self.state.pos == 0:
                self.short(bar.close_price, 1)
            elif self.state.pos > 0:
                self.sell(bar.close_price, 1)
                self.short(bar.close_price, 1)

        self.put_event()

    def on_trade(self, trade: TradeData):
        """成交回调"""
        self.put_event()
