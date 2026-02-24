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
    CheckBox, IndeterminateProgressBar,
    InfoBar, InfoBarPosition,
    MessageBox, StateToolTip,
    FluentIcon,
)

from guanlan.ui.common.mixin import ThemeMixin
from guanlan.ui.widgets import ThemedDialog
from guanlan.core.trader.data import DataManagerEngine
from guanlan.core.constants import Interval, Exchange
from vnpy.trader.database import TickOverview
from guanlan.core.events.signal_bus import signal_bus
from guanlan.core.setting.contract import load_contracts
from guanlan.core.utils.symbol_converter import SymbolConverter
from guanlan.core.services.tdx import TdxService, TdxFileInfo

# 周期名称映射
INTERVAL_NAME_MAP: dict[Interval, str] = {
    Interval.MINUTE: "分钟线",
    Interval.HOUR: "小时线",
    Interval.DAILY: "日线",
}


# ────────────────────────────────────────────────────────────
# 工作线程
# ────────────────────────────────────────────────────────────

class TdxLocalImportThread(QThread):
    """通达信本地二进制文件导入线程"""

    progress = Signal(str, bool)  # (消息, 是否完成)

    def __init__(
        self,
        engine: DataManagerEngine,
        file_list: list[TdxFileInfo],
        parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.file_list = file_list

    def run(self) -> None:
        total = len(self.file_list)
        count = 0

        for i, file_info in enumerate(self.file_list, 1):
            self.progress.emit(
                f"({i}/{total}) 正在导入: {file_info.vt_symbol}", False
            )

            try:
                bars = TdxService.read_bars(file_info)
                if bars:
                    self.engine.database.save_bar_data(bars)
                    count += 1
            except Exception as e:
                self.progress.emit(
                    f"导入 {file_info.vt_symbol} 失败: {e}", False
                )

        self.progress.emit(f"导入完成，共导入 {count} 个合约", True)


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

class TdxDiscoverThread(QThread):
    """通达信目录扫描线程"""

    finished = Signal(list)  # list[TdxFileInfo]

    def __init__(self, tdx_path: str, parent=None) -> None:
        super().__init__(parent)
        self.tdx_path = tdx_path

    def run(self) -> None:
        result = TdxService.discover(self.tdx_path)
        self.finished.emit(result)


class TdxImportDialog(ThemedDialog):
    """通达信本地数据导入对话框"""

    def __init__(
        self,
        tdx_path: str,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.file_list: list[TdxFileInfo] = []
        self._visible_indices: list[int] = []

        self.widget.setMinimumWidth(600)

        # 标题
        self.viewLayout.addWidget(SubtitleLabel("通达信本地数据导入", self))

        # 扫描提示（标题下方、勾选上方）
        self._scan_label = CaptionLabel("正在扫描通达信目录...", self)
        self._progress_bar = IndeterminateProgressBar(self)
        self._progress_bar.start()
        self.viewLayout.addWidget(self._scan_label)
        self.viewLayout.addWidget(self._progress_bar)

        # 过滤行
        filter_row = QHBoxLayout()
        self._filter_daily = CheckBox("日线")
        self._filter_minute = CheckBox("分钟线")
        self._filter_continuous = CheckBox("主力/指数")
        self._filter_daily.setChecked(True)
        self._filter_minute.setChecked(True)
        self._filter_continuous.setChecked(True)
        self._filter_daily.stateChanged.connect(self._apply_filter)
        self._filter_minute.stateChanged.connect(self._apply_filter)
        self._filter_continuous.stateChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_daily)
        filter_row.addWidget(self._filter_minute)
        filter_row.addWidget(self._filter_continuous)
        filter_row.addStretch(1)
        self.viewLayout.addLayout(filter_row)

        # 数据表格
        self.table = TableWidget(self)
        self._checkboxes: list[CheckBox] = []
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "", "合约代码", "品种名", "周期", "数据量"
        ])
        self.table.setBorderVisible(False)
        self.table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        # 代码和品种名按比例拉伸，周期和数据量固定宽度
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 80)
        self.table.hide()
        self.viewLayout.addWidget(self.table)

        # 全选/反选按钮
        btn_row = QHBoxLayout()
        select_all_btn = PushButton("全选", self)
        select_all_btn.setFixedHeight(30)
        select_all_btn.clicked.connect(self._select_all)
        invert_btn = PushButton("反选", self)
        invert_btn.setFixedHeight(30)
        invert_btn.clicked.connect(self._invert_selection)
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(invert_btn)
        btn_row.addStretch(1)
        self.viewLayout.addLayout(btn_row)

        self.yesButton.setText("导入")
        self.yesButton.setEnabled(False)
        self.cancelButton.setText("取消")

        # 启动扫描
        self._scan_thread = TdxDiscoverThread(tdx_path, self)
        self._scan_thread.finished.connect(self._on_scan_finished)
        self._scan_thread.start()

    def _on_scan_finished(self, file_list: list[TdxFileInfo]) -> None:
        """扫描完成回调"""
        self.file_list = file_list
        self._progress_bar.stop()
        self._progress_bar.hide()

        if not file_list:
            self._scan_label.setText("未发现数据：通达信目录下未发现期货数据文件")
            return

        self._scan_label.hide()

        self.table.show()
        self.yesButton.setEnabled(True)
        self._fill_table()

    def _apply_filter(self) -> None:
        """根据过滤条件重新填充表格"""
        self._fill_table()

    def _fill_table(self) -> None:
        """按过滤条件填充数据表格"""
        interval_names = {
            Interval.MINUTE: "1分钟",
            Interval.DAILY: "日线",
        }

        show_daily = self._filter_daily.isChecked()
        show_minute = self._filter_minute.isChecked()
        show_continuous = self._filter_continuous.isChecked()

        # 筛选可见项
        self._visible_indices.clear()
        for i, info in enumerate(self.file_list):
            if info.is_continuous and not show_continuous:
                continue
            if info.interval == Interval.DAILY and not show_daily:
                continue
            if info.interval == Interval.MINUTE and not show_minute:
                continue
            self._visible_indices.append(i)

        self.table.setRowCount(len(self._visible_indices))
        self._checkboxes.clear()

        for row, idx in enumerate(self._visible_indices):
            info = self.file_list[idx]

            cb = CheckBox()
            cb.setChecked(True)
            self._checkboxes.append(cb)
            self.table.setCellWidget(row, 0, cb)

            symbol_item = QTableWidgetItem(info.vt_symbol)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, symbol_item)

            name_item = QTableWidgetItem(info.name)
            name_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, name_item)

            interval_name = interval_names.get(
                info.interval, info.interval.value
            )
            interval_item = QTableWidgetItem(interval_name)
            interval_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, interval_item)

            count_item = QTableWidgetItem(str(info.bar_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, count_item)

    def _select_all(self) -> None:
        """全选"""
        for cb in self._checkboxes:
            cb.setChecked(True)

    def _invert_selection(self) -> None:
        """反选"""
        for cb in self._checkboxes:
            cb.setChecked(not cb.isChecked())

    def get_selected(self) -> list[TdxFileInfo]:
        """获取勾选的文件列表"""
        return [
            self.file_list[idx]
            for idx, cb in zip(self._visible_indices, self._checkboxes)
            if cb.isChecked()
        ]


class DateRangeDialog(ThemedDialog):
    """日期范围选择对话框"""

    def __init__(self, start: datetime, end: datetime, parent=None) -> None:
        super().__init__(parent)

        # 默认区间：从今天往前推一个月（北京时间）
        from guanlan.core.utils.trading_period import beijing_now
        now = beijing_now()
        one_month_ago = now - timedelta(days=30)

        self.viewLayout.addWidget(SubtitleLabel("选择数据区间", self))

        self.start_edit = DateEdit(self)
        self.start_edit.setDate(QDate(
            one_month_ago.year, one_month_ago.month, one_month_ago.day
        ))
        self.start_edit.setDisplayFormat("yyyy年MM月dd日")
        self.viewLayout.addWidget(self.start_edit)

        self.end_edit = DateEdit(self)
        self.end_edit.setDate(QDate(now.year, now.month, now.day))
        self.end_edit.setDisplayFormat("yyyy年MM月dd日")
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
        self._import_thread: TdxLocalImportThread | AkShareImportThread | None = None
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
        self._import_tdx_local_action = Action(FluentIcon.FOLDER, "本地数据")
        tdx_menu.addAction(self._import_tdx_local_action)
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

        self._import_tdx_local_action.triggered.connect(self._import_tdx_local)
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

        # ── Tick 数据 ──
        tick_overviews = self.engine.get_tick_overview()
        tick_overviews.sort(key=lambda x: x.symbol)

        tick_root = QTreeWidgetItem()
        tick_root.setText(0, "Tick数据")

        tick_exchange_nodes: dict[str, QTreeWidgetItem] = {}

        for overview in tick_overviews:
            ex_val = overview.exchange.value
            ex_node = tick_exchange_nodes.get(ex_val)
            if not ex_node:
                ex_node = QTreeWidgetItem(tick_root)
                ex_node.setText(0, ex_val)
                tick_exchange_nodes[ex_val] = ex_node

            item = QTreeWidgetItem(ex_node)

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

            show_btn = PushButton("查看", self)
            show_btn.setFixedSize(80, 30)
            show_btn.clicked.connect(partial(
                self._show_tick_data,
                overview.symbol, overview.exchange,
                overview.start, overview.end
            ))

            delete_btn = PushButton("删除", self)
            delete_btn.setFixedSize(80, 30)
            delete_btn.clicked.connect(partial(
                self._delete_tick_data,
                overview.symbol, overview.exchange, item
            ))

            for col in range(8, 11):
                item.setSizeHint(col, QSize(20, 40))

            self.tree.setItemWidget(item, 8, show_btn)
            self.tree.setItemWidget(item, 10, delete_btn)

        # 添加顶层节点并展开
        all_nodes = list(interval_nodes.values()) + [tick_root]
        self.tree.addTopLevelItems(all_nodes)
        for node in all_nodes:
            node.setExpanded(True)

        # 显示数据统计
        if show_info:
            total = len(overviews) + len(tick_overviews)
            if total:
                bar_count = sum(o.count for o in overviews)
                tick_count = sum(o.count for o in tick_overviews)
                InfoBar.success(
                    title="数据概览",
                    content=(
                        f"K线 {len(overviews)} 个合约 {bar_count} 条，"
                        f"Tick {len(tick_overviews)} 个合约 {tick_count} 条"
                    ),
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

        # 恢复 K 线表头
        bar_headers = [
            "时间", "开盘价", "最高价", "最低价",
            "收盘价", "成交量", "成交额", "持仓量"
        ]
        self.table.setColumnCount(len(bar_headers))
        self.table.setHorizontalHeaderLabels(bar_headers)

        self.table.setRowCount(0)
        self.table.setRowCount(len(bars))

        for row, bar in enumerate(reversed(bars)):
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

    # ── Tick 数据查看 / 删除 ─────────────────────────────────

    def _show_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime
    ) -> None:
        """查看 Tick 数据"""
        dialog = DateRangeDialog(start, end, self.window())
        if not dialog.exec():
            return

        start, end = dialog.get_date_range()
        ticks = self.engine.load_tick_data(symbol, exchange, start, end)

        if not ticks:
            InfoBar.info(
                title="提示", content="所选区间无数据",
                position=InfoBarPosition.TOP,
                duration=3000, parent=self
            )
            return

        self._table_title.setText(
            f"{symbol}.{exchange.value}  Tick  共 {len(ticks)} 条"
        )
        self._table_title.show()

        # 切换表头为 Tick 格式
        tick_headers = [
            "时间", "最新价", "成交量", "买一价",
            "买一量", "卖一价", "卖一量", "持仓量"
        ]
        self.table.setColumnCount(len(tick_headers))
        self.table.setHorizontalHeaderLabels(tick_headers)

        self.table.setRowCount(0)
        self.table.setRowCount(len(ticks))

        for row, tick in enumerate(reversed(ticks)):
            items = [
                tick.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                str(round(tick.last_price, 3)),
                str(tick.volume),
                str(round(tick.bid_price_1, 3)),
                str(tick.bid_volume_1),
                str(round(tick.ask_price_1, 3)),
                str(tick.ask_volume_1),
                str(tick.open_interest),
            ]
            for col, text in enumerate(items):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, cell)

        self.table.show()

    def _delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        item: QTreeWidgetItem
    ) -> None:
        """删除 Tick 数据"""
        box = MessageBox(
            "删除确认",
            f"确认删除 {symbol} {exchange.value} 的全部 Tick 数据？",
            self.window()
        )
        if not box.exec():
            return

        count = self.engine.delete_tick_data(symbol, exchange)

        parent = item.parent()
        if parent:
            parent.removeChild(item)
            if parent.childCount() == 0:
                grandparent = parent.parent()
                if grandparent:
                    grandparent.removeChild(parent)

        InfoBar.success(
            title="删除成功",
            content=f"已删除 {count} 条 Tick 数据",
            orient=Qt.Vertical, isClosable=True,
            position=InfoBarPosition.TOP,
            duration=4000, parent=self
        )

    # ── 通达信导入 ──────────────────────────────────────────

    def _import_tdx_local(self) -> None:
        """通达信本地二进制数据导入"""
        from guanlan.ui.common.config import cfg

        tdx_path = cfg.get(cfg.tdxPath)
        if not tdx_path:
            InfoBar.warning(
                title="未配置路径",
                content="请先在「设置 → 数据 → 通达信目录」中配置路径",
                position=InfoBarPosition.TOP,
                duration=4000, parent=self
            )
            return

        dialog = TdxImportDialog(tdx_path, self.window())
        if not dialog.exec():
            return

        selected = dialog.get_selected()
        if not selected:
            InfoBar.info(
                title="提示", content="未选择任何合约",
                position=InfoBarPosition.TOP,
                duration=3000, parent=self
            )
            return

        self._start_tdx_local_import(selected)

    def _start_tdx_local_import(self, file_list: list[TdxFileInfo]) -> None:
        """启动本地数据导入线程"""
        self.import_button.setEnabled(False)

        self._state_tooltip = StateToolTip(
            "数据导入", "正在导入通达信本地数据，请稍候", self.window()
        )
        self._state_tooltip.move(self._state_tooltip.getSuitablePos())
        self._state_tooltip.show()

        self._import_thread = TdxLocalImportThread(
            self.engine, file_list, self
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
