# -*- coding: utf-8 -*-
"""
观澜量化 - 海龟通道突破指标

经典海龟交易法 N 日通道突破，价格突破上轨做多、跌破下轨做空。

Author: 海山观澜
"""

import numpy as np
from pydantic import Field

from guanlan.core.constants import COLOR_UP, COLOR_DOWN
from guanlan.core.indicators import BaseIndicator, BaseIndicatorParams, register_indicator


class TurtleParams(BaseIndicatorParams):
    period: int = Field(default=20, title="突破周期", ge=2, le=200)


@register_indicator("海龟通道")
class TurtleIndicator(BaseIndicator):
    """海龟通道突破（主图叠加）

    上轨 = N 日最高价的最高值
    下轨 = N 日最低价的最低值
    """

    author = "海山观澜"
    overlay = True
    params = TurtleParams()

    def __init__(self) -> None:
        super().__init__()
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._prev_upper: float | None = None
        self._prev_lower: float | None = None
        self._prev_close: float | None = None
        self._last_signal: dict | None = None

    @property
    def lookback(self) -> int:
        return self.params.period

    def lines(self) -> list[dict]:
        return [
            {"name": "上轨", "color": COLOR_UP, "width": 1},
            {"name": "下轨", "color": COLOR_DOWN, "width": 1},
        ]

    def _calc(self, highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """计算 N 日最高最低通道"""
        n = self.params.period
        length = len(highs)
        upper = np.full(length, np.nan)
        lower = np.full(length, np.nan)
        for i in range(n - 1, length):
            upper[i] = np.max(highs[i - n + 1:i + 1])
            lower[i] = np.min(lows[i - n + 1:i + 1])
        return upper, lower

    def _compute_init(self, bars: list[dict]) -> dict[str, np.ndarray]:
        """计算历史海龟通道数据"""
        self._highs = [b["high"] for b in bars]
        self._lows = [b["low"] for b in bars]
        upper, lower = self._calc(np.array(self._highs), np.array(self._lows))
        self.inited = True

        # 保存前一个有效值
        if len(bars) >= 2:
            self._prev_close = bars[-2]["close"]
            self._prev_upper = None if np.isnan(upper[-2]) else upper[-2]
            self._prev_lower = None if np.isnan(lower[-2]) else lower[-2]

        # 直接返回 numpy 数组，基类会自动处理
        return {"上轨": upper, "下轨": lower}

    def _compute_bar(self, bar: dict) -> dict[str, float]:
        """计算单根 K 线的海龟通道值"""
        self._highs.append(bar["high"])
        self._lows.append(bar["low"])

        # 性能优化：只使用计算窗口，而不是全部历史
        # 海龟通道只需 lookback 数据，但用 ×2 保险
        highs_window = self._get_compute_window(self._highs, window_factor=2, min_size=100)
        lows_window = self._get_compute_window(self._lows, window_factor=2, min_size=100)
        upper, lower = self._calc(np.array(highs_window), np.array(lows_window))

        curr_upper = upper[-1]
        curr_lower = lower[-1]
        curr_close = bar["close"]

        # 检测通道突破
        self._last_signal = None
        if self._prev_close is not None:
            if self._prev_upper is not None and curr_close > self._prev_upper:
                self._last_signal = {"type": "long", "text": "突破上轨"}
            elif self._prev_lower is not None and curr_close < self._prev_lower:
                self._last_signal = {"type": "short", "text": "跌破下轨"}

        # 更新前值
        self._prev_close = curr_close
        self._prev_upper = None if np.isnan(curr_upper) else curr_upper
        self._prev_lower = None if np.isnan(curr_lower) else curr_lower

        # 直接返回原始值（可能是 NaN），基类会自动转换
        return {"上轨": curr_upper, "下轨": curr_lower}

    def on_bar_signal(self, bar: dict) -> dict | None:
        return self._last_signal

    def get_signals(self, bars: list[dict]) -> list[dict]:
        highs = np.array([b["high"] for b in bars])
        lows = np.array([b["low"] for b in bars])
        upper, lower = self._calc(highs, lows)

        signals = []
        for i in range(1, len(bars)):
            if np.isnan(upper[i - 1]) or np.isnan(lower[i - 1]):
                continue
            close = bars[i]["close"]
            if close > upper[i - 1]:
                signals.append({"time": bars[i]["time"], "type": "long", "text": "突破上轨"})
            elif close < lower[i - 1]:
                signals.append({"time": bars[i]["time"], "type": "short", "text": "跌破下轨"})
        return signals
