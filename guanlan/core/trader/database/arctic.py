# -*- coding: utf-8 -*-
"""
观澜量化 - ArcticDB 数据库适配器

基于 ArcticDB LMDB 后端实现 VNPY BaseDatabase 接口。
嵌入式存储，无需外部数据库服务。

Author: 海山观澜
"""

from datetime import datetime

import arcticdb as adb
import pandas as pd

from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.database import BaseDatabase, BarOverview, TickOverview, convert_tz
from vnpy.trader.object import BarData, TickData

from guanlan.core.constants import ARCTIC_DATA_DIR


# Tick 数值字段（不含 symbol/exchange/datetime）
TICK_FIELDS: list[str] = [
    "volume", "turnover", "open_interest",
    "last_price", "last_volume", "limit_up", "limit_down",
    "open_price", "high_price", "low_price", "pre_close",
    "bid_price_1", "bid_price_2", "bid_price_3", "bid_price_4", "bid_price_5",
    "ask_price_1", "ask_price_2", "ask_price_3", "ask_price_4", "ask_price_5",
    "bid_volume_1", "bid_volume_2", "bid_volume_3", "bid_volume_4", "bid_volume_5",
    "ask_volume_1", "ask_volume_2", "ask_volume_3", "ask_volume_4", "ask_volume_5",
]


def _bar_key(symbol: str, exchange: Exchange, interval: Interval) -> str:
    """生成 Bar 数据的 ArcticDB symbol 键名"""
    return f"{symbol}.{exchange.value}.{interval.value}"


def _tick_key(symbol: str, exchange: Exchange) -> str:
    """生成 Tick 数据的 ArcticDB symbol 键名"""
    return f"{symbol}.{exchange.value}"


def _parse_bar_key(key: str) -> tuple[str, Exchange, Interval] | None:
    """解析 Bar symbol 键名"""
    parts = key.rsplit(".", 2)
    if len(parts) != 3:
        return None
    try:
        return parts[0], Exchange(parts[1]), Interval(parts[2])
    except ValueError:
        return None


def _parse_tick_key(key: str) -> tuple[str, Exchange] | None:
    """解析 Tick symbol 键名"""
    parts = key.rsplit(".", 1)
    if len(parts) != 2:
        return None
    try:
        return parts[0], Exchange(parts[1])
    except ValueError:
        return None


def _to_utc_timestamp(dt: datetime) -> pd.Timestamp:
    """将 datetime 转为 UTC 时间戳，兼容有/无时区"""
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


class ArcticDBDatabase(BaseDatabase):
    """ArcticDB 数据库实现（单例）

    使用 LMDB 后端的嵌入式存储，无需外部服务。
    LMDB 不支持同一进程内对同一路径打开多个连接，
    因此使用单例模式确保全局只有一个实例。

    键名编码规则：
    - Bar: {symbol}.{exchange}.{interval}
    - Tick: {symbol}.{exchange}
    DataFrame 中只存数值列，元信息由键名携带。
    """

    _instance: "ArcticDBDatabase | None" = None

    def __new__(cls) -> "ArcticDBDatabase":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        ARCTIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
        uri = f"lmdb://{ARCTIC_DATA_DIR}"
        self.arctic = adb.Arctic(uri)
        self.bar_lib = self.arctic.get_library("bar", create_if_missing=True)
        self.tick_lib = self.arctic.get_library("tick", create_if_missing=True)

    # ── 通用操作 ──────────────────────────────────────────

    def _upsert(self, lib, key: str, df: pd.DataFrame, stream: bool) -> None:
        """写入数据到 Library

        stream=True: 流式追加，数据时间严格递增
        stream=False: 合并去重后覆盖写入
        """
        if not lib.has_symbol(key):
            lib.write(key, df, prune_previous_versions=True)
            return

        if stream:
            lib.append(key, df, prune_previous_versions=True)
        else:
            existing = lib.read(key).data
            merged = pd.concat([existing, df])
            merged = merged[~merged.index.duplicated(keep="last")]
            merged = merged.sort_index()
            lib.write(key, merged, prune_previous_versions=True)

    # ── Bar 数据操作 ─────────────────────────────────────

    def save_bar_data(self, bars: list[BarData], stream: bool = False) -> bool:
        """保存 K 线数据"""
        if not bars:
            return False

        groups: dict[str, list[BarData]] = {}
        for bar in bars:
            key = _bar_key(bar.symbol, bar.exchange, bar.interval)
            groups.setdefault(key, []).append(bar)

        for key, group_bars in groups.items():
            data = [{
                "datetime": convert_tz(bar.datetime),
                "open_price": bar.open_price,
                "high_price": bar.high_price,
                "low_price": bar.low_price,
                "close_price": bar.close_price,
                "volume": bar.volume,
                "turnover": bar.turnover,
                "open_interest": bar.open_interest,
            } for bar in group_bars]

            df = pd.DataFrame(data)
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)
            self._upsert(self.bar_lib, key, df, stream)

        return True

    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> list[BarData]:
        """加载 K 线数据"""
        key = _bar_key(symbol, exchange, interval)
        if not self.bar_lib.has_symbol(key):
            return []

        result = self.bar_lib.read(
            key, date_range=(_to_utc_timestamp(start), _to_utc_timestamp(end))
        )
        df = result.data
        if df.empty:
            return []

        bars: list[BarData] = []
        for tp in df.itertuples():
            bars.append(BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=tp.Index.to_pydatetime(),
                interval=interval,
                open_price=tp.open_price,
                high_price=tp.high_price,
                low_price=tp.low_price,
                close_price=tp.close_price,
                volume=tp.volume,
                turnover=tp.turnover,
                open_interest=tp.open_interest,
                gateway_name="DB",
            ))
        return bars

    def delete_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
    ) -> int:
        """删除 K 线数据"""
        key = _bar_key(symbol, exchange, interval)
        if not self.bar_lib.has_symbol(key):
            return 0

        count = self.bar_lib.get_description(key).row_count
        self.bar_lib.delete(key)
        return count

    def get_bar_overview(self) -> list[BarOverview]:
        """获取所有 K 线数据概览"""
        overviews = []
        for key in self.bar_lib.list_symbols():
            parsed = _parse_bar_key(key)
            if not parsed:
                continue

            symbol, exchange, interval = parsed
            try:
                desc = self.bar_lib.get_description(key)
                dr = desc.date_range
                overviews.append(BarOverview(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    count=desc.row_count,
                    start=dr[0].to_pydatetime() if dr else None,
                    end=dr[1].to_pydatetime() if dr else None,
                ))
            except Exception:
                continue

        return overviews

    # ── Tick 数据操作 ────────────────────────────────────

    def save_tick_data(self, ticks: list[TickData], stream: bool = False) -> bool:
        """保存 Tick 数据"""
        if not ticks:
            return False

        groups: dict[str, list[TickData]] = {}
        for tick in ticks:
            key = _tick_key(tick.symbol, tick.exchange)
            groups.setdefault(key, []).append(tick)

        for key, group_ticks in groups.items():
            data = []
            for tick in group_ticks:
                d = {"datetime": convert_tz(tick.datetime)}
                for field in TICK_FIELDS:
                    d[field] = getattr(tick, field, 0.0)
                data.append(d)

            df = pd.DataFrame(data)
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)
            self._upsert(self.tick_lib, key, df, stream)

        return True

    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime,
    ) -> list[TickData]:
        """加载 Tick 数据"""
        key = _tick_key(symbol, exchange)
        if not self.tick_lib.has_symbol(key):
            return []

        result = self.tick_lib.read(
            key, date_range=(_to_utc_timestamp(start), _to_utc_timestamp(end))
        )
        df = result.data
        if df.empty:
            return []

        ticks: list[TickData] = []
        for tp in df.itertuples():
            kwargs = {
                "symbol": symbol,
                "exchange": exchange,
                "datetime": tp.Index.to_pydatetime(),
                "gateway_name": "DB",
            }
            for field in TICK_FIELDS:
                kwargs[field] = getattr(tp, field, 0.0)
            ticks.append(TickData(**kwargs))
        return ticks

    def delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
    ) -> int:
        """删除 Tick 数据"""
        key = _tick_key(symbol, exchange)
        if not self.tick_lib.has_symbol(key):
            return 0

        count = self.tick_lib.get_description(key).row_count
        self.tick_lib.delete(key)
        return count

    def get_tick_overview(self) -> list[TickOverview]:
        """获取所有 Tick 数据概览"""
        overviews = []
        for key in self.tick_lib.list_symbols():
            parsed = _parse_tick_key(key)
            if not parsed:
                continue

            symbol, exchange = parsed
            try:
                desc = self.tick_lib.get_description(key)
                dr = desc.date_range
                overviews.append(TickOverview(
                    symbol=symbol,
                    exchange=exchange,
                    count=desc.row_count,
                    start=dr[0].to_pydatetime() if dr else None,
                    end=dr[1].to_pydatetime() if dr else None,
                ))
            except Exception:
                continue

        return overviews
