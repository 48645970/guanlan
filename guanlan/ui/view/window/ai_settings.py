# -*- coding: utf-8 -*-
"""
观澜量化 - AI 配置管理窗口

卡片式布局，支持模型增删改查、设置默认模型。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
)

from qfluentwidgets import (
    SubtitleLabel, StrongBodyLabel, BodyLabel,
    LineEdit, SpinBox, DoubleSpinBox, CheckBox, RadioButton,
    PushButton, PrimaryPushButton, ToolButton, TransparentToolButton,
    CardWidget, MessageBox, MessageBoxBase,
    SmoothScrollArea,
    InfoBar, InfoBarPosition,
    FluentIcon, FluentWidget,
    isDarkTheme, qconfig,
)

from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.core.services.ai import get_config, ModelConfig


# 交互控件类型（点击时不触发折叠）
_INTERACTIVE_TYPES = (
    PushButton, PrimaryPushButton, ToolButton,
    CheckBox, LineEdit, SpinBox, DoubleSpinBox,
)


class ModelAddDialog(MessageBoxBase):
    """添加模型对话框"""

    def __init__(self, existing_names: list[str], parent=None):
        super().__init__(parent)

        self.existing_names = existing_names
        self.model_name: str = ""

        self.titleLabel = SubtitleLabel("添加模型", self)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("输入模型名称，如：deepseek-chat")
        self.name_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self.name_edit)

        self.yesButton.setText("添加")
        self.cancelButton.setText("取消")
        self.widget.setMinimumWidth(400)

    def validate(self) -> bool:
        """验证输入（基类 MessageBoxBase 在确认时自动调用）"""
        name = self.name_edit.text().strip()
        if not name:
            InfoBar.error(
                title="输入错误",
                content="模型名称不能为空",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return False
        if name in self.existing_names:
            InfoBar.error(
                title="输入错误",
                content=f"模型名称「{name}」已存在",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return False

        self.model_name = name
        return True


class AIModelCard(CardWidget):
    """AI 模型卡片

    显示模型摘要信息，点击展开/收起编辑表单。
    """

    def __init__(self, model_name: str, is_default: bool, parent=None):
        super().__init__(parent)

        self.model_name = model_name
        self._is_default = is_default
        self._expanded = False

        self._init_ui()
        self._connect_signals()
        self._load_form_data()

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

        # 模型名称
        self.name_label = StrongBodyLabel(self.model_name, self)
        self.name_label.setMinimumWidth(120)
        summary.addWidget(self.name_label)

        summary.addStretch(1)

        # 默认模型单选框
        self.default_radio = RadioButton("默认模型", self)
        self.default_radio.setChecked(self._is_default)
        summary.addWidget(self.default_radio)

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
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        # API Base
        self.api_base_edit = LineEdit(self.form_widget)
        self.api_base_edit.setPlaceholderText("https://api.deepseek.com/v1")
        self.api_base_edit.setMinimumWidth(300)
        form.addRow(BodyLabel("API Base", self.form_widget), self.api_base_edit)

        # API Key
        self.api_key_edit = LineEdit(self.form_widget)
        self.api_key_edit.setPlaceholderText("sk-...")
        self.api_key_edit.setEchoMode(LineEdit.EchoMode.Password)
        self.api_key_edit.setMinimumWidth(300)
        form.addRow(BodyLabel("API Key", self.form_widget), self.api_key_edit)

        # 模型 ID
        self.model_id_edit = LineEdit(self.form_widget)
        self.model_id_edit.setPlaceholderText("deepseek-chat")
        self.model_id_edit.setMinimumWidth(300)
        form.addRow(BodyLabel("模型 ID", self.form_widget), self.model_id_edit)

        # Max Tokens
        self.max_tokens_spin = SpinBox(self.form_widget)
        self.max_tokens_spin.setRange(1, 32768)
        self.max_tokens_spin.setValue(4096)
        self.max_tokens_spin.setMinimumWidth(150)
        form.addRow(BodyLabel("Max Tokens", self.form_widget), self.max_tokens_spin)

        # Temperature
        self.temperature_spin = DoubleSpinBox(self.form_widget)
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setDecimals(1)
        self.temperature_spin.setMinimumWidth(150)
        form.addRow(BodyLabel("Temperature", self.form_widget), self.temperature_spin)

        # 支持图片
        self.supports_vision_check = CheckBox("支持图片输入", self.form_widget)
        form.addRow(BodyLabel("能力", self.form_widget), self.supports_vision_check)

        form_layout.addLayout(form)

        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.save_btn = PrimaryPushButton("保存", self.form_widget)
        self.save_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        form_layout.addLayout(btn_layout)

        self.main_layout.addWidget(self.form_widget)

    def _load_form_data(self) -> None:
        """加载模型配置到表单"""
        try:
            config = get_config()
            model_config = config.get_model_config(self.model_name)

            self.api_base_edit.setText(model_config.api_base)
            self.api_key_edit.setText(model_config.api_key)
            self.model_id_edit.setText(model_config.model)
            self.max_tokens_spin.setValue(model_config.max_tokens)
            self.temperature_spin.setValue(model_config.temperature)
            self.supports_vision_check.setChecked(model_config.supports_vision)
        except Exception:
            # 新建模型，使用默认值
            pass

    def _collect_form_data(self) -> ModelConfig:
        """从表单收集数据"""
        return ModelConfig(
            api_base=self.api_base_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model=self.model_id_edit.text().strip(),
            max_tokens=self.max_tokens_spin.value(),
            temperature=self.temperature_spin.value(),
            supports_vision=self.supports_vision_check.isChecked(),
        )

    def _connect_signals(self) -> None:
        """连接信号"""
        self.save_btn.clicked.connect(self._on_save)

    def _toggle_expand(self) -> None:
        """展开/收起编辑表单"""
        self._expanded = not self._expanded

        # 旋转箭头图标
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

    def _on_save(self) -> None:
        """保存编辑"""
        model_config = self._collect_form_data()

        # 验证必填字段
        if not model_config.api_base:
            InfoBar.error(
                title="保存失败",
                content="API Base 不能为空",
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
            return
        if not model_config.api_key:
            InfoBar.error(
                title="保存失败",
                content="API Key 不能为空",
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
            return
        if not model_config.model:
            InfoBar.error(
                title="保存失败",
                content="模型 ID 不能为空",
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
            return

        # 保存配置
        try:
            config = get_config()
            config.add_model(self.model_name, model_config)
            config.save()

            InfoBar.success(
                title="保存成功",
                content=f"模型「{self.model_name}」配置已保存",
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
        except Exception as e:
            InfoBar.error(
                title="保存失败",
                content=str(e),
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

    def set_default(self, is_default: bool) -> None:
        """设置默认状态"""
        self._is_default = is_default
        self.default_radio.setChecked(is_default)


class AISettingsWindow(CursorFixMixin, FluentWidget):
    """AI 配置管理窗口"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.cards: dict[str, AIModelCard] = {}

        self._init_ui()
        self._load_models()

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("AI 配置")
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

        self.add_btn = PrimaryPushButton("添加模型", self, FluentIcon.ADD)
        self.add_btn.clicked.connect(self._add_model)
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

    def _load_models(self) -> None:
        """从配置文件加载模型列表"""
        config = get_config()
        models = config.list_models()
        default_model = config.default_model

        for model_name in models:
            is_default = (model_name == default_model)
            self._create_card(model_name, is_default)

    def _create_card(self, model_name: str, is_default: bool) -> AIModelCard:
        """创建并添加一张模型卡片"""
        card = AIModelCard(model_name, is_default, self.scroll_widget)
        card.delete_btn.clicked.connect(lambda: self._remove_model(model_name))
        card.default_radio.clicked.connect(lambda: self._set_default_model(model_name))

        # 插入到 stretch 之前
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
        self.cards[model_name] = card
        return card

    def _add_model(self) -> None:
        """添加模型"""
        existing = list(self.cards.keys())
        dialog = ModelAddDialog(existing, self)
        if dialog.exec():
            model_name = dialog.model_name

            # 判断是否为第一个模型
            config = get_config()
            is_first = len(config.list_models()) == 0

            # 创建默认配置并保存
            default_config = ModelConfig(
                api_base="https://api.example.com/v1",
                api_key="",
                model=model_name,
                max_tokens=4096,
                temperature=0.7,
                supports_vision=False,
            )
            config.add_model(model_name, default_config)

            # 如果是第一个模型，设为默认
            if is_first:
                config.default_model = model_name

            config.save()

            # 创建卡片
            card = self._create_card(model_name, is_default=is_first)
            # 自动展开编辑
            card._toggle_expand()

            # 刷新首页 AI 面板模型列表
            self._refresh_ai_chat_models()

    def _remove_model(self, model_name: str) -> None:
        """删除模型"""
        card = self.cards.get(model_name)
        if not card:
            return

        box = MessageBox(
            "删除确认",
            f"确定删除模型「{model_name}」？",
            self,
        )
        if not box.exec():
            return

        # 从布局移除
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        self.cards.pop(model_name)

        # 从配置移除
        config = get_config()
        config.remove_model(model_name)

        # 如果删除的是默认模型，选择第一个作为默认
        if config.default_model == model_name:
            remaining = config.list_models()
            if remaining:
                new_default = remaining[0]
                config.default_model = new_default
                if new_default in self.cards:
                    self.cards[new_default].set_default(True)

        config.save()

        # 刷新首页 AI 面板模型列表
        self._refresh_ai_chat_models()

    def _set_default_model(self, model_name: str) -> None:
        """设置默认模型"""
        config = get_config()
        config.default_model = model_name
        config.save()

        # 更新所有卡片的默认状态
        for name, card in self.cards.items():
            card.set_default(name == model_name)

        InfoBar.success(
            title="设置成功",
            content=f"已将「{model_name}」设为默认模型",
            duration=3000,
            position=InfoBarPosition.TOP,
            parent=self,
        )

    def _refresh_ai_chat_models(self) -> None:
        """刷新首页 AI 聊天面板的模型列表"""
        try:
            from guanlan.core.events import signal_bus
            signal_bus.ai_models_changed.emit()
        except Exception:
            # 如果信号总线未定义该信号，忽略
            pass

    def _apply_content_style(self) -> None:
        """应用内容区域样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, [
            "common.qss", "window.qss",
        ], theme)
