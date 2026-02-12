# -*- coding: utf-8 -*-
"""
观澜量化 - 状态标签组件

基于 InfoBadge 的自定义圆角状态标签。

Author: 海山观澜
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QWidget

from qfluentwidgets import InfoBadge


class StatusBadge(InfoBadge):
    """状态标签（自定义圆角半径）"""

    def __init__(self, text: str, parent: QWidget = None, radius: int = 4):
        super().__init__(text, parent)
        self._radius = radius

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._backgroundColor())
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)
        # 跳过 InfoBadge.paintEvent，直接调用 QLabel.paintEvent 绘制文字
        QLabel.paintEvent(self, e)
