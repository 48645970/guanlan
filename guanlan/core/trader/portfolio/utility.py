# -*- coding: utf-8 -*-
"""
观澜量化 - 组合策略K线合成工具

PortfolioBarGenerator: 多合约K线合成器
- update_tick: Tick → 1分钟K线切片
- update_bars: 1分钟K线 → N分钟/小时K线切片
- 不含日K线合成

Author: 海山观澜
"""

from collections.abc import Callable
from copy import copy
from datetime import datetime

from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TickData


class PortfolioBarGenerator:
    """组合K线生成器

    将多合约的 Tick/分钟K线合成为统一时间切片的 N分钟/小时K线。
    """

    def __init__(
        self,
        on_bars: Callable,
        window: int = 0,
        on_window_bars: Callable | None = None,
        interval: Interval = Interval.MINUTE,
    ) -> None:
        self.on_bars: Callable = on_bars
        self.window: int = window
        self.on_window_bars: Callable | None = on_window_bars
        self.interval: Interval = interval
        self.interval_count: int = 0

        self.bars: dict[str, BarData] = {}
        self.last_ticks: dict[str, TickData] = {}

        self.hour_bars: dict[str, BarData] = {}
        self.finished_hour_bars: dict[str, BarData] = {}

        self.window_bars: dict[str, BarData] = {}

        self.last_dt: datetime | None = None

    def update_tick(self, tick: TickData) -> None:
        """Tick 合成分钟K线

        当分钟切换时推送上一批K线切片。
        """
        last_tick: TickData | None = self.last_ticks.get(tick.vt_symbol, None)
        self.last_ticks[tick.vt_symbol] = tick

        if not last_tick or not tick.last_price:
            return

        # 判断分钟切换
        if last_tick.datetime.minute != tick.datetime.minute:
            # 推送上一分钟的K线切片
            if self.bars:
                finished_bars: dict[str, BarData] = {}
                for vt_symbol, bar in self.bars.items():
                    finished_bars[vt_symbol] = copy(bar)
                self.on_bars(finished_bars)
                self.bars.clear()

        bar: BarData | None = self.bars.get(tick.vt_symbol, None)

        if bar is None:
            bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime.replace(second=0, microsecond=0),
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest,
            )
            self.bars[tick.vt_symbol] = bar
        else:
            bar.high_price = max(bar.high_price, tick.last_price)
            bar.low_price = min(bar.low_price, tick.last_price)
            bar.close_price = tick.last_price
            bar.open_interest = tick.open_interest
            bar.datetime = tick.datetime.replace(second=0, microsecond=0)

        if last_tick:
            volume_change: float = tick.volume - last_tick.volume
            bar.volume += max(volume_change, 0)

            turnover_change: float = tick.turnover - last_tick.turnover
            bar.turnover += max(turnover_change, 0)

    def update_bars(self, bars: dict[str, BarData]) -> None:
        """分钟K线合成 N分钟/小时K线"""
        if self.interval == Interval.MINUTE:
            self.update_bar_minute_window(bars)
        else:
            self.update_bar_hour_window(bars)

    def update_bar_minute_window(self, bars: dict[str, BarData]) -> None:
        """合成 N 分钟K线"""
        for vt_symbol, bar in bars.items():
            window_bar: BarData | None = self.window_bars.get(vt_symbol, None)

            if window_bar is None:
                window_bar = BarData(
                    symbol=bar.symbol,
                    exchange=bar.exchange,
                    interval=Interval.MINUTE,
                    datetime=bar.datetime,
                    gateway_name=bar.gateway_name,
                    open_price=bar.open_price,
                    high_price=bar.high_price,
                    low_price=bar.low_price,
                    close_price=bar.close_price,
                    volume=bar.volume,
                    turnover=bar.turnover,
                    open_interest=bar.open_interest,
                )
                self.window_bars[vt_symbol] = window_bar
            else:
                window_bar.high_price = max(window_bar.high_price, bar.high_price)
                window_bar.low_price = min(window_bar.low_price, bar.low_price)
                window_bar.close_price = bar.close_price
                window_bar.volume += bar.volume
                window_bar.turnover += bar.turnover
                window_bar.open_interest = bar.open_interest

        self.interval_count += 1

        if not self.interval_count % self.window:
            self.interval_count = 0

            finished_bars: dict[str, BarData] = {}
            for vt_symbol, bar in self.window_bars.items():
                finished_bars[vt_symbol] = copy(bar)
            self.window_bars.clear()

            self.on_window_bars(finished_bars)

    def update_bar_hour_window(self, bars: dict[str, BarData]) -> None:
        """合成小时K线"""
        for vt_symbol, bar in bars.items():
            hour_bar: BarData | None = self.hour_bars.get(vt_symbol, None)

            if hour_bar is None:
                hour_bar = BarData(
                    symbol=bar.symbol,
                    exchange=bar.exchange,
                    interval=Interval.HOUR,
                    datetime=bar.datetime,
                    gateway_name=bar.gateway_name,
                    open_price=bar.open_price,
                    high_price=bar.high_price,
                    low_price=bar.low_price,
                    close_price=bar.close_price,
                    volume=bar.volume,
                    turnover=bar.turnover,
                    open_interest=bar.open_interest,
                )
                self.hour_bars[vt_symbol] = hour_bar
            else:
                hour_bar.high_price = max(hour_bar.high_price, bar.high_price)
                hour_bar.low_price = min(hour_bar.low_price, bar.low_price)
                hour_bar.close_price = bar.close_price
                hour_bar.volume += bar.volume
                hour_bar.turnover += bar.turnover
                hour_bar.open_interest = bar.open_interest

        # 检查小时切换（任意合约触发即可）
        if self.last_dt is not None:
            last_hour = self.last_dt.hour
            cur_bar = next(iter(bars.values()))

            if cur_bar.datetime.hour != last_hour:
                finished_bars: dict[str, BarData] = {}
                for vt_symbol, bar in self.hour_bars.items():
                    finished_bars[vt_symbol] = copy(bar)
                self.hour_bars.clear()

                self.on_hour_bars(finished_bars)

        self.last_dt = next(iter(bars.values())).datetime

    def on_hour_bars(self, bars: dict[str, BarData]) -> None:
        """小时K线推送（含 N 小时窗口合成）"""
        if self.window == 1:
            self.on_window_bars(bars)
            return

        for vt_symbol, bar in bars.items():
            window_bar: BarData | None = self.window_bars.get(vt_symbol, None)

            if window_bar is None:
                window_bar = BarData(
                    symbol=bar.symbol,
                    exchange=bar.exchange,
                    interval=Interval.HOUR,
                    datetime=bar.datetime,
                    gateway_name=bar.gateway_name,
                    open_price=bar.open_price,
                    high_price=bar.high_price,
                    low_price=bar.low_price,
                    close_price=bar.close_price,
                    volume=bar.volume,
                    turnover=bar.turnover,
                    open_interest=bar.open_interest,
                )
                self.window_bars[vt_symbol] = window_bar
            else:
                window_bar.high_price = max(window_bar.high_price, bar.high_price)
                window_bar.low_price = min(window_bar.low_price, bar.low_price)
                window_bar.close_price = bar.close_price
                window_bar.volume += bar.volume
                window_bar.turnover += bar.turnover
                window_bar.open_interest = bar.open_interest

        self.interval_count += 1

        if not self.interval_count % self.window:
            self.interval_count = 0

            finished_bars: dict[str, BarData] = {}
            for vt_symbol, bar in self.window_bars.items():
                finished_bars[vt_symbol] = copy(bar)
            self.window_bars.clear()

            self.on_window_bars(finished_bars)
