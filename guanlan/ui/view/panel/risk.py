# -*- coding: utf-8 -*-
"""
观澜量化 - 风控监控面板

嵌入首页中间区域右侧，按规则类型分 TAB 实时显示参数和变量。
数据由 EVENT_RISK_RULE 事件驱动更新。
支持多账户：通过 ComboBox 切换查看汇总或单账户风控数据。

Author: 海山观澜
"""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QHeaderView, QTableWidgetItem,
)

from qfluentwidgets import ListWidget, TableWidget, ComboBox

from guanlan.core.trader.event import Event, EventEngine
from vnpy_riskmanager.base import EVENT_RISK_RULE


class RuleTab(TableWidget):
    """单个规则的监控表格

    自动检测 _limit / _count 配对：
    - 有配对：三列（名称 / 上限 / 当前），limit 和 count 合并为一行
    - 无配对：两列（名称 / 值）
    """

    def __init__(self, risk_engine, rule_data: dict, parent=None) -> None:
        super().__init__(parent)

        self._risk_engine = risk_engine
        self._cells: dict[str, QTableWidgetItem] = {}

        self._init_table(rule_data)

    def _init_table(self, data: dict) -> None:
        self.setBorderVisible(False)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)

        params = data.get("parameters", {})
        variables = data.get("variables", {})
        field_names = self._risk_engine.field_name_map if self._risk_engine else {}

        # 检测 _limit / _count 配对
        pairs: list[tuple[str, str, str]] = []  # (base_display, limit_key, count_key)
        paired_keys: set[str] = set()

        for p_key in params:
            if p_key.endswith("_limit"):
                prefix = p_key[:-6]  # 去掉 _limit
                v_key = prefix + "_count"
                if v_key in variables:
                    # 从显示名中去掉"上限"得到基础名
                    display = field_names.get(p_key, p_key)
                    base = display.replace("上限", "")
                    pairs.append((base, p_key, v_key))
                    paired_keys.add(p_key)
                    paired_keys.add(v_key)

        if pairs:
            self._init_paired(pairs, params, variables, paired_keys, field_names)
        else:
            self._init_flat(params, variables, field_names)

        # 列宽：前面列固定初始宽度 + Interactive，最后一列拉伸
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        last = self.columnCount() - 1
        header.setSectionResizeMode(last, QHeaderView.ResizeMode.Stretch)
        for col in range(last):
            header.resizeSection(col, 100)

    def _init_paired(
        self,
        pairs: list[tuple[str, str, str]],
        params: dict, variables: dict,
        paired_keys: set[str],
        field_names: dict,
    ) -> None:
        """配对模式：三列表格（名称 / 上限 / 当前）"""
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["名称", "上限", "当前"])

        row = 0

        # 未配对的参数（如 active）
        for key, value in params.items():
            if key in paired_keys:
                continue
            display = field_names.get(key, key)
            self.insertRow(row)
            self._set_row_2col(row, display, value, key)
            row += 1

        # 配对行
        for base, limit_key, count_key in pairs:
            self.insertRow(row)

            name_item = QTableWidgetItem(base)
            name_item.setTextAlignment(Qt.AlignCenter)

            limit_item = QTableWidgetItem(self._format(params[limit_key]))
            limit_item.setTextAlignment(Qt.AlignCenter)

            count_item = QTableWidgetItem(self._format(variables[count_key]))
            count_item.setTextAlignment(Qt.AlignCenter)

            self.setItem(row, 0, name_item)
            self.setItem(row, 1, limit_item)
            self.setItem(row, 2, count_item)
            self._cells[limit_key] = limit_item
            self._cells[count_key] = count_item
            row += 1

        # 未配对的变量
        for key, value in variables.items():
            if key in paired_keys:
                continue
            display = field_names.get(key, key)
            self.insertRow(row)
            self._set_row_2col(row, display, value, key)
            row += 1

    def _init_flat(
        self,
        params: dict, variables: dict,
        field_names: dict,
    ) -> None:
        """普通模式：两列表格（名称 / 值）"""
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["名称", "值"])

        row = 0
        for key, value in params.items():
            display = field_names.get(key, key)
            self.insertRow(row)
            self._set_row_2col(row, display, value, key)
            row += 1

        for key, value in variables.items():
            display = field_names.get(key, key)
            self.insertRow(row)
            self._set_row_2col(row, display, value, key)
            row += 1

    def _set_row_2col(self, row: int, display: str, value: Any, key: str) -> None:
        """填充两列行"""
        name_item = QTableWidgetItem(display)
        name_item.setTextAlignment(Qt.AlignCenter)

        val_item = QTableWidgetItem(self._format(value))
        val_item.setTextAlignment(Qt.AlignCenter)

        self.setItem(row, 0, name_item)
        self.setItem(row, 1, val_item)
        self._cells[key] = val_item

    def update_data(self, data: dict) -> None:
        """更新规则数据"""
        for key, value in data.get("parameters", {}).items():
            cell = self._cells.get(key)
            if cell:
                cell.setText(self._format(value))

        for key, value in data.get("variables", {}).items():
            cell = self._cells.get(key)
            if cell:
                cell.setText(self._format(value))

    @staticmethod
    def _format(value: Any) -> str:
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, float):
            return f"{value:g}"
        if isinstance(value, dict):
            return str(len(value))
        return str(value)


_SUMMARY = "汇总"


class RiskMonitor(QWidget):
    """风控监控面板

    嵌入首页中间区域，SegmentedWidget 分 TAB 显示各规则状态。
    通过 EVENT_RISK_RULE 事件实时更新。
    ComboBox 支持切换查看汇总或单账户风控数据。
    """

    _signal_rule = Signal(Event)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._tabs: dict[str, RuleTab] = {}
        self._rule_data_cache: dict[str, dict] = {}
        self._known_gateways: set[str] = set()

        self._init_ui()
        self._init_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 账户选择器
        self._gateway_combo = ComboBox(self)
        self._gateway_combo.setFixedWidth(120)
        self._gateway_combo.addItem(_SUMMARY)
        self._gateway_combo.currentTextChanged.connect(self._on_gateway_changed)
        layout.addWidget(self._gateway_combo)

        # 左侧规则列表 + 右侧内容
        content = QHBoxLayout()
        content.setSpacing(4)

        self._rule_list = ListWidget(self)
        self._rule_list.setFixedWidth(120)
        content.addWidget(self._rule_list)

        self._stacked = QStackedWidget(self)
        content.addWidget(self._stacked, 1)

        layout.addLayout(content, 1)

    def _init_data(self) -> None:
        """从风控引擎读取规则数据并创建 TAB"""
        from guanlan.core.app import AppEngine
        risk_engine = AppEngine.instance().main_engine.get_engine("RiskManager")
        if not risk_engine:
            return

        for rule_name in risk_engine.get_all_rule_names():
            data = risk_engine.get_rule_data(rule_name)
            tab = RuleTab(risk_engine, data, self)
            self._stacked.addWidget(tab)
            self._rule_list.addItem(rule_name)
            self._tabs[rule_name] = tab
            self._rule_data_cache[rule_name] = data

        self._rule_list.currentRowChanged.connect(
            self._stacked.setCurrentIndex
        )
        if self._tabs:
            self._rule_list.setCurrentRow(0)

        # 注册事件
        self._signal_rule.connect(self._on_rule_event)
        self._rule_handler = self._signal_rule.emit

        event_engine: EventEngine = AppEngine.instance().event_engine
        event_engine.register(EVENT_RISK_RULE, self._rule_handler)

    def _on_rule_event(self, event: Event) -> None:
        """规则数据更新"""
        data: dict = event.data
        rule_name: str = data.get("name", "")

        # 缓存完整数据
        self._rule_data_cache[rule_name] = data

        # 从 per_gateway 发现新账户
        per_gateway: dict | None = data.get("per_gateway")
        if per_gateway:
            new_gws = set(per_gateway.keys()) - self._known_gateways
            if new_gws:
                self._known_gateways.update(new_gws)
                self._update_gateway_combo()

        # 更新表格显示
        tab = self._tabs.get(rule_name)
        if tab:
            display_data = self._extract_display_data(data)
            tab.update_data(display_data)

    def _extract_display_data(self, data: dict) -> dict:
        """根据当前选中账户提取要显示的数据"""
        gateway = self._gateway_combo.currentText()
        if gateway == _SUMMARY:
            return data

        per_gateway: dict | None = data.get("per_gateway")
        if not per_gateway or gateway not in per_gateway:
            return data

        # 用单账户变量覆盖汇总变量
        return {
            "name": data["name"],
            "parameters": data["parameters"],
            "variables": {**data["variables"], **per_gateway[gateway]},
        }

    def _on_gateway_changed(self, _text: str) -> None:
        """账户选择变更，刷新所有规则表格"""
        for rule_name, tab in self._tabs.items():
            data = self._rule_data_cache.get(rule_name)
            if data:
                display_data = self._extract_display_data(data)
                tab.update_data(display_data)

    def _update_gateway_combo(self) -> None:
        """更新账户下拉列表"""
        current = self._gateway_combo.currentText()

        self._gateway_combo.blockSignals(True)
        self._gateway_combo.clear()
        self._gateway_combo.addItem(_SUMMARY)
        for gw in sorted(self._known_gateways):
            self._gateway_combo.addItem(gw)

        # 恢复之前的选中项
        idx = self._gateway_combo.findText(current)
        self._gateway_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._gateway_combo.blockSignals(False)
