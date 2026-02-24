# -*- coding: utf-8 -*-
"""
观澜量化 - 脚本策略管理窗口

多脚本并发管理，卡片式布局。左侧脚本卡片滚动区域，右侧日志表格。
参考 CTA 策略管理窗口（cta.py）的布局模式。

Author: 海山观澜
"""

from guanlan.core.utils.trading_period import beijing_now

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFileDialog,
)

from qfluentwidgets import (
    FluentIcon, FluentWidget,
    PushButton, PrimaryPushButton,
    BodyLabel, SubtitleLabel,
    LineEdit, TableWidget, CardWidget, ScrollArea,
    InfoBar, InfoBarPosition,
    isDarkTheme, qconfig,
)

from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.script import EVENT_SCRIPT_LOG, EVENT_SCRIPT_STRATEGY
from guanlan.ui.view.panel.base import StrategyLogTable
from vnpy.trader.object import LogData


class ScriptCard(CardWidget):
    """脚本管理卡片

    每个脚本一张卡片，显示脚本名、路径、运行状态，提供启停和移除按钮。
    """

    def __init__(
        self,
        script_window: "ScriptTraderWindow",
        script_engine,
        data: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._script_window = script_window
        self._script_engine = script_engine
        self.script_name: str = data["script_name"]
        self._data: dict = data

        self._init_ui()
        self.update_status(data.get("active", False))

    def _init_ui(self) -> None:
        self.setFixedHeight(100)

        script_name: str = self._data["script_name"]
        script_path: str = self._data.get("script_path", "")

        # 标题区域
        header = QWidget(self)
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(0)

        name_label = SubtitleLabel(script_name, self)
        name_label.setObjectName("cardTitle")

        dot = BodyLabel("  ·  ", self)
        dot.setObjectName("cardDot")

        path_label = BodyLabel(script_path, self)
        path_label.setObjectName("cardInfoSub")
        path_label.setToolTip(script_path)

        header_layout.addWidget(name_label)
        header_layout.addWidget(dot)
        header_layout.addWidget(path_label, 1)

        header.setObjectName("cardHeader")

        # 状态和按钮行
        btn_layout = QHBoxLayout()

        self._status_label = BodyLabel("已停止", self)
        self._status_label.setStyleSheet(
            "font-size: 13px; color: #8b95a5; padding: 2px 8px;"
        )
        btn_layout.addWidget(self._status_label)
        btn_layout.addStretch(1)

        self._btn_start = PrimaryPushButton("启动", self)
        self._btn_start.clicked.connect(self._on_start)
        btn_layout.addWidget(self._btn_start)

        self._btn_stop = PrimaryPushButton("停止", self)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        btn_layout.addWidget(self._btn_stop)

        self._btn_remove = PushButton("移除", self)
        self._btn_remove.clicked.connect(self._on_remove)
        btn_layout.addWidget(self._btn_remove)

        # 主布局
        vbox = QVBoxLayout()
        vbox.addWidget(header)
        vbox.addLayout(btn_layout)
        vbox.setContentsMargins(20, 10, 20, 10)

        self.setLayout(vbox)

    def update_status(self, active: bool) -> None:
        """更新运行状态"""
        if active:
            self._status_label.setText("运行中")
            self._status_label.setStyleSheet(
                "font-size: 13px; color: #4CAF50; font-weight: 600; padding: 2px 8px;"
            )
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_remove.setEnabled(False)
        else:
            self._status_label.setText("已停止")
            self._status_label.setStyleSheet(
                "font-size: 13px; color: #8b95a5; padding: 2px 8px;"
            )
            self._btn_start.setEnabled(True)
            self._btn_stop.setEnabled(False)
            self._btn_remove.setEnabled(True)

    def _on_start(self) -> None:
        self._script_engine.start_script(self.script_name)

    def _on_stop(self) -> None:
        self._script_engine.stop_script(self.script_name)

    def _on_remove(self) -> None:
        result = self._script_engine.remove_script(self.script_name)
        if result:
            self._script_window.remove_script(self.script_name)


class ScriptTraderWindow(CursorFixMixin, FluentWidget):
    """脚本策略管理窗口（卡片式布局）"""

    _signal_log = Signal(Event)
    _signal_strategy = Signal(Event)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._managers: dict[str, ScriptCard] = {}

        self._init_ui()
        self._register_events()
        self._init_engine()

    def _get_script_engine(self):
        """获取脚本策略引擎实例"""
        from guanlan.core.app import AppEngine
        return AppEngine.instance().main_engine.get_engine("ScriptTrader")

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("脚本策略")
        self.resize(1200, 800)

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
        self._content_widget = QWidget(self)
        self._content_widget.setObjectName("dialogContent")

        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self._content_widget)

        self._apply_content_style()
        qconfig.themeChanged.connect(self._apply_content_style)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()

        self._name_edit = LineEdit(self)
        self._name_edit.setPlaceholderText("输入脚本名称...")
        self._name_edit.setMinimumWidth(140)
        toolbar.addWidget(self._name_edit)

        self._path_edit = LineEdit(self)
        self._path_edit.setPlaceholderText("选择脚本文件路径...")
        self._path_edit.setReadOnly(True)
        self._path_edit.setMinimumWidth(260)
        toolbar.addWidget(self._path_edit, 1)

        self._btn_open = PushButton("打开...", self)
        self._btn_open.clicked.connect(self._on_open)
        toolbar.addWidget(self._btn_open)

        btn_add = PrimaryPushButton("添加脚本", self, FluentIcon.ADD)
        btn_add.clicked.connect(self._on_add)
        toolbar.addWidget(btn_add)

        toolbar.addStretch(1)

        btn_start_all = PushButton("全部启动", self)
        btn_start_all.clicked.connect(self._on_start_all)
        toolbar.addWidget(btn_start_all)

        btn_stop_all = PushButton("全部停止", self)
        btn_stop_all.clicked.connect(self._on_stop_all)
        toolbar.addWidget(btn_stop_all)

        btn_clear = PushButton("清空日志", self)
        btn_clear.clicked.connect(self._on_clear)
        toolbar.addWidget(btn_clear)

        content_layout.addLayout(toolbar)

        # ── 主体区域：脚本卡片 + 日志 ──
        grid = QGridLayout()

        # 左侧：脚本卡片滚动区域
        self._scroll_layout = QVBoxLayout()
        self._scroll_layout.addStretch()

        scroll_widget = QWidget()
        scroll_widget.setLayout(self._scroll_layout)
        scroll_widget.setObjectName("scrollWidget")

        self._scroll_area = ScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(scroll_widget)

        grid.addWidget(self._scroll_area, 0, 0, 2, 1)

        # 右侧：脚本日志表格
        log_widget = QWidget(self)
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(8, 0, 0, 0)
        log_layout.setSpacing(2)

        log_label = BodyLabel("脚本日志", self)
        log_layout.addWidget(log_label)

        self._log_table = StrategyLogTable(self)
        log_layout.addWidget(self._log_table)

        grid.addWidget(log_widget, 0, 1)

        # 列宽比例
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        content_layout.addLayout(grid, 1)

    def _register_events(self) -> None:
        """注册事件（跨线程信号桥接）"""
        from guanlan.core.app import AppEngine
        event_engine: EventEngine = AppEngine.instance().event_engine

        self._signal_log.connect(self._process_log_event)
        self._signal_strategy.connect(self._process_strategy_event)

        self._log_handler = self._signal_log.emit
        self._strategy_handler = self._signal_strategy.emit

        event_engine.register(EVENT_SCRIPT_LOG, self._log_handler)
        event_engine.register(EVENT_SCRIPT_STRATEGY, self._strategy_handler)

    def _unregister_events(self) -> None:
        """注销事件"""
        try:
            from guanlan.core.app import AppEngine
            event_engine: EventEngine = AppEngine.instance().event_engine
            event_engine.unregister(EVENT_SCRIPT_LOG, self._log_handler)
            event_engine.unregister(
                EVENT_SCRIPT_STRATEGY, self._strategy_handler
            )
        except Exception:
            pass

    def _init_engine(self) -> None:
        """初始化引擎（加载已保存的脚本卡片）"""
        engine = self._get_script_engine()
        if not engine:
            return

        for script_name, runner in engine.scripts.items():
            if script_name not in self._managers:
                data = {
                    "script_name": script_name,
                    "script_path": runner.script_path,
                    "active": runner.strategy_active,
                }
                card = ScriptCard(
                    script_window=self,
                    script_engine=engine,
                    data=data,
                    parent=self,
                )
                self._scroll_layout.insertWidget(0, card)
                self._managers[script_name] = card

    # ── 事件处理 ──

    def _process_log_event(self, event: Event) -> None:
        """脚本日志事件"""
        log: LogData = event.data
        time_str = beijing_now().strftime("%H:%M:%S")

        # 解析 [脚本名] 前缀
        msg = log.msg
        script = ""
        if msg.startswith("["):
            end = msg.find("]")
            if end > 0:
                script = msg[1:end]
                msg = msg[end + 1:].lstrip()

        self._log_table.process_data({
            "time": time_str, "strategy": script, "msg": msg,
        })

    def _process_strategy_event(self, event: Event) -> None:
        """脚本状态变更事件"""
        data: dict = event.data
        script_name: str = data["script_name"]

        if script_name in self._managers:
            card = self._managers[script_name]
            card.update_status(data["active"])
        else:
            engine = self._get_script_engine()
            card = ScriptCard(
                script_window=self,
                script_engine=engine,
                data=data,
                parent=self,
            )
            self._scroll_layout.insertWidget(0, card)
            self._managers[script_name] = card

    # ── 工具栏操作 ──

    def _on_open(self) -> None:
        """打开脚本文件（默认策略目录）"""
        from guanlan.core.constants import PROJECT_ROOT

        default_dir = str(PROJECT_ROOT / "strategies" / "script")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择脚本文件", default_dir, "Python 脚本 (*.py)"
        )
        if file_path:
            self._path_edit.setText(file_path)

    def _on_add(self) -> None:
        """添加脚本"""
        script_name = self._name_edit.text().strip()
        script_path = self._path_edit.text().strip()

        if not script_name:
            InfoBar.warning(
                "提示", "请输入脚本名称",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )
            return

        if not script_path:
            InfoBar.warning(
                "提示", "请选择脚本文件",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )
            return

        engine = self._get_script_engine()
        if not engine:
            return

        result = engine.add_script(script_name, script_path)
        if result:
            self._name_edit.clear()
            self._path_edit.clear()
        else:
            InfoBar.warning(
                "提示", f"脚本名 [{script_name}] 已存在",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )

    def _on_start_all(self) -> None:
        """全部启动"""
        engine = self._get_script_engine()
        if engine:
            engine.start_all_scripts()

    def _on_stop_all(self) -> None:
        """全部停止"""
        engine = self._get_script_engine()
        if engine:
            engine.stop_all_scripts()

    def _on_clear(self) -> None:
        """清空日志"""
        self._log_table.clear_data()

    # ── 脚本管理 ──

    def remove_script(self, script_name: str) -> None:
        """移除脚本卡片"""
        card = self._managers.pop(script_name, None)
        if card:
            card.deleteLater()

    # ── 样式 ──

    def _apply_content_style(self) -> None:
        """应用内容区域样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, [
            "common.qss", "window.qss", "strategy_card.qss",
        ], theme)
