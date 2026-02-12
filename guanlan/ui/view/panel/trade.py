# -*- coding: utf-8 -*-
"""
观澜量化 - 成交监控面板

Author: 海山观澜
"""

from vnpy.trader.event import EVENT_TRADE
from vnpy.trader.object import TradeData

from .base import BaseMonitor, MonitorPanel
from ._refs import get_order_reference


class _TradeTable(BaseMonitor):
    """成交表格"""

    headers = {
        "symbol":       {"display": "代码"},
        "direction":    {"display": "方向",  "color": "direction"},
        "offset":       {"display": "开平"},
        "price":        {"display": "价格",  "format": ".2f"},
        "volume":       {"display": "数量",  "format": "int"},
        "datetime":     {"display": "时间",  "format": "time"},
        "reference":    {"display": "来源"},
        "gateway_name": {"display": "账户"},
        "tradeid":      {"display": "成交号"},
        "orderid":      {"display": "委托号"},
    }
    data_key = ""  # 仅追加


class TradeMonitor(MonitorPanel):
    """成交监控面板"""

    table_class = _TradeTable
    filter_fields = {"gateway_name": "账户", "symbol": "代码", "direction": "方向", "offset": "开平"}
    auto_scroll = True
    event_type = EVENT_TRADE

    def _convert_data(self, trade: TradeData) -> dict:
        return {
            "tradeid": trade.tradeid,
            "orderid": trade.orderid,
            "symbol": trade.symbol,
            "direction": trade.direction.value if trade.direction else "",
            "offset": trade.offset.value,
            "price": trade.price,
            "volume": trade.volume,
            "datetime": str(trade.datetime) if trade.datetime else "",
            "reference": get_order_reference(trade.vt_orderid),
            "gateway_name": trade.gateway_name,
        }
