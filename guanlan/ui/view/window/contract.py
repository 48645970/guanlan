# -*- coding: utf-8 -*-
"""
观澜量化 - 合约编辑对话框

Author: 海山观澜
"""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout

from qfluentwidgets import (
    SubtitleLabel, BodyLabel, LineEdit, ComboBox,
    DoubleSpinBox, SpinBox
)

from guanlan.ui.widgets import ThemedDialog

from guanlan.core.setting.contract import CONTRACT_FIELDS, EXCHANGES


class ContractEditDialog(ThemedDialog):
    """合约编辑对话框"""

    def __init__(
        self,
        symbol: str = "",
        data: dict[str, Any] | None = None,
        parent=None
    ):
        super().__init__(parent)

        self._is_new = not symbol
        self._symbol = symbol
        self._data = data or {}

        self.widgets: dict[str, LineEdit | ComboBox | DoubleSpinBox | SpinBox] = {}

        self._init_content()
        self._init_buttons()
        self._init_theme(self.form_widget)

        self.widget.setMinimumWidth(500)

    def _init_content(self) -> None:
        """初始化对话框内容"""
        title = "新增合约" if self._is_new else f"编辑合约 - {self._symbol}"
        self.viewLayout.addWidget(SubtitleLabel(title, self))

        self.form_widget = self._create_form()
        self.form_widget.setObjectName("contentPanel")
        self.viewLayout.addWidget(self.form_widget)

    def _create_form(self):
        """创建表单"""
        from PySide6.QtWidgets import QWidget

        form_widget = QWidget(self)
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        for display_name, key, field_type, default in CONTRACT_FIELDS:
            value = self._data.get(key, default)

            # 品种代码：新增时可编辑，编辑时只读
            if key == "symbol":
                widget = LineEdit(form_widget)
                widget.setText(self._symbol)
                widget.setMinimumWidth(200)
                if not self._is_new:
                    widget.setReadOnly(True)

            # 交易所：下拉框
            elif key == "exchange":
                widget = ComboBox(form_widget)
                widget.addItems(EXCHANGES)
                widget.setCurrentText(str(value) if value else EXCHANGES[0])
                widget.setMinimumWidth(200)

            # 浮点数字段
            elif field_type is float:
                widget = DoubleSpinBox(form_widget)
                widget.setRange(0, 999999.0)
                widget.setDecimals(4)
                widget.setValue(float(value) if value else 0.0)
                widget.setMinimumWidth(200)

            # 整数字段
            elif field_type is int:
                widget = SpinBox(form_widget)
                widget.setRange(0, 999999)
                widget.setValue(int(value) if value else 0)
                widget.setMinimumWidth(200)

            # 字符串字段
            else:
                widget = LineEdit(form_widget)
                widget.setText(str(value) if value else "")
                widget.setMinimumWidth(200)

            label = BodyLabel(display_name, form_widget)
            form.addRow(label, widget)
            self.widgets[key] = widget

        return form_widget

    def _init_buttons(self) -> None:
        """汉化按钮文本"""
        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

    def get_result(self) -> tuple[str, dict[str, Any]]:
        """获取编辑结果

        Returns
        -------
        tuple[str, dict]
            (品种代码, 合约数据字典)
        """
        data: dict[str, Any] = {}

        for key, widget in self.widgets.items():
            if key == "symbol":
                continue

            if isinstance(widget, ComboBox):
                data[key] = widget.currentText()
            elif isinstance(widget, DoubleSpinBox):
                data[key] = widget.value()
            elif isinstance(widget, SpinBox):
                data[key] = widget.value()
            else:
                data[key] = widget.text()

        symbol_widget = self.widgets.get("symbol")
        symbol = symbol_widget.text().strip().upper() if symbol_widget else self._symbol

        return symbol, data
