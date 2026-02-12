# -*- coding: utf-8 -*-
"""
观澜量化 - 持仓监控面板

Author: 海山观澜
"""

from vnpy.trader.event import EVENT_POSITION
from vnpy.trader.object import PositionData

from .base import BaseMonitor, MonitorPanel


class _PositionTable(BaseMonitor):
    """持仓表格"""

    headers = {
        "symbol":       {"display": "代码"},
        "direction":    {"display": "方向",  "color": "direction"},
        "volume":       {"display": "数量",  "format": "int"},
        "yd_volume":    {"display": "昨仓",  "format": "int"},
        "frozen":       {"display": "冻结",  "format": "int"},
        "price":        {"display": "均价",  "format": ".2f"},
        "pnl":          {"display": "盈亏",  "format": ".2f", "color": "pnl"},
        "gateway_name": {"display": "账户"},
    }
    data_key = "vt_positionid"


class PositionMonitor(MonitorPanel):
    """持仓监控面板"""

    table_class = _PositionTable
    filter_fields = {"gateway_name": "账户", "symbol": "代码", "direction": "方向"}
    event_type = EVENT_POSITION

    def _convert_data(self, pos: PositionData) -> dict:
        return {
            "symbol": pos.symbol,
            "direction": pos.direction.value,
            "volume": pos.volume,
            "yd_volume": pos.yd_volume,
            "frozen": pos.frozen,
            "price": pos.price,
            "pnl": pos.pnl,
            "gateway_name": pos.gateway_name,
            "vt_positionid": pos.vt_positionid,
        }
