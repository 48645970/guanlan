# -*- coding: utf-8 -*-
"""
观澜量化 - AKShare 数据服务接口

基于新浪财经免费数据源，提供期货历史行情数据。
- 日线：futures_main_sina，主力连续合约，可指定日期范围
- 分钟/小时：futures_zh_minute_sina，具体合约，最近约 1000 根

Author: 海山观澜
"""

from collections.abc import Callable
from datetime import datetime

from vnpy.trader.constant import Interval
from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.object import BarData, HistoryRequest

from guanlan.core.utils.symbol_converter import SymbolConverter

# 支持的数据周期及其对应的 AKShare period 参数
_INTERVAL_PERIOD_MAP: dict[Interval, str] = {
    Interval.MINUTE: "1",
    Interval.HOUR: "60",
}


class AkShareDatafeed(BaseDatafeed):
    """AKShare 数据服务接口（新浪财经免费数据源）

    支持周期：
    - DAILY：主力连续合约日线，可指定日期范围
    - MINUTE：具体合约1分钟线，最近约 1000 根
    - HOUR：具体合约60分钟线，最近约 1000 根
    """

    def init(self, output: Callable = print) -> bool:
        """检查 akshare 是否可用"""
        try:
            import akshare  # noqa: F401
            self.inited = True
            return True
        except ImportError:
            output("请先安装 akshare: pip install akshare")
            return False

    def query_bar_history(
        self, req: HistoryRequest, output: Callable = print
    ) -> list[BarData]:
        """查询 K 线数据

        Parameters
        ----------
        req : HistoryRequest
            查询请求，symbol 应为交易所格式（如 rb2505、OI9999）
        output : Callable
            消息输出回调

        Returns
        -------
        list[BarData]
            K 线数据列表
        """
        if req.interval == Interval.DAILY:
            return self._query_daily(req, output)
        elif req.interval in _INTERVAL_PERIOD_MAP:
            return self._query_intraday(req, output)
        else:
            output(f"AKShare 不支持 {req.interval.value} 周期")
            return []

    def _query_daily(
        self, req: HistoryRequest, output: Callable
    ) -> list[BarData]:
        """查询日线数据（主力连续合约）"""
        import akshare as ak

        commodity = SymbolConverter.extract_commodity(req.symbol)
        if not commodity:
            output(f"无法识别品种代码: {req.symbol}")
            return []

        ak_symbol = commodity + "0"
        start_date = req.start.strftime("%Y%m%d")
        end_date = (req.end or datetime.now()).strftime("%Y%m%d")

        try:
            df = ak.futures_main_sina(
                symbol=ak_symbol,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            output(f"AKShare 请求失败: {e}")
            return []

        if df is None or df.empty:
            output(f"{commodity} 未获取到数据")
            return []

        # 列名：日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 持仓量, 动态结算价
        bars: list[BarData] = []
        for _, row in df.iterrows():
            dt = datetime.strptime(str(row["日期"]), "%Y-%m-%d")

            bar = BarData(
                symbol=req.symbol,
                exchange=req.exchange,
                interval=Interval.DAILY,
                datetime=dt,
                open_price=float(row["开盘价"]),
                high_price=float(row["最高价"]),
                low_price=float(row["最低价"]),
                close_price=float(row["收盘价"]),
                volume=float(row["成交量"]),
                turnover=0,
                open_interest=float(row["持仓量"]),
                gateway_name="AKShare",
            )
            bars.append(bar)

        return bars

    def _query_intraday(
        self, req: HistoryRequest, output: Callable
    ) -> list[BarData]:
        """查询日内数据（1分钟/60分钟，具体合约，最近约 1000 根）"""
        import akshare as ak

        # AKShare 分钟接口需要标准格式（大写 + 4位年月，如 OI2605）
        # CZCE 交易所格式为 3 位（OI605），需转回标准格式
        ak_symbol = SymbolConverter.to_standard(req.symbol, req.exchange)
        period = _INTERVAL_PERIOD_MAP[req.interval]

        try:
            df = ak.futures_zh_minute_sina(symbol=ak_symbol, period=period)
        except Exception as e:
            output(f"AKShare 数据请求失败: {e}")
            return []

        if df is None or df.empty:
            output(f"{ak_symbol} 未获取到数据")
            return []

        # 列名：datetime, open, high, low, close, volume, hold
        # 不加时区标记，AKShare 返回的就是北京时间，保持 naive datetime
        # 与 TDX 导入一致，避免 convert_tz 的时区转换问题
        bars: list[BarData] = []
        for _, row in df.iterrows():
            dt = datetime.strptime(str(row["datetime"]), "%Y-%m-%d %H:%M:%S")

            bar = BarData(
                symbol=req.symbol,
                exchange=req.exchange,
                interval=req.interval,
                datetime=dt,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=float(row["close"]),
                volume=float(row["volume"]),
                turnover=0,
                open_interest=float(row["hold"]),
                gateway_name="AKShare",
            )
            bars.append(bar)

        return bars
