# -*- coding: utf-8 -*-
"""
UI 测试策略

每隔 N 秒随机输出信号方向、强度、提示和开仓许可，
用于验证辅助交易窗口的界面效果和音效。不含任何交易逻辑。

Author: 海山观澜
"""

import random
from datetime import datetime, timedelta

from pydantic import Field

from guanlan.core.trader.cta.template import BaseParams, CtaTemplate
from vnpy.trader.object import BarData, TickData


# 随机提示文本池
_TIPS_LONG = [
    "MACD 金叉，多头趋势确立",
    "均线多头排列，建议做多",
    "放量突破前高，多头信号",
    "RSI 超卖反弹，看多",
    "布林下轨支撑有效，偏多",
    "量价齐升，趋势向上",
]

_TIPS_SHORT = [
    "MACD 死叉，空头趋势确立",
    "均线空头排列，建议做空",
    "放量跌破前低，空头信号",
    "RSI 超买回落，看空",
    "布林上轨压力明显，偏空",
    "量价背离，趋势向下",
]

_TIPS_NEUTRAL = [
    "震荡区间，暂时观望",
    "信号不明确，等待方向",
    "多空交织，保持耐心",
    "窄幅整理，等待突破",
]


class UiTestParams(BaseParams):
    """UI 测试策略参数"""

    interval: int = Field(default=10, title="刷新间隔(秒)", ge=3, le=60)


class UiTestStrategy(CtaTemplate):
    """UI 测试策略"""

    author = "海山观澜"
    params = UiTestParams()

    def __init__(self, cta_engine, strategy_name, vt_symbol, gateway_name):
        super().__init__(cta_engine, strategy_name, vt_symbol, gateway_name)

        self._next_time: datetime | None = None

    def on_init(self):
        """策略初始化"""
        pass

    def on_start(self):
        """策略启动"""
        self._next_time = None

    def on_stop(self):
        """策略停止"""
        self._next_time = None

    def on_tick(self, tick: TickData):
        """Tick 回调：定时随机刷新信号"""
        now = tick.datetime
        if not now:
            return

        if self._next_time is None:
            self._next_time = now + timedelta(seconds=self.params.interval)
            return

        if now < self._next_time:
            return

        self._next_time = now + timedelta(seconds=self.params.interval)
        self._random_signal(tick)

    def _random_signal(self, tick: TickData):
        """随机生成信号"""
        # 随机场景：做多、做空、观望，权重 3:3:2
        scene = random.choices(["long", "short", "neutral"], weights=[3, 3, 2])[0]

        if scene == "long":
            self.vars.direction = 1
            self.vars.strength = random.randint(40, 100)
            self.vars.tip = random.choice(_TIPS_LONG)
            self.vars.suggest_price = tick.last_price
            self.vars.suggest_volume = random.choice([1, 2, 3])
            self.vars.allow_open_long = True
            self.vars.allow_open_short = False
        elif scene == "short":
            self.vars.direction = -1
            self.vars.strength = random.randint(40, 100)
            self.vars.tip = random.choice(_TIPS_SHORT)
            self.vars.suggest_price = tick.last_price
            self.vars.suggest_volume = random.choice([1, 2, 3])
            self.vars.allow_open_long = False
            self.vars.allow_open_short = True
        else:
            self.vars.direction = 0
            self.vars.strength = random.randint(0, 30)
            self.vars.tip = random.choice(_TIPS_NEUTRAL)
            self.vars.suggest_price = 0
            self.vars.suggest_volume = 0
            self.vars.allow_open_long = False
            self.vars.allow_open_short = False

        self.put_signal()
        self.put_event()

    def on_bar(self, bar: BarData):
        """K 线回调（不使用）"""
        pass
