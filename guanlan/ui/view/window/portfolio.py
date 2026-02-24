# -*- coding: utf-8 -*-
"""
观澜量化 - 组合策略管理窗口

独立窗口，从首页 Banner 卡片进入。
卡片式布局：每个策略一张 CardWidget，显示合约列表、参数/状态表。
复用 CTA 的 DataMonitor 和 SettingEditor 模式。

Author: 海山观澜
"""

from copy import copy
from guanlan.core.utils.trading_period import beijing_now

from pydantic import BaseModel

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QAbstractItemView,
)

from qfluentwidgets import (
    FluentIcon, FluentWidget,
    PushButton, PrimaryPushButton,
    BodyLabel, SubtitleLabel,
    LineEdit, ComboBox, EditableComboBox, SpinBox, DoubleSpinBox, SwitchButton,
    TableWidget, CardWidget, ScrollArea,
    MessageBoxBase,
    InfoBar, InfoBarPosition,
    isDarkTheme, qconfig,
)

from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.portfolio.base import (
    EVENT_PORTFOLIO_LOG,
    EVENT_PORTFOLIO_STRATEGY,
)
from guanlan.core.trader.cta.template import BaseParams
from guanlan.ui.view.window.cta import DataMonitor
from guanlan.ui.view.panel.base import StrategyLogTable
from vnpy.trader.object import LogData


class PortfolioSettingEditor(MessageBoxBase):
    """组合策略参数编辑器

    与 CTA 的 SettingEditor 类似，但合约输入改为多个（逗号分隔）。
    """

    def __init__(
        self,
        params: BaseParams,
        strategy_name: str = "",
        class_name: str = "",
        gateway_names: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._params: BaseParams = params
        self._strategy_name: str = strategy_name
        self._class_name: str = class_name
        self._gateway_names: list[str] = gateway_names or []

        self._edits: dict[str, tuple] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        self.widget.setMinimumWidth(480)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # 新增策略模式
        if self._class_name:
            title = SubtitleLabel(f"添加策略：{self._class_name}", self)
            self.viewLayout.addWidget(title)

            # 策略名称
            name_edit = LineEdit(self)
            name_edit.setPlaceholderText("请输入策略名称")
            form.addRow(BodyLabel("策略名称", self), name_edit)
            self._edits["strategy_name"] = (name_edit, str)

            # 合约列表（逗号分隔）
            symbols_edit = LineEdit(self)
            symbols_edit.setPlaceholderText("输入合约代码，逗号分隔（如 RB,HC 或 rb2509.SHFE,hc2509.SHFE）")
            form.addRow(BodyLabel("合约列表", self), symbols_edit)
            self._edits["symbols"] = (symbols_edit, str)

            # 合约快速添加（从收藏选择或手动输入）
            self._favorites_combo = EditableComboBox(self)
            self._favorites_combo.setPlaceholderText("选择收藏或输入品种代码")
            self._load_favorites(self._favorites_combo)
            self._favorites_combo.returnPressed.connect(
                lambda se=symbols_edit: self._on_symbol_input(se)
            )

            btn_append = PushButton("追加", self)
            btn_append.setFixedWidth(60)
            btn_append.clicked.connect(
                lambda: self._append_symbol(symbols_edit, self._favorites_combo)
            )

            fav_layout = QHBoxLayout()
            fav_layout.addWidget(self._favorites_combo, 1)
            fav_layout.addWidget(btn_append)
            form.addRow(BodyLabel("", self), fav_layout)

            # 交易账户
            gateway_combo = ComboBox(self)
            gateway_combo.addItems(self._gateway_names)
            form.addRow(BodyLabel("交易账户", self), gateway_combo)
            self._edits["gateway_name"] = (gateway_combo, "combo")

            # hot 开关
            hot_switch = SwitchButton(self)
            hot_switch.setChecked(True)
            form.addRow(BodyLabel("主力合约", self), hot_switch)
            self._edits["hot"] = (hot_switch, bool)

        else:
            title = SubtitleLabel(f"参数编辑：{self._strategy_name}", self)
            self.viewLayout.addWidget(title)

        # Pydantic 参数字段
        for name, field_info in self._params.model_fields.items():
            field_type = field_info.annotation
            current_value = getattr(self._params, name)
            field_title = field_info.title or name

            # 提取 ge/le 约束
            ge_val, le_val = None, None
            for m in field_info.metadata:
                if hasattr(m, "ge"):
                    ge_val = m.ge
                if hasattr(m, "le"):
                    le_val = m.le

            if field_type is bool:
                widget = SwitchButton(self)
                widget.setChecked(current_value)
            elif field_type is int:
                widget = SpinBox(self)
                widget.setValue(current_value)
                widget.setSingleStep(1)
                if ge_val is not None:
                    widget.setMinimum(ge_val)
                if le_val is not None:
                    widget.setMaximum(le_val)
            elif field_type is float:
                widget = DoubleSpinBox(self)
                widget.setValue(current_value)
                widget.setSingleStep(0.1)
                if ge_val is not None:
                    widget.setMinimum(ge_val)
                if le_val is not None:
                    widget.setMaximum(le_val)
            elif field_type is str and field_info.examples:
                widget = ComboBox(self)
                for example in field_info.examples:
                    widget.addItem(str(example))
                widget.setCurrentText(str(current_value))
            else:
                widget = LineEdit(self)
                widget.setText(str(current_value))

            form.addRow(BodyLabel(field_title, self), widget)
            self._edits[name] = (widget, field_type)

        form.setContentsMargins(0, 20, 0, 0)
        self.viewLayout.addLayout(form)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

    def get_setting(self) -> dict:
        """获取编辑结果"""
        setting: dict = {}

        for name, (widget, type_) in self._edits.items():
            if type_ is bool:
                setting[name] = widget.isChecked()
            elif type_ == "combo":
                idx = widget.currentIndex()
                if idx >= 0 and hasattr(widget, "itemData"):
                    data = widget.itemData(idx)
                    if data:
                        setting[name] = data
                        continue
                setting[name] = widget.currentText()
            elif type_ is int:
                setting[name] = widget.value()
            elif type_ is float:
                setting[name] = widget.value()
            else:
                text = widget.text().strip()
                setting[name] = text

        return setting

    def _append_symbol(self, symbols_edit: LineEdit, combo: EditableComboBox) -> None:
        """将收藏品种追加到合约列表"""
        idx = combo.currentIndex()
        if idx < 0:
            return

        code = combo.itemData(idx)
        if not code:
            code = combo.currentText().strip()
        if not code:
            return

        current = symbols_edit.text().strip()
        if current:
            symbols_edit.setText(f"{current},{code}")
        else:
            symbols_edit.setText(code)

        combo.setCurrentIndex(-1)

    def _load_favorites(self, combo: EditableComboBox) -> None:
        """加载收藏品种到合约下拉列表"""
        from guanlan.core.setting import contract as contract_setting

        contracts = contract_setting.load_contracts()
        favorites = contract_setting.load_favorites()

        for key in favorites:
            c = contracts.get(key, {})
            name = c.get("name", key)
            vt_symbol = c.get("vt_symbol", "")
            if not vt_symbol:
                continue
            combo.addItem(f"{name}  {key}", userData=key)

        combo.setCurrentIndex(-1)

    def _on_symbol_input(self, symbols_edit: LineEdit) -> None:
        """手动输入品种代码回车后解析并追加到合约列表"""
        from guanlan.core.setting import contract as contract_setting
        from guanlan.core.utils.symbol_converter import SymbolConverter

        combo = self._favorites_combo
        index = combo.currentIndex()
        if index < 0:
            return
        if combo.itemData(index):
            return

        text = combo.itemText(index)
        resolved = contract_setting.resolve_symbol(text)

        # 清除裸文本项
        combo.blockSignals(True)
        combo.removeItem(index)
        combo.setCurrentIndex(-1)
        combo.blockSignals(False)

        if not resolved:
            InfoBar.warning(
                "合约未找到", f"无法识别 \"{text}\"",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        name, vt_symbol, _exchange = resolved
        symbol_part = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol
        commodity = SymbolConverter.extract_commodity(symbol_part)

        # 追加到合约列表
        current = symbols_edit.text().strip()
        if current:
            symbols_edit.setText(f"{current},{commodity}")
        else:
            symbols_edit.setText(commodity)


class PortfolioCard(CardWidget):
    """组合策略管理卡片

    每个策略一张卡片，包含标题（策略名·合约列表·账户）、操作按钮、参数表、状态表。
    """

    def __init__(
        self,
        portfolio_window: "PortfolioStrategyWindow",
        portfolio_engine,
        data: dict,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._portfolio_window = portfolio_window
        self._portfolio_engine = portfolio_engine
        self.strategy_name: str = data["strategy_name"]
        self._data: dict = data

        self._init_ui()

    def _init_ui(self) -> None:
        self.setFixedHeight(310)

        # 标题区域
        strategy_name: str = self._data["strategy_name"]
        symbols: list[str] = self._data.get("symbols", self._data.get("vt_symbols", []))
        gateway_name: str = self._data.get("gateway_name", "")

        header = QWidget(self)
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(0)

        # 策略名称
        name_label = SubtitleLabel(strategy_name, self)
        name_label.setObjectName("cardTitle")

        dot1 = BodyLabel("  ·  ", self)
        dot1.setObjectName("cardDot")

        # 合约列表（显示原始输入）
        symbols_str = ", ".join(symbols)
        symbol_label = BodyLabel(f"合约：{symbols_str}", self)
        symbol_label.setObjectName("cardInfo")
        symbol_label.setToolTip(symbols_str)

        dot2 = BodyLabel("  ·  ", self)
        dot2.setObjectName("cardDot")

        gateway_label = BodyLabel(f"账户：{gateway_name}", self)
        gateway_label.setObjectName("cardInfo")

        header_layout.addWidget(name_label)
        header_layout.addWidget(dot1)
        header_layout.addWidget(symbol_label)
        header_layout.addWidget(dot2)
        header_layout.addWidget(gateway_label)
        header_layout.addStretch(1)

        header.setObjectName("cardHeader")

        # 操作按钮
        self._btn_init = PrimaryPushButton("初始化", self)
        self._btn_init.clicked.connect(self._on_init)

        self._btn_start = PrimaryPushButton("启动", self)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_start.setEnabled(False)

        self._btn_stop = PrimaryPushButton("停止", self)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)

        self._btn_edit = PrimaryPushButton("编辑", self)
        self._btn_edit.clicked.connect(self._on_edit)

        self._btn_reset = PrimaryPushButton("重置", self)
        self._btn_reset.clicked.connect(self._on_reset)

        self._btn_remove = PrimaryPushButton("移除", self)
        self._btn_remove.clicked.connect(self._on_remove)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self._btn_init)
        btn_layout.addWidget(self._btn_start)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_edit)
        btn_layout.addWidget(self._btn_reset)
        btn_layout.addWidget(self._btn_remove)

        # 参数、状态、信号表
        self._params_monitor = DataMonitor(self._data["params"], self)
        self._state_monitor = DataMonitor(self._data["state"], self)
        self._vars_monitor = DataMonitor(self._data.get("vars"), self) if self._data.get("vars") else None

        vbox = QVBoxLayout()
        vbox.addWidget(header)
        vbox.addSpacing(6)
        vbox.addLayout(btn_layout)
        vbox.addWidget(self._params_monitor)
        vbox.addWidget(self._state_monitor)
        if self._vars_monitor:
            vbox.addWidget(self._vars_monitor)
        vbox.setContentsMargins(20, 10, 20, 10)

        self.setLayout(vbox)

    def update_data(self, data: dict) -> None:
        """更新策略数据"""
        self._data = data

        self._params_monitor.update_data(data["params"])
        self._state_monitor.update_data(data["state"])
        if self._vars_monitor and "vars" in data:
            self._vars_monitor.update_data(data["vars"])

        inited: bool = data["inited"]
        trading: bool = data["trading"]

        if not inited:
            return

        self._btn_init.setEnabled(False)

        if trading:
            self._btn_start.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_edit.setEnabled(False)
            self._btn_reset.setEnabled(False)
            self._btn_remove.setEnabled(False)
        else:
            self._btn_start.setEnabled(True)
            self._btn_stop.setEnabled(False)
            self._btn_edit.setEnabled(True)
            self._btn_reset.setEnabled(True)
            self._btn_remove.setEnabled(True)

    def _on_init(self) -> None:
        self._portfolio_engine.init_strategy(self.strategy_name)

    def _on_start(self) -> None:
        self._portfolio_engine.start_strategy(self.strategy_name)

    def _on_stop(self) -> None:
        self._portfolio_engine.stop_strategy(self.strategy_name)

    def _on_reset(self) -> None:
        self._portfolio_engine.reset_strategy(self.strategy_name)

    def _on_edit(self) -> None:
        params = self._portfolio_engine.get_strategy_parameters(self.strategy_name)
        editor = PortfolioSettingEditor(
            params=params,
            strategy_name=self.strategy_name,
            parent=self._portfolio_window,
        )
        if editor.exec():
            setting = editor.get_setting()
            self._portfolio_engine.edit_strategy(self.strategy_name, setting)

    def _on_remove(self) -> None:
        result = self._portfolio_engine.remove_strategy(self.strategy_name)
        if result:
            self._portfolio_window.remove_strategy(self.strategy_name)


class PortfolioStrategyWindow(CursorFixMixin, FluentWidget):
    """组合策略管理窗口（卡片式布局）"""

    _signal_log = Signal(Event)
    _signal_strategy = Signal(Event)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._managers: dict[str, PortfolioCard] = {}

        self._init_ui()
        self._register_events()
        self._init_engine()

    def _get_engine(self):
        """获取组合策略引擎实例"""
        from guanlan.core.app import AppEngine
        return AppEngine.instance().main_engine.get_engine("PortfolioStrategy")

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("组合策略管理")
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

        self._class_combo = ComboBox(self)
        self._class_combo.setMinimumWidth(200)
        toolbar.addWidget(self._class_combo)

        btn_add = PrimaryPushButton("添加策略", self, FluentIcon.ADD)
        btn_add.clicked.connect(self._on_add_strategy)
        toolbar.addWidget(btn_add)

        btn_reload = PushButton("刷新策略", self)
        btn_reload.clicked.connect(self._on_reload_class)
        toolbar.addWidget(btn_reload)

        toolbar.addStretch(1)

        # 策略查找
        self._strategy_combo = ComboBox(self)
        self._strategy_combo.setMinimumWidth(160)
        toolbar.addWidget(self._strategy_combo)

        btn_find = PushButton("定位", self)
        btn_find.clicked.connect(self._on_find_strategy)
        toolbar.addWidget(btn_find)

        toolbar.addStretch(1)

        btn_init_all = PushButton("全部初始化", self)
        btn_init_all.clicked.connect(self._on_init_all)
        toolbar.addWidget(btn_init_all)

        btn_start_all = PushButton("全部启动", self)
        btn_start_all.clicked.connect(self._on_start_all)
        toolbar.addWidget(btn_start_all)

        btn_stop_all = PushButton("全部停止", self)
        btn_stop_all.clicked.connect(self._on_stop_all)
        toolbar.addWidget(btn_stop_all)

        content_layout.addLayout(toolbar)

        # ── 主体区域：策略卡片 + 日志 ──
        grid = QGridLayout()

        # 左侧：策略卡片滚动区域
        self._scroll_layout = QVBoxLayout()
        self._scroll_layout.addStretch()

        scroll_widget = QWidget()
        scroll_widget.setLayout(self._scroll_layout)
        scroll_widget.setObjectName("scrollWidget")

        self._scroll_area = ScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(scroll_widget)

        grid.addWidget(self._scroll_area, 0, 0, 2, 1)

        # 右侧：日志表格
        log_widget = QWidget(self)
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(8, 0, 0, 0)
        log_layout.setSpacing(2)

        log_label = BodyLabel("组合策略日志", self)
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

        event_engine.register(EVENT_PORTFOLIO_LOG, self._log_handler)
        event_engine.register(EVENT_PORTFOLIO_STRATEGY, self._strategy_handler)

    def _unregister_events(self) -> None:
        """注销事件"""
        try:
            from guanlan.core.app import AppEngine
            event_engine: EventEngine = AppEngine.instance().event_engine
            event_engine.unregister(EVENT_PORTFOLIO_LOG, self._log_handler)
            event_engine.unregister(EVENT_PORTFOLIO_STRATEGY, self._strategy_handler)
        except Exception:
            pass

    def _init_engine(self) -> None:
        """初始化组合策略引擎"""
        engine = self._get_engine()
        if not engine:
            return

        engine.init_engine()
        self._update_class_combo()

        # 加载已有策略卡片
        for strategy in engine.strategies.values():
            data = strategy.get_data()
            strategy_name = data["strategy_name"]
            if strategy_name not in self._managers:
                card = PortfolioCard(
                    portfolio_window=self,
                    portfolio_engine=engine,
                    data=data,
                    parent=self,
                )
                card.update_data(data)
                self._scroll_layout.insertWidget(0, card)
                self._managers[strategy_name] = card

        self._update_strategy_combo()

    # ── 事件处理 ──

    def _process_log_event(self, event: Event) -> None:
        """组合策略日志事件"""
        log: LogData = event.data
        time_str = beijing_now().strftime("%H:%M:%S")

        # 解析 [策略名] 前缀
        msg = log.msg
        strategy = ""
        if msg.startswith("["):
            end = msg.find("]")
            if end > 0:
                strategy = msg[1:end]
                msg = msg[end + 1:].lstrip()

        self._log_table.process_data({
            "time": time_str, "strategy": strategy, "msg": msg,
        })

    def _process_strategy_event(self, event: Event) -> None:
        """策略数据更新事件"""
        data: dict = event.data
        strategy_name: str = data["strategy_name"]

        if strategy_name in self._managers:
            card = self._managers[strategy_name]
            card.update_data(data)
        else:
            engine = self._get_engine()
            card = PortfolioCard(
                portfolio_window=self,
                portfolio_engine=engine,
                data=data,
                parent=self,
            )
            self._scroll_layout.insertWidget(0, card)
            self._managers[strategy_name] = card
            self._update_strategy_combo()

    # ── 工具栏操作 ──

    def _update_class_combo(self) -> None:
        """更新策略类下拉（显示中文名，userData 存类名）"""
        engine = self._get_engine()
        if not engine:
            return

        display_map = engine.get_strategy_class_display_names()
        items = sorted(display_map.items(), key=lambda x: x[1])

        self._class_combo.clear()
        for class_name, display_name in items:
            self._class_combo.addItem(display_name, userData=class_name)

    def _update_strategy_combo(self) -> None:
        """更新策略查找下拉"""
        names = sorted(self._managers.keys())
        self._strategy_combo.clear()
        self._strategy_combo.addItems(names)

    def _on_reload_class(self) -> None:
        """刷新策略类"""
        engine = self._get_engine()
        if engine:
            engine.load_strategy_class()
            self._update_class_combo()
            InfoBar.success(
                "提示", "策略类已刷新",
                parent=self, position=InfoBarPosition.TOP, duration=2000,
            )

    def _on_find_strategy(self) -> None:
        """定位策略卡片"""
        strategy_name = self._strategy_combo.currentText()
        card = self._managers.get(strategy_name)
        if card:
            self._scroll_area.ensureWidgetVisible(card)

    def _on_add_strategy(self) -> None:
        """添加策略"""
        engine = self._get_engine()
        if not engine:
            return

        idx = self._class_combo.currentIndex()
        if idx < 0:
            InfoBar.warning(
                "提示", "未发现策略类，请在 strategies/portfolio/ 目录放置策略文件",
                parent=self, position=InfoBarPosition.TOP,
            )
            return

        class_name = self._class_combo.itemData(idx)
        params = engine.get_strategy_class_parameters(class_name)

        from guanlan.core.app import AppEngine
        gateway_names = AppEngine.instance().connected_envs

        editor = PortfolioSettingEditor(
            params=params,
            class_name=class_name,
            gateway_names=gateway_names,
            parent=self,
        )
        if editor.exec():
            setting = editor.get_setting()

            strategy_name = setting.pop("strategy_name", "")
            symbols_str = setting.pop("symbols", "")
            gateway_name = setting.pop("gateway_name", "")
            hot = setting.pop("hot", False)

            if not strategy_name:
                InfoBar.warning(
                    "提示", "策略名称不能为空",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            if not symbols_str:
                InfoBar.warning(
                    "提示", "合约列表不能为空",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            # 解析逗号分隔的合约列表
            symbols: list[str] = [
                s.strip() for s in symbols_str.split(",") if s.strip()
            ]

            if not symbols:
                InfoBar.warning(
                    "提示", "合约列表解析失败",
                    parent=self, position=InfoBarPosition.TOP,
                )
                return

            engine.add_strategy(
                class_name, strategy_name, symbols, gateway_name, hot, setting,
            )

    def _on_init_all(self) -> None:
        """全部初始化"""
        engine = self._get_engine()
        if engine:
            engine.init_all_strategies()

    def _on_start_all(self) -> None:
        """全部启动"""
        engine = self._get_engine()
        if engine:
            engine.start_all_strategies()

    def _on_stop_all(self) -> None:
        """全部停止"""
        engine = self._get_engine()
        if engine:
            engine.stop_all_strategies()

    # ── 策略管理 ──

    def remove_strategy(self, strategy_name: str) -> None:
        """移除策略卡片"""
        card = self._managers.pop(strategy_name, None)
        if card:
            card.deleteLater()
        self._update_strategy_combo()

    # ── 样式和窗口行为 ──

    def _apply_content_style(self) -> None:
        """应用内容区域样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, [
            "common.qss", "window.qss", "strategy_card.qss",
        ], theme)
