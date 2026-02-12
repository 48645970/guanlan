# -*- coding: utf-8 -*-
"""
观澜量化 - 委托监控面板

继承 MonitorPanel，增加"仅可撤"过滤和双击撤单。

Author: 海山观澜
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from qfluentwidgets import CheckBox

from vnpy.trader.event import EVENT_ORDER
from vnpy.trader.object import OrderData, CancelRequest
from vnpy.trader.constant import Exchange

from .base import BaseMonitor, MonitorPanel
from ._refs import cache_order_reference, get_order_reference


class _OrderTable(BaseMonitor):
    """委托表格（内部使用）"""

    headers = {
        "symbol":       {"display": "代码"},
        "direction":    {"display": "方向",  "color": "direction"},
        "offset":       {"display": "开平"},
        "price":        {"display": "价格",  "format": ".2f"},
        "volume":       {"display": "数量",  "format": "int"},
        "traded":       {"display": "已成交", "format": "int"},
        "status":       {"display": "状态"},
        "datetime":     {"display": "时间",  "format": "time"},
        "reference":    {"display": "来源"},
        "gateway_name": {"display": "账户"},
        "orderid":      {"display": "委托号"},
    }
    data_key = "vt_orderid"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setToolTip("双击撤单")

    def _fill_row(self, row: int, data: dict) -> None:
        """重写：给每个 item 存 vt_orderid"""
        super()._fill_row(row, data)
        vt_orderid = data.get("vt_orderid", "")
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setData(Qt.UserRole, vt_orderid)


class OrderMonitor(MonitorPanel):
    """委托监控面板（过滤器 + 仅可撤 + 双击撤单）"""

    table_class = _OrderTable
    filter_fields = {"gateway_name": "账户", "symbol": "代码", "direction": "方向", "offset": "开平", "status": "状态"}
    auto_scroll = True
    event_type = EVENT_ORDER

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._table.itemDoubleClicked.connect(self._cancel_order)

    def _convert_data(self, order: OrderData) -> dict:
        # 缓存 reference（CTP 回报不带 reference）
        cache_order_reference(order.vt_orderid, order.reference)
        reference = get_order_reference(order.vt_orderid)

        return {
            "orderid": order.orderid,
            "symbol": order.symbol,
            "exchange": order.exchange.value,
            "direction": order.direction.value if order.direction else "",
            "offset": order.offset.value,
            "price": order.price,
            "volume": order.volume,
            "traded": order.traded,
            "status": order.status.value,
            "is_active": order.is_active(),
            "datetime": str(order.datetime) if order.datetime else "",
            "reference": reference,
            "gateway_name": order.gateway_name,
            "vt_orderid": order.vt_orderid,
        }

    def _create_filters(self) -> None:
        """重写：添加"仅可撤"复选框（放在过滤器前面）"""
        self._active_check = CheckBox("仅可撤", self)
        self._active_check.setToolTip("仅显示可撤销的活动委托")
        self._active_check.stateChanged.connect(self._apply_filters)
        self._toolbar.addWidget(self._active_check)
        super()._create_filters()

    def _should_hide(self, data: dict) -> bool:
        """重写：增加活动委托过滤"""
        if super()._should_hide(data):
            return True
        if self._active_check.isChecked() and not data.get("is_active", False):
            return True
        return False

    def _cancel_order(self, item: QTableWidgetItem) -> None:
        """双击撤单"""
        vt_orderid = item.data(Qt.UserRole)
        if not vt_orderid:
            return

        data = self._table._row_data.get(vt_orderid)
        if not data:
            return

        if not data.get("is_active", False):
            return

        req = CancelRequest(
            orderid=data["orderid"],
            symbol=data["symbol"],
            exchange=Exchange(data["exchange"]),
        )

        from guanlan.core.app import AppEngine
        AppEngine.instance().main_engine.cancel_order(req, data["gateway_name"])
