# -*- coding: utf-8 -*-
"""
观澜量化 - 指标管理弹出面板

Flyout 式指标管理面板，支持勾选添加/移除和参数编辑。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    CheckBox, CaptionLabel, BodyLabel,
    TransparentToolButton, FluentIcon,
    FlyoutViewBase, SmoothScrollArea,
)

from guanlan.core.indicators import get_all_indicators
from guanlan.ui.common.style import StyleSheet


class IndicatorCard(QWidget):
    """单个指标的卡片行

    布局：
        ☑ 指标名称    [主图]  [编辑]

    Signals
    -------
    toggled(str, bool)
        勾选状态变化，参数为 (指标名, 是否勾选)
    edit_requested(str)
        点击编辑按钮，参数为 指标名
    """

    toggled = Signal(str, bool)
    edit_requested = Signal(str)

    def __init__(self, name: str, checked: bool, is_overlay: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 勾选框 + 名称
        self._checkbox = CheckBox(name)
        self._checkbox.setChecked(checked)
        self._checkbox.checkStateChanged.connect(self._on_check_changed)
        layout.addWidget(self._checkbox)

        layout.addStretch()

        # 主图/副图标签
        tag_text = "主图" if is_overlay else "副图"
        self._tag = CaptionLabel(tag_text)
        self._tag.setObjectName("overlayTag" if is_overlay else "subchartTag")
        self._tag.setAlignment(Qt.AlignCenter)
        self._tag.setFixedWidth(36)
        layout.addWidget(self._tag)

        # 编辑按钮
        self._edit_btn = TransparentToolButton(FluentIcon.SETTING)
        self._edit_btn.setFixedSize(30, 30)
        self._edit_btn.setIconSize(QSize(14, 14))
        self._edit_btn.setEnabled(checked)
        self._edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._name))
        layout.addWidget(self._edit_btn)

    def _on_check_changed(self) -> None:
        """勾选状态变化"""
        checked = self._checkbox.isChecked()
        self._edit_btn.setEnabled(checked)
        self.toggled.emit(self._name, checked)


class IndicatorFlyoutView(FlyoutViewBase):
    """指标管理 Flyout 面板

    列出所有已注册的指标，每个指标显示为一张 IndicatorCard。

    Signals
    -------
    indicator_toggled(str, bool)
        指标勾选状态变化
    indicator_edit_requested(str)
        请求编辑指标参数
    """

    indicator_toggled = Signal(str, bool)
    indicator_edit_requested = Signal(str)

    def __init__(self, active_indicators: dict[str, dict],
                 parent: QWidget | None = None) -> None:
        """
        Parameters
        ----------
        active_indicators : dict[str, dict]
            当前已激活的指标及其参数，如 {"双均线交叉": {"short_window": 5, ...}}
        """
        super().__init__(parent)

        self._cards: dict[str, IndicatorCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(0)

        # 标题
        title = BodyLabel("指标管理")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(8)

        # 滚动区域
        scroll = SmoothScrollArea(self)
        scroll.setObjectName("indicatorScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("indicatorContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 指标卡片列表
        all_indicators = get_all_indicators()
        for i, (name, ind_cls) in enumerate(all_indicators.items()):
            is_active = name in active_indicators

            # 分隔线
            if i > 0:
                sep = QWidget()
                sep.setObjectName("indicatorSep")
                sep.setFixedHeight(1)
                container_layout.addWidget(sep)

            card = IndicatorCard(name, is_active, ind_cls.overlay, self)
            card.toggled.connect(self.indicator_toggled)
            card.edit_requested.connect(self.indicator_edit_requested)
            self._cards[name] = card
            container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.setFixedWidth(280)
        self.setMaximumHeight(400)

        # 应用 QSS 样式
        StyleSheet.apply(self, ["common.qss", "indicator_panel.qss"])
