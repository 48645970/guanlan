# -*- coding: utf-8 -*-
"""
观澜量化 - 标题栏行情连接状态指示器

与标题栏 min/max/close 按钮同风格的状态指示器，
用色块背景 + 白色文字/图标表示行情账户连接状态。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets.common.icon import Theme


# 颜色定义（与 CloseButton 红色一致）
_COLOR_DISCONNECTED = QColor(232, 17, 35)
_COLOR_CONNECTED = QColor(0, 120, 212)


class ConnectionIndicator(QWidget):
    """标题栏行情连接状态指示器

    色块背景 + 白色"行情"文字 + FluentIcon 图标：
    - 未连接：红色背景 + WIFI 图标 + 斜杠
    - 已连接：蓝色背景 + WIFI 图标
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 32)
        self._connected = False

    def setConnected(self, connected: bool, tooltip: str = "") -> None:
        """设置连接状态"""
        self._connected = connected
        self.setToolTip(tooltip)
        self.update()

    def isConnected(self) -> bool:
        return self._connected

    def paintEvent(self, e) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)

        # 色块背景
        bg = _COLOR_CONNECTED if self._connected else _COLOR_DISCONNECTED
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        # 左侧 WIFI 图标（白色，16x16）
        icon_size = 14
        ix = 6
        iy = (self.height() - icon_size) / 2
        icon_rect = QRectF(ix, iy, icon_size, icon_size)
        FIF.WIFI.render(painter, icon_rect, Theme.DARK)

        if not self._connected:
            # 斜杠覆盖图标（断开标记）
            pen = QPen(QColor(255, 255, 255), 1.5)
            pen.setCosmetic(True)
            painter.setPen(pen)
            cx = ix + icon_size / 2
            cy = self.height() / 2
            painter.drawLine(
                int(cx - 6), int(cy + 6),
                int(cx + 6), int(cy - 6),
            )

        # 右侧状态文字
        pen = QPen(QColor(255, 255, 255))
        painter.setPen(pen)
        font = QFont()
        font.setPixelSize(12)
        painter.setFont(font)
        text = "行情连接" if self._connected else "行情断开"
        painter.drawText(
            QRectF(ix + icon_size + 2, 0, self.width() - ix - icon_size - 2, self.height()),
            Qt.AlignCenter, text,
        )
