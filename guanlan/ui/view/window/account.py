# -*- coding: utf-8 -*-
"""
观澜量化 - 账户管理窗口

卡片式布局，支持连接管理、自动登录、行情服务选择。

Author: 海山观澜
"""

from typing import Any

from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSizePolicy,
)

from qfluentwidgets import (
    SubtitleLabel, StrongBodyLabel, BodyLabel,
    LineEdit, ComboBox,
    PushButton, PrimaryPushButton, ToolButton, TransparentToolButton,
    CheckBox, RadioButton,
    CardWidget, MessageBox, MessageBoxBase,
    SmoothScrollArea,
    InfoBar, InfoBarPosition, InfoLevel,
    FluentIcon, FluentWidget,
    isDarkTheme, qconfig,
)

from guanlan.ui.widgets.components.badge import StatusBadge
from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.core.app import AppEngine
from guanlan.core.events import signal_bus
from guanlan.core.setting.account import (
    ACCOUNT_FIELDS, PASSWORD_FIELDS,
    load_config, save_config, get_accounts, get_default_env,
    new_account, get_display_name,
    is_auto_login, set_auto_login,
    is_market_source, set_market_source,
)

# 交互控件类型（点击时不触发折叠）
_INTERACTIVE_TYPES = (
    PushButton, PrimaryPushButton, ToolButton,
    CheckBox, RadioButton,
    LineEdit, ComboBox,
)


class AccountAddDialog(MessageBoxBase):
    """添加账户对话框"""

    def __init__(self, existing_keys: list[str], parent=None):
        super().__init__(parent)

        self.existing_keys = existing_keys
        self.env_key: str = ""

        self.titleLabel = SubtitleLabel("添加账户", self)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("输入环境名称，如：实盘、仿真")
        self.name_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.name_edit)

        self.yesButton.setText("添加")
        self.cancelButton.setText("取消")
        self.widget.setMinimumWidth(400)

    def validate(self) -> bool:
        """验证输入（基类 MessageBoxBase 在确认时自动调用）"""
        key = self.name_edit.text().strip()
        if not key:
            InfoBar.error(
                title="输入错误",
                content="环境名称不能为空",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return False
        if key in self.existing_keys:
            InfoBar.error(
                title="输入错误",
                content=f"环境名称「{key}」已存在",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return False

        self.env_key = key
        return True


class AccountCard(CardWidget):
    """账户卡片

    显示账户摘要信息，点击展开/收起编辑表单。
    """

    # 请求删除此卡片
    delete_requested = Signal(str)
    # 行情服务选择变更
    market_source_clicked = Signal(str)

    def __init__(self, env_key: str, account_data: dict, parent=None):
        super().__init__(parent)

        self.env_key = env_key
        self.account_data = account_data
        self._expanded = False

        self._init_ui()
        self._connect_signals()

        # 检查当前连接状态
        app = AppEngine.instance()
        if app.is_connected(env_key):
            self._set_connected(True)
        elif app.is_connecting(env_key):
            self._set_connecting()

    def _init_ui(self) -> None:
        """初始化界面"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(0)

        # ── 摘要行 ──
        self._init_summary()

        # ── 编辑表单（默认隐藏）──
        self._init_form()

    def _init_summary(self) -> None:
        """初始化摘要行"""
        summary = QHBoxLayout()
        summary.setSpacing(20)

        # 折叠箭头
        self.arrow_btn = ToolButton(FluentIcon.CHEVRON_RIGHT, self)
        self.arrow_btn.setFixedSize(20, 20)
        self.arrow_btn.setIconSize(QSize(10, 10))
        self.arrow_btn.clicked.connect(self._toggle_expand)
        summary.addWidget(self.arrow_btn)

        # 连接状态
        self.status_badge = StatusBadge("未连接", self)
        self.status_badge.setLevel(InfoLevel.INFOAMTION)
        self.status_badge.setFixedHeight(20)
        summary.addWidget(self.status_badge)

        # 环境名
        display_name = get_display_name(self.env_key, self.account_data)
        self.name_label = StrongBodyLabel(display_name, self)
        self.name_label.setMinimumWidth(80)
        summary.addWidget(self.name_label)

        summary.addStretch(1)

        # 行情服务
        self.market_radio = RadioButton("行情服务", self)
        self.market_radio.setChecked(is_market_source(self.account_data))
        summary.addWidget(self.market_radio)

        # 自动登录
        self.auto_login_check = CheckBox("自动登录", self)
        self.auto_login_check.setChecked(is_auto_login(self.account_data))
        summary.addWidget(self.auto_login_check)

        # 连接/断开按钮
        self.connect_btn = PrimaryPushButton("连接", self)
        self.connect_btn.setFixedWidth(100)
        summary.addWidget(self.connect_btn)

        self.disconnect_btn = PushButton("断开", self)
        self.disconnect_btn.setFixedWidth(100)
        self.disconnect_btn.hide()
        summary.addWidget(self.disconnect_btn)

        # 删除按钮
        self.delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        summary.addWidget(self.delete_btn)

        self.main_layout.addLayout(summary)

    def _init_form(self) -> None:
        """初始化编辑表单（默认隐藏）"""
        self.form_widget = QWidget(self)
        self.form_widget.setVisible(False)
        self.form_widget.setMaximumHeight(0)

        form_layout = QVBoxLayout(self.form_widget)
        form_layout.setContentsMargins(0, 12, 0, 4)

        # 表单字段
        self.field_widgets: dict[str, LineEdit | ComboBox] = {}
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        for field_name, _ in ACCOUNT_FIELDS:
            if field_name == "柜台环境":
                widget = ComboBox(self.form_widget)
                widget.addItems(["实盘", "测试"])
                widget.setMinimumWidth(200)
            else:
                widget = LineEdit(self.form_widget)
                widget.setMinimumWidth(200)

            label = BodyLabel(field_name, self.form_widget)
            form.addRow(label, widget)
            self.field_widgets[field_name] = widget

        form_layout.addLayout(form)

        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.save_btn = PrimaryPushButton("保存", self.form_widget)
        self.save_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        form_layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.form_widget)

        # 加载数据到表单
        self._load_form_data()

    def _load_form_data(self) -> None:
        """加载账户数据到表单"""
        for field_name, widget in self.field_widgets.items():
            value = self.account_data.get(field_name, "")
            if isinstance(widget, ComboBox):
                widget.setCurrentText(value or "实盘")
            else:
                widget.setText(value)

    def _collect_form_data(self) -> dict[str, str]:
        """从表单收集数据"""
        data: dict[str, str] = {}
        for field_name, widget in self.field_widgets.items():
            if isinstance(widget, ComboBox):
                data[field_name] = widget.currentText()
            else:
                data[field_name] = widget.text()
        return data

    def _connect_signals(self) -> None:
        """连接信号"""
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.auto_login_check.stateChanged.connect(self._on_auto_login_changed)
        self.market_radio.clicked.connect(self._on_market_source_clicked)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.env_key))
        self.save_btn.clicked.connect(self._on_save)

        # 全局信号
        signal_bus.account_connected.connect(self._on_account_connected)
        signal_bus.account_disconnected.connect(self._on_account_disconnected)
        signal_bus.account_connect_timeout.connect(self._on_connect_timeout)

    def _toggle_expand(self) -> None:
        """展开/收起编辑表单"""
        self._expanded = not self._expanded

        # 旋转箭头图标（同一个图标，展开时顺时针 90°）
        angle = 90 if self._expanded else 0
        icon_size = self.arrow_btn.iconSize()
        pixmap = FluentIcon.CHEVRON_RIGHT.icon().pixmap(icon_size)
        rotated = pixmap.transformed(QTransform().rotate(angle), Qt.SmoothTransformation)
        self.arrow_btn.setIcon(QIcon(rotated))

        if self._expanded:
            self.form_widget.setVisible(True)
            target_height = self.form_widget.sizeHint().height()

            anim = QPropertyAnimation(self.form_widget, b"maximumHeight", self)
            anim.setDuration(200)
            anim.setStartValue(0)
            anim.setEndValue(target_height)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._expand_anim = anim
        else:
            anim = QPropertyAnimation(self.form_widget, b"maximumHeight", self)
            anim.setDuration(200)
            anim.setStartValue(self.form_widget.height())
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: self.form_widget.setVisible(False))
            anim.start()
            self._expand_anim = anim

    def _is_interactive_widget(self, widget: QWidget | None) -> bool:
        """检查控件或其祖先是否为交互控件"""
        while widget is not None and widget is not self:
            if isinstance(widget, _INTERACTIVE_TYPES):
                return True
            widget = widget.parentWidget()
        return False

    def mouseReleaseEvent(self, event):
        """点击卡片非交互区域展开/收起"""
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            if not self._is_interactive_widget(child):
                self._toggle_expand()
        super().mouseReleaseEvent(event)

    def _on_connect(self) -> None:
        """连接按钮"""
        app = AppEngine.instance()
        app.connect(self.env_key)
        self._set_connecting()

    def _on_disconnect(self) -> None:
        """断开按钮"""
        app = AppEngine.instance()
        app.disconnect(self.env_key)

    def _on_auto_login_changed(self, state: int) -> None:
        """自动登录变化"""
        checked = state == Qt.Checked.value
        set_auto_login(self.account_data, checked)
        self._save_config()

    def _on_market_source_clicked(self) -> None:
        """行情服务点击"""
        self.market_source_clicked.emit(self.env_key)

    def _on_save(self) -> None:
        """保存编辑"""
        form_data = self._collect_form_data()
        self.account_data.update(form_data)
        self._save_config()

        # 更新卡片显示名
        display_name = get_display_name(self.env_key, self.account_data)
        self.name_label.setText(display_name)

        InfoBar.success(
            title="保存成功",
            content=f"账户「{self.env_key}」配置已保存",
            duration=3000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _on_account_connected(self, env_name: str) -> None:
        """连接成功"""
        if env_name == self.env_key:
            self._set_connected(True)

    def _on_account_disconnected(self, env_name: str) -> None:
        """断开连接"""
        if env_name == self.env_key:
            self._set_connected(False)

    def _on_connect_timeout(self, env_name: str) -> None:
        """连接超时"""
        if env_name != self.env_key:
            return

        self._set_connected(False)
        InfoBar.warning(
            title="连接超时",
            content=f"账户「{self.env_key}」连接超时，请检查网络后重试",
            duration=5000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _set_connecting(self) -> None:
        """设置连接中状态"""
        self.status_badge.setText("连接中")
        self.status_badge.setLevel(InfoLevel.WARNING)
        self.connect_btn.setText("连接中...")
        self.connect_btn.setEnabled(False)
        self.connect_btn.show()
        self.disconnect_btn.hide()
        self.status_badge.adjustSize()

    def _set_connected(self, connected: bool) -> None:
        """设置连接状态显示"""
        if connected:
            self.status_badge.setText("已连接")
            self.status_badge.setLevel(InfoLevel.SUCCESS)
            self.connect_btn.hide()
            self.disconnect_btn.show()
        else:
            self.status_badge.setText("未连接")
            self.status_badge.setLevel(InfoLevel.INFOAMTION)
            self.connect_btn.setText("连接")
            self.connect_btn.setEnabled(True)
            self.connect_btn.show()
            self.disconnect_btn.hide()

        self.status_badge.adjustSize()

    def set_market_source(self, enabled: bool) -> None:
        """设置行情服务选中状态"""
        self.market_radio.setChecked(enabled)
        set_market_source(self.account_data, enabled)

    def _save_config(self) -> None:
        """保存配置到文件"""
        config = load_config()
        accounts = get_accounts(config)
        accounts[self.env_key] = self.account_data
        save_config(config)


class AccountManagerWindow(CursorFixMixin, FluentWidget):
    """账户管理窗口（非模态独立窗口）"""

    # 行情服务互斥信号
    market_source_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.cards: dict[str, AccountCard] = {}

        self._init_ui()
        self._load_accounts()

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("账户管理")
        self.setFixedSize(850, 600)

        # 标题栏
        self.titleBar.setFixedHeight(48)
        self.titleBar.vBoxLayout.insertStretch(0, 1)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        # 内容容器
        self._content_widget = QWidget(self)
        self._content_widget.setObjectName("dialogContent")

        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(20, 16, 20, 12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self._content_widget)

        self._apply_content_style()
        qconfig.themeChanged.connect(self._apply_content_style)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)

        self.add_btn = PrimaryPushButton("添加账户", self, FluentIcon.ADD)
        self.add_btn.clicked.connect(self._add_account)
        toolbar.addWidget(self.add_btn)

        content_layout.addLayout(toolbar)

        # ── 卡片滚动区 ──
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.scroll_widget)
        self.cards_layout.setContentsMargins(0, 8, 0, 8)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch(1)

        self.scroll_area.setWidget(self.scroll_widget)
        content_layout.addWidget(self.scroll_area, 1)

    def _load_accounts(self) -> None:
        """从配置文件加载账户列表"""
        config = load_config()
        accounts = get_accounts(config)

        for env_key, data in accounts.items():
            self._create_card(env_key, data)

    def _create_card(self, env_key: str, account_data: dict) -> AccountCard:
        """创建并添加一张账户卡片"""
        card = AccountCard(env_key, account_data, self.scroll_widget)
        card.delete_requested.connect(self._remove_account)
        card.market_source_clicked.connect(self._on_market_source_changed)

        # 插入到 stretch 之前
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self.cards[env_key] = card
        return card

    def _add_account(self) -> None:
        """添加账户"""
        existing = list(self.cards.keys())
        dialog = AccountAddDialog(existing, self)
        if dialog.exec():
            env_key = dialog.env_key
            account_data = new_account()
            # 将环境名预填到名称字段
            account_data["名称"] = env_key

            # 保存到配置
            config = load_config()
            accounts = get_accounts(config)
            accounts[env_key] = account_data

            # 如果是第一个账户，设为默认环境
            if len(accounts) == 1:
                config["默认环境"] = env_key

            save_config(config)

            # 创建卡片
            card = self._create_card(env_key, account_data)
            # 自动展开编辑
            card._toggle_expand()

    def _remove_account(self, env_key: str) -> None:
        """删除账户"""
        card = self.cards.get(env_key)
        if not card:
            return

        config = load_config()
        accounts = get_accounts(config)
        display_name = get_display_name(env_key, accounts.get(env_key, {}))

        box = MessageBox(
            "删除确认",
            f"确定删除账户「{display_name}」？",
            self,
        )
        if not box.exec():
            return

        # 如果已连接，先断开
        app = AppEngine.instance()
        if app.is_connected(env_key):
            app.disconnect(env_key)

        # 从布局移除
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        self.cards.pop(env_key)

        # 从配置移除
        accounts.pop(env_key, None)
        if get_default_env(config) == env_key:
            config["默认环境"] = next(iter(accounts), "")
        save_config(config)

        # 如果只剩一个账户且无行情服务，自动设为行情服务
        if len(self.cards) == 1:
            remaining_key = next(iter(self.cards))
            remaining_card = self.cards[remaining_key]
            if not remaining_card.market_radio.isChecked():
                self._on_market_source_changed(remaining_key)

    def _on_market_source_changed(self, env_key: str) -> None:
        """行情服务选择变更（互斥）"""
        config = load_config()
        accounts = get_accounts(config)

        for key, card in self.cards.items():
            enabled = (key == env_key)
            card.set_market_source(enabled)
            if key in accounts:
                set_market_source(accounts[key], enabled)

        save_config(config)

    def _apply_content_style(self) -> None:
        """应用内容区域样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, [
            "common.qss", "window.qss",
        ], theme)

    # closeEvent 由 CursorFixMixin 提供（隐藏窗口 + 重置按钮状态）
