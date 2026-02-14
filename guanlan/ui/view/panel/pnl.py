# -*- coding: utf-8 -*-
"""
观澜量化 - 盈亏监控面板

按策略组合 × 合约 × 账户维度展示实时盈亏。
嵌入首页右栏 TAB，数据由 PortfolioEngine 推送。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTreeWidgetItem,
)

from qfluentwidgets import TreeWidget, ComboBox, BodyLabel, RoundMenu, FluentIcon, MessageBox

from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.pnl.engine import EVENT_PM_CONTRACT, EVENT_PM_PORTFOLIO
from guanlan.ui.widgets.components.button import DangerPushButton


def _long_color():
    from . import long_color
    return long_color()


def _short_color():
    from . import short_color
    return short_color()


class PortfolioMonitor(QWidget):
    """盈亏监控面板（TreeWidget）"""

    _signal_contract = Signal(Event)
    _signal_portfolio = Signal(Event)

    _TREE_LABELS = [
        "组合名称", "账户", "合约代码", "开盘仓位", "当前仓位",
        "交易盈亏", "持仓盈亏", "总盈亏", "手续费", "多头成交", "空头成交",
    ]

    _FILTER_FIELDS = [
        ("reference", "组合"),
        ("gateway_name", "账户"),
        ("vt_symbol", "代码"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._contract_items: dict[tuple[str, str, str], QTreeWidgetItem] = {}
        self._portfolio_items: dict[tuple[str, str], QTreeWidgetItem] = {}
        self._combos: dict[str, ComboBox] = {}

        self._init_ui()
        self._register_events()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 过滤工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 2, 0, 2)
        for field, display in self._FILTER_FIELDS:
            toolbar.addWidget(BodyLabel(f"{display}:", self))
            combo = ComboBox(self)
            combo.addItem("全部")
            combo.setFixedWidth(120)
            combo.setFixedHeight(28)
            combo.currentTextChanged.connect(self._apply_filters)
            self._combos[field] = combo
            toolbar.addWidget(combo)
        toolbar.addStretch(1)

        clear_btn = DangerPushButton("清空", self)
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        self._tree = TreeWidget(self)
        self._tree.setColumnCount(len(self._TREE_LABELS))
        self._tree.setHeaderLabels(self._TREE_LABELS)
        self._tree.header().setDefaultAlignment(Qt.AlignCenter)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree, 1)

    def _register_events(self) -> None:
        """注册事件（跨线程信号桥接）"""
        from guanlan.core.app import AppEngine
        event_engine: EventEngine = AppEngine.instance().event_engine

        self._signal_contract.connect(self._process_contract_event)
        self._signal_portfolio.connect(self._process_portfolio_event)

        event_engine.register(EVENT_PM_CONTRACT, self._signal_contract.emit)
        event_engine.register(EVENT_PM_PORTFOLIO, self._signal_portfolio.emit)

    # ── 数据展示 ──

    def _get_portfolio_item(self, reference: str, gateway_name: str) -> QTreeWidgetItem:
        """获取或创建组合级 TreeItem"""
        key = (reference, gateway_name)
        item = self._portfolio_items.get(key)
        if not item:
            item = QTreeWidgetItem()
            item.setText(0, reference)
            item.setText(1, gateway_name)
            for i in range(3, len(self._TREE_LABELS)):
                item.setTextAlignment(i, Qt.AlignCenter)

            self._portfolio_items[key] = item
            self._tree.addTopLevelItem(item)

            # 动态更新过滤选项
            self._update_filter_option("reference", reference)
            self._update_filter_option("gateway_name", gateway_name)

        return item

    def _get_contract_item(
        self, reference: str, vt_symbol: str, gateway_name: str
    ) -> QTreeWidgetItem:
        """获取或创建合约级 TreeItem"""
        key = (reference, vt_symbol, gateway_name)
        item = self._contract_items.get(key)
        if not item:
            item = QTreeWidgetItem()
            item.setText(1, gateway_name)
            item.setText(2, vt_symbol)
            for i in range(3, len(self._TREE_LABELS)):
                item.setTextAlignment(i, Qt.AlignCenter)

            self._contract_items[key] = item
            portfolio_item = self._get_portfolio_item(reference, gateway_name)
            portfolio_item.addChild(item)

            # 动态更新过滤选项
            self._update_filter_option("vt_symbol", vt_symbol)

        return item

    def _process_contract_event(self, event: Event) -> None:
        """合约级盈亏更新"""
        data: dict = event.data

        item = self._get_contract_item(data["reference"], data["vt_symbol"], data["gateway_name"])
        item.setText(3, str(data["open_pos"]))
        item.setText(4, str(data["last_pos"]))
        item.setText(5, f'{data["trading_pnl"]:.2f}')
        item.setText(6, f'{data["holding_pnl"]:.2f}')
        item.setText(7, f'{data["total_pnl"]:.2f}')
        item.setText(8, f'{data["commission"]:.2f}')
        item.setText(9, str(data["long_volume"]))
        item.setText(10, str(data["short_volume"]))

        self._update_item_color(item, data)

    def _process_portfolio_event(self, event: Event) -> None:
        """组合级盈亏更新"""
        data: dict = event.data

        item = self._get_portfolio_item(data["reference"], data["gateway_name"])
        item.setText(5, f'{data["trading_pnl"]:.2f}')
        item.setText(6, f'{data["holding_pnl"]:.2f}')
        item.setText(7, f'{data["total_pnl"]:.2f}')
        item.setText(8, f'{data["commission"]:.2f}')

        self._update_item_color(item, data)

    @staticmethod
    def _update_item_color(item: QTreeWidgetItem, data: dict) -> None:
        """根据盈亏正负设置颜色"""
        for col, key in enumerate(
            ["trading_pnl", "holding_pnl", "total_pnl"], start=5
        ):
            pnl = data.get(key, 0)
            if pnl > 0:
                item.setForeground(col, _long_color())
            elif pnl < 0:
                item.setForeground(col, _short_color())

    # ── 过滤 ──

    def _update_filter_option(self, field: str, value: str) -> None:
        """动态添加过滤选项"""
        combo = self._combos.get(field)
        if combo and value and combo.findText(value) < 0:
            combo.addItem(value)

    def _apply_filters(self) -> None:
        """根据过滤条件显示/隐藏顶层节点"""
        ref_filter = self._combos["reference"].currentText()
        gw_filter = self._combos["gateway_name"].currentText()
        sym_filter = self._combos["vt_symbol"].currentText()

        for (reference, gateway_name), item in self._portfolio_items.items():
            # 组合和账户过滤：直接匹配顶层节点
            if ref_filter != "全部" and reference != ref_filter:
                item.setHidden(True)
                continue
            if gw_filter != "全部" and gateway_name != gw_filter:
                item.setHidden(True)
                continue

            # 代码过滤：检查子节点是否有匹配
            if sym_filter != "全部":
                has_match = False
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.text(2) == sym_filter:
                        child.setHidden(False)
                        has_match = True
                    else:
                        child.setHidden(True)
                item.setHidden(not has_match)
            else:
                item.setHidden(False)
                for i in range(item.childCount()):
                    item.child(i).setHidden(False)

    # ── 清空 / 右键菜单 ──

    def _clear_all(self) -> None:
        """清空所有盈亏记录（需确认）"""
        msg = MessageBox("确认清空", "将清空所有盈亏统计记录，是否继续？", self.window())
        if not msg.exec():
            return

        from guanlan.core.app import AppEngine

        engine = AppEngine.instance().main_engine.engines["portfolio"]
        engine.contract_results.clear()
        engine.portfolio_results.clear()
        engine._save_data()

        self._contract_items.clear()
        self._portfolio_items.clear()
        self._tree.clear()

    def _show_context_menu(self, pos) -> None:
        """右键菜单：删除选中记录"""
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = RoundMenu(parent=self._tree)
        menu.addAction(QAction(
            FluentIcon.DELETE.icon(), "删除", self._tree,
            triggered=lambda: self._delete_item(item),
        ))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _delete_item(self, item: QTreeWidgetItem) -> None:
        """删除记录（合约级或组合级）"""
        from guanlan.core.app import AppEngine

        engine = AppEngine.instance().main_engine.engines["portfolio"]
        parent = item.parent()

        if parent is None:
            # 顶层节点（组合）：删除所有子合约
            reference = item.text(0)
            gateway_name = item.text(1)

            for i in range(item.childCount()):
                child = item.child(i)
                vt_symbol = child.text(2)
                self._contract_items.pop((reference, vt_symbol, gateway_name), None)
                engine.contract_results.pop((reference, vt_symbol, gateway_name), None)

            self._portfolio_items.pop((reference, gateway_name), None)
            engine.portfolio_results.pop((reference, gateway_name), None)

            idx = self._tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self._tree.takeTopLevelItem(idx)
        else:
            # 子节点（合约）
            reference = parent.text(0)
            gateway_name = item.text(1)
            vt_symbol = item.text(2)

            self._contract_items.pop((reference, vt_symbol, gateway_name), None)
            engine.contract_results.pop((reference, vt_symbol, gateway_name), None)
            parent.removeChild(item)

            # 父节点无子节点时一并移除
            if parent.childCount() == 0:
                self._portfolio_items.pop((reference, gateway_name), None)
                engine.portfolio_results.pop((reference, gateway_name), None)
                idx = self._tree.indexOfTopLevelItem(parent)
                if idx >= 0:
                    self._tree.takeTopLevelItem(idx)

        engine._save_data()
