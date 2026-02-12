# -*- coding: utf-8 -*-
"""
观澜量化 - 标的查询界面

连接 CTP 后，查询网关返回的所有合约信息，支持按代码/交易所筛选。

Author: 海山观澜
"""

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QTableWidgetItem,
)

from qfluentwidgets import (
    ScrollArea, TableWidget, TitleLabel, CaptionLabel,
    BodyLabel, PrimaryPushButton, LineEdit,
    InfoBar, InfoBarPosition, FluentIcon,
)

from guanlan.ui.common.mixin import ThemeMixin
from guanlan.core.app import AppEngine
from guanlan.core.events import signal_bus


# 表头定义：(ContractData 属性名, 显示名)
HEADERS: list[tuple[str, str]] = [
    ("vt_symbol", "本地代码"),
    ("symbol", "代码"),
    ("exchange", "交易所"),
    ("name", "名称"),
    ("product", "合约分类"),
    ("size", "合约乘数"),
    ("pricetick", "价格跳动"),
    ("min_volume", "最小委托量"),
    ("gateway_name", "交易接口"),
]


class ContractQueryInterface(ThemeMixin, ScrollArea):
    """标的查询界面"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.view = QWidget(self)
        self.main_layout = QVBoxLayout(self.view)

        self._init_toolbar()
        self._init_controls()
        self._init_table()
        self._init_widget()
        self._connect_signals()

        self._update_connection_status()

    def _init_toolbar(self) -> None:
        """初始化标题栏"""
        toolbar = QWidget(self)
        toolbar.setFixedHeight(90)

        layout = QVBoxLayout(toolbar)
        layout.setSpacing(4)
        layout.setContentsMargins(36, 22, 36, 8)

        # 标题行
        title_row = QHBoxLayout()
        self.title_label = TitleLabel("标的查询", toolbar)

        title_row.addWidget(self.title_label)
        title_row.addStretch(1)

        # 副标题
        self.subtitle_label = CaptionLabel(
            "查询已连接网关的所有可交易合约", toolbar
        )

        layout.addLayout(title_row)
        layout.addWidget(self.subtitle_label)
        layout.setAlignment(Qt.AlignTop)

        self.toolbar = toolbar

    def _init_controls(self) -> None:
        """初始化筛选控件"""
        self._controls_layout = QHBoxLayout()

        self.filter_line = LineEdit(self.view)
        self.filter_line.setPlaceholderText(
            "输入合约代码或交易所筛选，留空查询全部"
        )
        self.filter_line.setClearButtonEnabled(True)
        self.filter_line.returnPressed.connect(self._query_contracts)

        self.query_button = PrimaryPushButton(
            "查询", self.view, FluentIcon.SEARCH
        )
        self.query_button.setFixedSize(100, 33)
        self.query_button.clicked.connect(self._query_contracts)

        self.count_label = BodyLabel("", self.view)

        self._controls_layout.addWidget(self.filter_line, 1)
        self._controls_layout.addSpacing(12)
        self._controls_layout.addWidget(self.query_button)
        self._controls_layout.addSpacing(12)
        self._controls_layout.addWidget(self.count_label)

    def _init_table(self) -> None:
        """初始化合约表格"""
        labels = [h[1] for h in HEADERS]

        self.table = TableWidget(self.view)
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setBorderVisible(False)
        self.table.verticalHeader().hide()
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            TableWidget.SelectionBehavior.SelectRows
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        # 名称列自动拉伸
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

    def _init_widget(self) -> None:
        """初始化界面"""
        self.view.setObjectName("view")
        self.setObjectName("contractQueryInterface")

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, self.toolbar.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.main_layout.setSpacing(12)
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_layout.setContentsMargins(36, 20, 36, 36)
        self.main_layout.addLayout(self._controls_layout)
        self.main_layout.addWidget(self.table, 1)

        self._init_theme()

    # ── 信号连接 ─────────────────────────────────────────

    def _connect_signals(self) -> None:
        """连接信号槽"""
        signal_bus.account_connected.connect(self._on_account_connected)
        signal_bus.account_disconnected.connect(self._on_account_disconnected)

    def _on_account_connected(self, env_name: str) -> None:
        """账户连接成功"""
        self._update_connection_status()

    def _on_account_disconnected(self, env_name: str) -> None:
        """账户断开连接"""
        self._update_connection_status()
        if not AppEngine.instance().is_connected():
            self.table.setRowCount(0)
            self.count_label.setText("")

    def _update_connection_status(self) -> None:
        """更新连接状态"""
        app = AppEngine.instance()
        if app.is_connected():
            self.query_button.setEnabled(True)
        else:
            self.query_button.setEnabled(False)

    # ── 查询逻辑 ─────────────────────────────────────────

    def _query_contracts(self) -> None:
        """查询并显示合约"""
        app = AppEngine.instance()
        if not app.is_connected():
            InfoBar.warning(
                title="提示",
                content="请先连接CTP账户",
                position=InfoBarPosition.TOP,
                duration=3000, parent=self,
            )
            return

        flt = self.filter_line.text().strip().upper()
        all_contracts = app.main_engine.get_all_contracts()

        if flt:
            contracts = [
                c for c in all_contracts
                if flt in c.vt_symbol.upper()
                or flt in c.name
            ]
        else:
            contracts = all_contracts

        # 按本地代码排序
        contracts.sort(key=lambda c: c.vt_symbol)

        # 填充表格（暂停排序避免闪烁）
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(contracts))

        for row, contract in enumerate(contracts):
            for col, (attr, _) in enumerate(HEADERS):
                value = getattr(contract, attr, "")

                if value is None or value == 0:
                    text = ""
                elif isinstance(value, Enum):
                    text = value.value
                elif isinstance(value, float):
                    text = str(value) if value != int(value) else str(int(value))
                else:
                    text = str(value)

                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)

        self.count_label.setText(
            f"共 {len(contracts)} 个合约"
            + (f"（筛选自 {len(all_contracts)} 个）" if flt else "")
        )

    # ── 生命周期 ────────────────────────────────────────

    def resizeEvent(self, e) -> None:
        """调整标题栏宽度"""
        super().resizeEvent(e)
        self.toolbar.resize(self.width(), self.toolbar.height())
