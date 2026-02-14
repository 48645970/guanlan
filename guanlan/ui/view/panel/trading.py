# -*- coding: utf-8 -*-
"""
观澜量化 - 交易面板

嵌入首页的快速交易面板。
直接向 VNPY EventEngine 注册事件，获取完整原始数据。

Author: 海山观澜
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout

from qfluentwidgets import (
    BodyLabel, ComboBox, EditableComboBox, LineEdit, PushButton, CheckBox,
    DoubleSpinBox, SpinBox,
    InfoBar, InfoBarPosition,
)

from vnpy.trader.event import EVENT_TICK, EVENT_ORDER, EVENT_TRADE, EVENT_LOG
from vnpy.trader.object import (
    TickData, OrderData, TradeData, LogData,
    SubscribeRequest, OrderRequest,
)
from vnpy.trader.constant import Exchange, Direction, Offset, OrderType, Status
from vnpy.trader.utility import get_digits

from guanlan.core.setting import contract as contract_setting
from guanlan.core.utils.symbol_converter import SymbolConverter
from guanlan.core.services.sound import play as play_sound


# 期货交易所列表
FUTURES_EXCHANGES: list[Exchange] = [
    Exchange.CFFEX, Exchange.SHFE, Exchange.CZCE,
    Exchange.DCE, Exchange.INE, Exchange.GFEX,
]

# 中文 → 枚举映射
DIRECTION_MAP: dict[str, Direction] = {
    "多": Direction.LONG,
    "空": Direction.SHORT,
}

OFFSET_MAP: dict[str, Offset] = {
    "开": Offset.OPEN,
    "平": Offset.CLOSE,
    "平今": Offset.CLOSETODAY,
    "平昨": Offset.CLOSEYESTERDAY,
}

ORDERTYPE_MAP: dict[str, OrderType] = {
    "限价": OrderType.LIMIT,
    "市价": OrderType.MARKET,
}


class TradingPanel(QWidget):
    """交易面板（嵌入首页）

    直接与 VNPY EventEngine / MainEngine 交互，
    不走 signal_bus 桥接。
    """

    REFERENCE = "手动交易"

    # 跨线程信号
    _signal_tick = Signal(object)
    _signal_order = Signal(object)
    _signal_trade = Signal(object)
    _signal_log = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        self._event_engine = app.event_engine
        self._main_engine = app.main_engine

        self._vt_symbol: str = ""
        self._price_digits: int = 0
        self._manual_orderids: set[str] = set()
        self._pending_reject: bool = False

        self._init_ui()
        self._register_events()

    def _init_ui(self) -> None:
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # 下单区
        layout.addLayout(self._create_order_panel())
        layout.addStretch(1)

    def _create_order_panel(self) -> QGridLayout:
        """创建下单区"""
        grid = QGridLayout()
        grid.setVerticalSpacing(8)

        row = 0

        # 合约
        grid.addWidget(BodyLabel("合约"), row, 0)
        self.symbol_combo = EditableComboBox(self)
        self.symbol_combo.setPlaceholderText("选择或输入后回车")
        self._load_favorites()
        self.symbol_combo.currentIndexChanged.connect(self._on_symbol_selected)
        self.symbol_combo.returnPressed.connect(self._on_symbol_input)
        grid.addWidget(self.symbol_combo, row, 1, 1, 2)

        # 交易所
        row += 1
        grid.addWidget(BodyLabel("交易所"), row, 0)
        self.exchange_combo = ComboBox(self)
        self.exchange_combo.addItems([e.value for e in FUTURES_EXCHANGES])
        grid.addWidget(self.exchange_combo, row, 1, 1, 2)

        # 名称
        row += 1
        grid.addWidget(BodyLabel("名称"), row, 0)
        self.name_line = LineEdit(self)
        self.name_line.setReadOnly(True)
        grid.addWidget(self.name_line, row, 1, 1, 2)

        # 方向
        row += 1
        grid.addWidget(BodyLabel("方向"), row, 0)
        self.direction_combo = ComboBox(self)
        self.direction_combo.addItems(list(DIRECTION_MAP.keys()))
        grid.addWidget(self.direction_combo, row, 1, 1, 2)

        # 开平
        row += 1
        grid.addWidget(BodyLabel("开平"), row, 0)
        self.offset_combo = ComboBox(self)
        self.offset_combo.addItems(list(OFFSET_MAP.keys()))
        grid.addWidget(self.offset_combo, row, 1, 1, 2)

        # 类型
        row += 1
        grid.addWidget(BodyLabel("类型"), row, 0)
        self.order_type_combo = ComboBox(self)
        self.order_type_combo.addItems(list(ORDERTYPE_MAP.keys()))
        grid.addWidget(self.order_type_combo, row, 1, 1, 2)

        # 价格 + 跟价
        row += 1
        grid.addWidget(BodyLabel("价格"), row, 0)
        self.price_spin = DoubleSpinBox(self)
        self.price_spin.setRange(0, 9999999)
        self.price_spin.setDecimals(2)
        self.price_spin.setSingleStep(1)
        grid.addWidget(self.price_spin, row, 1)

        self.price_check = CheckBox("跟价", self)
        self.price_check.setChecked(True)
        self.price_check.setToolTip("价格随最新价实时更新")
        grid.addWidget(self.price_check, row, 2)

        # 数量
        row += 1
        grid.addWidget(BodyLabel("数量"), row, 0)
        self.volume_spin = SpinBox(self)
        self.volume_spin.setRange(1, 9999)
        self.volume_spin.setValue(1)
        grid.addWidget(self.volume_spin, row, 1, 1, 2)

        # 接口
        row += 1
        grid.addWidget(BodyLabel("接口"), row, 0)
        self.gateway_combo = ComboBox(self)
        self._refresh_gateways()
        grid.addWidget(self.gateway_combo, row, 1, 1, 2)

        # 委托按钮
        row += 1
        send_button = PushButton("委托", self)
        send_button.clicked.connect(self._send_order)
        grid.addWidget(send_button, row, 0, 1, 3)

        # 全撤按钮
        row += 1
        cancel_button = PushButton("全撤", self)
        cancel_button.clicked.connect(self._cancel_all)
        grid.addWidget(cancel_button, row, 0, 1, 3)

        return grid

    # ── 收藏品种 ──

    def _load_favorites(self) -> None:
        """加载收藏品种到合约下拉列表"""
        contracts = contract_setting.load_contracts()
        favorites = contract_setting.load_favorites()

        for key in favorites:
            c = contracts.get(key, {})
            name = c.get("name", key)
            vt_symbol = c.get("vt_symbol", "")
            exchange = c.get("exchange", "")
            if not vt_symbol:
                continue

            # vt_symbol 格式为 "rb2510.SHFE"，提取纯合约代码
            symbol = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol

            self.symbol_combo.addItem(
                f"{name}  {symbol}",
                userData={"symbol": symbol, "exchange": exchange, "name": name},
            )

        # 不预选（显示 placeholder）
        self.symbol_combo.setCurrentIndex(-1)

    def _on_symbol_selected(self, index: int) -> None:
        """下拉选中收藏品种（有 userData 的项）"""
        if index < 0:
            return
        data = self.symbol_combo.itemData(index)
        if not data:
            return

        # 自动设置交易所
        exchange = data.get("exchange", "")
        if exchange:
            ex_idx = self.exchange_combo.findText(exchange)
            if ex_idx >= 0:
                self.exchange_combo.setCurrentIndex(ex_idx)

        self._set_vt_symbol()

    def _on_symbol_input(self) -> None:
        """手动输入合约后回车

        执行顺序：EditableComboBox 内部 _onReturnPressed 先执行，
        会把裸文本（如 "OI"）addItem 到下拉列表。
        本方法随后执行，检测到无 userData 的裸项后进行解析替换。
        """
        index = self.symbol_combo.currentIndex()
        if index < 0:
            return

        # 已有 userData 说明是收藏项或已解析项，跳过
        if self.symbol_combo.itemData(index):
            return

        text = self.symbol_combo.itemText(index)
        resolved = contract_setting.resolve_symbol(text)

        if not resolved:
            # 解析失败：移除裸文本项，提示用户
            self.symbol_combo.blockSignals(True)
            self.symbol_combo.removeItem(index)
            self.symbol_combo.setCurrentIndex(-1)
            self.symbol_combo.blockSignals(False)
            InfoBar.warning(
                "合约未找到",
                f"无法识别 \"{text}\"，请检查品种代码是否正确",
                parent=self, duration=3000, position=InfoBarPosition.TOP,
            )
            return

        name, vt_symbol, exchange_str = resolved

        # 解析成功：用完整格式替换裸文本项
        symbol_part = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol
        display = f"{name}  {symbol_part}"
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.removeItem(index)
        self.symbol_combo.addItem(
            display,
            userData={"symbol": symbol_part, "exchange": exchange_str, "name": name},
        )
        self.symbol_combo.setCurrentIndex(self.symbol_combo.count() - 1)
        # setText 确保输入框显示完整格式
        self.symbol_combo.setText(display)
        self.symbol_combo.blockSignals(False)

        # 设置交易所
        ex_idx = self.exchange_combo.findText(exchange_str)
        if ex_idx >= 0:
            self.exchange_combo.setCurrentIndex(ex_idx)

        self._set_vt_symbol()

    # ── 事件注册 ──

    def _register_events(self) -> None:
        """注册事件（直连 EventEngine）"""
        self._signal_tick.connect(self._process_tick)
        self._signal_order.connect(self._process_order)
        self._signal_trade.connect(self._process_trade)
        self._signal_log.connect(self._process_log)

        self._event_engine.register(EVENT_TICK, self._on_tick_event)
        self._event_engine.register(EVENT_ORDER, self._on_order_event)
        self._event_engine.register(EVENT_TRADE, self._on_trade_event)
        self._event_engine.register(EVENT_LOG, self._on_log_event)

        from guanlan.core.events import signal_bus
        signal_bus.account_connected.connect(self._refresh_gateways)
        signal_bus.account_disconnected.connect(self._refresh_gateways)

    def _on_tick_event(self, event) -> None:
        """EventEngine 线程回调 → Qt Signal 跨线程"""
        self._signal_tick.emit(event.data)

    def _on_order_event(self, event) -> None:
        """EventEngine 线程回调 → Qt Signal 跨线程"""
        self._signal_order.emit(event.data)

    def _on_trade_event(self, event) -> None:
        """EventEngine 线程回调 → Qt Signal 跨线程"""
        self._signal_trade.emit(event.data)

    def _on_log_event(self, event) -> None:
        """EventEngine 线程回调 → Qt Signal 跨线程"""
        self._signal_log.emit(event.data)

    def _refresh_gateways(self, _env_name: str = "") -> None:
        """刷新接口下拉列表"""
        current = self.gateway_combo.currentText()
        self.gateway_combo.clear()

        from guanlan.core.app import AppEngine
        self.gateway_combo.addItems(AppEngine.instance().connected_envs)

        idx = self.gateway_combo.findText(current)
        if idx >= 0:
            self.gateway_combo.setCurrentIndex(idx)

    def _process_tick(self, tick: TickData) -> None:
        """主线程处理 tick 数据（跟价）"""
        if tick.vt_symbol != self._vt_symbol:
            return

        if self.price_check.isChecked():
            self.price_spin.setValue(tick.last_price)

    # ── 合约切换 ──

    def _set_vt_symbol(self) -> None:
        """合约切换，订阅行情"""
        idx = self.symbol_combo.currentIndex()
        data = self.symbol_combo.itemData(idx) if idx >= 0 else None

        if data:
            symbol = data["symbol"]
            exchange_value = data["exchange"]
        else:
            text = self.symbol_combo.currentText().strip()
            if not text:
                return
            if "." in text:
                symbol, exchange_value = text.rsplit(".", 1)
            else:
                symbol = text
                exchange_value = self.exchange_combo.currentText()

        # 转换为交易所格式（如 CZCE: OI2605 → OI605）
        exchange = Exchange(exchange_value)
        exchange_symbol = SymbolConverter.to_exchange(symbol, exchange)

        vt_symbol = f"{exchange_symbol}.{exchange_value}"
        if vt_symbol == self._vt_symbol:
            return
        self._vt_symbol = vt_symbol

        # 查询合约信息
        contract = self._main_engine.get_contract(vt_symbol)
        if contract:
            self.name_line.setText(contract.name)
            self._price_digits = get_digits(contract.pricetick)
            self.price_spin.setDecimals(self._price_digits)
            self.price_spin.setSingleStep(contract.pricetick)

            gw_name = contract.gateway_name
            gw_idx = self.gateway_combo.findText(gw_name)
            if gw_idx >= 0:
                self.gateway_combo.setCurrentIndex(gw_idx)
        elif data:
            self.name_line.setText(data.get("name", ""))
        else:
            self.name_line.setText("")

        self.volume_spin.setValue(1)

        # 订阅行情
        from guanlan.core.app import AppEngine
        AppEngine.instance().subscribe(vt_symbol)

        # 从缓存获取最新价作为初始价格
        tick = self._main_engine.get_tick(vt_symbol)
        if tick and tick.last_price:
            self.price_spin.setValue(tick.last_price)
        else:
            self.price_spin.setValue(0)

    # ── 下单 / 撤单 ──

    def _send_order(self) -> None:
        """委托下单"""
        if not self._vt_symbol:
            InfoBar.error(
                "委托失败", "请先选择合约",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        volume = self.volume_spin.value()
        if volume <= 0:
            InfoBar.error(
                "委托失败", "请输入委托数量",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        price = self.price_spin.value()

        gateway_name = self.gateway_combo.currentText()
        if not gateway_name:
            InfoBar.error(
                "委托失败", "请选择交易接口",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        # _vt_symbol 已是交易所格式（如 OI605.CZCE）
        symbol, exchange_value = self._vt_symbol.rsplit(".", 1)

        req = OrderRequest(
            symbol=symbol,
            exchange=Exchange(exchange_value),
            direction=DIRECTION_MAP[self.direction_combo.currentText()],
            type=ORDERTYPE_MAP[self.order_type_combo.currentText()],
            volume=volume,
            price=price,
            offset=OFFSET_MAP[self.offset_combo.currentText()],
            reference=self.REFERENCE,
        )

        vt_orderid = self._main_engine.send_order(req, gateway_name)
        if vt_orderid:
            self._manual_orderids.add(vt_orderid)

        # 下单音效
        if req.direction == Direction.LONG:
            play_sound("buy")
        else:
            play_sound("sell")

    def _cancel_all(self) -> None:
        """全撤活动委托"""
        for order in self._main_engine.get_all_active_orders():
            req = order.create_cancel_request()
            self._main_engine.cancel_order(req, order.gateway_name)

    # ── 事件处理（音效 + 拒单提示） ──

    def _process_order(self, order: OrderData) -> None:
        """委托状态变化（音效 + 拒单标记，仅手动交易）"""
        if order.vt_orderid not in self._manual_orderids:
            return

        if order.status == Status.CANCELLED:
            play_sound("cancel")
            self._manual_orderids.discard(order.vt_orderid)
        elif order.status == Status.REJECTED:
            play_sound("error")
            self._manual_orderids.discard(order.vt_orderid)
            self._pending_reject = True

    def _process_trade(self, trade: TradeData) -> None:
        """成交音效（仅手动交易）"""
        if trade.vt_orderid not in self._manual_orderids:
            return

        if trade.offset == Offset.OPEN:
            if trade.direction == Direction.LONG:
                play_sound("con_buy")
            else:
                play_sound("con_sell")
        else:
            play_sound("con_close")

    def _process_log(self, log: LogData) -> None:
        """日志处理（拒单错误信息展示）"""
        if self._pending_reject and "交易委托失败" in log.msg:
            self._pending_reject = False
            InfoBar.error(
                "委托失败", log.msg,
                parent=self.window(), position=InfoBarPosition.TOP,
                duration=5000,
            )
