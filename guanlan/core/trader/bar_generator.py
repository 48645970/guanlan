# -*- coding: utf-8 -*-
"""
观澜量化 - 扩展 K 线生成器

继承 VNPY BarGenerator，增加秒级、小时级、日线级 K 线合成支持。

Author: 海山观澜
"""

from collections.abc import Callable
from datetime import datetime

from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TickData
from vnpy.trader.utility import BarGenerator

from guanlan.core.utils.trading_period import get_trading_date


class ChartBarGenerator(BarGenerator):
    """扩展 K 线生成器

    在 BarGenerator 基础上扩展：
    - second_window > 0：按秒级周期合成（10秒/20秒/30秒等）
    - daily=True：日线模式，按交易日边界合成
    - 覆盖 update_bar_minute_window：用 total_minutes 支持 >60 分钟窗口（小时级）
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable | None = None,
        interval: Interval = Interval.MINUTE,
        second_window: int = 0,
        daily: bool = False,
    ) -> None:
        super().__init__(on_bar, window, on_window_bar, interval)
        self.second_window: int = second_window
        self._daily: bool = daily
        self._trading_date: str = ""  # 当前交易日（日线模式用）
        self._daily_count: int = 0  # 多日窗口计数

    def update_tick(self, tick: TickData) -> None:
        """处理 Tick：秒级/日线走自定义逻辑，分钟级走父类"""
        if self.second_window > 0:
            self._update_tick_second(tick)
        elif self._daily:
            self._update_tick_daily(tick)
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

    def _update_tick_daily(self, tick: TickData) -> None:
        """日线 K 线合成：按交易日边界切割"""
        if not tick.last_price:
            return

        trading_date = get_trading_date(tick.datetime)
        new_day: bool = False

        if not self.bar:
            new_day = True
        elif trading_date != self._trading_date:
            # 交易日切换，推送上一日 bar
            self.on_bar(self.bar)
            new_day = True

        if new_day:
            self._trading_date = trading_date
            # bar.datetime 设为交易日 00:00:00
            day_dt = datetime.strptime(trading_date, "%Y-%m-%d")
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.DAILY,
                datetime=day_dt,
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

    def update_bar(self, bar: BarData) -> None:
        """路由 1 分钟 bar 到对应的窗口合成方法"""
        if self._daily:
            self._update_bar_daily_window(bar)
        else:
            # 分钟/小时级走覆盖后的 update_bar_minute_window
            self.update_bar_minute_window(bar)

    def update_bar_minute_window(self, bar: BarData) -> None:
        """覆盖父类：用 total_minutes 支持任意分钟窗口（含小时级）

        父类使用 (minute+1) % window 判断完成，对 window > 60 无效。
        改为 (total_minutes+1) % window，对 window <= 60 行为完全一致。
        同时增加间隙检测：当新 bar 属于下一个窗口周期时，先推送当前
        不完整的 window_bar，再开始新窗口，避免跨休盘数据错误聚合。
        """
        total_minutes = bar.datetime.hour * 60 + bar.datetime.minute
        start_minutes = (total_minutes // self.window) * self.window

        if self.window_bar:
            # 间隙检测：新 bar 所属窗口起点 != 当前 window_bar 起点
            wb_total = (
                self.window_bar.datetime.hour * 60
                + self.window_bar.datetime.minute
            )
            if start_minutes != wb_total:
                # 新窗口周期，推送当前不完整的 window_bar
                if self.on_window_bar:
                    self.on_window_bar(self.window_bar)
                self.window_bar = None

        if not self.window_bar:
            dt = bar.datetime.replace(
                hour=start_minutes // 60,
                minute=start_minutes % 60,
                second=0,
                microsecond=0,
            )
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
            )
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price, bar.high_price,
            )
            self.window_bar.low_price = min(
                self.window_bar.low_price, bar.low_price,
            )

        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += bar.volume
        self.window_bar.turnover += bar.turnover
        self.window_bar.open_interest = bar.open_interest

        # 完成判断：用 total_minutes 替代 minute
        if not (total_minutes + 1) % self.window:
            if self.on_window_bar:
                self.on_window_bar(self.window_bar)
            self.window_bar = None

    def _update_bar_daily_window(self, bar: BarData) -> None:
        """多日窗口合成：按交易日计数聚合"""
        trading_date = get_trading_date(bar.datetime)

        if not self.window_bar:
            day_dt = datetime.strptime(trading_date, "%Y-%m-%d")
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=day_dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
            )
            self._trading_date = trading_date
            self._daily_count = 0
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price, bar.high_price,
            )
            self.window_bar.low_price = min(
                self.window_bar.low_price, bar.low_price,
            )

        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += bar.volume
        self.window_bar.turnover += bar.turnover
        self.window_bar.open_interest = bar.open_interest

        # 交易日切换时计数+1
        if trading_date != self._trading_date:
            self._trading_date = trading_date
            self._daily_count += 1

            if self._daily_count >= self.window:
                if self.on_window_bar:
                    self.on_window_bar(self.window_bar)
                self.window_bar = None
                self._daily_count = 0

    def generate(self) -> BarData | None:
        """推送当前未完成的 bar"""
        if self.second_window > 0 or self._daily:
            bar = self.bar
            if bar:
                self.on_bar(bar)
            self.bar = None
            return bar
        return super().generate()

    @staticmethod
    def normalize_bar_time(
        dt: datetime, second_window: int = 0, window: int = 0,
    ) -> datetime:
        """将 K 线时间归一化到周期起点

        Parameters
        ----------
        dt : datetime
            原始 K 线时间
        second_window : int
            秒级周期长度。0 表示分钟级。
        window : int
            分钟窗口大小。0 表示 1 分钟模式，截断秒即可。
            >0 时按 total_minutes 归整（支持小时级）。
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
        elif window > 0:
            total_minutes = dt.hour * 60 + dt.minute
            start_minutes = (total_minutes // window) * window
            return dt.replace(
                hour=start_minutes // 60,
                minute=start_minutes % 60,
                second=0,
                microsecond=0,
            )
        else:
            return dt.replace(second=0, microsecond=0)
