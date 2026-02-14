# -*- coding: utf-8 -*-
"""
观澜量化 - 双均线交叉指标

金叉/死叉信号标记，第一版内置指标。

Author: 海山观澜
"""

import numpy as np
from pydantic import Field
from MyTT import MA

from guanlan.core.indicators import BaseIndicator, BaseIndicatorParams, register_indicator


class MACrossParams(BaseIndicatorParams):
    short_window: int = Field(default=5, title="快线周期", ge=1, le=200)
    long_window: int = Field(default=20, title="慢线周期", ge=1, le=500)


@register_indicator("双均线交叉")
class MACrossIndicator(BaseIndicator):
    """双均线交叉（金叉/死叉信号标记）"""

    author = "海山观澜"
    overlay = True
    params = MACrossParams()

    def __init__(self) -> None:
        super().__init__()
        self._closes: list[float] = []
        self._prev_short: float | None = None
        self._prev_long: float | None = None
        self._last_cross: str | None = None

    @property
    def lookback(self) -> int:
        return max(self.params.short_window, self.params.long_window)

    def lines(self) -> list[dict]:
        return [
            {"name": f"MA{self.params.short_window}", "color": "#FFFFFF", "width": 1},
            {"name": f"MA{self.params.long_window}", "color": "#FFD700", "width": 1},
        ]

    def _compute_init(self, bars: list[dict]) -> dict[str, np.ndarray]:
        """计算历史双均线数据"""
        self._closes = [b["close"] for b in bars]
        short_ma = MA(np.array(self._closes), self.params.short_window)
        long_ma = MA(np.array(self._closes), self.params.long_window)
        short_name = f"MA{self.params.short_window}"
        long_name = f"MA{self.params.long_window}"

        self.inited = True

        # 保存最后两个值用于后续交叉检测
        if len(self._closes) >= 2:
            self._prev_short = None if np.isnan(short_ma[-2]) else short_ma[-2]
            self._prev_long = None if np.isnan(long_ma[-2]) else long_ma[-2]

        # 直接返回 numpy 数组，基类会自动处理
        return {short_name: short_ma, long_name: long_ma}

    def _compute_bar(self, bar: dict) -> dict[str, float]:
        """计算单根 K 线的双均线值"""
        self._closes.append(bar["close"])

        # 性能优化：只使用计算窗口，而不是全部历史
        # MA 是简单平均，只需 lookback 数据，但用 ×2 保险
        window = self._get_compute_window(self._closes, window_factor=2, min_size=100)
        short_ma = MA(np.array(window), self.params.short_window)
        long_ma = MA(np.array(window), self.params.long_window)
        short_name = f"MA{self.params.short_window}"
        long_name = f"MA{self.params.long_window}"

        curr_short = short_ma[-1]
        curr_long = long_ma[-1]

        # 检测交叉信号
        self._last_cross = None
        if (self._prev_short is not None and self._prev_long is not None
                and not np.isnan(curr_short) and not np.isnan(curr_long)):
            if self._prev_short <= self._prev_long and curr_short > curr_long:
                self._last_cross = "golden"
            elif self._prev_short >= self._prev_long and curr_short < curr_long:
                self._last_cross = "death"

        # 更新前值
        self._prev_short = None if np.isnan(curr_short) else curr_short
        self._prev_long = None if np.isnan(curr_long) else curr_long

        # 直接返回原始值（可能是 NaN），基类会自动转换
        return {short_name: curr_short, long_name: curr_long}

    def on_bar_signal(self, bar: dict) -> dict | None:
        if self._last_cross == "golden":
            return {"type": "long", "text": "金叉"}
        elif self._last_cross == "death":
            return {"type": "short", "text": "死叉"}
        return None

    def get_signals(self, bars: list[dict]) -> list[dict]:
        closes = [b["close"] for b in bars]
        short_ma = MA(np.array(closes), self.params.short_window)
        long_ma = MA(np.array(closes), self.params.long_window)

        signals = []
        start = max(self.params.short_window, self.params.long_window)

        for i in range(start, len(bars)):
            prev_s, prev_l = short_ma[i - 1], long_ma[i - 1]
            curr_s, curr_l = short_ma[i], long_ma[i]
            if np.isnan(prev_s) or np.isnan(prev_l):
                continue

            if prev_s <= prev_l and curr_s > curr_l:
                signals.append({"time": bars[i]["time"], "type": "long", "text": "金叉"})
            elif prev_s >= prev_l and curr_s < curr_l:
                signals.append({"time": bars[i]["time"], "type": "short", "text": "死叉"})

        return signals
