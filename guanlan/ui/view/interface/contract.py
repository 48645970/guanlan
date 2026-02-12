# -*- coding: utf-8 -*-
"""
观澜量化 - 合约管理界面

Author: 海山观澜
"""

from typing import Any

from PySide6.QtCore import Qt, Signal, QObject, QModelIndex
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QTableWidgetItem, QStyleOptionViewItem
)

from qfluentwidgets import (
    ScrollArea, TableWidget, TableItemDelegate, TitleLabel, CaptionLabel,
    PrimaryPushButton, PrimaryToolButton, ToolButton,
    CheckBox, StateToolTip, MessageBox,
    InfoBar, InfoBarPosition, FluentIcon, isDarkTheme
)

from guanlan.ui.common.config import cfg
from guanlan.ui.common import signal_bus
from guanlan.ui.common.mixin import ThemeMixin

from guanlan.core.setting.contract import (
    HEADERS, COLUMNS,
    load_contracts, delete_contract, add_contract, update_contract,
    new_contract, load_favorites, add_favorite, remove_favorite
)
from guanlan.core.services.sina import refresh_all
from guanlan.ui.view.window.contract import ContractEditDialog


class AccentTableDelegate(TableItemDelegate):
    """选中行使用主题强调色的 TableItemDelegate"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipping(True)
        painter.setClipRect(option.rect)

        option.rect.adjust(0, self.margin, 0, -self.margin)

        isHover = self.hoverRow == index.row()
        isPressed = self.pressedRow == index.row()
        isAlternate = (index.row() % 2 == 0
                       and self.parent().alternatingRowColors())
        isDark = isDarkTheme()

        if index.row() in self.selectedRows:
            # 选中行：使用配置的主题色
            accent = QColor(cfg.get(cfg.themeColor))
            if isPressed:
                accent.setAlpha(200)
            elif isHover:
                accent.setAlpha(180)
            else:
                accent.setAlpha(160)
            color = accent
        else:
            # 未选中行：保持原始灰色逻辑
            c = 255 if isDark else 0
            alpha = 0
            if isPressed:
                alpha = 9 if isDark else 6
            elif isHover:
                alpha = 12
            elif isAlternate:
                alpha = 5
            color = QColor(c, c, c, alpha)

        if index.data(Qt.ItemDataRole.BackgroundRole):
            painter.setBrush(index.data(Qt.ItemDataRole.BackgroundRole))
        else:
            painter.setBrush(color)

        self._drawBackground(painter, option, index)

        if (index.row() in self.selectedRows and index.column() == 0
                and self.parent().horizontalScrollBar().value() == 0):
            self._drawIndicator(painter, option, index)

        if index.data(Qt.CheckStateRole) is not None:
            self._drawCheckBox(painter, option, index)

        painter.restore()

        # 调用 QStyledItemDelegate.paint（跳过 TableItemDelegate.paint）
        super(TableItemDelegate, self).paint(painter, option, index)

    def initStyleOption(self, option: QStyleOptionViewItem,
                        index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        # 选中行文字强制白色
        if index.row() in self.selectedRows:
            option.palette.setColor(QPalette.Text, QColor(255, 255, 255))
            option.palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))


class ContractTable(TableWidget):
    """合约数据表格（只读，双击编辑）"""

    # 请求编辑信号：(品种代码)
    edit_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.contracts: dict[str, dict[str, Any]] = {}
        self.favorites: list[str] = []

        # 表格基础配置
        self.verticalHeader().hide()
        self.setBorderRadius(6)
        self.setBorderVisible(True)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)

        # 选中行强调色
        self.setItemDelegate(AccentTableDelegate(self))

        # 双击编辑
        self.doubleClicked.connect(self._on_double_click)

    def load_data(self) -> None:
        """加载合约数据到表格"""
        self.contracts = load_contracts()
        self.favorites = load_favorites()

        self.clear()
        self.setColumnCount(len(HEADERS))
        self.setRowCount(len(self.contracts))
        self.setHorizontalHeaderLabels(HEADERS)

        # 列宽设置
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        for row, (code, data) in enumerate(self.contracts.items()):
            # 第 0 列：收藏勾选框
            check = CheckBox(self)
            check.setFixedSize(30, 30)
            check.setChecked(code in self.favorites)
            check.stateChanged.connect(self._on_favorite_changed)
            self.setCellWidget(row, 0, check)

            # 第 1 列：品种代码
            item = QTableWidgetItem(code)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.setItem(row, 1, item)

            # 第 2-12 列（全部只读）
            for col in range(2, len(COLUMNS)):
                field = COLUMNS[col]
                value = data.get(field, "")
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                # 数字列右对齐
                if isinstance(value, (int, float)):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                self.setItem(row, col, item)

    def get_selected_symbol(self) -> str | None:
        """获取当前选中行的品种代码"""
        row = self.currentRow()
        if row < 0:
            return None
        item = self.item(row, 1)
        return item.text() if item else None

    def _on_double_click(self, index) -> None:
        """双击行打开编辑"""
        symbol_item = self.item(index.row(), 1)
        if symbol_item:
            self.edit_requested.emit(symbol_item.text())

    def _on_favorite_changed(self, state: int) -> None:
        """收藏勾选回调"""
        check = self.sender()
        if check is None:
            return

        row = self.indexAt(check.pos()).row()
        symbol_item = self.item(row, 1)
        if symbol_item is None:
            return

        symbol = symbol_item.text()
        name = self.contracts.get(symbol, {}).get("name", symbol)

        if state == 2:  # Qt.Checked
            add_favorite(self.favorites, symbol)
            InfoBar.success(
                name, "已加入收藏夹",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
        else:
            remove_favorite(self.favorites, symbol)
            InfoBar.info(
                name, "已移出收藏夹",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )


class _RefreshSignal(QObject):
    """线程安全的刷新完成信号"""
    finished = Signal(int, int)


class ContractInterface(ThemeMixin, ScrollArea):
    """合约管理界面"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.view = QWidget(self)
        self.main_layout = QVBoxLayout(self.view)
        self.state_tooltip: StateToolTip | None = None

        # 线程安全信号
        self._refresh_signal = _RefreshSignal(self)
        self._refresh_signal.finished.connect(self._on_refresh_complete)

        self._init_toolbar()
        self._init_table()
        self._init_widget()

        # 连接自动刷新信号
        signal_bus.contract_auto_refresh.connect(self._on_refresh)

    def _init_toolbar(self) -> None:
        """初始化标题栏"""
        toolbar = QWidget(self)
        toolbar.setFixedHeight(90)

        layout = QVBoxLayout(toolbar)
        layout.setSpacing(4)
        layout.setContentsMargins(36, 22, 36, 8)

        # 标题行：标题 + 工具按钮
        title_row = QHBoxLayout()
        self.title_label = TitleLabel("合约管理", toolbar)

        self.add_btn = PrimaryToolButton(FluentIcon.ADD, toolbar)
        self.add_btn.setToolTip("新增合约")
        self.add_btn.clicked.connect(self._on_add)

        self.edit_btn = ToolButton(FluentIcon.EDIT, toolbar)
        self.edit_btn.setToolTip("编辑合约")
        self.edit_btn.clicked.connect(self._on_edit)

        self.del_btn = ToolButton(FluentIcon.DELETE, toolbar)
        self.del_btn.setToolTip("删除合约")
        self.del_btn.clicked.connect(self._on_delete)

        self.refresh_btn = PrimaryPushButton(
            text="手动获取", parent=toolbar, icon=FluentIcon.SYNC
        )
        self.refresh_btn.clicked.connect(self._on_refresh)

        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.add_btn)
        title_row.addWidget(self.edit_btn)
        title_row.addWidget(self.del_btn)
        title_row.addSpacing(12)
        title_row.addWidget(self.refresh_btn)

        # 副标题
        self.subtitle_label = CaptionLabel(
            "交易日08:55自动刷新，也可点击手动刷新主力合约", toolbar
        )

        layout.addLayout(title_row)
        layout.addWidget(self.subtitle_label)
        layout.setAlignment(Qt.AlignTop)

        self.toolbar = toolbar

    def _init_table(self) -> None:
        """初始化表格"""
        self.table = ContractTable(self.view)
        self.table.edit_requested.connect(self._on_edit_symbol)
        self.table.load_data()

    def _init_widget(self) -> None:
        """初始化界面"""
        self.view.setObjectName("view")
        self.setObjectName("contractInterface")

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, self.toolbar.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_layout.setContentsMargins(36, 20, 36, 36)
        self.main_layout.addWidget(self.table)

        self._init_theme()

    def _on_add(self) -> None:
        """新增合约"""
        dialog = ContractEditDialog(parent=self.window())
        if dialog.exec():
            symbol, data = dialog.get_result()
            if not symbol:
                InfoBar.warning("新增失败", "品种代码不能为空", parent=self)
                return
            if add_contract(self.table.contracts, symbol, data):
                self.table.load_data()
                InfoBar.success("新增成功", f"已添加合约 {symbol}", parent=self)
            else:
                InfoBar.warning("新增失败", f"品种 {symbol} 已存在", parent=self)

    def _on_edit(self) -> None:
        """编辑当前选中合约"""
        symbol = self.table.get_selected_symbol()
        if symbol:
            self._on_edit_symbol(symbol)

    def _on_edit_symbol(self, symbol: str) -> None:
        """编辑指定合约"""
        data = self.table.contracts.get(symbol)
        if not data:
            return
        dialog = ContractEditDialog(symbol=symbol, data=data, parent=self.window())
        if dialog.exec():
            _, new_data = dialog.get_result()
            update_contract(self.table.contracts, symbol, new_data)
            self.table.load_data()
            InfoBar.success("编辑成功", f"合约 {symbol} 已更新", parent=self)

    def _on_delete(self) -> None:
        """删除当前选中合约"""
        symbol = self.table.get_selected_symbol()
        if not symbol:
            return
        name = self.table.contracts.get(symbol, {}).get("name", symbol)
        box = MessageBox("删除确认", f"确定删除合约「{name}（{symbol}）」？", self.window())
        if not box.exec():
            return
        if delete_contract(self.table.contracts, symbol):
            self.table.load_data()
            InfoBar.success("删除成功", f"已删除合约 {symbol}", parent=self)

    def _on_refresh(self) -> None:
        """手动获取主力合约"""
        self.refresh_btn.setEnabled(False)

        self.state_tooltip = StateToolTip(
            "主力合约刷新",
            "正在从外部刷新主力合约数据，请稍候",
            self.window()
        )
        self.state_tooltip.move(self.state_tooltip.getSuitablePos())
        self.state_tooltip.show()

        refresh_all(self.table.contracts, self._refresh_signal.finished.emit)

    def _on_refresh_complete(self, total: int, errors: int) -> None:
        """刷新完成回调"""
        if self.state_tooltip:
            self.state_tooltip.setContent(
                f"刷新完成，总计: {total}，成功: {total - errors}"
            )
            self.state_tooltip.setState(True)
            self.state_tooltip = None

        self.refresh_btn.setEnabled(True)
        self.table.load_data()

    def resizeEvent(self, e) -> None:
        """调整标题栏宽度"""
        super().resizeEvent(e)
        self.toolbar.resize(self.width(), self.toolbar.height())
