# -*- coding: utf-8 -*-
"""
观澜量化 - 图表数据加载器

从 ChartWindow 提取的数据加载逻辑，负责：
- 从 ArcticDB 加载历史 K 线 / Tick 数据
- 通过 ChartBarGenerator 合成多周期 K 线
- 转换为 lightweight-charts 所需的 dict 格式

Author: 海山观澜
"""

from datetime import datetime, timedelta

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from guanlan.core.trader.bar_generator import ChartBarGenerator
from guanlan.core.trader.database import ArcticDBDatabase
from guanlan.core.utils.period import Period


def bar_to_dict(bar: BarData) -> dict:
    """BarData → lightweight-charts dict"""
    if bar.interval == Interval.DAILY:
        time_str = bar.datetime.strftime("%Y-%m-%d")
    else:
        time_str = bar.datetime.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "time": time_str,
        "open": bar.open_price,
        "high": bar.high_price,
        "low": bar.low_price,
        "close": bar.close_price,
        "volume": bar.volume,
        "open_interest": bar.open_interest,
    }


class ChartDataLoader:
    """图表历史数据加载器

    封装从数据库加载历史数据并合成目标周期 K 线的逻辑。
    """

    def __init__(self) -> None:
        self._database = ArcticDBDatabase()

    def load(
        self, vt_symbol: str, period: Period, count: int,
    ) -> list[dict]:
        """加载历史数据

        Parameters
        ----------
        vt_symbol : str
            合约代码（如 "OI605.CZCE"）
        period : Period
            K 线周期
        count : int
            目标 K 线根数

        Returns
        -------
        list[dict]
            lightweight-charts 格式的 K 线数据，空列表表示无数据
        """
        parts = vt_symbol.rsplit(".", 1)
        if len(parts) != 2:
            return []

        symbol, exchange_str = parts
        try:
            exchange = Exchange(exchange_str)
        except ValueError:
            return []

        if period.is_second:
            # 秒级周期：必须从 tick 合成
            minutes_needed = period.history_minutes(count)
            end = datetime.now()
            start = end - timedelta(minutes=minutes_needed)
            temp_bars = self._load_from_tick(
                symbol, exchange, start, end, period,
            )
        elif period.is_daily:
            # 日线周期：从 DB 日线数据加载
            temp_bars = self._load_from_daily(
                symbol, exchange, period, count,
            )
        else:
            # 分钟/小时级周期：优先加载已录制的 1 分钟 bar
            temp_bars = self._load_from_bar(
                symbol, exchange, period, count,
            )
            # bar 数据不存在时，尝试从 tick 合成
            if not temp_bars:
                minutes_needed = period.history_minutes(count)
                end = datetime.now()
                start = end - timedelta(minutes=minutes_needed)
                temp_bars = self._load_from_tick(
                    symbol, exchange, start, end, period,
                )

        if not temp_bars:
            return []

        # 只取最后 N 根
        if len(temp_bars) > count:
            temp_bars = temp_bars[-count:]

        return [bar_to_dict(b) for b in temp_bars]

    def _load_from_bar(
        self,
        symbol: str,
        exchange: Exchange,
        period: Period,
        count: int,
    ) -> list[BarData]:
        """从数据库按条数加载 bar 数据

        1 分钟模式直接取最后 count 条；
        多分钟窗口先加载足够的 1 分钟 bar，再通过生成器合成。
        """
        bars_needed = count * period.window if period.is_window else count

        key = f"{symbol}.{exchange.value}.{Interval.MINUTE.value}"
        if not self._database.bar_lib.has_symbol(key):
            return []

        result = self._database.bar_lib.read(key)
        df = result.data
        if df.empty:
            return []

        df = df.tail(bars_needed)

        bars_1m: list[BarData] = []
        for tp in df.itertuples():
            bars_1m.append(BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=tp.Index.to_pydatetime(),
                interval=Interval.MINUTE,
                open_price=tp.open_price,
                high_price=tp.high_price,
                low_price=tp.low_price,
                close_price=tp.close_price,
                volume=tp.volume,
                turnover=tp.turnover,
                open_interest=tp.open_interest,
                gateway_name="DB",
            ))

        if not period.is_window:
            return bars_1m

        # 多分钟窗口：用 ChartBarGenerator 合成
        window_bars: list[BarData] = []
        temp_gen = ChartBarGenerator(
            on_bar=lambda b: temp_gen.update_bar(b),
            window=period.window,
            on_window_bar=lambda b: window_bars.append(b),
            interval=period.interval,
        )
        for bar in bars_1m:
            temp_gen.on_bar(bar)
        temp_gen.generate()
        return window_bars

    def _load_from_daily(
        self,
        symbol: str,
        exchange: Exchange,
        period: Period,
        count: int,
    ) -> list[BarData]:
        """从数据库加载日线数据

        1 日模式直接返回；多日窗口做简单分组聚合。
        """
        key = f"{symbol}.{exchange.value}.{Interval.DAILY.value}"
        if not self._database.bar_lib.has_symbol(key):
            return []

        result = self._database.bar_lib.read(key)
        df = result.data
        if df.empty:
            return []

        bars_needed = count * max(period.window, 1)
        df = df.tail(bars_needed)

        daily_bars: list[BarData] = []
        for tp in df.itertuples():
            daily_bars.append(BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=tp.Index.to_pydatetime(),
                interval=Interval.DAILY,
                open_price=tp.open_price,
                high_price=tp.high_price,
                low_price=tp.low_price,
                close_price=tp.close_price,
                volume=tp.volume,
                turnover=tp.turnover,
                open_interest=tp.open_interest,
                gateway_name="DB",
            ))

        if not period.is_window:
            return daily_bars

        # 多日窗口：简单分组聚合
        window_bars: list[BarData] = []
        for i in range(0, len(daily_bars), period.window):
            group = daily_bars[i:i + period.window]
            if not group:
                break
            merged = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=group[0].datetime,
                interval=Interval.DAILY,
                open_price=group[0].open_price,
                high_price=max(b.high_price for b in group),
                low_price=min(b.low_price for b in group),
                close_price=group[-1].close_price,
                volume=sum(b.volume for b in group),
                turnover=sum(b.turnover for b in group),
                open_interest=group[-1].open_interest,
                gateway_name="DB",
            )
            window_bars.append(merged)
        return window_bars

    def _load_from_tick(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime,
        period: Period,
    ) -> list[BarData]:
        """从数据库加载 tick 数据并合成 K 线"""
        ticks = self._database.load_tick_data(symbol, exchange, start, end)
        if not ticks:
            return []

        result: list[BarData] = []

        def on_temp_bar(bar: BarData):
            result.append(bar)

        if period.is_second:
            temp_gen = ChartBarGenerator(
                on_bar=on_temp_bar, second_window=period.second_window,
            )
        elif period.is_window:
            temp_gen = ChartBarGenerator(
                on_bar=lambda b: temp_gen.update_bar(b),
                window=period.window,
                on_window_bar=on_temp_bar,
                interval=period.interval,
            )
        else:
            temp_gen = ChartBarGenerator(on_bar=on_temp_bar)

        for tick in ticks:
            temp_gen.update_tick(tick)
        temp_gen.generate()
        return result
