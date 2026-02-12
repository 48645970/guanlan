# -*- coding: utf-8 -*-
"""
观澜量化 - 功能卡片组件

用于首页展示功能模块。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    CardWidget, IconWidget, BodyLabel, CaptionLabel,
    FluentIcon, FlowLayout, setFont
)

from guanlan.core.events import signal_bus


class FeatureCard(CardWidget):
    """功能卡片 - 用于展示功能模块"""

    # 点击信号
    card_clicked = Signal(str)

    def __init__(
        self,
        icon: FluentIcon,
        title: str,
        content: str,
        route_key: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.route_key = route_key
        self.setFixedSize(280, 160)

        # 图标
        self.icon_widget = IconWidget(icon, self)
        self.icon_widget.setFixedSize(36, 36)

        # 标题
        self.title_label = BodyLabel(title, self)
        setFont(self.title_label, 16, weight=QFont.Weight.DemiBold)

        # 描述
        self.content_label = CaptionLabel(content, self)
        self.content_label.setWordWrap(True)

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化组件"""
        if self.route_key:
            self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.addWidget(self.icon_widget)
        layout.addWidget(self.title_label)
        layout.addWidget(self.content_label)
        layout.addStretch()

    def mouseReleaseEvent(self, event) -> None:
        """点击事件"""
        super().mouseReleaseEvent(event)
        if self.route_key:
            self.card_clicked.emit(self.route_key)
            signal_bus.navigate_to.emit(self.route_key)


class FeatureCardView(QWidget):
    """功能卡片视图 - 带标题的水平布局"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent=parent)

        self.title_label = BodyLabel(title, self) if title else None
        self.h_layout = QHBoxLayout()
        self.cards: list[FeatureCard] = []

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化组件"""
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(16)
        self.h_layout.setAlignment(Qt.AlignLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(36, 0, 36, 0)
        main_layout.setSpacing(12)

        if self.title_label:
            self.title_label.setObjectName("viewTitleLabel")
            setFont(self.title_label, 24, weight=QFont.Weight.Bold)
            main_layout.addWidget(self.title_label)

        main_layout.addLayout(self.h_layout)

    def add_card(
        self,
        icon: FluentIcon,
        title: str,
        content: str,
        route_key: str = ""
    ) -> FeatureCard:
        """添加功能卡片"""
        card = FeatureCard(icon, title, content, route_key, self)
        self.cards.append(card)
        self.h_layout.addWidget(card)
        return card

    def add_stretch(self) -> None:
        """添加弹性空间"""
        self.h_layout.addStretch()
