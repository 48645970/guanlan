# -*- coding: utf-8 -*-
"""
观澜量化 - 风控管理对话框

Author: 海山观澜
"""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFormLayout, QHBoxLayout, QStackedWidget

from qfluentwidgets import (
    SubtitleLabel, BodyLabel,
    SpinBox, DoubleSpinBox, SwitchButton, ListWidget,
    InfoBar, InfoBarPosition
)

from guanlan.ui.widgets import ThemedDialog

from guanlan.core.setting.risk import RISK_RULES, SETTING_FILENAME
from guanlan.core.utils.common import load_json_file, save_json_file


class RuleTab(QWidget):
    """单个风控规则的标签页"""

    def __init__(
        self,
        rule_fields: dict[str, tuple[str, Any]],
        saved_values: dict[str, Any],
        parent=None
    ):
        super().__init__(parent)

        self.widgets: dict[str, tuple[QWidget, type]] = {}

        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        for field_name, (display_name, default_value) in rule_fields.items():
            value = saved_values.get(field_name, default_value)
            value_type = type(default_value)

            if value_type is bool:
                widget = SwitchButton(self)
                widget.setOnText("开")
                widget.setOffText("关")
                widget.setChecked(value)
            elif value_type is float:
                widget = DoubleSpinBox(self)
                widget.setDecimals(2)
                widget.setRange(0, 1_000_000_000)
                widget.setValue(value)
                widget.setMinimumWidth(200)
            elif value_type is int:
                widget = SpinBox(self)
                widget.setRange(0, 1_000_000_000)
                widget.setValue(value)
                widget.setMinimumWidth(200)
            else:
                continue

            label = BodyLabel(display_name, self)
            label.setMinimumWidth(100)
            form.addRow(label, widget)
            self.widgets[field_name] = (widget, value_type)

    def get_setting(self) -> dict[str, Any]:
        """收集当前参数值"""
        setting: dict[str, Any] = {}

        for field_name, (widget, value_type) in self.widgets.items():
            if value_type is bool:
                setting[field_name] = widget.isChecked()
            elif value_type is float:
                setting[field_name] = widget.value()
            elif value_type is int:
                setting[field_name] = widget.value()

        return setting


class RiskManagerDialog(ThemedDialog):
    """风控管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.rule_tabs: dict[str, RuleTab] = {}

        self._init_content()
        self._init_buttons()
        self._init_theme(self.stacked_widget)

    def _init_content(self) -> None:
        """初始化对话框内容"""
        # 标题
        title_label = SubtitleLabel("风控管理", self)
        self.viewLayout.addWidget(title_label)

        # 读取已保存的配置
        saved_settings: dict = load_json_file(SETTING_FILENAME)

        # 左侧规则列表 + 右侧参数面板
        self.rule_list = ListWidget(self)
        self.stacked_widget = QStackedWidget(self)

        for rule_name, rule_fields in RISK_RULES.items():
            saved_values = saved_settings.get(rule_name, {})
            tab = RuleTab(rule_fields, saved_values, self)

            self.stacked_widget.addWidget(tab)
            self.rule_tabs[rule_name] = tab
            self.rule_list.addItem(rule_name)

        self.rule_list.currentRowChanged.connect(
            self.stacked_widget.setCurrentIndex
        )
        self.rule_list.setCurrentRow(0)
        self.rule_list.setFixedWidth(120)

        # 水平布局：列表 | 参数
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.addWidget(self.rule_list)
        content_layout.addWidget(self.stacked_widget, 1)

        self.viewLayout.addLayout(content_layout)
        self.stacked_widget.setMinimumHeight(300)
        self.stacked_widget.setObjectName("contentPanel")

    def _init_buttons(self) -> None:
        """汉化按钮文本"""
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

    def _save_settings(self) -> None:
        """保存所有规则配置"""
        settings: dict[str, dict[str, Any]] = {}

        for rule_name, tab in self.rule_tabs.items():
            settings[rule_name] = tab.get_setting()

        save_json_file(SETTING_FILENAME, settings)

    def _sync_to_engine(self) -> None:
        """将新参数同步到运行中的风控引擎"""
        try:
            from guanlan.core.app import AppEngine
            risk_engine = AppEngine.instance().main_engine.get_engine("RiskManager")
            if not risk_engine:
                return

            for rule_name, tab in self.rule_tabs.items():
                if rule_name in risk_engine.rules:
                    risk_engine.update_rule_setting(rule_name, tab.get_setting())
        except Exception:
            pass

    def accept(self) -> None:
        """保存按钮回调"""
        self._save_settings()
        self._sync_to_engine()

        InfoBar.success(
            "保存成功",
            "风控参数已生效",
            duration=4000,
            position=InfoBarPosition.TOP,
            parent=self.parent()
        )

        super().accept()
