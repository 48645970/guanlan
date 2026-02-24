# -*- coding: utf-8 -*-
"""
观澜量化 - 行情记录界面

Author: 海山观澜
"""

from guanlan.core.utils.trading_period import beijing_now

from PySide6.QtCore import Qt, Signal, QTimer, QAbstractItemModel, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGridLayout, QCompleter, QSpacerItem, QSizePolicy,
)

from qfluentwidgets import (
    ScrollArea, TitleLabel, CaptionLabel,
    BodyLabel,
    PushButton, PrimaryPushButton,
    LineEdit, SpinBox, TextEdit,
    InfoBar, InfoBarPosition,
    FluentIcon,
)

from guanlan.ui.common.mixin import ThemeMixin
from guanlan.ui.common.config import cfg
from guanlan.core.app import AppEngine
from guanlan.core.trader.data import DataRecorderEngine
from guanlan.core.events import signal_bus


class DataRecorderInterface(ThemeMixin, ScrollArea):
    """行情记录界面"""

    # 信号桥接（从引擎回调 → Qt 主线程）
    signal_log = Signal(str)
    signal_update = Signal(list, list)
    signal_contract_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # 合约补全列表（数据由 AppEngine 统一管理）

        # 创建引擎
        self.engine = DataRecorderEngine(
            on_log=self.signal_log.emit,
            on_update=self.signal_update.emit,
        )

        # 闪烁定时器
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_visible = True


        self.view = QWidget(self)
        self.main_layout = QVBoxLayout(self.view)

        self._init_toolbar()
        self._init_controls()
        self._init_data_area()
        self._init_log_area()
        self._init_widget()
        self._connect_signals()

        # 信号连接后，重新推送录制列表到 UI（引擎 init 时信号尚未连接）
        self.engine.put_event()

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
        self.title_label = TitleLabel("行情记录", toolbar)

        # 录制指示灯
        self.recording_dot = BodyLabel("●", toolbar)
        self.recording_dot.setObjectName("recordingDot")
        self.recording_dot.setTextColor(
            light=QColor(230, 0, 18),
            dark=QColor(230, 0, 18),
        )
        self.recording_dot.hide()

        self.recording_label = BodyLabel("记录中", toolbar)
        self.recording_label.hide()

        # 开始/停止按钮
        self.record_button = PrimaryPushButton(
            "开始记录", toolbar, FluentIcon.PLAY
        )
        self.record_button.setFixedSize(120, 32)
        self.record_button.clicked.connect(self._toggle_recording)

        # 清理失效按钮（合约查询完毕后启用）
        self.clean_btn = PrimaryPushButton("清理失效", toolbar, FluentIcon.DELETE)
        self.clean_btn.setFixedHeight(32)
        self.clean_btn.setEnabled(False)
        self.clean_btn.setObjectName("dangerButton")
        self.clean_btn.setStyleSheet(
            "#dangerButton { background-color: #c42b1c; border-color: #c42b1c; padding: 5px 16px; }"
            "#dangerButton:hover { background-color: #e81123; border-color: #e81123; }"
            "#dangerButton:pressed { background-color: #a4262c; border-color: #a4262c; }"
            "#dangerButton:disabled { background-color: #4d4d4d; border-color: #4d4d4d; }"
        )
        self.clean_btn.clicked.connect(self._remove_expired)

        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.recording_dot)
        title_row.addWidget(self.recording_label)
        title_row.addSpacing(16)
        title_row.addWidget(self.record_button)
        title_row.addSpacing(8)
        title_row.addWidget(self.clean_btn)

        # 副标题
        self.subtitle_label = CaptionLabel(
            "实时记录K线和Tick行情数据", toolbar
        )

        layout.addLayout(title_row)
        layout.addWidget(self.subtitle_label)
        layout.setAlignment(Qt.AlignTop)

        self.toolbar = toolbar

    def _init_controls(self) -> None:
        """初始化操作区"""
        self.symbol_line = LineEdit(self.view)
        self.symbol_line.setPlaceholderText("输入合约代码，如 rb2501.SHFE")
        self.symbol_line.setMinimumWidth(250)
        self.symbol_line.installEventFilter(self)

        self.symbol_completer = QCompleter([], self)
        self.symbol_completer.setFilterMode(Qt.MatchContains)
        self.symbol_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.symbol_line.setCompleter(self.symbol_completer)

        self.interval_spin = SpinBox(self.view)
        self.interval_spin.setMinimum(1)
        self.interval_spin.setMaximum(60)
        self.interval_spin.setValue(self.engine.timer_interval)
        self.interval_spin.setSuffix("  秒")
        self.interval_spin.valueChanged.connect(self._set_interval)

        form = QFormLayout()
        form.addRow(BodyLabel("本地代码", self.view), self.symbol_line)
        form.addRow(BodyLabel("写入间隔", self.view), self.interval_spin)

        add_bar_btn = PrimaryPushButton("添加", self.view)
        add_bar_btn.clicked.connect(self._add_bar_recording)
        remove_bar_btn = PushButton("移除", self.view)
        remove_bar_btn.clicked.connect(self._remove_bar_recording)

        add_tick_btn = PrimaryPushButton("添加", self.view)
        add_tick_btn.clicked.connect(self._add_tick_recording)
        remove_tick_btn = PushButton("移除", self.view)
        remove_tick_btn.clicked.connect(self._remove_tick_recording)

        grid = QGridLayout()
        grid.addWidget(BodyLabel("K线记录", self.view), 0, 0)
        grid.addWidget(add_bar_btn, 0, 1)
        grid.addWidget(remove_bar_btn, 0, 2)
        grid.addWidget(BodyLabel("Tick记录", self.view), 1, 0)
        grid.addWidget(add_tick_btn, 1, 1)
        grid.addWidget(remove_tick_btn, 1, 2)

        self._controls_layout = QHBoxLayout()
        self._controls_layout.addLayout(form)
        self._controls_layout.addItem(
            QSpacerItem(40, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        )
        self._controls_layout.addLayout(grid)
        self._controls_layout.addStretch(1)

    def _init_data_area(self) -> None:
        """初始化录制列表区"""
        self.bar_recording_edit = TextEdit(self.view)
        self.bar_recording_edit.setReadOnly(True)

        self.tick_recording_edit = TextEdit(self.view)
        self.tick_recording_edit.setReadOnly(True)

        self._data_grid = QGridLayout()
        self._data_grid.addWidget(BodyLabel("K线记录列表", self.view), 0, 0)
        self._data_grid.addWidget(BodyLabel("Tick记录列表", self.view), 0, 1)
        self._data_grid.addWidget(self.bar_recording_edit, 1, 0)
        self._data_grid.addWidget(self.tick_recording_edit, 1, 1)

    def _init_log_area(self) -> None:
        """初始化日志区"""
        self._log_label = BodyLabel("日志", self.view)

        self.log_edit = TextEdit(self.view)
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(180)

    def _init_widget(self) -> None:
        """初始化界面"""
        self.view.setObjectName("view")
        self.setObjectName("dataRecorderInterface")

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, self.toolbar.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.main_layout.setSpacing(12)
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_layout.setContentsMargins(36, 20, 36, 36)
        self.main_layout.addLayout(self._controls_layout)
        self.main_layout.addLayout(self._data_grid, 1)
        self.main_layout.addWidget(self._log_label)
        self.main_layout.addWidget(self.log_edit)

        self._init_theme()

    # ── 信号连接 ─────────────────────────────────────────

    def _connect_signals(self) -> None:
        """连接信号槽"""
        self.signal_log.connect(self._process_log)
        self.signal_update.connect(self._process_update)
        signal_bus.account_connected.connect(self._on_account_connected)
        signal_bus.account_disconnected.connect(self._on_account_disconnected)

        # 合约查询完毕后启用"清理失效"按钮
        self.signal_contract_ready.connect(
            lambda: self.clean_btn.setEnabled(True)
        )
        from guanlan.core.trader.gateway import EVENT_CONTRACT_INITED
        app = AppEngine.instance()
        app.event_engine.register(
            EVENT_CONTRACT_INITED, self._on_contract_inited
        )

    def _process_log(self, msg: str) -> None:
        """处理日志消息"""
        timestamp = beijing_now().strftime("%H:%M:%S")
        self.log_edit.append(f"{timestamp}\t{msg}")

    def _process_update(self, bar_symbols: list, tick_symbols: list) -> None:
        """处理录制列表更新"""
        self.bar_recording_edit.clear()
        self.bar_recording_edit.setText("\n".join(bar_symbols))

        self.tick_recording_edit.clear()
        self.tick_recording_edit.setText("\n".join(tick_symbols))

    def _update_connection_status(self) -> None:
        """更新行情账户连接状态"""
        app = AppEngine.instance()
        market_gw = app.market_gateway

        if market_gw and app.is_connected(market_gw):
            self.engine.gateway_name = market_gw
            self.record_button.setEnabled(True)

            # 连接后将收藏夹合约加入录制列表（仅加入列表显示，不开始录制）
            self.engine.add_favorites_to_recording()
        else:
            self.record_button.setEnabled(False)

    def _on_account_connected(self, env_name: str) -> None:
        """账户连接成功"""
        self._update_connection_status()

        # 自动行情记录：连接后自动开始
        if cfg.get(cfg.autoDataRecording) and not self.engine.is_recording:
            self._start_recording()

    def _on_account_disconnected(self, env_name: str) -> None:
        """账户断开连接"""
        self._update_connection_status()

    # ── 录制控制 ─────────────────────────────────────────

    def _toggle_recording(self) -> None:
        """切换录制状态"""
        if self.engine.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """开始录制"""
        app = AppEngine.instance()
        market_gw = app.market_gateway

        if not market_gw or not app.is_connected(market_gw):
            InfoBar.warning(
                title="提示",
                content="行情账户未连接",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        self.engine.gateway_name = market_gw
        self.engine.add_favorites_to_recording()
        self.engine.start_recording()

        self.record_button.setText("停止记录")
        self.record_button.setIcon(FluentIcon.PAUSE)
        self.recording_dot.show()
        self.recording_label.show()
        self._blink_timer.start()

    def _stop_recording(self) -> None:
        """停止录制"""
        self.engine.stop_recording()

        self.record_button.setText("开始记录")
        self.record_button.setIcon(FluentIcon.PLAY)
        self._blink_timer.stop()
        self.recording_dot.hide()
        self.recording_label.hide()

    def _toggle_blink(self) -> None:
        """闪烁录制指示灯"""
        self._blink_visible = not self._blink_visible
        self.recording_dot.setVisible(self._blink_visible)

    # ── 合约操作 ─────────────────────────────────────────

    def _add_bar_recording(self) -> None:
        vt_symbol = self.symbol_line.text().strip()
        if vt_symbol:
            self.engine.add_bar_recording(vt_symbol)

    def _remove_bar_recording(self) -> None:
        vt_symbol = self.symbol_line.text().strip()
        if vt_symbol:
            self.engine.remove_bar_recording(vt_symbol)

    def _add_tick_recording(self) -> None:
        vt_symbol = self.symbol_line.text().strip()
        if vt_symbol:
            self.engine.add_tick_recording(vt_symbol)

    def _remove_tick_recording(self) -> None:
        vt_symbol = self.symbol_line.text().strip()
        if vt_symbol:
            self.engine.remove_tick_recording(vt_symbol)

    def _remove_expired(self) -> None:
        """清理引擎中不存在的失效合约"""
        self.engine.remove_expired()

    def _on_contract_inited(self, event) -> None:
        """合约查询完毕回调（事件线程 → 信号桥接到主线程）"""
        self.signal_contract_ready.emit()

    def _set_interval(self, interval: int) -> None:
        self.engine.timer_interval = interval

    # ── 生命周期 ────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        """输入框获得焦点时刷新合约补全列表"""
        if not hasattr(self, 'symbol_line'):
            return super().eventFilter(obj, event)
        if obj is self.symbol_line and event.type() == QEvent.FocusIn:
            model: QAbstractItemModel = self.symbol_completer.model()
            model.setStringList(AppEngine.instance().vt_symbols)
        return super().eventFilter(obj, event)

    def resizeEvent(self, e) -> None:
        """调整标题栏宽度"""
        super().resizeEvent(e)
        self.toolbar.resize(self.width(), self.toolbar.height())
