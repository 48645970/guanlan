# -*- coding: utf-8 -*-
"""
观澜量化 - 数据管理引擎

独立模式，不依赖 MainEngine，直接持有 ArcticDB 数据库。

Author: 海山观澜
"""

import csv
from collections.abc import Callable
from datetime import datetime, timedelta

from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.object import BarData, HistoryRequest
from vnpy.trader.database import BarOverview

from guanlan.core.trader.database import ArcticDBDatabase
from guanlan.core.setting.contract import load_contracts, load_favorites
from guanlan.core.utils.symbol_converter import SymbolConverter


class DataManagerEngine:
    """数据管理引擎

    独立于 MainEngine，直接操作 ArcticDB 数据库。
    """

    def __init__(self) -> None:
        self.database = ArcticDBDatabase()

    def get_bar_overview(self) -> list[BarOverview]:
        """查询 K 线数据概况"""
        return self.database.get_bar_overview()

    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> list[BarData]:
        """加载 bar 数据"""
        return self.database.load_bar_data(
            symbol, exchange, interval, start, end
        )

    def delete_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval
    ) -> int:
        """删除数据"""
        return self.database.delete_bar_data(symbol, exchange, interval)

    def output_data_to_csv(
        self,
        file_path: str,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> bool:
        """CSV 导出"""
        bars: list[BarData] = self.load_bar_data(
            symbol, exchange, interval, start, end
        )

        fieldnames: list[str] = [
            "symbol", "exchange", "datetime",
            "open", "high", "low", "close",
            "volume", "turnover", "open_interest"
        ]

        try:
            with open(file_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=fieldnames, lineterminator="\n"
                )
                writer.writeheader()

                for bar in bars:
                    writer.writerow({
                        "symbol": bar.symbol,
                        "exchange": bar.exchange.value,
                        "datetime": bar.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": bar.open_price,
                        "high": bar.high_price,
                        "low": bar.low_price,
                        "close": bar.close_price,
                        "volume": bar.volume,
                        "turnover": bar.turnover,
                        "open_interest": bar.open_interest,
                    })
            return True
        except PermissionError:
            return False

    def download_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        callback: Callable[[str, bool], None] | None = None
    ) -> int:
        """从 AKShare 数据服务下载 K 线数据

        Parameters
        ----------
        symbol : str
            合约代码（交易所格式）
        exchange : Exchange
            交易所
        interval : Interval
            数据周期
        start : datetime
            起始时间
        callback : Callable[[str, bool], None] | None
            进度回调，参数为 (消息, 是否完成)

        Returns
        -------
        int
            下载的数据条数
        """
        from guanlan.core.trader.datafeed import AkShareDatafeed

        def _output(msg: str) -> None:
            if callback:
                callback(msg, False)

        datafeed = AkShareDatafeed()
        if not datafeed.init(output=_output):
            return 0

        req = HistoryRequest(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start=start,
            end=datetime.now()
        )
        bars = datafeed.query_bar_history(req, output=_output)

        if bars:
            self.database.save_bar_data(bars)

        return len(bars)

    def download_akshare_favorites(
        self,
        interval: Interval = Interval.DAILY,
        callback: Callable[[str, bool], None] | None = None
    ) -> int:
        """从 AKShare 下载收藏品种的历史数据

        Parameters
        ----------
        interval : Interval
            数据周期（DAILY 或 MINUTE）
        callback : Callable[[str, bool], None] | None
            进度回调，参数为 (消息, 是否完成)

        Returns
        -------
        int
            成功导入的品种数
        """
        from guanlan.core.trader.datafeed import AkShareDatafeed

        def _output(msg: str) -> None:
            if callback:
                callback(msg, False)

        datafeed = AkShareDatafeed()
        if not datafeed.init(output=_output):
            if callback:
                callback("AKShare 初始化失败", True)
            return 0

        favorites = load_favorites()
        contracts = load_contracts()
        count = 0

        for commodity in favorites:
            contract_info = contracts.get(commodity)
            if not contract_info:
                continue

            exchange = Exchange(contract_info["exchange"])
            vt_symbol = contract_info.get("vt_symbol", "")
            if not vt_symbol:
                continue

            # 转为交易所格式（与 TDX 导入一致）
            ex_symbol = SymbolConverter.to_exchange(vt_symbol, exchange)
            name = contract_info.get("name", commodity)
            start = datetime.now() - timedelta(days=365)

            if callback:
                callback(f"正在下载: {name} ({ex_symbol})", False)

            req = HistoryRequest(
                symbol=ex_symbol,
                exchange=exchange,
                interval=interval,
                start=start,
                end=datetime.now()
            )
            bars = datafeed.query_bar_history(req)

            if bars:
                self.database.save_bar_data(bars)
                count += 1
                if callback:
                    callback(f"已导入: {name} {len(bars)} 条", False)

        if callback:
            callback(f"导入完成，共导入 {count} 个品种", True)

        return count

    def download_akshare_all(
        self,
        callback: Callable[[str, bool], None] | None = None
    ) -> int:
        """一键下载收藏品种的全周期数据（日线 + 小时 + 分钟）

        Parameters
        ----------
        callback : Callable[[str, bool], None] | None
            进度回调，参数为 (消息, 是否完成)

        Returns
        -------
        int
            成功导入的品种数（去重后）
        """
        from guanlan.core.trader.datafeed import AkShareDatafeed

        def _output(msg: str) -> None:
            if callback:
                callback(msg, False)

        datafeed = AkShareDatafeed()
        if not datafeed.init(output=_output):
            if callback:
                callback("AKShare 初始化失败", True)
            return 0

        favorites = load_favorites()
        contracts = load_contracts()
        intervals = [Interval.DAILY, Interval.HOUR, Interval.MINUTE]
        interval_names = {
            Interval.DAILY: "日线",
            Interval.HOUR: "小时线",
            Interval.MINUTE: "分钟线",
        }
        count = 0

        for commodity in favorites:
            contract_info = contracts.get(commodity)
            if not contract_info:
                continue

            exchange = Exchange(contract_info["exchange"])
            vt_symbol = contract_info.get("vt_symbol", "")
            if not vt_symbol:
                continue

            ex_symbol = SymbolConverter.to_exchange(vt_symbol, exchange)
            name = contract_info.get("name", commodity)
            imported = False

            for interval in intervals:
                start = datetime.now() - timedelta(days=365)

                if callback:
                    callback(
                        f"正在下载: {name} {interval_names[interval]}",
                        False
                    )

                req = HistoryRequest(
                    symbol=ex_symbol,
                    exchange=exchange,
                    interval=interval,
                    start=start,
                    end=datetime.now()
                )
                bars = datafeed.query_bar_history(req)

                if bars:
                    self.database.save_bar_data(bars)
                    imported = True
                    if callback:
                        callback(
                            f"已导入: {name} {interval_names[interval]}"
                            f" {len(bars)} 条",
                            False
                        )

            if imported:
                count += 1

        if callback:
            callback(f"导入完成，共导入 {count} 个品种", True)

        return count

    def close(self) -> None:
        """清理资源"""
        pass
