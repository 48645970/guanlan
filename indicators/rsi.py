# -*- coding: utf-8 -*-
"""
观澜量化 - RSI 指标

Author: 海山观澜
"""

import warnings
import numpy as np
from pydantic import Field
from MyTT import RSI

from guanlan.core.constants import COLOR_UP, COLOR_DOWN
from guanlan.core.indicators import BaseIndicator, BaseIndicatorParams, register_indicator


class RSIParams(BaseIndicatorParams):
    period: int = Field(default=14, title="周期", ge=2, le=100)


@register_indicator("RSI")
class RSIIndicator(BaseIndicator):
    """RSI 相对强弱指标（副图显示）"""

    author = "海山观澜"
    overlay = False
    params = RSIParams()

    @property
    def lookback(self) -> int:
        # RSI 需要足够的数据计算涨跌幅平均值
        return self.params.period

    def lines(self) -> list[dict]:
        return [
            {"name": "RSI", "color": "#FFD700", "width": 1},
        ]

    def reference_lines(self) -> list[dict]:
        return [
            {"price": 70, "color": COLOR_UP, "style": "dashed"},
            {"price": 30, "color": COLOR_DOWN, "style": "dashed"},
        ]

    def _compute_init(self, bars: list[dict]) -> dict[str, np.ndarray]:
        """计算历史 RSI 数据"""
        # 初始化实例变量
        self._closes: list[float] = [b["close"] for b in bars]
        self._prev_rsi: float | None = None
        self._last_signal: dict | None = None

        # 计算并返回原始数据（抑制除零警告）
        with np.errstate(invalid='ignore', divide='ignore'):
            rsi = RSI(np.array(self._closes), self.params.period)
        self.inited = True

        # 保存最后一个有效值
        for v in reversed(rsi):
            if not np.isnan(v):
                self._prev_rsi = v
                break

        # 直接返回 numpy 数组，基类会自动处理
        return {"RSI": rsi}

    def _compute_bar(self, bar: dict) -> dict[str, float]:
        """计算单根 K 线的 RSI 值"""
        self._closes.append(bar["close"])

        # 数据不足时返回 NaN（基类会转换为 None）
        if len(self._closes) < self.lookback:
            return {"RSI": np.nan}

        # 性能优化：只使用计算窗口，而不是全部历史
        window = self._get_compute_window(self._closes, window_factor=3, min_size=100)
        with np.errstate(invalid='ignore', divide='ignore'):
            rsi = RSI(np.array(window), self.params.period)
        curr = rsi[-1]

        # 检测超买超卖穿越信号
        self._last_signal = None
        if self._prev_rsi is not None and not np.isnan(curr):
            if self._prev_rsi >= 30 and curr < 30:
                self._last_signal = {"type": "long", "text": "超卖"}
            elif self._prev_rsi <= 70 and curr > 70:
                self._last_signal = {"type": "short", "text": "超买"}

        # 保存当前值
        self._prev_rsi = None if np.isnan(curr) else curr

        # 直接返回原始值（可能是 NaN），基类会自动转换
        return {"RSI": curr}

    def on_bar_signal(self, bar: dict) -> dict | None:
        return self._last_signal

    def get_signals(self, bars: list[dict]) -> list[dict]:
        closes = [b["close"] for b in bars]
        with np.errstate(invalid='ignore', divide='ignore'):
            rsi = RSI(np.array(closes), self.params.period)

        signals = []
        for i in range(1, len(bars)):
            prev, curr = rsi[i - 1], rsi[i]
            if np.isnan(prev) or np.isnan(curr):
                continue
            if prev >= 30 and curr < 30:
                signals.append({"time": bars[i]["time"], "type": "long", "text": "超卖"})
            elif prev <= 70 and curr > 70:
                signals.append({"time": bars[i]["time"], "type": "short", "text": "超买"})
        return signals
