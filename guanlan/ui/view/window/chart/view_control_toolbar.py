# -*- coding: utf-8 -*-
"""
观澜量化 - 图表视图控制工具栏

提供图表视图的各种控制选项：
- 自动适应视图
- 磁性光标开关
- 价格轴模式切换
- AI 价格线显示控制
- 十字光标样式选择
- 缩放控制

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets import (
    BodyLabel, PushButton, SwitchButton, ComboBox,
    FluentIcon, TransparentToolButton, DropDownPushButton,
    RoundMenu, Action, MenuAnimationType,
)


class ViewControlToolBar(QWidget):
    """图表视图控制工具栏

    提供以下控制选项：
    - 自动适应：一键调整视图适应所有数据
    - 磁性光标：十字光标吸附到数据点
    - 价格模式：普通/对数/百分比/指数100
    - AI 价格线：显示/隐藏 AI 分析的价格线
    - 光标样式：完整/仅水平/仅垂直/隐藏
    - 缩放控制：手动缩放按钮
    """

    # 信号
    fit_content_requested = Signal()                 # 自动适应
    magnet_mode_changed = Signal(bool)              # 磁性模式切换
    price_mode_changed = Signal(int)                # 价格模式切换（0=普通, 1=对数, 2=百分比, 3=指数100）
    percentage_scale_toggled = Signal(bool)         # 左侧百分比轴显示切换
    ai_price_lines_toggled = Signal(bool)           # AI 价格线显示切换
    crosshair_style_changed = Signal(str)           # 光标样式（full/horizontal/vertical/hidden）
    zoom_in_requested = Signal()                    # 放大
    zoom_out_requested = Signal()                   # 缩小
    zoom_reset_requested = Signal()                 # 重置缩放

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewControlToolbar")

        self._init_ui()

    def _init_ui(self) -> None:
        """初始化界面"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(12)

        # ── 分组 1：视图调整 ──
        self._add_group_label(main_layout, "视图调整")

        # 自动适应按钮
        self.fit_btn = PushButton("自动适应", self)
        self.fit_btn.setIcon(FluentIcon.FIT_PAGE)
        self.fit_btn.clicked.connect(self.fit_content_requested)
        main_layout.addWidget(self.fit_btn)

        # 缩放控制按钮组
        zoom_layout = QHBoxLayout()
        zoom_layout.setSpacing(2)

        self.zoom_in_btn = TransparentToolButton(FluentIcon.ZOOM_IN, self)
        self.zoom_in_btn.setToolTip("放大")
        self.zoom_in_btn.clicked.connect(self.zoom_in_requested)
        zoom_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = TransparentToolButton(FluentIcon.ZOOM_OUT, self)
        self.zoom_out_btn.setToolTip("缩小")
        self.zoom_out_btn.clicked.connect(self.zoom_out_requested)
        zoom_layout.addWidget(self.zoom_out_btn)

        self.zoom_reset_btn = TransparentToolButton(FluentIcon.CANCEL, self)
        self.zoom_reset_btn.setToolTip("重置缩放")
        self.zoom_reset_btn.clicked.connect(self.zoom_reset_requested)
        zoom_layout.addWidget(self.zoom_reset_btn)

        main_layout.addLayout(zoom_layout)

        # 分隔线
        self._add_separator(main_layout)

        # ── 分组 2：光标设置 ──
        self._add_group_label(main_layout, "光标设置")

        # 磁性光标开关
        self.magnet_switch = SwitchButton("磁性", self)
        self.magnet_switch.setChecked(True)  # 默认开启
        self.magnet_switch.setToolTip("开启后光标会吸附到最近的数据点")
        self.magnet_switch.checkedChanged.connect(self.magnet_mode_changed)
        main_layout.addWidget(self.magnet_switch)

        # 光标样式下拉按钮
        self.crosshair_style_btn = DropDownPushButton("完整", self)
        self.crosshair_style_btn.setIcon(FluentIcon.ALIGNMENT)
        self._setup_crosshair_menu()
        main_layout.addWidget(self.crosshair_style_btn)

        # 分隔线
        self._add_separator(main_layout)

        # ── 分组 3：价格设置 ──
        self._add_group_label(main_layout, "价格设置")

        # 价格模式下拉
        self.price_mode_combo = ComboBox(self)
        self.price_mode_combo.addItems([
            "普通模式",
            "对数模式",
            "百分比模式",
            "指数100模式"
        ])
        self.price_mode_combo.setCurrentIndex(0)
        self.price_mode_combo.setFixedWidth(120)
        self.price_mode_combo.setToolTip(
            "右侧价格轴模式：\n"
            "普通：显示原始价格\n"
            "对数：适合大幅波动品种\n"
            "百分比：显示涨跌幅\n"
            "指数100：以某点为基准100"
        )
        self.price_mode_combo.currentIndexChanged.connect(self.price_mode_changed)
        main_layout.addWidget(self.price_mode_combo)

        # 左侧百分比轴开关
        self.percentage_scale_switch = SwitchButton("左侧百分比", self)
        self.percentage_scale_switch.setChecked(False)  # 默认关闭
        self.percentage_scale_switch.setToolTip("在左侧显示百分比价格轴")
        self.percentage_scale_switch.checkedChanged.connect(self.percentage_scale_toggled)
        main_layout.addWidget(self.percentage_scale_switch)

        # AI 价格线开关
        self.ai_lines_switch = SwitchButton("AI 价格线", self)
        self.ai_lines_switch.setChecked(True)  # 默认显示
        self.ai_lines_switch.setToolTip("显示/隐藏 AI 分析的止损止盈线")
        self.ai_lines_switch.checkedChanged.connect(self.ai_price_lines_toggled)
        main_layout.addWidget(self.ai_lines_switch)

        main_layout.addStretch()

    def _setup_crosshair_menu(self) -> None:
        """设置光标样式菜单"""
        menu = RoundMenu(parent=self)

        # 完整十字
        action_full = Action(FluentIcon.ALIGNMENT, "完整十字", self)
        action_full.triggered.connect(lambda: self._on_crosshair_style_selected("完整", "full"))
        menu.addAction(action_full)

        # 仅水平线
        action_horizontal = Action(FluentIcon.REMOVE, "仅水平线", self)
        action_horizontal.triggered.connect(lambda: self._on_crosshair_style_selected("水平", "horizontal"))
        menu.addAction(action_horizontal)

        # 仅垂直线
        action_vertical = Action(FluentIcon.LAYOUT, "仅垂直线", self)
        action_vertical.triggered.connect(lambda: self._on_crosshair_style_selected("垂直", "vertical"))
        menu.addAction(action_vertical)

        # 隐藏光标
        action_hidden = Action(FluentIcon.HIDE, "隐藏光标", self)
        action_hidden.triggered.connect(lambda: self._on_crosshair_style_selected("隐藏", "hidden"))
        menu.addAction(action_hidden)

        self.crosshair_style_btn.setMenu(menu)

    def _on_crosshair_style_selected(self, text: str, style: str) -> None:
        """光标样式选择"""
        self.crosshair_style_btn.setText(text)
        self.crosshair_style_changed.emit(style)

    def _add_group_label(self, layout: QHBoxLayout, text: str) -> None:
        """添加分组标签"""
        label = BodyLabel(text, self)
        label.setObjectName("groupLabel")
        layout.addWidget(label)

    def _add_separator(self, layout: QHBoxLayout) -> None:
        """添加分隔线"""
        separator = QWidget(self)
        separator.setObjectName("separator")
        separator.setFixedWidth(1)
        separator.setFixedHeight(20)
        layout.addWidget(separator)

    def set_magnet_mode(self, enabled: bool) -> None:
        """设置磁性模式（外部调用）"""
        self.magnet_switch.setChecked(enabled)

    def set_price_mode(self, mode: int) -> None:
        """设置价格模式（外部调用）"""
        if 0 <= mode <= 3:
            self.price_mode_combo.setCurrentIndex(mode)

    def set_ai_lines_visible(self, visible: bool) -> None:
        """设置 AI 价格线可见性（外部调用）"""
        self.ai_lines_switch.setChecked(visible)

    def set_percentage_scale(self, enabled: bool) -> None:
        """设置左侧百分比轴（外部调用）"""
        self.percentage_scale_switch.setChecked(enabled)
