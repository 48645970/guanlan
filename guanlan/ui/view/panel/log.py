# -*- coding: utf-8 -*-
"""
观澜量化 - 日志监控面板

Author: 海山观澜
"""

from guanlan.core.utils.trading_period import beijing_now

from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QToolTip

from qfluentwidgets import isDarkTheme

from vnpy.trader.event import EVENT_LOG
from vnpy.trader.object import LogData

from .base import BaseMonitor, MonitorPanel

# 最大行数，超出移除最早行
_MAX_ROWS = 500

_LEVEL_NAMES: dict[int, str] = {
    10: "DEBUG",
    20: "INFO",
    30: "WARNING",
    40: "ERROR",
    50: "CRITICAL",
}


class _LogTable(BaseMonitor):
    """日志表格"""

    headers = {
        "time":   {"display": "时间", "width": 70},
        "level":  {"display": "级别", "width": 60},
        "source": {"display": "来源", "width": 80},
        "msg":    {"display": "信息", "align": "left"},
    }
    data_key = ""  # 仅追加

    def process_data(self, data: dict) -> None:
        """追加日志（超限移除最早行）"""
        if self.rowCount() >= _MAX_ROWS:
            self.removeRow(0)
            self._data_by_row.pop(0)
        super().process_data(data)

    def _fill_row(self, row: int, data: dict) -> None:
        """填充行 + 级别着色 + 信息 tooltip"""
        super()._fill_row(row, data)

        # 信息列 tooltip
        msg_col = self._header_keys.index("msg")
        msg_item = self.item(row, msg_col)
        if msg_item:
            msg_item.setToolTip(data.get("msg", ""))

        # 按日志级别着色整行
        level_int = data.get("_level")
        if level_int is not None:
            from . import LEVEL_COLORS
            colors = LEVEL_COLORS.get(level_int)
            if colors:
                color = colors[0] if isDarkTheme() else colors[1]
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setForeground(color)

    def viewportEvent(self, event) -> bool:
        """原生 QToolTip 显示在鼠标位置"""
        if event.type() == QHelpEvent.Type.ToolTip:
            help_event: QHelpEvent = event
            item = self.itemAt(help_event.pos())
            if item and item.toolTip():
                QToolTip.showText(help_event.globalPos(), item.toolTip(), self)
            else:
                QToolTip.hideText()
            return True
        return super().viewportEvent(event)


class LogMonitor(MonitorPanel):
    """日志监控面板"""

    table_class = _LogTable
    filter_fields = {"level": "级别", "source": "来源"}
    auto_scroll = True
    event_type = EVENT_LOG

    def _convert_data(self, log: LogData) -> dict:
        return {
            "time": beijing_now().strftime("%H:%M:%S"),
            "level": _LEVEL_NAMES.get(log.level, str(log.level)),
            "source": log.gateway_name or "System",
            "msg": log.msg,
            "_level": log.level,
        }
