# -*- coding: utf-8 -*-
"""
观澜量化 - MACD 指标

DIF / DEA 双线 + MACD 柱状（以线显示）

Author: 海山观澜
"""

import numpy as np
from pydantic import Field
from MyTT import MACD

from guanlan.core.constants import COLOR_UP, COLOR_DOWN
from guanlan.core.indicators import BaseIndicator, BaseIndicatorParams, register_indicator


class MACDParams(BaseIndicatorParams):
    short: int = Field(default=12, title="快线周期", ge=2, le=100)
    long: int = Field(default=26, title="慢线周期", ge=2, le=200)
    signal: int = Field(default=9, title="信号周期", ge=2, le=100)


@register_indicator("MACD")
class MACDIndicator(BaseIndicator):
    """MACD 指标（副图显示）"""

    author = "海山观澜"
    overlay = False
    params = MACDParams()

    @property
    def lookback(self) -> int:
        # MACD 需要足够的数据计算 EMA26 和 DEA(EMA9)
        return self.params.long + self.params.signal - 1

    def lines(self) -> list[dict]:
        return [
            {"name": "DIF", "color": "#FFFFFF", "width": 1},
            {"name": "DEA", "color": "#FFD700", "width": 1},
            {"name": "MACD", "type": "histogram", "color": COLOR_DOWN,
             "color_up": COLOR_UP, "color_down": COLOR_DOWN},
        ]

    def reference_lines(self) -> list[dict]:
        return [
            {"price": 0, "color": "#555555", "style": "dashed"},
        ]

    def _compute_init(self, bars: list[dict]) -> dict[str, np.ndarray]:
        """计算历史 MACD 数据"""
        # 初始化实例变量
        self._closes: list[float] = [b["close"] for b in bars]
        self._prev_dif: float | None = None
        self._prev_dea: float | None = None
        self._last_signal: dict | None = None

        # 计算并返回原始数据（包含 NaN）
        closes = np.array(self._closes)
        dif, dea, macd = MACD(closes, self.params.short, self.params.long, self.params.signal)
        self.inited = True

        # 保存最后两个值（基类会过滤，这里直接用原始数组）
        if len(dif) >= 2:
            self._prev_dif = None if np.isnan(dif[-2]) else dif[-2]
            self._prev_dea = None if np.isnan(dea[-2]) else dea[-2]

        # 直接返回 numpy 数组，基类会自动处理
        return {"DIF": dif, "DEA": dea, "MACD": macd}

    def _compute_bar(self, bar: dict) -> dict[str, float]:
        """计算单根 K 线的 MACD 值"""
        self._closes.append(bar["close"])

        # 数据不足时返回 NaN（基类会转换为 None）
        if len(self._closes) < self.lookback:
            return {"DIF": np.nan, "DEA": np.nan, "MACD": np.nan}

        # 性能优化：只使用计算窗口，而不是全部历史
        window = self._get_compute_window(self._closes, window_factor=3, min_size=150)
        closes = np.array(window)
        dif, dea, macd = MACD(closes, self.params.short, self.params.long, self.params.signal)

        curr_dif = dif[-1]
        curr_dea = dea[-1]

        # 检测 DIF/DEA 交叉（使用清理后的值）
        self._last_signal = None
        if (self._prev_dif is not None and self._prev_dea is not None
                and not np.isnan(curr_dif) and not np.isnan(curr_dea)):
            if self._prev_dif <= self._prev_dea and curr_dif > curr_dea:
                self._last_signal = {"type": "long", "text": "MACD金叉"}
            elif self._prev_dif >= self._prev_dea and curr_dif < curr_dea:
                self._last_signal = {"type": "short", "text": "MACD死叉"}

        # 保存当前值（基类处理后的会是 None）
        self._prev_dif = None if np.isnan(curr_dif) else curr_dif
        self._prev_dea = None if np.isnan(curr_dea) else curr_dea

        # 直接返回原始值（可能是 NaN），基类会自动转换
        return {"DIF": curr_dif, "DEA": curr_dea, "MACD": macd[-1]}

    def on_bar_signal(self, bar: dict) -> dict | None:
        return self._last_signal

    def get_signals(self, bars: list[dict]) -> list[dict]:
        closes = [b["close"] for b in bars]
        dif, dea, _ = MACD(np.array(closes), self.params.short, self.params.long, self.params.signal)

        signals = []
        for i in range(1, len(bars)):
            pd_, cd = dif[i - 1], dif[i]
            pe, ce = dea[i - 1], dea[i]
            if np.isnan(pd_) or np.isnan(pe) or np.isnan(cd) or np.isnan(ce):
                continue
            if pd_ <= pe and cd > ce:
                signals.append({"time": bars[i]["time"], "type": "long", "text": "MACD金叉"})
            elif pd_ >= pe and cd < ce:
                signals.append({"time": bars[i]["time"], "type": "short", "text": "MACD死叉"})
        return signals
