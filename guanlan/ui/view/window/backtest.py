# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 回测窗口

独立窗口，从首页 Banner 卡片进入。三栏布局：
左栏（参数+按钮）、中栏（统计+日志）、右栏（图表）。
统计指标、pyqtgraph 四图表、K线图表、成交/委托/每日记录弹窗。

Author: 海山观澜
"""

import csv
from copy import copy
from datetime import datetime, timedelta

import numpy as np

from guanlan.core.utils.trading_period import beijing_now
import pyqtgraph as pg

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QIcon, QColor, QPen, QDoubleValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QHeaderView, QTableWidgetItem,
    QAbstractItemView, QFileDialog, QLabel,
)

from qfluentwidgets import (
    FluentWidget,
    PushButton, PrimaryPushButton,
    BodyLabel, SubtitleLabel,
    LineEdit, ComboBox, EditableComboBox, DateEdit,
    TableWidget, TextEdit,
    MessageBoxBase, ScrollArea,
    InfoBar, InfoBarPosition,
    isDarkTheme, qconfig,
)

from vnpy.trader.constant import Interval, Direction, Exchange
from vnpy.trader.object import TradeData, BarData
from vnpy.trader.optimize import OptimizationSetting

from guanlan.core.utils.symbol_converter import SymbolConverter
from vnpy.chart import ChartWidget, CandleItem, VolumeItem

from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.backtest import (
    BacktesterEngine,
    EVENT_BACKTESTER_LOG,
    EVENT_BACKTESTER_FINISHED,
    EVENT_BACKTESTER_OPT_FINISHED,
)
from guanlan.core.trader.cta.template import BaseParams
from guanlan.core.utils.common import load_json_file, save_json_file

SETTING_FILENAME: str = "config/cta_backtester_setting.json"


# ── 统计指标表 ──────────────────────────────────────────────


class StatisticsMonitor(TableWidget):
    """回测统计指标表（24 项，单列竖排）"""

    KEY_NAME_MAP: dict[str, str] = {
        "start_date": "首个交易日",
        "end_date": "最后交易日",
        "total_days": "总交易日",
        "profit_days": "盈利交易日",
        "loss_days": "亏损交易日",
        "capital": "起始资金",
        "end_balance": "结束资金",
        "total_return": "总收益率",
        "annual_return": "年化收益",
        "max_drawdown": "最大回撤",
        "max_ddpercent": "百分比最大回撤",
        "total_net_pnl": "总盈亏",
        "total_commission": "总手续费",
        "total_slippage": "总滑点",
        "total_turnover": "总成交额",
        "total_trade_count": "总成交笔数",
        "daily_net_pnl": "日均盈亏",
        "daily_commission": "日均手续费",
        "daily_slippage": "日均滑点",
        "daily_turnover": "日均成交额",
        "daily_trade_count": "日均成交笔数",
        "daily_return": "日均收益率",
        "return_std": "收益标准差",
        "sharpe_ratio": "夏普比率",
        "return_drawdown_ratio": "收益回撤比",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cells: dict[str, QTableWidgetItem] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.setRowCount(len(self.KEY_NAME_MAP))
        self.setVerticalHeaderLabels(list(self.KEY_NAME_MAP.values()))
        self.setColumnCount(1)
        self.horizontalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for row, key in enumerate(self.KEY_NAME_MAP):
            cell = QTableWidgetItem()
            self.setItem(row, 0, cell)
            self._cells[key] = cell

    def clear_data(self) -> None:
        for cell in self._cells.values():
            cell.setText("")

    def set_data(self, data: dict) -> None:
        # 格式化显示
        fmt = {
            "capital": "{:,.2f}", "end_balance": "{:,.2f}",
            "total_return": "{:,.2f}%", "annual_return": "{:,.2f}%",
            "max_drawdown": "{:,.2f}", "max_ddpercent": "{:,.2f}%",
            "total_net_pnl": "{:,.2f}", "total_commission": "{:,.2f}",
            "total_slippage": "{:,.2f}", "total_turnover": "{:,.2f}",
            "daily_net_pnl": "{:,.2f}", "daily_commission": "{:,.2f}",
            "daily_slippage": "{:,.2f}", "daily_turnover": "{:,.2f}",
            "daily_trade_count": "{:,.2f}", "daily_return": "{:,.2f}%",
            "return_std": "{:,.2f}%", "sharpe_ratio": "{:,.2f}",
            "return_drawdown_ratio": "{:,.2f}",
        }
        for key, cell in self._cells.items():
            value = data.get(key, "")
            template = fmt.get(key)
            if template and isinstance(value, (int, float)):
                cell.setText(template.format(value))
            else:
                cell.setText(str(value))


# ── pyqtgraph 四图表 ───────────────────────────────────────


class DateAxis(pg.AxisItem):
    """日期坐标轴"""

    def __init__(self, dates: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._dates = dates

    def tickStrings(self, values, scale, spacing) -> list:
        return [str(self._dates.get(v, "")) for v in values]


class BacktesterChart(pg.GraphicsLayoutWidget):
    """回测图表（净值 / 回撤 / 每日盈亏 / 盈亏分布）"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent, title="Backtester Chart")
        self._dates: dict = {}
        self._init_ui()

    def _init_ui(self) -> None:
        pg.setConfigOptions(antialias=True)

        # 账户净值
        self._balance_plot = self.addPlot(
            title="账户净值",
            axisItems={"bottom": DateAxis(self._dates, orientation="bottom")},
        )
        self.nextRow()

        # 净值回撤
        self._drawdown_plot = self.addPlot(
            title="净值回撤",
            axisItems={"bottom": DateAxis(self._dates, orientation="bottom")},
        )
        self.nextRow()

        # 每日盈亏
        self._pnl_plot = self.addPlot(
            title="每日盈亏",
            axisItems={"bottom": DateAxis(self._dates, orientation="bottom")},
        )
        self.nextRow()

        # 盈亏分布
        self._dist_plot = self.addPlot(title="盈亏分布")

        # 曲线与柱状图
        self._balance_curve = self._balance_plot.plot(
            pen=pg.mkPen("#ffc107", width=3),
        )
        dd_color = "#303f9f"
        self._drawdown_curve = self._drawdown_plot.plot(
            fillLevel=-0.3, brush=dd_color, pen=dd_color,
        )

        self._profit_bar = pg.BarGraphItem(
            x=[], height=[], width=0.3, brush="r", pen="r",
        )
        self._loss_bar = pg.BarGraphItem(
            x=[], height=[], width=0.3, brush="g", pen="g",
        )
        self._pnl_plot.addItem(self._profit_bar)
        self._pnl_plot.addItem(self._loss_bar)

        dist_color = "#6d4c41"
        self._dist_curve = self._dist_plot.plot(
            fillLevel=-0.3, brush=dist_color, pen=dist_color,
        )

    def clear_data(self) -> None:
        self._balance_curve.setData([], [])
        self._drawdown_curve.setData([], [])
        self._profit_bar.setOpts(x=[], height=[])
        self._loss_bar.setOpts(x=[], height=[])
        self._dist_curve.setData([], [])

    def set_data(self, df) -> None:
        if df is None:
            return

        self._dates.clear()
        for n, date in enumerate(df.index):
            self._dates[n] = date

        self._balance_curve.setData(df["balance"])
        self._drawdown_curve.setData(df["drawdown"])

        profit_x, profit_h = [], []
        loss_x, loss_h = [], []
        for i, pnl in enumerate(df["net_pnl"]):
            if pnl >= 0:
                profit_x.append(i)
                profit_h.append(pnl)
            else:
                loss_x.append(i)
                loss_h.append(pnl)

        self._profit_bar.setOpts(x=profit_x, height=profit_h)
        self._loss_bar.setOpts(x=loss_x, height=loss_h)

        hist, x = np.histogram(df["net_pnl"], bins="auto")
        self._dist_curve.setData(x[:-1], hist)


# ── 参数优化设置 ───────────────────────────────────────────


class OptimizationSettingEditor(MessageBoxBase):
    """参数优化配置对话框"""

    DISPLAY_NAME_MAP: dict[str, str] = {
        "总收益率": "total_return",
        "夏普比率": "sharpe_ratio",
        "收益回撤比": "return_drawdown_ratio",
        "日均盈亏": "daily_net_pnl",
    }

    def __init__(self, class_name: str, params: BaseParams, parent=None) -> None:
        super().__init__(parent)

        self._class_name = class_name
        self._params = params
        self._edits: dict[str, dict] = {}
        self._use_ga: bool = False

        self._init_ui()

    def _init_ui(self) -> None:
        self.widget.setMinimumWidth(500)

        title = SubtitleLabel(f"优化参数配置：{self._class_name}", self)
        self.viewLayout.addWidget(title)

        grid = QGridLayout()

        # 优化目标
        self._target_combo = ComboBox(self)
        self._target_combo.addItems(list(self.DISPLAY_NAME_MAP.keys()))
        grid.addWidget(BodyLabel("优化目标", self), 0, 0)
        grid.addWidget(self._target_combo, 0, 1, 1, 3)

        # 进程上限
        self._worker_line = LineEdit(self)
        self._worker_line.setText("0")
        self._worker_line.setToolTip("设为 0 则自动根据 CPU 核心数启动")
        grid.addWidget(BodyLabel("进程上限", self), 1, 0)
        grid.addWidget(self._worker_line, 1, 1, 1, 3)

        # 优化模式
        self._mode_combo = ComboBox(self)
        self._mode_combo.addItems(["多进程优化", "遗传算法优化"])
        grid.addWidget(BodyLabel("优化模式", self), 2, 0)
        grid.addWidget(self._mode_combo, 2, 1, 1, 3)

        # 参数表头
        grid.addWidget(BodyLabel("参数", self), 3, 0)
        grid.addWidget(BodyLabel("开始", self), 3, 1)
        grid.addWidget(BodyLabel("步进", self), 3, 2)
        grid.addWidget(BodyLabel("结束", self), 3, 3)

        validator = QDoubleValidator()
        row = 4

        for name, field_info in self._params.model_fields.items():
            field_type = field_info.annotation
            if field_type not in (int, float):
                continue

            value = getattr(self._params, name)
            field_title = field_info.title or name

            start_edit = LineEdit(self)
            start_edit.setText(str(value))
            start_edit.setValidator(validator)

            step_edit = LineEdit(self)
            step_edit.setText("1")
            step_edit.setValidator(validator)

            end_edit = LineEdit(self)
            end_edit.setText(str(value))
            end_edit.setValidator(validator)

            grid.addWidget(BodyLabel(field_title, self), row, 0)
            grid.addWidget(start_edit, row, 1)
            grid.addWidget(step_edit, row, 2)
            grid.addWidget(end_edit, row, 3)

            self._edits[name] = {
                "type": field_type,
                "start": start_edit,
                "step": step_edit,
                "end": end_edit,
            }
            row += 1

        scroll_widget = QWidget()
        scroll_widget.setLayout(grid)

        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_widget)
        scroll.setMinimumHeight(300)

        self.viewLayout.addWidget(scroll)

        self.yesButton.setText("开始优化")
        self.cancelButton.setText("取消")

    @property
    def target_display(self) -> str:
        return self._target_combo.currentText()

    def get_setting(self) -> tuple[OptimizationSetting, bool, int]:
        """获取优化配置"""
        optimization_setting = OptimizationSetting()

        target_name = self.DISPLAY_NAME_MAP[self._target_combo.currentText()]
        optimization_setting.set_target(target_name)

        for name, d in self._edits.items():
            type_ = d["type"]
            start_value = type_(d["start"].text())
            step_value = type_(d["step"].text())
            end_value = type_(d["end"].text())

            if start_value == end_value:
                optimization_setting.add_parameter(name, start_value)
            else:
                optimization_setting.add_parameter(
                    name, start_value, end_value, step_value,
                )

        use_ga = self._mode_combo.currentIndex() == 1
        max_workers = int(self._worker_line.text() or "0")
        return optimization_setting, use_ga, max_workers


# ── 优化结果窗口 ───────────────────────────────────────────


class OptimizationResultWindow(CursorFixMixin, FluentWidget):
    """参数优化结果窗口（含 CSV 导出）"""

    def __init__(self, result_values: list, target_display: str, parent=None) -> None:
        super().__init__(parent)
        self._result_values = result_values
        self._target_display = target_display
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("参数优化结果")
        self.resize(1100, 600)

        self.titleBar.setFixedHeight(48)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        content = QWidget(self)
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(content)

        # 结果表格
        table = TableWidget(self)
        table.setColumnCount(2)
        table.setRowCount(len(self._result_values))
        table.setHorizontalHeaderLabels(["参数", self._target_display])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents,
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        for n, tp in enumerate(self._result_values):
            setting, target_value, _ = tp
            setting_cell = QTableWidgetItem(str(setting))
            target_cell = QTableWidgetItem(f"{target_value:.2f}")
            setting_cell.setTextAlignment(Qt.AlignCenter)
            target_cell.setTextAlignment(Qt.AlignCenter)
            table.setItem(n, 0, setting_cell)
            table.setItem(n, 1, target_cell)

        content_layout.addWidget(table)

        # 导出按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_save = PushButton("导出 CSV", self)
        btn_save.clicked.connect(lambda: self._save_csv(table))
        btn_layout.addWidget(btn_save)
        content_layout.addLayout(btn_layout)

        self._apply_style(content)
        qconfig.themeChanged.connect(lambda: self._apply_style(content))

    def _save_csv(self, table: TableWidget) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存数据", "", "CSV(*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["参数", self._target_display])
            for tp in self._result_values:
                setting, target_value, _ = tp
                writer.writerow([str(setting), str(target_value)])

    @staticmethod
    def _apply_style(widget: QWidget) -> None:
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(widget, ["common.qss", "window.qss"], theme)


# ── 回测结果窗口（成交 / 委托 / 每日盈亏） ─────────────────


class BacktestResultWindow(CursorFixMixin, FluentWidget):
    """通用回测结果展示窗口"""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._title = title
        self._updated = False
        self._table: TableWidget | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(self._title)
        self.resize(1100, 600)

        self.titleBar.setFixedHeight(48)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        content = QWidget(self)
        content.setObjectName("dialogContent")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(content)

        self._apply_style(content)
        qconfig.themeChanged.connect(lambda: self._apply_style(content))

    def setup_table(self, columns: list[tuple[str, str]]) -> None:
        """初始化表格列 [(field_name, display_name), ...]"""
        self._columns = columns
        self._table = TableWidget(self)
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([c[1] for c in columns])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self._content_layout.addWidget(self._table)

    def update_data(self, data_list: list) -> None:
        """填充数据（从对象属性提取）"""
        self._updated = True
        self._table.setRowCount(len(data_list))

        for row, obj in enumerate(reversed(data_list)):
            for col, (field, _) in enumerate(self._columns):
                value = getattr(obj, field, "")
                if isinstance(value, float):
                    text = f"{value:,.2f}"
                elif hasattr(value, "value"):
                    text = value.value
                else:
                    text = str(value)
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, col, cell)

    def clear_data(self) -> None:
        self._updated = False
        if self._table:
            self._table.setRowCount(0)

    def is_updated(self) -> bool:
        return self._updated

    @staticmethod
    def _apply_style(widget: QWidget) -> None:
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(widget, ["common.qss", "window.qss"], theme)


# ── K线图表窗口 ────────────────────────────────────────────


def generate_trade_pairs(trades: list) -> list[dict]:
    """将成交记录配对为开平仓组合"""
    long_trades: list = []
    short_trades: list = []
    trade_pairs: list = []

    for trade in trades:
        trade = copy(trade)

        if trade.direction == Direction.LONG:
            same_direction = long_trades
            opposite_direction = short_trades
        else:
            same_direction = short_trades
            opposite_direction = long_trades

        while trade.volume and opposite_direction:
            open_trade = opposite_direction[0]
            close_volume = min(open_trade.volume, trade.volume)

            trade_pairs.append({
                "open_dt": open_trade.datetime,
                "open_price": open_trade.price,
                "close_dt": trade.datetime,
                "close_price": trade.price,
                "direction": open_trade.direction,
                "volume": close_volume,
            })

            open_trade.volume -= close_volume
            if not open_trade.volume:
                opposite_direction.pop(0)
            trade.volume -= close_volume

        if trade.volume:
            same_direction.append(trade)

    return trade_pairs


class CandleChartWindow(CursorFixMixin, FluentWidget):
    """K线图表窗口（含交易标注）"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updated = False
        self._dt_ix_map: dict = {}
        self._ix_bar_map: dict = {}
        self._high_price: float = 0
        self._low_price: float = 0
        self._price_range: float = 0
        self._items: list = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("回测 K 线图表")
        self.resize(1440, 960)

        self.titleBar.setFixedHeight(48)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        content = QWidget(self)
        content.setObjectName("dialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(content)

        # K线图
        self._chart = ChartWidget()
        self._chart.add_plot("candle", hide_x_axis=True)
        self._chart.add_plot("volume", maximum_height=200)
        self._chart.add_item(CandleItem, "candle", "candle")
        self._chart.add_item(VolumeItem, "volume", "volume")
        self._chart.add_cursor()
        content_layout.addWidget(self._chart)

        # 图例说明
        legend_items = [
            ("红色虚线 —— 盈利交易", "red"),
            ("绿色虚线 —— 亏损交易", "#00FF00"),
            ("黄色向上箭头 —— 买入开仓 Buy", "yellow"),
            ("黄色向下箭头 —— 卖出平仓 Sell", "yellow"),
            ("紫红向下箭头 —— 卖出开仓 Short", "magenta"),
            ("紫红向上箭头 —— 买入平仓 Cover", "magenta"),
        ]
        for i in range(0, len(legend_items), 2):
            hbox = QHBoxLayout()
            hbox.addStretch()
            for text, color in legend_items[i:i + 2]:
                label = QLabel(text)
                label.setStyleSheet(f"color:{color}")
                hbox.addWidget(label)
                hbox.addStretch()
            content_layout.addLayout(hbox)

        self._apply_style(content)
        qconfig.themeChanged.connect(lambda: self._apply_style(content))

    def update_history(self, history: list[BarData]) -> None:
        self._updated = True
        self._chart.update_history(history)

        for ix, bar in enumerate(history):
            self._ix_bar_map[ix] = bar
            self._dt_ix_map[bar.datetime] = ix

            if not self._high_price:
                self._high_price = bar.high_price
                self._low_price = bar.low_price
            else:
                self._high_price = max(self._high_price, bar.high_price)
                self._low_price = min(self._low_price, bar.low_price)

        self._price_range = self._high_price - self._low_price

    def update_trades(self, trades: list[TradeData]) -> None:
        trade_pairs = generate_trade_pairs(trades)
        candle_plot = self._chart.get_plot("candle")
        scatter_data: list = []
        y_adj = self._price_range * 0.001

        for d in trade_pairs:
            open_ix = self._dt_ix_map[d["open_dt"]]
            close_ix = self._dt_ix_map[d["close_dt"]]
            open_price = d["open_price"]
            close_price = d["close_price"]

            # 交易连线
            if d["direction"] == Direction.LONG and close_price >= open_price:
                color = "r"
            elif d["direction"] == Direction.SHORT and close_price <= open_price:
                color = "r"
            else:
                color = "g"

            pen = pg.mkPen(color, width=1.5, style=Qt.DashLine)
            line = pg.PlotCurveItem(
                [open_ix, close_ix], [open_price, close_price], pen=pen,
            )
            self._items.append(line)
            candle_plot.addItem(line)

            # 交易标注
            open_bar = self._ix_bar_map[open_ix]
            close_bar = self._ix_bar_map[close_ix]

            if d["direction"] == Direction.LONG:
                scatter_color = "yellow"
                open_sym, close_sym = "t1", "t"
                open_side, close_side = 1, -1
                open_y = open_bar.low_price
                close_y = close_bar.high_price
            else:
                scatter_color = "magenta"
                open_sym, close_sym = "t", "t1"
                open_side, close_side = -1, 1
                open_y = open_bar.high_price
                close_y = close_bar.low_price

            s_pen = pg.mkPen(QColor(scatter_color))
            s_brush = pg.mkBrush(QColor(scatter_color))

            scatter_data.append({
                "pos": (open_ix, open_y - open_side * y_adj),
                "size": 10, "pen": s_pen, "brush": s_brush, "symbol": open_sym,
            })
            scatter_data.append({
                "pos": (close_ix, close_y - close_side * y_adj),
                "size": 10, "pen": s_pen, "brush": s_brush, "symbol": close_sym,
            })

            # 成交量文字
            volume = d["volume"]
            text_color = QColor(scatter_color)
            for ix, y, side in [
                (open_ix, open_y, open_side),
                (close_ix, close_y, close_side),
            ]:
                text = pg.TextItem(f"[{volume}]", color=text_color, anchor=(0.5, 0.5))
                text.setPos(ix, y - side * y_adj * 3)
                self._items.append(text)
                candle_plot.addItem(text)

        if scatter_data:
            scatter = pg.ScatterPlotItem(scatter_data)
            self._items.append(scatter)
            candle_plot.addItem(scatter)

    def clear_data(self) -> None:
        self._updated = False
        candle_plot = self._chart.get_plot("candle")
        for item in self._items:
            candle_plot.removeItem(item)
        self._items.clear()
        self._chart.clear_all()
        self._dt_ix_map.clear()
        self._ix_bar_map.clear()
        self._high_price = 0
        self._low_price = 0
        self._price_range = 0

    def is_updated(self) -> bool:
        return self._updated

    @staticmethod
    def _apply_style(widget: QWidget) -> None:
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(widget, ["common.qss", "window.qss"], theme)


# ── 成交/委托/每日结果列定义 ───────────────────────────────

TRADE_COLUMNS: list[tuple[str, str]] = [
    ("tradeid", "成交号"),
    ("orderid", "委托号"),
    ("symbol", "代码"),
    ("exchange", "交易所"),
    ("direction", "方向"),
    ("offset", "开平"),
    ("price", "价格"),
    ("volume", "数量"),
    ("datetime", "时间"),
]

ORDER_COLUMNS: list[tuple[str, str]] = [
    ("orderid", "委托号"),
    ("symbol", "代码"),
    ("exchange", "交易所"),
    ("type", "类型"),
    ("direction", "方向"),
    ("offset", "开平"),
    ("price", "价格"),
    ("volume", "总数量"),
    ("traded", "已成交"),
    ("status", "状态"),
    ("datetime", "时间"),
]

DAILY_COLUMNS: list[tuple[str, str]] = [
    ("date", "日期"),
    ("trade_count", "成交笔数"),
    ("start_pos", "开盘持仓"),
    ("end_pos", "收盘持仓"),
    ("turnover", "成交额"),
    ("commission", "手续费"),
    ("slippage", "滑点"),
    ("trading_pnl", "交易盈亏"),
    ("holding_pnl", "持仓盈亏"),
    ("total_pnl", "总盈亏"),
    ("net_pnl", "净盈亏"),
]


# ── 主窗口 ─────────────────────────────────────────────────


class BacktestWindow(CursorFixMixin, FluentWidget):
    """CTA 回测窗口（三栏布局）"""

    _signal_log = Signal(Event)
    _signal_finished = Signal(Event)
    _signal_opt_finished = Signal(Event)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._engine: BacktesterEngine | None = None
        self._settings: dict[str, BaseParams] = {}
        self._target_display: str = ""

        self._init_ui()
        self._register_events()
        self._init_engine()
        self._load_backtesting_setting()

    # ── 初始化 ──

    def _init_ui(self) -> None:
        self.setWindowTitle("CTA 回测")
        self.resize(1840, 960)
        self.setMinimumWidth(1200)

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

        content_layout = QHBoxLayout(self._content_widget)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self._content_widget)

        self._apply_content_style()
        qconfig.themeChanged.connect(self._apply_content_style)

        # ── 左栏：参数 + 按钮 ──
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # 策略选择
        self._class_combo = ComboBox(self)
        form.addRow(BodyLabel("交易策略", self), self._class_combo)

        # 合约选择（收藏品种）
        self._symbol_combo = EditableComboBox(self)
        self._symbol_combo.setPlaceholderText("选择或输入品种代码")
        self._load_favorites()
        form.addRow(BodyLabel("本地代码", self), self._symbol_combo)

        # K线周期
        self._interval_combo = ComboBox(self)
        for interval in Interval:
            self._interval_combo.addItem(interval.value)
        form.addRow(BodyLabel("K线周期", self), self._interval_combo)

        # 日期
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=3 * 365)

        self._start_date = DateEdit(self)
        self._start_date.setDate(QDate(start_dt.year, start_dt.month, start_dt.day))
        form.addRow(BodyLabel("开始日期", self), self._start_date)

        self._end_date = DateEdit(self)
        self._end_date.setDate(QDate.currentDate())
        form.addRow(BodyLabel("结束日期", self), self._end_date)

        # 回测参数（无手续费率）
        self._slippage_line = LineEdit(self)
        self._slippage_line.setText("0.2")
        form.addRow(BodyLabel("交易滑点", self), self._slippage_line)

        self._size_line = LineEdit(self)
        form.addRow(BodyLabel("合约乘数", self), self._size_line)

        self._pricetick_line = LineEdit(self)
        form.addRow(BodyLabel("价格跳动", self), self._pricetick_line)

        self._capital_line = LineEdit(self)
        self._capital_line.setText("1000000")
        form.addRow(BodyLabel("回测资金", self), self._capital_line)

        left_layout.addLayout(form)

        # 操作按钮
        btn_backtest = PrimaryPushButton("开始回测", self)
        btn_backtest.clicked.connect(self._start_backtesting)
        btn_backtest.setFixedHeight(36)
        left_layout.addWidget(btn_backtest)

        btn_reload = PushButton("策略重载", self)
        btn_reload.clicked.connect(self._reload_strategy_class)
        btn_reload.setFixedHeight(36)
        left_layout.addWidget(btn_reload)

        left_layout.addStretch()

        # 结果按钮
        result_grid = QGridLayout()

        self._trade_btn = PushButton("成交记录", self)
        self._trade_btn.clicked.connect(self._show_trades)
        self._trade_btn.setEnabled(False)
        result_grid.addWidget(self._trade_btn, 0, 0)

        self._order_btn = PushButton("委托记录", self)
        self._order_btn.clicked.connect(self._show_orders)
        self._order_btn.setEnabled(False)
        result_grid.addWidget(self._order_btn, 0, 1)

        self._daily_btn = PushButton("每日盈亏", self)
        self._daily_btn.clicked.connect(self._show_daily)
        self._daily_btn.setEnabled(False)
        result_grid.addWidget(self._daily_btn, 1, 0)

        self._candle_btn = PushButton("K线图表", self)
        self._candle_btn.clicked.connect(self._show_candle)
        self._candle_btn.setEnabled(False)
        result_grid.addWidget(self._candle_btn, 1, 1)

        left_layout.addLayout(result_grid)

        left_layout.addStretch()

        # 优化按钮
        btn_optimize = PushButton("参数优化", self)
        btn_optimize.clicked.connect(self._start_optimization)
        btn_optimize.setFixedHeight(36)
        left_layout.addWidget(btn_optimize)

        self._result_btn = PushButton("优化结果", self)
        self._result_btn.clicked.connect(self._show_optimization_result)
        self._result_btn.setEnabled(False)
        self._result_btn.setFixedHeight(36)
        left_layout.addWidget(self._result_btn)

        left_layout.addStretch()

        content_layout.addWidget(left_widget)

        # ── 中栏：统计 + 日志 ──
        middle_widget = QWidget(self)
        middle_layout = QVBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        self._statistics = StatisticsMonitor(self)
        middle_layout.addWidget(self._statistics, 3)

        self._log_edit = TextEdit(self)
        self._log_edit.setReadOnly(True)
        middle_layout.addWidget(self._log_edit, 2)

        content_layout.addWidget(middle_widget)

        # ── 右栏：图表 ──
        self._chart = BacktesterChart(self)
        content_layout.addWidget(self._chart, 1)

        # 列宽比例
        content_layout.setStretch(0, 0)  # 左栏固定
        content_layout.setStretch(1, 1)  # 中栏
        content_layout.setStretch(2, 2)  # 右栏

        # 信号连接（所有控件创建完成后）
        self._symbol_combo.currentIndexChanged.connect(self._on_symbol_changed)
        self._on_symbol_changed()

        # 结果子窗口（延迟创建）
        self._trade_window: BacktestResultWindow | None = None
        self._order_window: BacktestResultWindow | None = None
        self._daily_window: BacktestResultWindow | None = None
        self._candle_window: CandleChartWindow | None = None
        self._opt_result_window: OptimizationResultWindow | None = None

    @staticmethod
    def _make_vt_symbol(contract: dict) -> str:
        """从合约配置构造完整的本地代码（交易所格式 + 后缀）"""
        symbol_std = contract.get("vt_symbol", "")
        exchange_str = contract.get("exchange", "")
        if not symbol_std or not exchange_str:
            return ""
        exchange = Exchange(exchange_str)
        exchange_symbol = SymbolConverter.to_exchange(symbol_std, exchange)
        return f"{exchange_symbol}.{exchange_str}"

    def _load_favorites(self) -> None:
        """加载收藏品种到合约下拉"""
        from guanlan.core.setting import contract as contract_setting

        contracts = contract_setting.load_contracts()
        favorites = contract_setting.load_favorites()

        for key in favorites:
            c = contracts.get(key, {})
            name = c.get("name", key)
            vt_symbol = self._make_vt_symbol(c)
            if not vt_symbol:
                continue
            self._symbol_combo.addItem(f"{name}  {vt_symbol}", userData=key)

    def _on_symbol_changed(self) -> None:
        """品种切换时自动填充合约乘数和价格跳动"""
        from guanlan.core.setting import contract as contract_setting

        idx = self._symbol_combo.currentIndex()
        if idx < 0:
            return

        key = self._symbol_combo.itemData(idx)
        if not key:
            return

        contracts = contract_setting.load_contracts()
        c = contracts.get(key, {})
        if c:
            self._size_line.setText(str(c.get("size", "")))
            self._pricetick_line.setText(str(c.get("tick", "")))

    def _apply_content_style(self) -> None:
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, ["common.qss", "window.qss"], theme)

    # ── 事件注册 ──

    def _register_events(self) -> None:
        from guanlan.core.app import AppEngine
        event_engine: EventEngine = AppEngine.instance().event_engine

        self._signal_log.connect(self._process_log_event)
        self._signal_finished.connect(self._process_finished_event)
        self._signal_opt_finished.connect(self._process_opt_finished_event)

        self._log_handler = self._signal_log.emit
        self._finished_handler = self._signal_finished.emit
        self._opt_finished_handler = self._signal_opt_finished.emit

        event_engine.register(EVENT_BACKTESTER_LOG, self._log_handler)
        event_engine.register(EVENT_BACKTESTER_FINISHED, self._finished_handler)
        event_engine.register(EVENT_BACKTESTER_OPT_FINISHED, self._opt_finished_handler)

    def _unregister_events(self) -> None:
        try:
            from guanlan.core.app import AppEngine
            event_engine: EventEngine = AppEngine.instance().event_engine
            event_engine.unregister(EVENT_BACKTESTER_LOG, self._log_handler)
            event_engine.unregister(EVENT_BACKTESTER_FINISHED, self._finished_handler)
            event_engine.unregister(EVENT_BACKTESTER_OPT_FINISHED, self._opt_finished_handler)
        except Exception:
            pass

    # ── 引擎初始化 ──

    def _init_engine(self) -> None:
        self._engine = BacktesterEngine()
        self._engine.init_engine()
        self._init_strategy_settings()

    def _init_strategy_settings(self) -> None:
        """加载策略类并填充下拉"""
        display_map = self._engine.get_strategy_class_display_names()
        items = sorted(display_map.items(), key=lambda x: x[1])

        self._class_combo.clear()
        self._settings.clear()

        for class_name, display_name in items:
            self._class_combo.addItem(display_name, userData=class_name)
            self._settings[class_name] = self._engine.get_default_setting(class_name)

    # ── 配置持久化 ──

    def _load_backtesting_setting(self) -> None:
        setting = load_json_file(SETTING_FILENAME)
        if not setting:
            return

        # 策略
        class_name = setting.get("class_name", "")
        if class_name:
            idx = self._class_combo.findData(class_name)
            if idx >= 0:
                self._class_combo.setCurrentIndex(idx)

        # 合约 — 通过 userData(key) 查找合约数据匹配完整 vt_symbol
        vt_symbol = setting.get("vt_symbol", "")
        if vt_symbol:
            from guanlan.core.setting import contract as contract_setting
            contracts = contract_setting.load_contracts()
            matched = False
            for i in range(self._symbol_combo.count()):
                key = self._symbol_combo.itemData(i)
                if key:
                    c = contracts.get(key, {})
                    if self._make_vt_symbol(c) == vt_symbol:
                        self._symbol_combo.setCurrentIndex(i)
                        matched = True
                        break
            if not matched:
                self._symbol_combo.setCurrentText(vt_symbol)

        # 周期
        interval = setting.get("interval", "")
        if interval:
            idx = self._interval_combo.findText(interval)
            if idx >= 0:
                self._interval_combo.setCurrentIndex(idx)

        # 日期
        start_str = setting.get("start", "")
        if start_str:
            self._start_date.setDate(QDate.fromString(start_str, "yyyy-MM-dd"))

        # 参数
        self._slippage_line.setText(str(setting.get("slippage", "0.2")))
        if "size" in setting:
            self._size_line.setText(str(setting["size"]))
        if "pricetick" in setting:
            self._pricetick_line.setText(str(setting["pricetick"]))
        self._capital_line.setText(str(setting.get("capital", "1000000")))

    def _save_backtesting_setting(
        self, class_name: str, vt_symbol: str, interval: str,
        start: datetime, slippage: float, size: float,
        pricetick: float, capital: float,
    ) -> None:
        save_json_file(SETTING_FILENAME, {
            "class_name": class_name,
            "vt_symbol": vt_symbol,
            "interval": interval,
            "start": start.strftime("%Y-%m-%d"),
            "slippage": slippage,
            "size": size,
            "pricetick": pricetick,
            "capital": capital,
        })

    # ── 事件处理 ──

    def _process_log_event(self, event: Event) -> None:
        msg = event.data
        timestamp = beijing_now().strftime("%H:%M:%S")
        self._log_edit.append(f"{timestamp}\t{msg}")

    def _process_finished_event(self, event: Event) -> None:
        statistics = self._engine.get_result_statistics()
        self._statistics.set_data(statistics)

        df = self._engine.get_result_df()
        self._chart.set_data(df)

        self._trade_btn.setEnabled(True)
        self._order_btn.setEnabled(True)
        self._daily_btn.setEnabled(True)

        # Tick 模式不支持 K 线显示
        interval = self._interval_combo.currentText()
        if interval != Interval.TICK.value:
            self._candle_btn.setEnabled(True)

    def _process_opt_finished_event(self, event: Event) -> None:
        self._write_log("请点击[优化结果]按钮查看")
        self._result_btn.setEnabled(True)

    def _write_log(self, msg: str) -> None:
        timestamp = beijing_now().strftime("%H:%M:%S")
        self._log_edit.append(f"{timestamp}\t{msg}")

    # ── 回测 ──

    def _get_vt_symbol(self) -> str:
        """获取当前完整本地代码（含交易所后缀）"""
        idx = self._symbol_combo.currentIndex()
        if idx >= 0:
            key = self._symbol_combo.itemData(idx)
            if key:
                from guanlan.core.setting import contract as contract_setting
                contracts = contract_setting.load_contracts()
                c = contracts.get(key, {})
                vt = self._make_vt_symbol(c)
                if vt:
                    return vt
        return self._symbol_combo.currentText()

    def _start_backtesting(self) -> None:
        idx = self._class_combo.currentIndex()
        if idx < 0:
            self._write_log("请选择要回测的策略")
            return

        class_name = self._class_combo.itemData(idx)
        vt_symbol = self._get_vt_symbol()
        interval = self._interval_combo.currentText()
        start = self._start_date.dateTime().toPython()
        end = self._end_date.dateTime().toPython()

        try:
            slippage = float(self._slippage_line.text())
            size = int(float(self._size_line.text()))
            pricetick = float(self._pricetick_line.text())
            capital = int(float(self._capital_line.text()))
        except ValueError:
            self._write_log("参数输入错误，请检查数值字段")
            return

        # 校验合约代码
        if "." not in vt_symbol:
            self._write_log("本地代码缺失交易所后缀，请检查")
            return

        # 保存参数
        self._save_backtesting_setting(
            class_name, vt_symbol, interval, start,
            slippage, size, pricetick, capital,
        )

        # 策略参数编辑
        params = self._settings.get(class_name)
        if params is None:
            self._write_log(f"策略 {class_name} 未找到")
            return

        from guanlan.ui.view.window.cta import SettingEditor
        editor = SettingEditor(params=copy(params), parent=self)
        if not editor.exec():
            return

        setting = editor.get_setting()

        # 启动回测
        result = self._engine.start_backtesting(
            class_name, vt_symbol, interval, start, end,
            slippage, size, pricetick, capital, setting,
        )

        if result:
            self._statistics.clear_data()
            self._chart.clear_data()
            self._trade_btn.setEnabled(False)
            self._order_btn.setEnabled(False)
            self._daily_btn.setEnabled(False)
            self._candle_btn.setEnabled(False)

            # 清除子窗口数据
            if self._trade_window:
                self._trade_window.clear_data()
            if self._order_window:
                self._order_window.clear_data()
            if self._daily_window:
                self._daily_window.clear_data()
            if self._candle_window:
                self._candle_window.clear_data()

    # ── 参数优化 ──

    def _start_optimization(self) -> None:
        idx = self._class_combo.currentIndex()
        if idx < 0:
            self._write_log("请选择要优化的策略")
            return

        class_name = self._class_combo.itemData(idx)
        vt_symbol = self._get_vt_symbol()
        interval = self._interval_combo.currentText()
        start = self._start_date.dateTime().toPython()
        end = self._end_date.dateTime().toPython()

        try:
            slippage = float(self._slippage_line.text())
            size = int(float(self._size_line.text()))
            pricetick = float(self._pricetick_line.text())
            capital = int(float(self._capital_line.text()))
        except ValueError:
            self._write_log("参数输入错误，请检查数值字段")
            return

        params = self._settings.get(class_name)
        if params is None:
            self._write_log(f"策略 {class_name} 未找到")
            return

        editor = OptimizationSettingEditor(class_name, params, self)
        if not editor.exec():
            return

        optimization_setting, use_ga, max_workers = editor.get_setting()
        self._target_display = editor.target_display

        result = self._engine.start_optimization(
            class_name, vt_symbol, interval, start, end,
            slippage, size, pricetick, capital,
            optimization_setting, use_ga, max_workers,
        )

        if result:
            self._result_btn.setEnabled(False)

    def _show_optimization_result(self) -> None:
        result_values = self._engine.get_result_values()
        if not result_values:
            self._write_log("暂无优化结果数据")
            return

        self._opt_result_window = OptimizationResultWindow(
            result_values, self._target_display, self,
        )
        self._opt_result_window.show()

    # ── 结果展示 ──

    def _show_trades(self) -> None:
        if not self._trade_window:
            self._trade_window = BacktestResultWindow("回测成交记录", self)
            self._trade_window.setup_table(TRADE_COLUMNS)

        if not self._trade_window.is_updated():
            trades = self._engine.get_all_trades()
            self._trade_window.update_data(trades)

        self._trade_window.show()

    def _show_orders(self) -> None:
        if not self._order_window:
            self._order_window = BacktestResultWindow("回测委托记录", self)
            self._order_window.setup_table(ORDER_COLUMNS)

        if not self._order_window.is_updated():
            orders = self._engine.get_all_orders()
            self._order_window.update_data(orders)

        self._order_window.show()

    def _show_daily(self) -> None:
        if not self._daily_window:
            self._daily_window = BacktestResultWindow("回测每日盈亏", self)
            self._daily_window.setup_table(DAILY_COLUMNS)

        if not self._daily_window.is_updated():
            results = self._engine.get_all_daily_results()
            self._daily_window.update_data(results)

        self._daily_window.show()

    def _show_candle(self) -> None:
        if not self._candle_window:
            self._candle_window = CandleChartWindow(self)

        if not self._candle_window.is_updated():
            history = self._engine.get_history_data()
            self._candle_window.update_history(history)

            trades = self._engine.get_all_trades()
            self._candle_window.update_trades(trades)

        self._candle_window.show()

    # ── 策略重载 ──

    def _reload_strategy_class(self) -> None:
        current = self._class_combo.currentData()
        self._engine.reload_strategy_class()
        self._init_strategy_settings()

        if current:
            idx = self._class_combo.findData(current)
            if idx >= 0:
                self._class_combo.setCurrentIndex(idx)

        InfoBar.success(
            "提示", "策略类已重载",
            parent=self, position=InfoBarPosition.TOP, duration=2000,
        )

    # ── 窗口显示 ──

    def show(self) -> None:
        super().show()

    # closeEvent 由 CursorFixMixin 提供（隐藏窗口 + 重置按钮状态）
