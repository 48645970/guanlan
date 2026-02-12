# -*- coding: utf-8 -*-
"""
观澜量化 - 模块卡片组件

用于首页展示功能模块入口，支持流式布局。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    CardWidget, IconWidget, FluentIcon, FlowLayout,
    StrongBodyLabel, BodyLabel, setFont
)

from guanlan.core.events import signal_bus


class ModuleCard(CardWidget):
    """模块卡片 - 点击导航到对应界面"""

    # 使用不同的信号名避免与 CardWidget.clicked 冲突
    card_clicked = Signal(str)

    def __init__(
        self,
        icon: FluentIcon,
        title: str,
        content: str,
        route_key: str,
        parent=None
    ):
        super().__init__(parent)
        self.route_key = route_key

        self.icon_widget = IconWidget(icon, self)
        self.title_label = StrongBodyLabel(title, self)
        self.content_label = BodyLabel(content, self)

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化组件"""
        self.setFixedSize(240, 72)
        self.setCursor(Qt.PointingHandCursor)

        self.icon_widget.setFixedSize(32, 32)

        # 右侧文字
        text_layout = QVBoxLayout()
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.content_label)
        text_layout.setSpacing(4)  # 标题与副标题间距
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setAlignment(Qt.AlignVCenter)

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self.icon_widget, 0, Qt.AlignVCenter)
        main_layout.addSpacing(12)
        main_layout.addLayout(text_layout)
        main_layout.addStretch()
        main_layout.setContentsMargins(16, 0, 16, 0)

    def mouseReleaseEvent(self, event) -> None:
        """点击事件"""
        # 不调用 super()，避免 CardWidget.clicked 信号冲突
        self.card_clicked.emit(self.route_key)
        signal_bus.navigate_to.emit(self.route_key)


class ModuleCardView(QWidget):
    """模块卡片视图 - 带标题的流式布局"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent=parent)

        self.title_label = StrongBodyLabel(title, self)
        self.flow_layout = FlowLayout()
        self.cards: list[ModuleCard] = []

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化组件"""
        self.title_label.setObjectName("viewTitleLabel")
        setFont(self.title_label, 18, weight=QFont.Weight.Bold)

        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setHorizontalSpacing(12)
        self.flow_layout.setVerticalSpacing(8)  # 减少卡片垂直间距

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 0, 28, 0)  # 与标题对齐
        main_layout.setSpacing(8)  # 减少标题与卡片间距
        main_layout.addWidget(self.title_label)
        main_layout.addLayout(self.flow_layout)

    def add_card(
        self,
        icon: FluentIcon,
        title: str,
        content: str,
        route_key: str
    ) -> ModuleCard:
        """添加模块卡片"""
        card = ModuleCard(icon, title, content, route_key, self)
        self.cards.append(card)
        self.flow_layout.addWidget(card)
        return card
