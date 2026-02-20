# -*- coding: utf-8 -*-
"""
观澜量化 - 监控表格基类

参考 VNPY BaseMonitor 设计，适配 QFluentWidgets。
子类通过类变量声明表格结构，基类自动完成表格初始化、数据更新、
右键菜单（调整列宽 / 导出 CSV）等公共功能。

MonitorPanel 在 BaseMonitor 之上封装了过滤工具栏和 EventEngine
事件直连。子类声明 event_type + _convert_data 即可自动接收原始
VNPY 事件并转换为 dict；声明 filter_fields 自动生成过滤 ComboBox。

Author: 海山观澜
"""

import csv
from collections import deque

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QTableWidgetItem, QFileDialog,
)

from qfluentwidgets import TableWidget, RoundMenu, FluentIcon, ComboBox, BodyLabel, CheckBox


class BaseMonitor(TableWidget):
    """监控表格基类

    子类声明示例::

        class PositionMonitor(BaseMonitor):
            headers = {
                "symbol":      {"display": "代码"},
                "direction":   {"display": "方向",  "color": "direction"},
                "volume":      {"display": "数量",  "format": "int"},
                "pnl":         {"display": "盈亏",  "format": ".2f", "color": "pnl"},
                "gateway_name":{"display": "接口"},
            }
            data_key = "vt_positionid"

    Attributes:
        headers : 列定义（有序 dict）
            key   - 数据字典的字段名
            display - 表头显示文字
            format  - 可选，格式化方式：".2f" / "int" / "time"
            color   - 可选，着色模式："direction" / "pnl"
        data_key : 行唯一键（空字符串则仅追加不更新）
    """

    headers: dict[str, dict] = {}
    data_key: str = ""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._rows: dict[str, int] = {}
        self._row_data: dict[str, dict] = {}
        self._data_by_row: list[dict] = []
        self._header_keys: list[str] = list(self.headers.keys())

        # 列宽自动增长：跟踪每列最大文本长度，内容变宽时自动调整
        self._max_text_lens: list[int] = [0] * len(self.headers)
        self._width_dirty: bool = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(200)
        self._resize_timer.timeout.connect(self._resize_columns)

        self._init_table()

    def _init_table(self) -> None:
        """初始化表格"""
        labels = [h["display"] for h in self.headers.values()]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        self.setBorderVisible(False)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # 最后一列拉伸
        last = len(labels) - 1
        header.setSectionResizeMode(last, QHeaderView.ResizeMode.Stretch)
        # 通过 headers 中的可选 width 字段设置初始列宽（默认 80px）
        for col, setting in enumerate(self.headers.values()):
            if col < last:
                header.resizeSection(col, setting.get("width", 80))

    # ── 数据处理 ──

    def process_data(self, data: dict) -> None:
        """处理一条数据：新增或更新行"""
        if self.data_key:
            key = str(data.get(self.data_key, ""))
            if key in self._rows:
                row = self._rows[key]
                self._data_by_row[row] = data
            else:
                row = self.rowCount()
                self.insertRow(row)
                self._rows[key] = row
                self._data_by_row.append(data)
            self._row_data[key] = data
        else:
            row = self.rowCount()
            self.insertRow(row)
            self._data_by_row.append(data)

        self._fill_row(row, data)

        # 列内容变宽 → 调度 debounce 列宽调整
        if self._width_dirty:
            self._width_dirty = False
            self._resize_timer.start()

    def process_batch(self, data_list: list[dict], scroll: bool = False) -> None:
        """批量处理数据：暂停 UI 重绘，批量写入后统一刷新"""
        self.setUpdatesEnabled(False)
        for data in data_list:
            self.process_data(data)
        self.setUpdatesEnabled(True)
        if scroll:
            self.scrollToBottom()

    def _fill_row(self, row: int, data: dict) -> None:
        """填充一行数据"""
        for col, key in enumerate(self._header_keys):
            setting = self.headers[key]
            value = data.get(key, "")

            text = self._format_value(value, data, setting)

            # 检测列内容是否变宽
            text_len = len(text)
            if text_len > self._max_text_lens[col]:
                self._max_text_lens[col] = text_len
                self._width_dirty = True

            item = QTableWidgetItem(text)
            align = setting.get("align", "center")
            if align == "left":
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignCenter)

            color = self._get_color(value, data, setting)
            if color:
                item.setForeground(color)

            self.setItem(row, col, item)

    # ── 格式化 ──

    @staticmethod
    def _format_value(value, data: dict, setting: dict) -> str:
        """根据 format 设置格式化值"""
        fmt = setting.get("format")
        if fmt is None:
            return str(value) if value is not None else ""
        if fmt == "int":
            return str(int(value)) if value else "0"
        if fmt == "time":
            s = str(value)
            if s and " " in s:
                return s.split(" ", 1)[1][:8]
            return s
        # 浮点格式如 ".2f"
        if fmt.startswith("."):
            try:
                return f"{float(value):{fmt}}"
            except (ValueError, TypeError):
                return ""
        return str(value)

    # ── 着色 ──

    @staticmethod
    def _get_color(value, data: dict, setting: dict) -> QColor | None:
        """根据 color 设置返回前景色"""
        from . import long_color, short_color

        mode = setting.get("color")
        if not mode:
            return None

        if mode == "direction":
            if value == "多":
                return long_color()
            elif value == "空":
                return short_color()
        elif mode == "pnl":
            try:
                v = float(value)
            except (ValueError, TypeError):
                return None
            if v > 0:
                return long_color()
            elif v < 0:
                return short_color()

        return None

    # ── 右键菜单 ──

    def contextMenuEvent(self, event) -> None:
        """右键菜单：调整列宽 / 导出 CSV / 清空"""
        menu = RoundMenu(parent=self)
        menu.addAction(QAction(
            FluentIcon.ZOOM_IN.icon(), "调整列宽", self,
            triggered=self._resize_columns,
        ))
        menu.addAction(QAction(
            FluentIcon.SAVE.icon(), "导出 CSV", self,
            triggered=self._save_csv,
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            FluentIcon.DELETE.icon(), "清空", self,
            triggered=self.clear_data,
        ))
        menu.exec(event.globalPos())

    def clear_data(self) -> None:
        """清空所有数据"""
        self.setRowCount(0)
        self._rows.clear()
        self._row_data.clear()
        self._data_by_row.clear()
        self._max_text_lens = [0] * len(self.headers)
        self._width_dirty = False

    def _resize_columns(self) -> None:
        """调整所有列宽"""
        self.horizontalHeader().resizeSections(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _save_csv(self) -> None:
        """导出可见行为 CSV"""
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "", "CSV(*.csv)")
        if not path:
            return

        labels = [h["display"] for h in self.headers.values()]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(labels)

            for row in range(self.rowCount()):
                if self.isRowHidden(row):
                    continue
                row_data = []
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)


class MonitorPanel(QWidget):
    """可过滤的监控面板基类

    在 BaseMonitor 表格之上封装过滤工具栏和 EventEngine 事件直连。

    子类声明示例::

        class PositionMonitor(MonitorPanel):
            table_class = _PositionTable
            filter_fields = {"gateway_name": "账户", "direction": "方向"}
            event_type = EVENT_POSITION

            def _convert_data(self, pos: PositionData) -> dict:
                return {"symbol": pos.symbol, ...}

    Attributes:
        table_class  : 内部表格类
        filter_fields: 过滤字段（key=字段名, value=显示标签）
        auto_scroll  : 是否显示"最新"自动滚动复选框
        event_type   : VNPY 事件类型（如 EVENT_POSITION），为空则不注册
    """

    table_class: type[BaseMonitor] = BaseMonitor
    filter_fields: dict[str, str] = {}
    auto_scroll: bool = False
    event_type: str = ""

    # EventEngine → 主线程 跨线程信号
    _signal_event = Signal(object)

    # 批量刷新间隔（毫秒）
    flush_interval: int = 100

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._combos: dict[str, ComboBox] = {}
        self._buffer: list = []
        self._init_ui()

        # 定时批量刷新
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(self.flush_interval)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

        if self.event_type:
            self._register_event()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 过滤工具栏
        self._toolbar = QHBoxLayout()
        self._toolbar.setContentsMargins(0, 2, 0, 2)
        self._create_filters()
        self._toolbar.addStretch(1)

        # 自动滚动复选框（靠右）
        if self.auto_scroll:
            self._scroll_check = CheckBox("最新", self)
            self._scroll_check.setChecked(True)
            self._scroll_check.setToolTip("自动滚动到最新数据")
            self._toolbar.addWidget(self._scroll_check)

        if self.filter_fields or self.auto_scroll:
            layout.addLayout(self._toolbar)

        # 表格
        self._table = self.table_class(self)
        layout.addWidget(self._table, 1)

    def _create_filters(self) -> None:
        """创建过滤控件（子类可重写以添加额外控件）"""
        first = True
        for field, display in self.filter_fields.items():
            if not first:
                self._toolbar.addSpacing(12)
            first = False

            label = BodyLabel(f"{display}:", self)
            combo = ComboBox(self)
            combo.addItem("全部")
            combo.setFixedWidth(120)
            combo.setFixedHeight(28)
            combo.currentTextChanged.connect(self._apply_filters)
            self._combos[field] = combo
            self._toolbar.addWidget(label)
            self._toolbar.addWidget(combo)

    # ── 数据入口 ──

    def process_data(self, data: dict) -> None:
        """处理一条数据：更新表格 + 动态更新过滤选项 + 应用过滤"""
        self._table.process_data(data)
        self._update_options(data)

        # 过滤当前行
        row = self._find_row(data)
        if row is not None:
            self._table.setRowHidden(row, self._should_hide(data))

        if self.auto_scroll and self._scroll_check.isChecked():
            self._table.scrollToBottom()

    def _find_row(self, data: dict) -> int | None:
        """查找数据对应的行号"""
        if self._table.data_key:
            key = str(data.get(self._table.data_key, ""))
            return self._table._rows.get(key)
        # 追加模式：刚插入的最后一行
        count = self._table.rowCount()
        return count - 1 if count > 0 else None

    # ── 过滤器 ──

    def _update_options(self, data: dict) -> None:
        """从数据中动态收集过滤选项"""
        for field, combo in self._combos.items():
            value = str(data.get(field, ""))
            if value and combo.findText(value) < 0:
                combo.addItem(value)

    def _apply_filters(self) -> None:
        """重新过滤所有行"""
        for row, data in enumerate(self._table._data_by_row):
            self._table.setRowHidden(row, self._should_hide(data))

    def _should_hide(self, data: dict) -> bool:
        """判断行是否应当隐藏（子类可重写扩展过滤条件）"""
        for field, combo in self._combos.items():
            selected = combo.currentText()
            if selected != "全部" and str(data.get(field, "")) != selected:
                return True
        return False

    # ── EventEngine 直连 ──

    def _register_event(self) -> None:
        """注册 EventEngine 事件监听"""
        from guanlan.core.app import AppEngine

        engine = AppEngine.instance().event_engine
        self._signal_event.connect(self._on_event)
        engine.register(self.event_type, self._on_event_callback)

    def _on_event_callback(self, event) -> None:
        """EventEngine 线程回调 → Qt Signal 跨线程"""
        self._signal_event.emit(event.data)

    def _on_event(self, data) -> None:
        """主线程：事件数据入缓冲区，等待定时批量刷新"""
        self._buffer.append(data)

    def _flush(self) -> None:
        """定时批量刷新：一次性处理缓冲区中的所有数据"""
        if not self._buffer:
            return

        batch = self._buffer
        self._buffer = []

        # 暂停 UI 重绘，批量完成后统一刷新
        self._table.setUpdatesEnabled(False)

        for raw_data in batch:
            converted = self._convert_data(raw_data)
            self._table.process_data(converted)
            self._update_options(converted)

        self._table.setUpdatesEnabled(True)

        # 过滤和滚动只做一次
        self._apply_filters()
        if self.auto_scroll and self._scroll_check.isChecked():
            self._table.scrollToBottom()

    def _convert_data(self, data) -> dict:
        """子类重写：将 VNPY 数据对象转换为 dict"""
        return {}


class StrategyLogTable(BaseMonitor):
    """策略日志表格

    三列追加表格（时间、策略、信息），带最大行数限制。
    供 CTA / 组合策略 / 脚本策略窗口复用。

    使用缓冲区 + QTimer 定时批量刷新，避免高频日志卡顿。
    """

    headers: dict[str, dict] = {
        "time": {"display": "时间", "width": 70},
        "strategy": {"display": "策略"},
        "msg": {"display": "信息", "align": "left"},
    }
    data_key: str = ""

    MAX_ROWS: int = 500
    _FLUSH_INTERVAL_MS: int = 100

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data_by_row: deque[dict] = deque()  # type: ignore[assignment]  # 有意用 deque 替代父类 list，支持 popleft 高效删旧行
        self._buffer: list[dict] = []

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(self._FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

    def process_data(self, data: dict) -> None:
        """日志入缓冲区，等待定时批量刷新"""
        self._buffer.append(data)

    def _flush(self) -> None:
        """定时批量刷新：一次性处理缓冲区中的所有日志"""
        if not self._buffer:
            return

        batch = self._buffer
        self._buffer = []

        # 单次批量超过上限，只保留最新的
        if len(batch) > self.MAX_ROWS:
            batch = batch[-self.MAX_ROWS:]

        self.setUpdatesEnabled(False)

        # 计算需要删除的旧行数
        to_remove = max(0, self.rowCount() + len(batch) - self.MAX_ROWS)
        if to_remove > 0:
            if to_remove > 50:
                # 大量溢出：重建表格更高效
                keep_count = max(0, self.MAX_ROWS - len(batch))
                keep_data = list(self._data_by_row)[-keep_count:] if keep_count > 0 else []
                self.setRowCount(0)
                self._data_by_row = deque(keep_data)
                for row, d in enumerate(keep_data):
                    self.insertRow(row)
                    self._fill_row(row, d)
            else:
                # 少量溢出：逐行删除最早的行
                for _ in range(to_remove):
                    self.removeRow(0)
                    self._data_by_row.popleft()

        # 追加新行
        for data in batch:
            row = self.rowCount()
            self.insertRow(row)
            self._data_by_row.append(data)
            self._fill_row(row, data)

        self.setUpdatesEnabled(True)
        self.scrollToBottom()

        # 列内容变宽 → 调度 debounce 列宽调整
        if self._width_dirty:
            self._width_dirty = False
            self._resize_timer.start()
