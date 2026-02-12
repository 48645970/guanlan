# -*- coding: utf-8 -*-
"""
MACD 策略

MACD 柱状图判断方向和强度，金叉/死叉控制开仓许可。
同时演示辅助交易信号输出（vars）的用法。

信号逻辑：
- 柱状图 > 0 → 方向做多，柱状图 < 0 → 方向做空
- 柱状图绝对值越大，强度越高
- 金叉（MACD 上穿 Signal）→ 允许开多
- 死叉（MACD 下穿 Signal）→ 允许开空
- 平仓始终自由，不受信号约束

Author: 海山观澜
"""

from pydantic import Field

from guanlan.core.trader.cta.template import BaseParams, BaseState, CtaTemplate
from vnpy.trader.object import BarData, TradeData, TickData
from vnpy.trader.utility import ArrayManager


class MacdParams(BaseParams):
    """MACD 策略参数"""

    fast_period: int = Field(default=12, title="快线周期", ge=2, le=100)
    slow_period: int = Field(default=26, title="慢线周期", ge=5, le=200)
    signal_period: int = Field(default=9, title="信号周期", ge=2, le=50)
    strength_scale: float = Field(default=5.0, title="强度缩放", ge=0.1, le=100.0)


class MacdState(BaseState):
    """MACD 策略状态"""

    macd: float = Field(default=0.0, title="MACD")
    signal: float = Field(default=0.0, title="Signal")
    hist: float = Field(default=0.0, title="柱状图")
    macd_prev: float = Field(default=0.0, title="MACD前值")
    signal_prev: float = Field(default=0.0, title="Signal前值")


class MacdStrategy(CtaTemplate):
    """MACD 策略"""

    author = "海山观澜"
    params = MacdParams()
    state = MacdState()

    def __init__(self, cta_engine, strategy_name, vt_symbol, gateway_name):
        super().__init__(cta_engine, strategy_name, vt_symbol, gateway_name)

        self.am = ArrayManager()

    def on_init(self):
        """策略初始化"""
        self.write_log("MACD 策略初始化")
        self.load_bar(10)

    def on_start(self):
        """策略启动"""
        self.write_log("MACD 策略启动")

    def on_stop(self):
        """策略停止"""
        self.write_log("MACD 策略停止")

    def on_tick(self, tick: TickData):
        """Tick 回调"""
        pass

    def on_bar(self, bar: BarData):
        """K 线回调"""
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 计算 MACD
        macd, signal, hist = am.macd(
            self.params.fast_period,
            self.params.slow_period,
            self.params.signal_period,
        )

        # 前值（用于判断金叉/死叉）
        macd_arr, signal_arr, _ = am.macd(
            self.params.fast_period,
            self.params.slow_period,
            self.params.signal_period,
            array=True,
        )

        self.state.macd_prev = self.state.macd
        self.state.signal_prev = self.state.signal
        self.state.macd = macd
        self.state.signal = signal
        self.state.hist = hist

        # 金叉/死叉判断
        cross_over = (
            self.state.macd > self.state.signal
            and self.state.macd_prev <= self.state.signal_prev
        )
        cross_below = (
            self.state.macd < self.state.signal
            and self.state.macd_prev >= self.state.signal_prev
        )

        # 强度：柱状图绝对值映射到 0~100
        strength = min(int(abs(hist) * self.params.strength_scale), 100)

        # 信号输出
        if hist > 0:
            self.vars.direction = 1
            self.vars.strength = strength
            self.vars.suggest_price = bar.close_price
            self.vars.suggest_volume = 1
            self.vars.allow_open_long = True
            self.vars.allow_open_short = False
            if cross_over:
                self.vars.tip = f"MACD 金叉 柱状图 {hist:.2f}"
            else:
                self.vars.tip = f"多头趋势 柱状图 {hist:.2f}"
        elif hist < 0:
            self.vars.direction = -1
            self.vars.strength = strength
            self.vars.suggest_price = bar.close_price
            self.vars.suggest_volume = 1
            self.vars.allow_open_long = False
            self.vars.allow_open_short = True
            if cross_below:
                self.vars.tip = f"MACD 死叉 柱状图 {hist:.2f}"
            else:
                self.vars.tip = f"空头趋势 柱状图 {hist:.2f}"
        else:
            self.vars.direction = 0
            self.vars.strength = 0
            self.vars.tip = "MACD 零轴"
            self.vars.allow_open_long = False
            self.vars.allow_open_short = False

        self.put_signal()

        # 自动交易逻辑（CTA 模式下执行，辅助模式下 send_order 返回空）
        if cross_over:
            if self.state.pos == 0:
                self.buy(bar.close_price, 1)
            elif self.state.pos < 0:
                self.cover(bar.close_price, abs(self.state.pos))
                self.buy(bar.close_price, 1)
        elif cross_below:
            if self.state.pos == 0:
                self.short(bar.close_price, 1)
            elif self.state.pos > 0:
                self.sell(bar.close_price, self.state.pos)
                self.short(bar.close_price, 1)

        self.put_event()

    def on_trade(self, trade: TradeData):
        """成交回调"""
        self.put_event()
