# -*- coding: utf-8 -*-
"""
观澜量化 - 辅助交易

策略计算 → 信号许可 → 人工确认执行。
窗口绑定策略实例，策略输出方向/强度/提示控制交易按钮，
强制执行交易纪律。

Author: 海山观澜
"""

from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QHeaderView, QTableWidgetItem, QAbstractItemView,
    QStackedWidget,
)

from qfluentwidgets import (
    FluentWidget, FluentIcon,
    PushButton, PrimaryPushButton,
    BodyLabel, SubtitleLabel,
    ComboBox, EditableComboBox, SpinBox, LineEdit,
    TableWidget, SegmentedWidget,
    SimpleCardWidget, ProgressRing,
    InfoBar, InfoBarPosition,
    isDarkTheme, qconfig,
)

from vnpy.trader.event import EVENT_TICK, EVENT_ORDER
from vnpy.trader.object import TickData, OrderData, SubscribeRequest
from vnpy.trader.constant import Exchange, Direction, Offset, OrderType, Status
from vnpy.trader.utility import BarGenerator, get_digits

from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.cta.template import CtaTemplate, BaseVars
from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.ui.view.window.cta import SettingEditor


class PriceType(Enum):
    """价格类型"""
    LATEST = "最新价"
    OPPONENT = "对手价"
    OVER = "超价"
    QUEUE = "排队价"


APP_REFERENCE = "辅助交易"


# ── 信号卡片 ──────────────────────────────────────────


class SignalCard(SimpleCardWidget):
    """信号卡片

    ProgressRing 仪表 + 方向大字 + 建议信息 + 提示文字。
    卡片边框颜色随信号方向和强度动态变化。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("signalCard")
        self.setBorderRadius(8)
        self.setFixedHeight(90)

        self._direction: int = 0
        self._strength: int = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        # 左侧：方向 + 提示（垂直居中）
        left_layout = QVBoxLayout()
        left_layout.setSpacing(6)

        left_layout.addStretch(1)

        self._direction_label = SubtitleLabel("— 观望", self)
        self._direction_label.setObjectName("directionLabel")
        left_layout.addWidget(self._direction_label)

        self._tip_label = BodyLabel("", self)
        self._tip_label.setObjectName("tipLabel")
        left_layout.addWidget(self._tip_label)

        left_layout.addStretch(1)
        layout.addLayout(left_layout, 1)

        # 中央：ProgressRing 信号仪表
        self._ring = ProgressRing(self, useAni=False)
        self._ring.setFixedSize(64, 64)
        self._ring.setRange(0, 100)
        self._ring.setValue(0)
        self._ring.setTextVisible(True)
        self._ring.setStrokeWidth(6)
        self._ring.setCustomBarColor(
            QColor(128, 128, 128), QColor(128, 128, 128)
        )
        layout.addWidget(self._ring)

        # 右侧：建议信息（两行，垂直居中）
        right_layout = QVBoxLayout()
        right_layout.setSpacing(6)

        right_layout.addStretch(1)

        self._suggest_price_label = BodyLabel("", self)
        self._suggest_price_label.setObjectName("suggestLabel")
        self._suggest_price_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_layout.addWidget(self._suggest_price_label)

        self._suggest_volume_label = BodyLabel("", self)
        self._suggest_volume_label.setObjectName("suggestLabel")
        self._suggest_volume_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_layout.addWidget(self._suggest_volume_label)

        right_layout.addStretch(1)
        layout.addLayout(right_layout, 1)

    def update_signal(self, direction: int, strength: int, tip: str) -> None:
        """更新信号显示"""
        self._direction = direction
        self._strength = strength

        # 更新 ProgressRing
        self._ring.setValue(strength)

        # 方向文字和颜色
        if direction >= 1:
            color = QColor(192, 64, 64)
            self._direction_label.setText("▲ 多头")
        elif direction <= -1:
            color = QColor(64, 160, 64)
            self._direction_label.setText("▼ 空头")
        else:
            color = QColor(128, 128, 128)
            self._direction_label.setText("— 观望")

        # 更新 Ring 颜色
        self._ring.setCustomBarColor(color, color)

        # 更新方向标签颜色
        self._direction_label.setStyleSheet(
            f"#directionLabel {{ color: {color.name()}; }}"
        )

        # 提示文字
        self._tip_label.setText(tip)

        # 氛围边框：强度影响透明度
        alpha = max(0.15, strength / 100 * 0.6)
        if direction >= 1:
            border_color = f"rgba(192, 64, 64, {alpha})"
            border_width = 2
        elif direction <= -1:
            border_color = f"rgba(64, 160, 64, {alpha})"
            border_width = 2
        else:
            border_color = "rgba(128, 128, 128, 0.15)"
            border_width = 1

        self.setStyleSheet(
            f"#signalCard {{ border: {border_width}px solid {border_color}; "
            f"border-radius: 8px; }}"
        )

    def update_suggest(self, suggest_price: float, suggest_volume: int) -> None:
        """更新建议信息"""
        if suggest_price > 0 or suggest_volume > 0:
            self._suggest_price_label.setText(f"建议价: {suggest_price}")
            self._suggest_volume_label.setText(f"上限: {suggest_volume}手")
        else:
            self._suggest_price_label.setText("")
            self._suggest_volume_label.setText("")

    def reset(self) -> None:
        """重置"""
        self.update_signal(0, 0, "")
        self.update_suggest(0, 0)


# ── 统计数据 ──────────────────────────────────────────


class TradeStats:
    """交易统计"""

    def __init__(self) -> None:
        self.gateway_name: str = ""
        self.count_buy_open: int = 0
        self.count_sell_open: int = 0
        self.count_close: int = 0
        self.profit: float = 0
        self.count_profit: int = 0
        self.max_profit: float = 0
        self.max_loss: float = 0


class StatsMonitor(TableWidget):
    """交易统计表"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        labels = ["多开", "空开", "平仓", "总盈亏", "盈利次", "最大获利", "最大亏损"]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        self.setRowCount(1)

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFixedHeight(self.horizontalHeader().height() + self.rowHeight(0) + 4)

        self._cells: list[QTableWidgetItem] = []
        for col in range(len(labels)):
            cell = QTableWidgetItem("0")
            cell.setTextAlignment(Qt.AlignCenter)
            self.setItem(0, col, cell)
            self._cells.append(cell)

    def update_stats(self, stats: TradeStats) -> None:
        """更新统计数据"""
        self._cells[0].setText(str(stats.count_buy_open))
        self._cells[1].setText(str(stats.count_sell_open))
        self._cells[2].setText(str(stats.count_close))
        self._cells[3].setText(f"{stats.profit:.1f}")
        self._cells[4].setText(str(stats.count_profit))
        self._cells[5].setText(f"{stats.max_profit:.1f}")
        self._cells[6].setText(f"{stats.max_loss:.1f}")


# ── 委托监控 ──────────────────────────────────────────


class OrderMonitor(TableWidget):
    """活跃委托监控（双击撤单）"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        labels = ["委托号", "方向", "开平", "价格", "数量", "状态", "时间"]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setToolTip("双击撤单")
        self.itemDoubleClicked.connect(self._on_cancel)

        self._orders: dict[str, int] = {}  # vt_orderid → row
        self._main_engine = None

    def set_main_engine(self, main_engine) -> None:
        self._main_engine = main_engine

    def process_order(self, order: OrderData) -> None:
        """处理委托事件"""
        vt_orderid = order.vt_orderid

        # 终态：移除行
        if order.status in (Status.ALLTRADED, Status.CANCELLED, Status.REJECTED):
            row = self._orders.pop(vt_orderid, None)
            if row is not None:
                # 行号可能因删除偏移，按 orderid 查找
                for r in range(self.rowCount()):
                    if self.item(r, 0) and self.item(r, 0).text() == order.orderid:
                        self.removeRow(r)
                        break
            return

        # 活跃委托：新增或更新
        if vt_orderid not in self._orders:
            row = self.rowCount()
            self.insertRow(row)
            self._orders[vt_orderid] = row

            items = [
                order.orderid,
                order.direction.value,
                order.offset.value,
                str(order.price),
                str(order.volume),
                order.status.value,
                order.datetime.strftime("%H:%M:%S") if order.datetime else "",
            ]
            for col, text in enumerate(items):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignCenter)
                cell.setData(Qt.UserRole, order)
                self.setItem(row, col, cell)

    def _on_cancel(self, item: QTableWidgetItem) -> None:
        """双击撤单"""
        order: OrderData = item.data(Qt.UserRole)
        if order and self._main_engine:
            req = order.create_cancel_request()
            self._main_engine.cancel_order(req, order.gateway_name)

    def clear_all(self) -> None:
        """清空"""
        self.setRowCount(0)
        self._orders.clear()


# ── 主窗口 ──────────────────────────────────────────


class AdvisorTraderWindow(CursorFixMixin, FluentWidget):
    """辅助交易窗口"""

    _signal_tick = Signal(object)
    _signal_order = Signal(object)
    _signal_vars = Signal(object)
    _signal_inited = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        self._event_engine: EventEngine = app.event_engine
        self._main_engine = app.main_engine

        # 策略相关
        self._strategy: CtaTemplate | None = None
        self._bar_generator: BarGenerator | None = None
        self._init_executor = ThreadPoolExecutor(max_workers=1)

        # 交易状态
        self._vt_symbol: str = ""
        self._pos: int = 0
        self._price_digits: int = 0
        self._pricetick: float = 0.01
        self._last_tick: TickData | None = None
        self._buy_price: float = 0
        self._sell_price: float = 0
        self._price_type: PriceType = PriceType.LATEST

        # 统计
        self._stats = TradeStats()

        # 最大持仓上限（策略 suggest_volume 控制）
        self._max_pos: int = 0

        # 未成交开仓挂单量
        self._pending_open_long: int = 0
        self._pending_open_short: int = 0

        # 开仓许可状态（用于检测变化播放音效）
        self._allow_long: bool = False
        self._allow_short: bool = False

        self._init_ui()
        self._register_events()

    def _get_cta_engine(self):
        """获取 CTA 引擎"""
        return self._main_engine.get_engine("CtaStrategy")

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("辅助交易")
        self.resize(380, 480)

        # 标题栏
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
        self._content = QWidget(self)
        self._content.setObjectName("dialogContent")

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(10, 8, 10, 8)
        content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self._content)

        self._apply_style()
        qconfig.themeChanged.connect(self._apply_style)

        # ── 工具栏卡片 ──
        toolbar_card = SimpleCardWidget(self)
        toolbar_card.setObjectName("toolbarCard")
        toolbar_card.setBorderRadius(8)
        toolbar_card_layout = QVBoxLayout(toolbar_card)
        toolbar_card_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_card_layout.setSpacing(6)

        # 第一行：账户 | 合约（各占一半）
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(BodyLabel("账户"))
        self._gateway_combo = ComboBox(self)
        row1.addWidget(self._gateway_combo, 1)

        row1.addWidget(BodyLabel("合约"))
        self._symbol_combo = EditableComboBox(self)
        row1.addWidget(self._symbol_combo, 1)

        toolbar_card_layout.addLayout(row1)

        # 第二行：策略 | 参数 | 初始化 | 启动 | 停止
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        row2.addWidget(BodyLabel("策略"))
        self._strategy_combo = ComboBox(self)
        row2.addWidget(self._strategy_combo, 1)

        self._btn_params = PushButton("参数", self)
        self._btn_params.setEnabled(False)
        self._btn_params.clicked.connect(self._on_edit_params)
        row2.addWidget(self._btn_params)

        self._btn_init = PrimaryPushButton("初始化", self)
        self._btn_init.setEnabled(False)
        self._btn_init.clicked.connect(self._on_init_strategy)
        row2.addWidget(self._btn_init)

        self._btn_start = PrimaryPushButton("启动", self)
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start_strategy)
        row2.addWidget(self._btn_start)

        self._btn_stop = PrimaryPushButton("停止", self)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop_strategy)
        row2.addWidget(self._btn_stop)

        self._btn_chart = PushButton("图表", self)
        self._btn_chart.setIcon(FluentIcon.MARKET)
        self._btn_chart.clicked.connect(self._on_open_chart)
        row2.addWidget(self._btn_chart)

        toolbar_card_layout.addLayout(row2)

        # 第三行：价格
        row3 = QHBoxLayout()
        row3.setSpacing(6)

        row3.addWidget(BodyLabel("价格"))
        self._price_type_combo = ComboBox(self)
        for pt in PriceType:
            self._price_type_combo.addItem(pt.value, userData=pt)
        self._price_type_combo.currentIndexChanged.connect(self._on_price_type_changed)
        row3.addWidget(self._price_type_combo, 1)

        row3.addWidget(BodyLabel("数量"))
        self._volume_spin = SpinBox(self)
        self._volume_spin.setMinimum(1)
        self._volume_spin.setMaximum(100)
        self._volume_spin.setValue(1)
        row3.addWidget(self._volume_spin, 1)

        row3.addWidget(BodyLabel("持仓"))
        self._pos_edit = LineEdit(self)
        self._pos_edit.setObjectName("posEdit")
        self._pos_edit.setReadOnly(True)
        self._pos_edit.setText("0")
        self._pos_edit.setAlignment(Qt.AlignCenter)
        row3.addWidget(self._pos_edit, 1)

        toolbar_card_layout.addLayout(row3)

        content_layout.addWidget(toolbar_card)

        # ── 信号卡片 ──
        self._signal_card = SignalCard(self)
        content_layout.addWidget(self._signal_card)

        # ── 交易按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_buy = PrimaryPushButton("买多\n--", self)
        self._btn_buy.setObjectName("buyButton")
        self._btn_buy.setFixedHeight(60)
        self._btn_buy.setEnabled(False)
        self._btn_buy.clicked.connect(self._send_buy_order)
        btn_layout.addWidget(self._btn_buy)

        self._btn_sell = PrimaryPushButton("卖空\n--", self)
        self._btn_sell.setObjectName("sellButton")
        self._btn_sell.setFixedHeight(60)
        self._btn_sell.setEnabled(False)
        self._btn_sell.clicked.connect(self._send_sell_order)
        btn_layout.addWidget(self._btn_sell)

        self._btn_close = PrimaryPushButton("平仓\n无持仓", self)
        self._btn_close.setObjectName("closeButton")
        self._btn_close.setFixedHeight(60)
        self._btn_close.setEnabled(False)
        self._btn_close.clicked.connect(self._send_close_order)
        btn_layout.addWidget(self._btn_close)

        content_layout.addLayout(btn_layout)

        # ── 底部卡片 ──
        bottom_card = SimpleCardWidget(self)
        bottom_card.setObjectName("bottomCard")
        bottom_card.setBorderRadius(8)
        bottom_card_layout = QVBoxLayout(bottom_card)
        bottom_card_layout.setContentsMargins(8, 8, 8, 8)
        bottom_card_layout.setSpacing(6)

        pivot = SegmentedWidget(self)
        stacked = QStackedWidget(self)

        self._order_monitor = OrderMonitor(self)
        self._order_monitor.set_main_engine(self._main_engine)
        self._order_monitor.setObjectName("orderTab")
        stacked.addWidget(self._order_monitor)

        self._stats_monitor = StatsMonitor(self)
        self._stats_monitor.setObjectName("statsTab")
        stacked.addWidget(self._stats_monitor)

        pivot.addItem(
            routeKey="orderTab", text="委托",
            onClick=lambda: stacked.setCurrentWidget(self._order_monitor),
        )
        pivot.addItem(
            routeKey="statsTab", text="统计",
            onClick=lambda: stacked.setCurrentWidget(self._stats_monitor),
        )
        pivot.setCurrentItem("orderTab")

        bottom_card_layout.addWidget(pivot)
        bottom_card_layout.addWidget(stacked, 1)

        content_layout.addWidget(bottom_card, 1)

        # ── 初始化下拉框数据 ──
        self._load_gateways()
        self._load_favorites()
        self._load_strategy_classes()

        # 下拉框联动
        self._gateway_combo.currentIndexChanged.connect(self._on_symbol_changed)
        self._symbol_combo.currentIndexChanged.connect(self._on_symbol_selected)
        self._symbol_combo.returnPressed.connect(self._on_symbol_input)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_class_changed)

    # ── 样式 ──

    def _apply_style(self) -> None:
        """应用样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(
            self._content,
            ["common.qss", "window.qss", "advisor_trader.qss"],
            theme,
        )

    # ── 下拉框数据加载 ──

    def _load_gateways(self) -> None:
        """加载账户列表"""
        from guanlan.core.app import AppEngine
        self._gateway_combo.addItems(AppEngine.instance().connected_envs)

    def _load_favorites(self) -> None:
        """加载收藏品种"""
        from guanlan.core.setting import contract as contract_setting
        from guanlan.core.utils.symbol_converter import SymbolConverter

        contracts = contract_setting.load_contracts()
        favorites = contract_setting.load_favorites()

        for key in favorites:
            c = contracts.get(key, {})
            name = c.get("name", key)
            vt_symbol = c.get("vt_symbol", "")
            exchange = c.get("exchange", "")
            if not vt_symbol:
                continue
            symbol = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol
            ex_symbol = SymbolConverter.to_exchange(symbol, Exchange(exchange))
            full_vt = f"{ex_symbol}.{exchange}"
            self._symbol_combo.addItem(f"{name}  {ex_symbol}", userData=full_vt)

        self._symbol_combo.setCurrentIndex(-1)

    def _load_strategy_classes(self) -> None:
        """加载策略类列表"""
        cta_engine = self._get_cta_engine()
        if not cta_engine:
            return
        cta_engine.init_engine()
        display_map = cta_engine.get_strategy_class_display_names()
        items = sorted(display_map.items(), key=lambda x: x[1])
        for class_name, display_name in items:
            self._strategy_combo.addItem(display_name, userData=class_name)
        self._strategy_combo.setCurrentIndex(-1)

    # ── 事件注册 ──

    def _register_events(self) -> None:
        """注册事件"""
        self._signal_tick.connect(self._process_tick)
        self._signal_order.connect(self._process_order)
        self._signal_vars.connect(self._on_signal_changed)
        self._signal_inited.connect(self._on_strategy_inited)

        self._tick_handler = lambda e: self._signal_tick.emit(e.data)
        self._order_handler = lambda e: self._signal_order.emit(e.data)

        self._event_engine.register(EVENT_TICK, self._tick_handler)
        self._event_engine.register(EVENT_ORDER, self._order_handler)

    def _unregister_events(self) -> None:
        """注销事件"""
        try:
            self._event_engine.unregister(EVENT_TICK, self._tick_handler)
            self._event_engine.unregister(EVENT_ORDER, self._order_handler)
        except Exception:
            pass

    # ── 下拉框联动 ──

    def _on_symbol_selected(self, index: int) -> None:
        """下拉选择合约（有 userData 的收藏项）"""
        if index < 0:
            return
        if not self._symbol_combo.itemData(index):
            return
        self._on_symbol_changed()

    def _on_symbol_input(self) -> None:
        """手动输入合约代码回车后解析"""
        from guanlan.core.setting import contract as contract_setting

        index = self._symbol_combo.currentIndex()
        if index < 0:
            return
        if self._symbol_combo.itemData(index):
            return

        text = self._symbol_combo.itemText(index)
        resolved = contract_setting.resolve_symbol(text)

        if not resolved:
            self._symbol_combo.blockSignals(True)
            self._symbol_combo.removeItem(index)
            self._symbol_combo.setCurrentIndex(-1)
            self._symbol_combo.blockSignals(False)
            InfoBar.warning(
                "合约未找到", f"无法识别 \"{text}\"",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        name, vt_symbol, _exchange = resolved
        symbol_part = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol
        display = f"{name}  {symbol_part}"

        self._symbol_combo.blockSignals(True)
        self._symbol_combo.removeItem(index)
        self._symbol_combo.addItem(display, userData=vt_symbol)
        self._symbol_combo.setCurrentIndex(self._symbol_combo.count() - 1)
        self._symbol_combo.setText(display)
        self._symbol_combo.blockSignals(False)

        self._on_symbol_changed()

    def _on_symbol_changed(self) -> None:
        """合约或账户变化"""
        idx = self._symbol_combo.currentIndex()
        if idx < 0:
            return

        vt_symbol = self._symbol_combo.itemData(idx)
        if not vt_symbol or vt_symbol == self._vt_symbol:
            return

        # 如果策略正在运行，先停止
        if self._strategy and self._strategy.trading:
            self._on_stop_strategy()

        # 如果已初始化，需要重新初始化
        if self._strategy and self._strategy.inited:
            self._strategy.on_stop()
            self._strategy = None
            self._bar_generator = None

        self._vt_symbol = vt_symbol

        # 查合约信息
        contract = self._main_engine.get_contract(vt_symbol)
        if contract:
            self._price_digits = get_digits(contract.pricetick)
            self._pricetick = contract.pricetick

        # 订阅行情
        from guanlan.core.app import AppEngine
        AppEngine.instance().subscribe(vt_symbol)

        # 重置状态
        self._pos = 0
        self._buy_price = 0
        self._sell_price = 0
        self._last_tick = None
        self._max_pos = 0
        self._pending_open_long = 0
        self._pending_open_short = 0
        self._allow_long = False
        self._allow_short = False
        self._signal_card.reset()
        self._order_monitor.clear_all()
        self._update_buttons(False, False, 0)

        self.setWindowTitle(f"辅助交易 - {self._symbol_combo.currentText()}")

        # 更新按钮状态
        self._update_lifecycle_buttons()

    def _on_strategy_class_changed(self) -> None:
        """策略类变化"""
        # 如果策略正在运行，先停止
        if self._strategy and self._strategy.trading:
            self._on_stop_strategy()

        if self._strategy and self._strategy.inited:
            self._strategy.on_stop()

        self._strategy = None
        self._bar_generator = None
        self._allow_long = False
        self._allow_short = False
        self._signal_card.reset()
        self._update_buttons(False, False, 0)
        self._update_lifecycle_buttons()

    def _on_price_type_changed(self) -> None:
        """价格类型变化"""
        self._price_type = self._price_type_combo.currentData()

    # ── 策略生命周期 ──

    def _update_lifecycle_buttons(self) -> None:
        """更新生命周期按钮状态"""
        has_symbol = bool(self._vt_symbol)
        has_strategy_class = self._strategy_combo.currentIndex() >= 0
        has_gateway = bool(self._gateway_combo.currentText())

        can_init = has_symbol and has_strategy_class and has_gateway
        is_inited = self._strategy is not None and self._strategy.inited
        is_trading = self._strategy is not None and self._strategy.trading

        self._btn_init.setEnabled(can_init and not is_inited)
        self._btn_start.setEnabled(is_inited and not is_trading)
        self._btn_stop.setEnabled(is_trading)
        self._btn_params.setEnabled(is_inited and not is_trading)

        # 合约/策略/账户切换在运行时禁用
        self._symbol_combo.setEnabled(not is_trading)
        self._strategy_combo.setEnabled(not is_trading)
        self._gateway_combo.setEnabled(not is_trading)

    def _on_init_strategy(self) -> None:
        """初始化策略"""
        idx = self._strategy_combo.currentIndex()
        if idx < 0:
            return

        class_name = self._strategy_combo.itemData(idx)
        cta_engine = self._get_cta_engine()
        if not cta_engine or class_name not in cta_engine.classes:
            InfoBar.error(
                "初始化失败", f"找不到策略类 {class_name}",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        if not self._vt_symbol:
            InfoBar.error(
                "初始化失败", "请先选择合约",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        gateway_name = self._gateway_combo.currentText()
        if not gateway_name:
            InfoBar.error(
                "初始化失败", "请先选择账户",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        strategy_class = cta_engine.classes[class_name]
        strategy_name = f"advisor_{id(self)}_{class_name}"

        self._strategy = strategy_class(
            cta_engine, strategy_name, self._vt_symbol, gateway_name
        )
        self._strategy.advisor = True
        self._strategy.set_signal_callback(self._signal_callback)

        # BarGenerator
        self._bar_generator = BarGenerator(self._strategy.on_bar)

        self._btn_init.setEnabled(False)
        self._btn_init.setText("初始化中...")

        # 在线程池中执行初始化（load_bar 可能耗时）
        self._init_executor.submit(self._do_init_strategy)

    def _do_init_strategy(self) -> None:
        """线程池中执行策略初始化"""
        try:
            self._strategy.on_init()
            self._strategy.inited = True
            self._signal_inited.emit()
        except Exception as e:
            # 通过信号通知主线程
            self._signal_inited.emit()

    def _on_strategy_inited(self) -> None:
        """策略初始化完成（主线程回调）"""
        self._btn_init.setText("初始化")
        if self._strategy and self._strategy.inited:
            InfoBar.success(
                "初始化成功", "策略已就绪，请点击启动",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )
        else:
            InfoBar.error(
                "初始化失败", "策略初始化异常",
                parent=self, position=InfoBarPosition.TOP,
            )
            self._strategy = None
            self._bar_generator = None

        self._update_lifecycle_buttons()

    def _on_start_strategy(self) -> None:
        """启动策略"""
        if not self._strategy or not self._strategy.inited:
            return

        self._strategy.on_start()
        self._strategy.trading = True

        InfoBar.success(
            "已启动", "策略开始运行，交易按钮由信号控制",
            parent=self, position=InfoBarPosition.TOP, duration=2000,
        )
        self._update_lifecycle_buttons()

    def _on_stop_strategy(self) -> None:
        """停止策略"""
        if not self._strategy:
            return

        self._strategy.on_stop()
        self._strategy.trading = False

        self._allow_long = False
        self._allow_short = False
        self._signal_card.reset()
        self._update_buttons(False, False, self._pos)
        self._update_lifecycle_buttons()

        InfoBar.info(
            "已停止", "策略已停止，交易按钮已禁用",
            parent=self, position=InfoBarPosition.TOP, duration=2000,
        )

    def _on_edit_params(self) -> None:
        """编辑策略参数"""
        if not self._strategy:
            return

        params = self._strategy.get_params()
        editor = SettingEditor(
            params=params,
            strategy_name=self._strategy.strategy_name,
            parent=self,
        )
        if editor.exec():
            setting = editor.get_setting()
            self._strategy.update_setting(setting)
            InfoBar.success(
                "参数已更新", "需要重新初始化策略使参数生效",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )

    def _on_open_chart(self) -> None:
        """打开图表窗口"""
        from guanlan.ui.view.window.chart import ChartWindow

        chart = ChartWindow(parent=None)
        if self._vt_symbol:
            chart.set_symbol(self._vt_symbol)
        chart.show()

    # ── 信号回调 ──

    def _signal_callback(self, vars: BaseVars) -> None:
        """策略信号回调（EventEngine 线程调用）"""
        self._signal_vars.emit(vars)

    def _on_signal_changed(self, vars: BaseVars) -> None:
        """主线程处理信号更新"""
        self._signal_card.update_signal(vars.direction, vars.strength, vars.tip)
        self._signal_card.update_suggest(vars.suggest_price, vars.suggest_volume)

        # 更新最大持仓上限
        self._max_pos = vars.suggest_volume

        # 根据上限和当前持仓限制开仓手数
        self._clamp_volume_spin()

        # 开仓许可变化时播放提示音
        newly_allowed = (
            (vars.allow_open_long and not self._allow_long)
            or (vars.allow_open_short and not self._allow_short)
        )
        self._allow_long = vars.allow_open_long
        self._allow_short = vars.allow_open_short

        if newly_allowed:
            from guanlan.core.services.sound import play as play_sound
            play_sound("alarm")

        self._update_buttons(vars.allow_open_long, vars.allow_open_short, self._pos)

    # ── Tick 处理 ──

    def _process_tick(self, tick: TickData) -> None:
        """处理 tick 事件"""
        if tick.vt_symbol != self._vt_symbol:
            return

        self._last_tick = tick

        # 计算买卖价
        buy_price = tick.last_price
        sell_price = tick.last_price

        if self._price_type == PriceType.OPPONENT:
            buy_price = tick.ask_price_1
            sell_price = tick.bid_price_1
        elif self._price_type == PriceType.OVER:
            buy_price = tick.ask_price_1 + self._pricetick
            sell_price = tick.bid_price_1 - self._pricetick
        elif self._price_type == PriceType.QUEUE:
            buy_price = tick.bid_price_1
            sell_price = tick.ask_price_1

        self._buy_price = round(buy_price, self._price_digits)
        self._sell_price = round(sell_price, self._price_digits)

        self._update_button_prices()

        # 转发给策略
        if self._strategy and self._strategy.trading:
            self._strategy.on_tick(tick)
            if self._bar_generator:
                self._bar_generator.update_tick(tick)

    # ── 委托处理 ──

    def _process_order(self, order: OrderData) -> None:
        """处理委托事件"""
        if order.reference != APP_REFERENCE:
            return
        if order.vt_symbol != self._vt_symbol:
            return

        from guanlan.core.services.sound import play as play_sound

        # 委托监控表更新
        self._order_monitor.process_order(order)

        # 终态时扣减挂单量
        if order.status in (Status.ALLTRADED, Status.CANCELLED, Status.REJECTED):
            if order.offset == Offset.OPEN:
                if order.direction == Direction.LONG:
                    self._pending_open_long = max(
                        0, self._pending_open_long - order.volume
                    )
                else:
                    self._pending_open_short = max(
                        0, self._pending_open_short - order.volume
                    )

        if order.status == Status.REJECTED:
            InfoBar.error(
                "拒单", f"报单被拒: {order.orderid}",
                parent=self, position=InfoBarPosition.TOP,
            )
            play_sound("error")
            self._enable_order_buttons()

        elif order.status == Status.CANCELLED:
            play_sound("cancel")
            self._enable_order_buttons()

        elif order.status == Status.ALLTRADED:
            # 更新持仓
            if order.offset == Offset.OPEN:
                if order.direction == Direction.LONG:
                    self._pos += order.volume
                    self._stats.count_buy_open += 1
                    play_sound("con_buy")
                else:
                    self._pos -= order.volume
                    self._stats.count_sell_open += 1
                    play_sound("con_sell")
            else:
                if order.direction == Direction.LONG:
                    self._pos += order.volume
                else:
                    self._pos -= order.volume
                self._stats.count_close += 1
                play_sound("con_close")

            self._stats_monitor.update_stats(self._stats)

            # 更新手数：平仓设为持仓量，开仓按上限约束
            self._clamp_volume_spin()
            if self._pos == 0:
                self._volume_spin.setValue(1)
            elif order.offset != Offset.OPEN:
                self._volume_spin.setValue(abs(self._pos))

            self._enable_order_buttons()

        self._update_button_prices()

    def _enable_order_buttons(self) -> None:
        """恢复按钮可点击（用于委托回报后恢复）"""
        if self._strategy and self._strategy.trading:
            v = self._strategy.vars
            self._update_buttons(v.allow_open_long, v.allow_open_short, self._pos)
        else:
            self._update_buttons(False, False, self._pos)

    # ── 按钮状态 ──

    def _update_buttons(self, allow_long: bool, allow_short: bool, pos: int) -> None:
        """根据开仓许可+持仓+上限更新按钮启用状态

        开仓由策略信号控制，平仓有持仓就能平。
        持仓达到上限时禁止同方向继续开仓。
        """
        strategy_running = self._strategy is not None and self._strategy.trading

        if strategy_running:
            # 持仓+挂单达到上限时禁止同方向开仓
            if self._max_pos > 0:
                if pos + self._pending_open_long >= self._max_pos:
                    allow_long = False
                if -pos + self._pending_open_short >= self._max_pos:
                    allow_short = False

            self._btn_buy.setEnabled(allow_long)
            self._btn_sell.setEnabled(allow_short)
            self._btn_close.setEnabled(pos != 0)
        else:
            self._btn_buy.setEnabled(False)
            self._btn_sell.setEnabled(False)
            self._btn_close.setEnabled(False)

    def _clamp_volume_spin(self) -> None:
        """根据最大持仓上限约束开仓手数 SpinBox（含未成交挂单）"""
        if self._max_pos <= 0:
            self._volume_spin.setMaximum(100)
            return

        pending = self._pending_open_long + self._pending_open_short
        remain = self._max_pos - abs(self._pos) - pending
        self._volume_spin.setMaximum(max(remain, 1))
        if self._volume_spin.value() > remain > 0:
            self._volume_spin.setValue(remain)

    def _update_button_prices(self) -> None:
        """更新按钮上的价格文字"""
        # 更新持仓显示
        if self._pos > 0:
            self._pos_edit.setText(f"{self._pos}手多")
        elif self._pos < 0:
            self._pos_edit.setText(f"{abs(self._pos)}手空")
        else:
            self._pos_edit.setText("0")

        if self._pos > 0:
            self._btn_buy.setText(f"加多\n{self._buy_price}")
            self._btn_sell.setText(f"卖空\n{self._sell_price}")
            self._btn_close.setText(f"平仓 {self._pos}手多\n{self._sell_price}")
        elif self._pos < 0:
            self._btn_buy.setText(f"买多\n{self._buy_price}")
            self._btn_sell.setText(f"加空\n{self._sell_price}")
            self._btn_close.setText(f"平仓 {abs(self._pos)}手空\n{self._buy_price}")
        else:
            self._btn_buy.setText(f"买多\n{self._buy_price}")
            self._btn_sell.setText(f"卖空\n{self._sell_price}")
            self._btn_close.setText(f"平仓\n无持仓")

    # ── 下单 ──

    def _send_buy_order(self) -> None:
        """买多下单"""
        self._send_order(Direction.LONG, Offset.OPEN, self._buy_price)

    def _send_sell_order(self) -> None:
        """卖空下单"""
        self._send_order(Direction.SHORT, Offset.OPEN, self._sell_price)

    def _send_close_order(self) -> None:
        """平仓下单"""
        if not self._last_tick:
            return

        if self._pos > 0:
            # 多平
            price = self._sell_price
            direction = Direction.SHORT
        elif self._pos < 0:
            # 空平
            price = self._buy_price
            direction = Direction.LONG
        else:
            return

        self._send_order(direction, Offset.CLOSETODAY, price)

    def _send_order(self, direction: Direction, offset: Offset, price: float) -> None:
        """发送委托"""
        if price <= 0:
            InfoBar.error(
                "委托失败", "价格不能为 0",
                parent=self, position=InfoBarPosition.TOP, duration=1000,
            )
            return

        symbol, exchange_value = self._vt_symbol.rsplit(".", 1)
        gateway_name = self._gateway_combo.currentText()
        if not gateway_name:
            InfoBar.error(
                "委托失败", "请选择交易账户",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        volume = self._volume_spin.value()
        # 平仓时使用持仓量
        if offset != Offset.OPEN:
            volume = abs(self._pos)

        from vnpy.trader.object import OrderRequest
        req = OrderRequest(
            symbol=symbol,
            exchange=Exchange(exchange_value),
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=APP_REFERENCE,
        )

        from guanlan.core.services.sound import play as play_sound
        if direction == Direction.LONG:
            play_sound("buy")
        else:
            play_sound("sell")

        self._main_engine.send_order(req, gateway_name)

        # 下单后累加挂单量并禁用按钮，等回报后恢复
        if offset == Offset.OPEN:
            if direction == Direction.LONG:
                self._pending_open_long += volume
                self._btn_buy.setEnabled(False)
            else:
                self._pending_open_short += volume
                self._btn_sell.setEnabled(False)
        else:
            self._btn_close.setEnabled(False)

    # ── 窗口关闭 ──

    def closeEvent(self, event) -> None:
        """关闭窗口（多实例模式，真正销毁而非隐藏）"""
        # 停止策略
        if self._strategy and self._strategy.trading:
            self._strategy.on_stop()
            self._strategy.trading = False

        self._strategy = None
        self._bar_generator = None

        # 注销事件
        self._unregister_events()

        # 关闭线程池
        self._init_executor.shutdown(wait=False)

        # 接受关闭（不走 CursorFixMixin 的 hide 逻辑）
        event.accept()
