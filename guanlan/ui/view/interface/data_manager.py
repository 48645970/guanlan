# -*- coding: utf-8 -*-
"""
观澜量化 - 数据管理界面

Author: 海山观澜
"""

from datetime import datetime, timedelta
from functools import partial

from PySide6.QtCore import Qt, QDate, QSize, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QTreeWidgetItem, QFileDialog,
    QTableWidgetItem,
)

from qfluentwidgets import (
    ScrollArea, TitleLabel, CaptionLabel,
    SubtitleLabel, BodyLabel,
    PushButton, PrimaryPushButton,
    PrimaryDropDownPushButton, RoundMenu, Action,
    TreeWidget, TableWidget, DateEdit,
    InfoBar, InfoBarPosition,
    MessageBox, StateToolTip,
    FluentIcon,
)

from guanlan.ui.common.mixin import ThemeMixin
from guanlan.ui.widgets import ThemedDialog
from guanlan.core.trader.data import DataManagerEngine
from guanlan.core.constants import Interval, Exchange
from guanlan.core.events.signal_bus import signal_bus
from guanlan.core.setting.contract import load_contracts
from guanlan.core.utils.symbol_converter import SymbolConverter

# 周期名称映射
INTERVAL_NAME_MAP: dict[Interval, str] = {
    Interval.MINUTE: "分钟线",
    Interval.HOUR: "小时线",
    Interval.DAILY: "日线",
}


# ────────────────────────────────────────────────────────────
# 工作线程
# ────────────────────────────────────────────────────────────

class TdxImportThread(QThread):
    """通达信导入工作线程"""

    progress = Signal(str, bool)  # (消息, 是否完成)

    def __init__(
        self,
        engine: DataManagerEngine,
        folder: str,
        interval: Interval,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.folder = folder
        self.interval = interval

    def run(self) -> None:
        self.engine.import_tdx_folder(
            self.folder, self.interval, self.progress.emit
        )


class AkShareImportThread(QThread):
    """AKShare 数据导入工作线程"""

    progress = Signal(str, bool)  # (消息, 是否完成)

    def __init__(
        self,
        engine: DataManagerEngine,
        interval: Interval | None = None,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.interval = interval

    def run(self) -> None:
        if self.interval is None:
            # 一键下载全周期
            self.engine.download_akshare_all(self.progress.emit)
        else:
            self.engine.download_akshare_favorites(
                self.interval, self.progress.emit
            )


# ────────────────────────────────────────────────────────────
# 子对话框
# ────────────────────────────────────────────────────────────

class DateRangeDialog(ThemedDialog):
    """日期范围选择对话框"""

    def __init__(self, start: datetime, end: datetime, parent=None) -> None:
        super().__init__(parent)

        self.viewLayout.addWidget(SubtitleLabel("选择数据区间", self))

        self.start_edit = DateEdit(self)
        self.start_edit.setDate(QDate(start.year, start.month, start.day))
        self.viewLayout.addWidget(self.start_edit)

        self.end_edit = DateEdit(self)
        self.end_edit.setDate(QDate(end.year, end.month, end.day))
        self.viewLayout.addWidget(self.end_edit)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

    def get_date_range(self) -> tuple[datetime, datetime]:
        """获取选中的日期范围"""
        start = self.start_edit.dateTime().toPython()
        end = self.end_edit.dateTime().toPython() + timedelta(days=1)
        return start, end


# ────────────────────────────────────────────────────────────
# 主界面
# ────────────────────────────────────────────────────────────

class DataManagerInterface(ThemeMixin, ScrollArea):
    """数据管理界面"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.engine = DataManagerEngine()
        self._import_thread: TdxImportThread | AkShareImportThread | None = None
        self._state_tooltip: StateToolTip | None = None
        self._loaded = False

        self.view = QWidget(self)
        self.main_layout = QVBoxLayout(self.view)

        self._init_toolbar()
        self._init_tree()
        self._init_table()
        self._init_widget()

    def _init_toolbar(self) -> None:
        """初始化标题栏"""
        toolbar = QWidget(self)
        toolbar.setFixedHeight(90)

        layout = QVBoxLayout(toolbar)
        layout.setSpacing(4)
        layout.setContentsMargins(36, 22, 36, 8)

        # 标题行：标题 + 工具按钮
        title_row = QHBoxLayout()
        self.title_label = TitleLabel("数据管理", toolbar)

        # 导入按钮（下拉菜单）
        self.import_button = PrimaryDropDownPushButton(
            "导入数据", toolbar, FluentIcon.SAVE_COPY
        )
        import_menu = RoundMenu(parent=toolbar)
        tdx_menu = RoundMenu("通达信", toolbar)
        self._import_daily_action = Action(FluentIcon.DATE_TIME, "日线数据")
        self._import_minute_action = Action(FluentIcon.DATE_TIME, "分钟数据")
        tdx_menu.addActions([self._import_daily_action, self._import_minute_action])
        import_menu.addMenu(tdx_menu)

        akshare_menu = RoundMenu("AKShare", toolbar)
        self._import_akshare_all_action = Action(FluentIcon.SYNC, "一键下载（收藏品种）")
        akshare_menu.addAction(self._import_akshare_all_action)
        akshare_menu.addSeparator()
        self._import_akshare_daily_action = Action(FluentIcon.DOWNLOAD, "日线数据")
        self._import_akshare_hour_action = Action(FluentIcon.DOWNLOAD, "小时数据")
        self._import_akshare_minute_action = Action(FluentIcon.DOWNLOAD, "1分钟数据")
        akshare_menu.addActions([
            self._import_akshare_daily_action,
            self._import_akshare_hour_action,
            self._import_akshare_minute_action,
        ])
        import_menu.addMenu(akshare_menu)

        self.import_button.setMenu(import_menu)

        self._import_daily_action.triggered.connect(
            lambda: self._import_tdx(Interval.DAILY)
        )
        self._import_minute_action.triggered.connect(
            lambda: self._import_tdx(Interval.MINUTE)
        )
        self._import_akshare_all_action.triggered.connect(
            lambda: self._import_akshare(None)
        )
        self._import_akshare_daily_action.triggered.connect(
            lambda: self._import_akshare(Interval.DAILY)
        )
        self._import_akshare_hour_action.triggered.connect(
            lambda: self._import_akshare(Interval.HOUR)
        )
        self._import_akshare_minute_action.triggered.connect(
            lambda: self._import_akshare(Interval.MINUTE)
        )

        # 刷新按钮
        self.refresh_button = PrimaryPushButton(
            "刷新", toolbar, FluentIcon.SYNC
        )
        self.refresh_button.clicked.connect(lambda: self._refresh_tree(show_info=True))
        self.refresh_button.setFixedSize(90, 32)

        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.import_button)
        title_row.addSpacing(20)
        title_row.addWidget(self.refresh_button)

        # 副标题
        self.subtitle_label = CaptionLabel(
            "管理本地历史数据，交易日20:00自动下载收藏品种数据", toolbar
        )

        layout.addLayout(title_row)
        layout.addWidget(self.subtitle_label)
        layout.setAlignment(Qt.AlignTop)

        self.toolbar = toolbar

    def _init_tree(self) -> None:
        """初始化数据概览树"""
        labels = [
            "数据", "本地代码", "代码", "名称", "交易所",
            "数据量", "开始时间", "结束时间", "", "", ""
        ]

        self.tree = TreeWidget(self.view)
        self.tree.setColumnCount(len(labels))
        self.tree.setHeaderLabels(labels)
        self.tree.setBorderVisible(False)
        self.tree.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        # 按钮列固定宽度
        for col in range(8, 11):
            self.tree.header().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Fixed
            )
            self.tree.setColumnWidth(col, 100)

    def _init_table(self) -> None:
        """初始化数据查看表格"""
        labels = [
            "时间", "开盘价", "最高价", "最低价",
            "收盘价", "成交量", "成交额", "持仓量"
        ]

        self.table = TableWidget(self.view)
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setBorderVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.table.hide()

        self._table_title = BodyLabel("", self.view)
        self._table_title.hide()

    def _init_widget(self) -> None:
        """初始化界面"""
        self.view.setObjectName("view")
        self.setObjectName("dataManagerInterface")

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, self.toolbar.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.main_layout.setSpacing(8)
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_layout.setContentsMargins(36, 20, 36, 36)
        self.main_layout.addWidget(self.tree, 1)
        self.main_layout.addWidget(self._table_title)
        self.main_layout.addWidget(self.table, 1)

        self._init_theme()

        # 连接自动下载信号（每日 20:00 触发）
        signal_bus.data_auto_download.connect(self._import_akshare)

    # ── 刷新树 ──────────────────────────────────────────────

    def _refresh_tree(self, show_info: bool = False) -> None:
        """刷新数据概览树

        Parameters
        ----------
        show_info : bool
            是否显示刷新结果的 InfoBar 提示
        """
        self.tree.clear()

        contracts = load_contracts()

        # 节点缓存
        interval_nodes: dict[Interval, QTreeWidgetItem] = {}
        exchange_nodes: dict[tuple, QTreeWidgetItem] = {}

        overviews = self.engine.get_bar_overview()
        overviews.sort(key=lambda x: x.symbol)

        # 创建周期节点
        for interval in [Interval.MINUTE, Interval.HOUR, Interval.DAILY]:
            node = QTreeWidgetItem()
            node.setText(0, INTERVAL_NAME_MAP[interval])
            interval_nodes[interval] = node

        # 填充数据节点
        for overview in overviews:
            key = (overview.interval, overview.exchange)
            exchange_node = exchange_nodes.get(key)

            if not exchange_node:
                parent_node = interval_nodes.get(overview.interval)
                if not parent_node:
                    continue
                exchange_node = QTreeWidgetItem(parent_node)
                exchange_node.setText(0, overview.exchange.value)
                exchange_nodes[key] = exchange_node

            item = QTreeWidgetItem(exchange_node)

            # 获取品种名称
            commodity = SymbolConverter.extract_commodity(overview.symbol)
            contract_info = contracts.get(commodity, {})
            name = contract_info.get("name", "")

            item.setText(1, f"{overview.symbol}.{overview.exchange.value}")
            item.setText(2, overview.symbol)
            item.setText(3, name)
            item.setText(4, overview.exchange.value)
            item.setText(5, str(overview.count))
            item.setText(6, overview.start.strftime("%Y-%m-%d %H:%M:%S"))
            item.setText(7, overview.end.strftime("%Y-%m-%d %H:%M:%S"))

            # 行内按钮
            show_btn = PushButton("查看", self)
            show_btn.setFixedSize(80, 30)
            show_btn.clicked.connect(partial(
                self._show_data,
                overview.symbol, overview.exchange,
                overview.interval, overview.start, overview.end
            ))

            export_btn = PushButton("导出", self)
            export_btn.setFixedSize(80, 30)
            export_btn.clicked.connect(partial(
                self._export_data,
                overview.symbol, overview.exchange,
                overview.interval, overview.start, overview.end
            ))

            delete_btn = PushButton("删除", self)
            delete_btn.setFixedSize(80, 30)
            delete_btn.clicked.connect(partial(
                self._delete_data,
                overview.symbol, overview.exchange, overview.interval, item
            ))

            for col in range(8, 11):
                item.setSizeHint(col, QSize(20, 40))

            self.tree.setItemWidget(item, 8, show_btn)
            self.tree.setItemWidget(item, 9, export_btn)
            self.tree.setItemWidget(item, 10, delete_btn)

        # 添加顶层节点并展开
        self.tree.addTopLevelItems(list(interval_nodes.values()))
        for node in interval_nodes.values():
            node.setExpanded(True)

        # 显示数据统计
        if show_info:
            if overviews:
                total_count = sum(o.count for o in overviews)
                InfoBar.success(
                    title="数据概览",
                    content=f"共 {len(overviews)} 个合约，{total_count} 条数据",
                    position=InfoBarPosition.TOP,
                    duration=3000, parent=self
                )
            else:
                InfoBar.info(
                    title="数据概览",
                    content="暂无数据",
                    position=InfoBarPosition.TOP,
                    duration=3000, parent=self
                )

    # ── 查看数据 ────────────────────────────────────────────

    def _show_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> None:
        """查看数据，加载到下方表格"""
        dialog = DateRangeDialog(start, end, self.window())
        if not dialog.exec():
            return

        start, end = dialog.get_date_range()
        bars = self.engine.load_bar_data(symbol, exchange, interval, start, end)

        if not bars:
            InfoBar.info(
                title="提示", content="所选区间无数据",
                position=InfoBarPosition.TOP,
                duration=3000, parent=self
            )
            return

        interval_name = INTERVAL_NAME_MAP.get(interval, interval.value)
        self._table_title.setText(
            f"{symbol}.{exchange.value}  {interval_name}  "
            f"共 {len(bars)} 条"
        )
        self._table_title.show()

        self.table.setRowCount(0)
        self.table.setRowCount(len(bars))

        for row, bar in enumerate(bars):
            items = [
                bar.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                str(round(bar.open_price, 3)),
                str(round(bar.high_price, 3)),
                str(round(bar.low_price, 3)),
                str(round(bar.close_price, 3)),
                str(bar.volume),
                str(bar.turnover),
                str(bar.open_interest),
            ]
            for col, text in enumerate(items):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, cell)

        self.table.show()

    # ── 导出数据 ────────────────────────────────────────────

    def _export_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> None:
        """导出 CSV"""
        dialog = DateRangeDialog(start, end, self.window())
        if not dialog.exec():
            return

        start, end = dialog.get_date_range()

        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "", "CSV(*.csv)"
        )
        if not path:
            return

        result = self.engine.output_data_to_csv(
            path, symbol, exchange, interval, start, end
        )

        if result:
            InfoBar.success(
                title="导出成功",
                content=f"数据已导出到 {path}",
                orient=Qt.Vertical, isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000, parent=self
            )
        else:
            InfoBar.error(
                title="导出失败",
                content="该文件已在其他程序中打开，请关闭后重试",
                orient=Qt.Vertical, isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000, parent=self
            )

    # ── 删除数据 ────────────────────────────────────────────

    def _delete_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        item: QTreeWidgetItem
    ) -> None:
        """删除数据"""
        box = MessageBox(
            "删除确认",
            f"确认删除 {symbol} {exchange.value} "
            f"{INTERVAL_NAME_MAP.get(interval, interval.value)} 的全部数据？",
            self.window()
        )
        if not box.exec():
            return

        count = self.engine.delete_bar_data(symbol, exchange, interval)

        # 从树中移除节点，父节点无子节点时一并移除
        parent = item.parent()
        if parent:
            parent.removeChild(item)
            if parent.childCount() == 0:
                grandparent = parent.parent()
                if grandparent:
                    grandparent.removeChild(parent)

        InfoBar.success(
            title="删除成功",
            content=f"已删除 {count} 条数据",
            orient=Qt.Vertical, isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000, parent=self
        )

    # ── 通达信导入 ──────────────────────────────────────────

    def _import_tdx(self, interval: Interval) -> None:
        """通达信数据导入"""
        folder = QFileDialog.getExistingDirectory(
            self.window(), "选择通达信导出文件夹"
        )
        if not folder:
            return

        self.import_button.setEnabled(False)

        self._state_tooltip = StateToolTip(
            "数据导入", "正在导入通达信数据，请稍候", self.window()
        )
        self._state_tooltip.move(self._state_tooltip.getSuitablePos())
        self._state_tooltip.show()

        self._import_thread = TdxImportThread(
            self.engine, folder, interval, self
        )
        self._import_thread.progress.connect(self._on_import_progress)
        self._import_thread.finished.connect(self._on_import_thread_finished)
        self._import_thread.start()

    def _import_akshare(self, interval: Interval | None = None) -> None:
        """AKShare 收藏品种数据导入

        Parameters
        ----------
        interval : Interval | None
            数据周期，None 表示一键下载全周期
        """
        if interval is None:
            desc = "正在从 AKShare 一键下载收藏品种数据"
        else:
            interval_name = INTERVAL_NAME_MAP.get(interval, interval.value)
            desc = f"正在从 AKShare 下载收藏品种{interval_name}数据"

        self.import_button.setEnabled(False)

        self._state_tooltip = StateToolTip("数据导入", desc, self.window())
        self._state_tooltip.move(self._state_tooltip.getSuitablePos())
        self._state_tooltip.show()

        self._import_thread = AkShareImportThread(
            self.engine, interval, self
        )
        self._import_thread.progress.connect(self._on_import_progress)
        self._import_thread.finished.connect(self._on_import_thread_finished)
        self._import_thread.start()

    def _on_import_progress(self, message: str, completed: bool) -> None:
        """导入进度回调"""
        if self._state_tooltip:
            self._state_tooltip.setContent(message)
            if completed:
                self._state_tooltip.setState(True)
                self.import_button.setEnabled(True)
                self._refresh_tree()

    def _on_import_thread_finished(self) -> None:
        """导入线程结束"""
        self._import_thread = None

    # ── 生命周期 ────────────────────────────────────────────

    def showEvent(self, event) -> None:
        """首次显示时刷新树"""
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self._refresh_tree()

    def resizeEvent(self, e) -> None:
        """调整标题栏宽度"""
        super().resizeEvent(e)
        self.toolbar.resize(self.width(), self.toolbar.height())
