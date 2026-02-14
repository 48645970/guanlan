# -*- coding: utf-8 -*-
"""
观澜量化 - 扩展 K 线生成器

继承 VNPY BarGenerator，增加秒级 K 线合成支持。

Author: 海山观澜
"""

from collections.abc import Callable
from datetime import datetime

from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import BarGenerator


class ChartBarGenerator(BarGenerator):
    """扩展 K 线生成器，支持秒级合成

    在 BarGenerator 基础上增加 second_window 参数：
    - second_window > 0：按秒级周期合成（10秒/20秒/30秒等）
    - second_window == 0：沿用父类分钟级逻辑
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable | None = None,
        interval: Interval = Interval.MINUTE,
        second_window: int = 0,
    ) -> None:
        super().__init__(on_bar, window, on_window_bar, interval)
        self.second_window: int = second_window

    def update_tick(self, tick: TickData) -> None:
        """处理 Tick，秒级走自定义逻辑，分钟级走父类"""
        if self.second_window > 0:
            self._update_tick_second(tick)
        else:
            super().update_tick(tick)

    def _update_tick_second(self, tick: TickData) -> None:
        """秒级 K 线合成"""
        if not tick.last_price:
            return

        # 计算当前秒级周期起始时刻
        total_seconds = (
            tick.datetime.hour * 3600
            + tick.datetime.minute * 60
            + tick.datetime.second
        )
        period_start = (total_seconds // self.second_window) * self.second_window
        current_period = tick.datetime.replace(
            hour=period_start // 3600,
            minute=(period_start % 3600) // 60,
            second=period_start % 60,
            microsecond=0,
        )

        new_period: bool = False

        if not self.bar:
            new_period = True
        elif current_period > self.bar.datetime:
            # 上一根 bar 完成，推送
            self.on_bar(self.bar)
            new_period = True

        if new_period:
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=current_period,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest,
            )
        elif self.bar:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            if self.last_tick and tick.high_price > self.last_tick.high_price:
                self.bar.high_price = max(self.bar.high_price, tick.high_price)

            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            if self.last_tick and tick.low_price < self.last_tick.low_price:
                self.bar.low_price = min(self.bar.low_price, tick.low_price)

            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest

        if self.last_tick and self.bar:
            volume_change: float = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

            turnover_change: float = tick.turnover - self.last_tick.turnover
            self.bar.turnover += max(turnover_change, 0)

        self.last_tick = tick

    def generate(self) -> BarData | None:
        """推送当前未完成的 bar"""
        if self.second_window > 0:
            bar = self.bar
            if bar:
                self.on_bar(bar)
            self.bar = None
            return bar
        return super().generate()

    @staticmethod
    def normalize_bar_time(dt: datetime, second_window: int = 0) -> datetime:
        """将 K 线时间归一化到周期起点

        VNPY BarGenerator 每个 Tick 都会更新 bar.datetime = tick.datetime，
        导致同一根 K 线内时间秒数不断变化。对于需要稳定时间戳的场景
        （如 lightweight-charts 通过时间判断是否为同一根 K 线），
        必须将时间归一化到周期起点。

        Parameters
        ----------
        dt : datetime
            原始 K 线时间
        second_window : int
            秒级周期长度。0 表示分钟级，截断秒和微秒即可。

        Returns
        -------
        datetime
            归一化后的时间
        """
        if second_window > 0:
            total_seconds = dt.hour * 3600 + dt.minute * 60 + dt.second
            period_start = (total_seconds // second_window) * second_window
            return dt.replace(
                hour=period_start // 3600,
                minute=(period_start % 3600) // 60,
                second=period_start % 60,
                microsecond=0,
            )
        else:
            return dt.replace(second=0, microsecond=0)
