# -*- coding: utf-8 -*-
"""
观澜量化 - 通达信本地数据服务

直接读取通达信安装目录下的二进制 K 线文件（.lc1 / .lc5 / .day），
自动发现合约并转换为 BarData 供导入 ArcticDB。

Author: 海山观澜
"""

import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from vnpy.trader.object import BarData

from guanlan.core.constants import Exchange, Interval
from guanlan.core.setting.contract import load_contracts
from guanlan.core.utils.logger import get_logger
from guanlan.core.utils.symbol_converter import SymbolConverter

logger = get_logger(__name__)

# 市场编号 → Exchange 映射
MARKET_EXCHANGE_MAP: dict[int, Exchange] = {
    28: Exchange.CZCE,
    29: Exchange.DCE,
    30: Exchange.SHFE,
    47: Exchange.CFFEX,
    60: Exchange.INE,
}

# 目录 → Interval 映射（及对应文件扩展名）
DIR_INTERVAL_MAP: dict[str, tuple[Interval, str]] = {
    "minline": (Interval.MINUTE, ".lc1"),
    "fzline": (Interval.MINUTE, ".lc5"),
    "lday": (Interval.DAILY, ".day"),
}


@dataclass
class TdxFileInfo:
    """通达信数据文件信息"""

    filepath: str
    market_code: int
    raw_symbol: str       # TDX 原始代码 (OI2605)
    vt_symbol: str        # 交易所格式 (OI605.CZCE)
    exchange: Exchange
    name: str             # 品种名称
    interval: Interval
    bar_count: int        # 按文件大小推算
    dir_type: str = ""    # 目录类型（minline/fzline/lday）
    is_continuous: bool = False  # 主力连续(L8)或指数(L9)


class TdxService:
    """通达信本地数据服务"""

    @staticmethod
    def discover(tdx_path: str) -> list[TdxFileInfo]:
        """扫描通达信目录，发现所有期货数据文件

        扫描 vipdoc/ds/ 下的 minline / lday / fzline 子目录。

        Parameters
        ----------
        tdx_path : str
            通达信安装根目录

        Returns
        -------
        list[TdxFileInfo]
            发现的数据文件列表
        """
        contracts = load_contracts()
        ds_path = Path(tdx_path) / "vipdoc" / "ds"

        if not ds_path.exists():
            logger.warning(f"通达信数据目录不存在: {ds_path}")
            return []

        results: list[TdxFileInfo] = []

        for dir_name, (interval, ext) in DIR_INTERVAL_MAP.items():
            dir_path = ds_path / dir_name
            if not dir_path.exists():
                continue

            for file_path in dir_path.iterdir():
                if not file_path.suffix.lower() in (ext, ext.upper()):
                    continue

                info = TdxService._parse_file(
                    file_path, interval, dir_name, contracts
                )
                if info:
                    results.append(info)

        # 按 vt_symbol 排序
        results.sort(key=lambda x: x.vt_symbol)
        return results

    @staticmethod
    def _parse_file(
        file_path: Path,
        interval: Interval,
        dir_type: str,
        contracts: dict,
    ) -> TdxFileInfo | None:
        """解析单个文件名，提取合约信息

        文件名格式: 28#OI2605.lc1
        """
        stem = file_path.stem  # 28#OI2605
        if "#" not in stem:
            return None

        parts = stem.split("#", 1)
        if len(parts) != 2:
            return None

        try:
            market_code = int(parts[0])
        except ValueError:
            return None

        raw_symbol = parts[1]  # OI2605

        # 市场编号映射
        exchange = MARKET_EXCHANGE_MAP.get(market_code)
        if not exchange:
            return None

        # 特殊合约处理：L8=主力连续, L9=指数
        symbol_for_convert = raw_symbol
        is_continuous = False
        if raw_symbol.endswith("L8"):
            symbol_for_convert = raw_symbol[:-2] + "8888"
            is_continuous = True
        elif raw_symbol.endswith("L9"):
            symbol_for_convert = raw_symbol[:-2] + "9999"
            is_continuous = True

        # 提取品种代码，查找合约信息
        commodity = SymbolConverter.extract_commodity(symbol_for_convert)
        if not commodity or commodity not in contracts:
            return None

        contract_info = contracts[commodity]
        name = contract_info.get("name", commodity)

        # 转为交易所格式
        ex_symbol = SymbolConverter.to_exchange(symbol_for_convert, exchange)

        # 推算数据条数（按文件大小和记录结构体大小）
        file_size = file_path.stat().st_size
        if dir_type == "lday":
            record_size = 32  # <IffffIIf> = 4+4*4+4+4+4 = 32
        else:
            record_size = 32  # <HHfffffII> = 2+2+4*5+4+4 = 32
        bar_count = file_size // record_size if record_size > 0 else 0

        return TdxFileInfo(
            filepath=str(file_path),
            market_code=market_code,
            raw_symbol=raw_symbol,
            vt_symbol=f"{ex_symbol}.{exchange.value}",
            exchange=exchange,
            name=name,
            interval=interval,
            bar_count=bar_count,
            dir_type=dir_type,
            is_continuous=is_continuous,
        )

    @staticmethod
    def read_bars(file_info: TdxFileInfo) -> list[BarData]:
        """读取通达信二进制文件，转换为 BarData 列表

        Parameters
        ----------
        file_info : TdxFileInfo
            文件信息

        Returns
        -------
        list[BarData]
            解析后的 K 线数据
        """
        if file_info.dir_type == "lday":
            return TdxService._read_daily_bars(file_info)
        else:
            return TdxService._read_minute_bars(file_info)

    @staticmethod
    def _read_minute_bars(file_info: TdxFileInfo) -> list[BarData]:
        """读取分钟线数据（.lc1 / .lc5）"""
        from pytdx.reader import TdxLCMinBarReader

        reader = TdxLCMinBarReader()
        df = reader.get_df(file_info.filepath)

        if df.empty:
            return []

        # 提取交易所格式的 symbol（不含交易所后缀）
        symbol = file_info.vt_symbol.split(".")[0]
        exchange = file_info.exchange
        interval = file_info.interval

        bars: list[BarData] = []
        for _, row in df.iterrows():
            dt = row.name.to_pydatetime()

            # 通达信分钟线时间处理：
            # 09:31 表示 09:30~09:31 这一分钟，需要减1分钟对齐
            dt = dt - timedelta(minutes=1)

            # 夜盘时间修正（>15:00 的归到前一天）
            if dt.hour > 15:
                dt = dt - timedelta(days=1)

            # 持仓量修正：amount 字段实际是 uint32 持仓量按 float 读取
            amount_float = row["amount"]
            open_interest = struct.unpack(
                "<I", struct.pack("<f", amount_float)
            )[0]

            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                datetime=dt,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                volume=float(row["volume"]),
                turnover=0.0,
                open_interest=float(open_interest),
                gateway_name="TDX",
            )
            bars.append(bar)

        return bars

    @staticmethod
    def _read_daily_bars(file_info: TdxFileInfo) -> list[BarData]:
        """读取日线数据（.day）"""
        from pytdx.reader import TdxExHqDailyBarReader

        reader = TdxExHqDailyBarReader()
        df = reader.get_df(file_info.filepath)

        if df.empty:
            return []

        symbol = file_info.vt_symbol.split(".")[0]
        exchange = file_info.exchange
        interval = file_info.interval

        bars: list[BarData] = []
        for _, row in df.iterrows():
            dt = row.name.to_pydatetime()

            # 日线的 amount 字段已经是 uint32，可直接用作持仓量
            open_interest = float(row["amount"])

            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                datetime=dt,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                volume=float(row["volume"]),
                turnover=0.0,
                open_interest=open_interest,
                gateway_name="TDX",
            )
            bars.append(bar)

        return bars
