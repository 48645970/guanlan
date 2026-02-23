# -*- coding: utf-8 -*-
"""
观澜量化 - 实时行情图表窗口

独立图表窗口，通过 EventEngine 实现数据联动。
支持多周期 K 线、指标插件、成交标记。

Author: 海山观澜
"""

from datetime import datetime

import pandas as pd

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
)

from qfluentwidgets import (
    FluentIcon,
    PushButton, BodyLabel,
    ComboBox, EditableComboBox,
    InfoBar, InfoBarPosition,
    Flyout, FlyoutAnimationType,
    qconfig,
)

from vnpy.trader.constant import Exchange, Direction, Offset
from vnpy.trader.event import EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import TickData, BarData, TradeData

from lightweight_charts.widgets import QtChart

from guanlan.core.constants import COLOR_UP, COLOR_DOWN, COLOR_UP_ALPHA, COLOR_DOWN_ALPHA
from guanlan.core.trader.bar_generator import ChartBarGenerator
from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.setting import chart as chart_setting
from guanlan.core.setting import chart_scheme
from guanlan.core.utils.period import (
    Period, PRESET_NUMBERS, UNITS, DEFAULT_NUMBER, DEFAULT_UNIT,
)
from guanlan.core.utils.symbol_converter import SymbolConverter
from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.style import StyleSheet
from guanlan.ui.widgets.window.webengine import WebEngineFluentWidget
from guanlan.core.utils.logger import get_logger

from .ai_analysis import AIAnalysisWorker
from .data_loader import ChartDataLoader, bar_to_dict
from .indicator import IndicatorManager
from .indicator_panel import IndicatorFlyoutView

logger = get_logger(__name__)

# 历史加载根数预设
HISTORY_BAR_COUNTS: list[str] = [
    "0", "100", "200", "500", "1000", "2000", "5000", "10000", "全部"
]
DEFAULT_BAR_COUNT: str = "200"

# Tick 节流间隔（毫秒）：限制图表刷新频率，避免 JS 队列堆积
TICK_THROTTLE_MS = 100


class ChartWindow(WebEngineFluentWidget):
    """实时行情图表窗口

    独立图表组件，通过 EVENT_TICK / EVENT_TRADE 联动。
    可从辅助交易、CTA 管理界面或主界面打开。
    """

    _signal_tick = Signal(object)
    _signal_trade = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        self._event_engine: EventEngine = app.event_engine
        self._main_engine = app.main_engine

        # 当前合约
        self._vt_symbol: str = ""

        # K 线生成器
        self._bar_generator: ChartBarGenerator | None = None
        self._current_period: str = f"{DEFAULT_NUMBER}{DEFAULT_UNIT}"
        self._period: Period = Period.parse(self._current_period)  # type: ignore[assignment]
        self._bar_count: int = int(DEFAULT_BAR_COUNT)

        # K 线数据缓存
        self._bars: list[dict] = []
        self._chart_initialized: bool = False
        self._chart_ready: bool = False  # WebEngine 页面是否加载完成
        self._pending_df: pd.DataFrame | None = None  # 等待页面加载后显示的数据

        # 成交标记
        self._entry_time: str | None = None
        self._entry_price: float | None = None
        self._entry_direction: Direction | None = None
        self._profit_lines: list = []
        self._trade_records: list[TradeData] = []  # 缓存成交记录，重建时重放

        # 数据加载器
        self._data_loader = ChartDataLoader()

        # 设置
        self._settings: dict = {}
        self._indicator_flyout = None
        self._scheme_override: dict | None = None  # apply_scheme 临时覆盖
        self._rebuilding: bool = False  # 图表初始化/重建期间禁止 tick 更新

        # Tick 节流：缓存最新 tick，定时器到期后统一刷新图表
        self._pending_tick: TickData | None = None
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(TICK_THROTTLE_MS)
        self._tick_timer.timeout.connect(self._flush_pending_tick)
        self._tick_timer.start()

        # 指标管理器（先用 None 占位，_init_ui 中 _create_chart_widget 会用到）
        self._ind_mgr = IndicatorManager(None, self._bars)  # type: ignore[arg-type]

        self._init_ui()
        self._register_events()

        # 绑定 _init_ui 中创建的 chart
        self._ind_mgr.bind_chart(self._chart)

        # 信号 → 主线程（首次 tick 用 _handle_first_tick 隐藏状态提示后切换）
        self._signal_tick.connect(self._handle_first_tick)
        self._signal_trade.connect(self._handle_trade)

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("实时图表")
        self.resize(1100, 750)
        self.setMinimumSize(600, 400)
        self.setResizeEnabled(True)

        # 标题栏
        self.titleBar.setFixedHeight(48)
        self.titleBar.vBoxLayout.insertStretch(0, 1)

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        # 内容容器
        content = QWidget(self)
        content.setObjectName("chartContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 4, 8, 8)
        content_layout.setSpacing(4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(content)

        # ── 工具栏 ──
        toolbar = QWidget()
        toolbar.setObjectName("chartToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.setSpacing(8)

        # 合约选择（支持下拉选择或手动输入）
        toolbar_layout.addWidget(BodyLabel("合约"))
        self._symbol_combo = EditableComboBox()
        self._symbol_combo.setPlaceholderText("选择或输入合约")
        self._symbol_combo.setFixedWidth(180)
        self._load_favorites()
        self._symbol_combo.currentIndexChanged.connect(self._on_symbol_selected)
        self._symbol_combo.returnPressed.connect(self._on_symbol_input)
        toolbar_layout.addWidget(self._symbol_combo)

        # 周期选择：数字 + 单位
        toolbar_layout.addWidget(BodyLabel("周期"))
        self._period_num_combo = EditableComboBox()
        self._period_num_combo.addItems(PRESET_NUMBERS[DEFAULT_UNIT])
        self._period_num_combo.setText(DEFAULT_NUMBER)
        self._period_num_combo.setFixedWidth(70)
        self._period_num_combo.returnPressed.connect(self._on_period_changed)
        self._period_num_combo.currentIndexChanged.connect(self._on_period_changed)
        toolbar_layout.addWidget(self._period_num_combo)

        self._period_unit_combo = ComboBox()
        self._period_unit_combo.addItems(UNITS)
        self._period_unit_combo.setCurrentText(DEFAULT_UNIT)
        self._period_unit_combo.setFixedWidth(60)
        self._period_unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        toolbar_layout.addWidget(self._period_unit_combo)

        # 历史条数
        toolbar_layout.addWidget(BodyLabel("条数"))
        self._bar_count_combo = ComboBox()
        self._bar_count_combo.addItems(HISTORY_BAR_COUNTS)
        self._bar_count_combo.setCurrentText(DEFAULT_BAR_COUNT)
        self._bar_count_combo.setFixedWidth(85)
        self._bar_count_combo.currentIndexChanged.connect(self._on_bar_count_changed)
        toolbar_layout.addWidget(self._bar_count_combo)

        # 指标管理
        self._btn_indicator = PushButton("指标")
        self._btn_indicator.setIcon(FluentIcon.DEVELOPER_TOOLS)
        self._btn_indicator.clicked.connect(self._on_show_indicator_panel)
        toolbar_layout.addWidget(self._btn_indicator)

        # 保存方案
        self._btn_save_scheme = PushButton("保存方案")
        self._btn_save_scheme.setIcon(FluentIcon.SAVE)
        self._btn_save_scheme.clicked.connect(self._on_save_scheme)
        toolbar_layout.addWidget(self._btn_save_scheme)

        # ── 视图缩放按钮组 ──
        zoom_panel = QWidget()
        zoom_panel.setObjectName("zoomPanel")
        zoom_layout = QHBoxLayout(zoom_panel)
        zoom_layout.setContentsMargins(4, 2, 4, 2)
        zoom_layout.setSpacing(4)

        from qfluentwidgets import TransparentToolButton

        # 视图标签
        zoom_layout.addWidget(BodyLabel("视图"))

        # 自动适应
        self._btn_fit = TransparentToolButton(FluentIcon.FIT_PAGE, self)
        self._btn_fit.setToolTip("自动适应")
        self._btn_fit.clicked.connect(self._on_fit_content)
        zoom_layout.addWidget(self._btn_fit)

        # 放大
        self._btn_zoom_in = TransparentToolButton(FluentIcon.ZOOM_IN, self)
        self._btn_zoom_in.setToolTip("放大")
        self._btn_zoom_in.clicked.connect(self._on_zoom_in)
        zoom_layout.addWidget(self._btn_zoom_in)

        # 缩小
        self._btn_zoom_out = TransparentToolButton(FluentIcon.ZOOM_OUT, self)
        self._btn_zoom_out.setToolTip("缩小")
        self._btn_zoom_out.clicked.connect(self._on_zoom_out)
        zoom_layout.addWidget(self._btn_zoom_out)

        toolbar_layout.addWidget(zoom_panel)

        # 状态标签
        self._status_label = BodyLabel("")
        self._status_label.setObjectName("statusLabel")
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self._status_label)

        content_layout.addWidget(toolbar)

        # ── AI 分析面板 ──
        from guanlan.ui.view.panel import ChartAnalysisPanel
        self._analysis_panel = ChartAnalysisPanel(content)
        self._analysis_panel.refresh_requested.connect(self._on_ai_analysis)
        content_layout.addWidget(self._analysis_panel)

        # ── 图表区域 ──
        self._chart_container = QWidget()
        self._chart_container.setObjectName("chartContainer")
        self._chart_layout = QVBoxLayout(self._chart_container)
        self._chart_layout.setContentsMargins(0, 0, 0, 0)
        self._chart_layout.setSpacing(0)

        self._create_chart_widget()

        content_layout.addWidget(self._chart_container, 1)

        self._apply_style()
        qconfig.themeChanged.connect(self._apply_style)

    def _create_chart_widget(self) -> None:
        """创建 QtChart 实例"""
        self._chart = QtChart(
            self._chart_container,
            inner_height=self._ind_mgr.calc_inner_height(),
        )
        self._chart.legend(visible=True, ohlc=True, percent=False, lines=True)
        # 中国配色：红涨绿跌
        self._chart.candle_style(
            up_color=COLOR_UP, down_color=COLOR_DOWN,
            wick_up_color=COLOR_UP, wick_down_color=COLOR_DOWN,
        )
        self._chart.volume_config(
            up_color=COLOR_UP_ALPHA, down_color=COLOR_DOWN_ALPHA,
        )
        # 本地化：中国时区 + 中文日期格式 + 配置左右价格轴
        self._chart.run_script(f'''
            {self._chart.id}.chart.applyOptions({{
                localization: {{
                    locale: 'zh-CN',
                    dateFormat: 'yyyy-MM-dd',
                }},
                leftPriceScale: {{
                    visible: false,  // 默认隐藏，通过开关控制
                    borderVisible: true,
                }},
                rightPriceScale: {{
                    visible: true,
                    borderVisible: true,
                }}
            }})
        ''')
        self._chart_layout.addWidget(self._chart.get_webview(), 1)

        # 注入 JS 全局错误拦截器（简化输出）
        self._chart.win.run_script("""
            window.addEventListener('error', function(e) {
                console.error('[Chart JS Error]', e.message);
            });
            // 包装 series.update 以捕获具体哪个 series 出错
            (function() {
                var _origUpdate = LightweightCharts.LineSeries
                    ? LightweightCharts.LineSeries.prototype.update
                    : null;
                var wrapUpdate = function(obj, label) {
                    if (!obj || !obj.series || !obj.series.update) return;
                    var orig = obj.series.update.bind(obj.series);
                    obj.series.update = function(data) {
                        try { return orig(data); }
                        catch(e) {
                            console.error('[series.update 失败]', label, e.message);
                            throw e;
                        }
                    };
                };
                // 延迟包装，等所有 series 创建完成
                window._wrapChartUpdates = function() {
                    for (var key in window) {
                        var v = window[key];
                        if (v && v.series && v.series.update) {
                            if (!v.series._wrapped) {
                                wrapUpdate(v, key);
                                v.series._wrapped = true;
                            }
                        }
                    }
                };
            })();
        """)

    def _destroy_chart_widget(self) -> None:
        """销毁旧 QtChart，释放 JS 资源"""
        old_webview = self._chart.get_webview()
        self._chart_layout.removeWidget(old_webview)
        old_webview.deleteLater()
        self._chart = None  # type: ignore[assignment]

    def _apply_style(self) -> None:
        """应用样式"""
        from qfluentwidgets import isDarkTheme
        from guanlan.ui.common.style import Theme

        # 同步 QFluentWidgets 的主题到 StyleSheet
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self, ["common.qss", "window.qss", "chart.qss"], theme=theme)

    def _on_save_scheme(self) -> None:
        """保存当前配置为方案"""
        if not self._vt_symbol:
            InfoBar.warning(
                "提示", "请先选择合约",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return

        from .scheme_dialog import SaveSchemeDialog

        # 推荐名称：合约代码 + 周期
        symbol = self._vt_symbol.rsplit(".", 1)[0] if "." in self._vt_symbol else self._vt_symbol
        default_name = f"{symbol} {self._current_period}"

        dlg = SaveSchemeDialog(default_name, parent=self)
        if dlg.exec():
            name = dlg.get_name()
            data = {
                "vt_symbol": self._vt_symbol,
                "period": self._current_period,
                "bar_count": self._bar_count,
                "indicators": self._ind_mgr.get_settings(),
            }
            chart_scheme.save_scheme(name, data)
            InfoBar.success(
                "成功", f"方案 \"{name}\" 已保存",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )

    def _on_ai_analysis(self) -> None:
        """请求 AI 分析"""
        # 检查合约
        if not self._vt_symbol:
            InfoBar.warning(
                "提示", "请先选择合约",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return

        # 检查指标
        state = self._ind_mgr.get_analysis_state()
        if not state:
            InfoBar.warning(
                "提示", "请先添加技术指标",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return

        # 检查 AI 配置
        from guanlan.core.services.ai import get_config
        try:
            config = get_config()
            missing = config.validate()
            if missing:
                InfoBar.warning(
                    "AI 未配置",
                    f"模型 {', '.join(missing)} 缺少 API Key，请先配置",
                    parent=self, duration=3000, position=InfoBarPosition.TOP,
                )
                return
        except Exception as e:
            InfoBar.error(
                "AI 配置错误", str(e),
                parent=self, duration=3000, position=InfoBarPosition.TOP,
            )
            return

        # 获取当前价格
        if not self._bars:
            InfoBar.warning(
                "提示", "暂无行情数据",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return

        current_price = self._bars[-1]["close"]

        # 设置加载状态
        self._analysis_panel.set_loading(True)

        # 启动工作线程
        self._ai_worker = AIAnalysisWorker(
            state,
            self._vt_symbol,
            current_price,
            self,
        )
        self._ai_worker.analysis_finished.connect(self._on_analysis_finished)
        self._ai_worker.analysis_error.connect(self._on_analysis_error)
        self._ai_worker.start()

    def _on_analysis_finished(self, data: dict) -> None:
        """AI 分析完成"""
        self._analysis_panel.set_loading(False)
        self._analysis_panel.set_result(data)

    def _on_analysis_error(self, error_msg: str) -> None:
        """AI 分析失败"""
        self._analysis_panel.set_loading(False)
        InfoBar.error(
            "分析失败", error_msg,
            parent=self, duration=5000, position=InfoBarPosition.TOP,
        )

    def apply_scheme(self, scheme_data: dict) -> None:
        """应用方案配置并打开图表

        Parameters
        ----------
        scheme_data : dict
            方案数据，包含 vt_symbol / period / bar_count / indicators
        """
        vt_symbol = scheme_data.get("vt_symbol", "")
        if not vt_symbol:
            return

        period = scheme_data.get("period", self._current_period)
        bar_count = scheme_data.get("bar_count")
        indicators = scheme_data.get("indicators", {})

        # 预设周期、条数和指标到 _settings，set_symbol 会调用 _load_settings 加载
        # 但我们需要在 _load_settings 之后覆盖，所以用延迟方式
        override: dict = {"period": period, "indicators": indicators}
        if bar_count is not None:
            override["bar_count"] = bar_count
        self._scheme_override = override
        self.set_symbol(vt_symbol)
        self._scheme_override = None

    def _on_show_indicator_panel(self) -> None:
        """弹出指标管理面板"""
        active = self._ind_mgr.get_settings()
        view = IndicatorFlyoutView(active, parent=self)
        view.indicator_toggled.connect(self._on_indicator_toggled)
        view.indicator_edit_requested.connect(self._on_indicator_edit)
        self._indicator_flyout = Flyout.make(
            view, self._btn_indicator, self,
            aniType=FlyoutAnimationType.DROP_DOWN,
        )

    # ── 事件注册 ──────────────────────────────────────

    def _register_events(self) -> None:
        """注册事件"""
        self._event_engine.register(EVENT_TICK, self._on_tick_event)
        self._event_engine.register(EVENT_TRADE, self._on_trade_event)

    def _unregister_events(self) -> None:
        """注销事件"""
        self._event_engine.unregister(EVENT_TICK, self._on_tick_event)
        self._event_engine.unregister(EVENT_TRADE, self._on_trade_event)

    def _on_tick_event(self, event: Event) -> None:
        """Tick 事件（VNPY 线程）"""
        tick: TickData = event.data
        if tick.vt_symbol == self._vt_symbol:
            self._signal_tick.emit(tick)

    def _on_trade_event(self, event: Event) -> None:
        """成交事件（VNPY 线程）"""
        trade: TradeData = event.data
        if trade.vt_symbol == self._vt_symbol:
            self._signal_trade.emit(trade)

    # ── 合约选择 ──────────────────────────────────────

    def _load_favorites(self) -> None:
        """加载收藏品种到合约下拉列表"""
        from guanlan.core.setting import contract as contract_setting

        contracts = contract_setting.load_contracts()
        favorites = contract_setting.load_favorites()

        for key in favorites:
            c = contracts.get(key, {})
            name = c.get("name", key)
            vt_symbol = c.get("vt_symbol", "")
            exchange_str = c.get("exchange", "")
            if not vt_symbol:
                continue

            # vt_symbol 格式为 "OI2605.CZCE" 或 "OI2605"，提取纯合约代码
            symbol = vt_symbol.rsplit(".", 1)[0] if "." in vt_symbol else vt_symbol

            # 转为交易所格式（如 CZCE: OI2605 → OI605）
            exchange_symbol = SymbolConverter.to_exchange(symbol, Exchange(exchange_str))
            full_vt = f"{exchange_symbol}.{exchange_str}"
            self._symbol_combo.addItem(
                f"{name}  {exchange_symbol}",
                userData=full_vt,
            )

        self._symbol_combo.setCurrentIndex(-1)

    def _on_symbol_selected(self, index: int) -> None:
        """下拉选中合约（有 userData 的收藏项）"""
        if index < 0:
            return
        vt_symbol = self._symbol_combo.itemData(index)
        if vt_symbol:
            self.set_symbol(vt_symbol)

    def _on_symbol_input(self) -> None:
        """手动输入合约后回车

        EditableComboBox 内部 _onReturnPressed 先执行，
        会把裸文本 addItem 到下拉列表。
        本方法随后检测并解析替换。
        """
        index = self._symbol_combo.currentIndex()
        if index < 0:
            return

        # 已有 userData 说明是收藏项或已解析项，跳过
        if self._symbol_combo.itemData(index):
            return

        text = self._symbol_combo.itemText(index)
        from guanlan.core.setting import contract as contract_setting

        resolved = contract_setting.resolve_symbol(text)

        if not resolved:
            # 解析失败：移除裸文本项，提示用户
            self._symbol_combo.blockSignals(True)
            self._symbol_combo.removeItem(index)
            self._symbol_combo.setCurrentIndex(-1)
            self._symbol_combo.blockSignals(False)
            InfoBar.warning(
                "合约未找到",
                f"无法识别 \"{text}\"，请检查品种代码是否正确",
                parent=self, duration=3000, position=InfoBarPosition.TOP,
            )
            return

        # 解析成功：用完整格式替换裸文本项
        name, resolved_vt, _exchange_str = resolved
        symbol_part = resolved_vt.rsplit(".", 1)[0] if "." in resolved_vt else resolved_vt
        display = f"{name}  {symbol_part}"
        self._symbol_combo.blockSignals(True)
        self._symbol_combo.removeItem(index)
        self._symbol_combo.addItem(display, userData=resolved_vt)
        self._symbol_combo.setCurrentIndex(self._symbol_combo.count() - 1)
        self._symbol_combo.setText(display)
        self._symbol_combo.blockSignals(False)

        self.set_symbol(resolved_vt)

    def set_symbol(self, vt_symbol: str) -> None:
        """设置合约（外部调用或下拉选择）"""
        if not vt_symbol:
            return

        # 统一转为交易所格式（如 OI2605.CZCE → OI605.CZCE）
        if "." in vt_symbol:
            symbol, exchange_str = vt_symbol.rsplit(".", 1)
            exchange_symbol = SymbolConverter.to_exchange(symbol, Exchange(exchange_str))
            vt_symbol = f"{exchange_symbol}.{exchange_str}"

        if vt_symbol == self._vt_symbol:
            return

        # 保存旧合约的配置（含视口）
        if self._vt_symbol:
            self._save_settings()

        self._vt_symbol = vt_symbol
        self.setWindowTitle(f"实时图表 - {vt_symbol}")

        # 同步下拉框（外部调用时）
        self._symbol_combo.blockSignals(True)
        matched = False
        for i in range(self._symbol_combo.count()):
            if self._symbol_combo.itemData(i) == vt_symbol:
                self._symbol_combo.setCurrentIndex(i)
                matched = True
                break
        if not matched:
            # 外部传入的合约不在收藏中，追加到列表（显示与收藏项一致的格式）
            from guanlan.core.setting import contract as contract_setting
            resolved = contract_setting.resolve_symbol(vt_symbol)
            if resolved:
                sym = resolved[1].rsplit(".", 1)[0] if "." in resolved[1] else resolved[1]
                display = f"{resolved[0]}  {sym}"
            else:
                display = vt_symbol
            self._symbol_combo.addItem(display, userData=vt_symbol)
            self._symbol_combo.setCurrentIndex(self._symbol_combo.count() - 1)
        self._symbol_combo.blockSignals(False)

        # 订阅行情
        from guanlan.core.app import AppEngine
        AppEngine.instance().subscribe(vt_symbol)

        # 切换合约时清空成交记录
        self._trade_records.clear()

        # 加载该合约的保存配置
        self._load_settings()

        # 初始化图表
        self._init_chart()

    def _init_chart(self) -> None:
        """初始化图表（切换合约或周期时调用）"""
        self._rebuilding = True
        try:
            # 清空状态
            self._bars.clear()
            self._chart_initialized = False
            self._chart_ready = False
            self._entry_time = None
            self._entry_price = None
            self._entry_direction = None
            self._profit_lines.clear()

            # 先加载指标实例（不创建图表线），以便计算正确的 inner_height
            self._ind_mgr.clear_all()
            self._ind_mgr.load_instances(self._settings.get("indicators", {}))

            # 用正确的 inner_height 创建 chart
            self._destroy_chart_widget()
            self._create_chart_widget()

            # 创建 K 线生成器
            self._create_bar_generator()

            # 加载历史数据
            history_loaded = self._load_history()

            # 使用 rebuild 统一初始化指标
            # 与指标 toggle 的 _rebuild_chart 走完全相同的路径，
            # 避免 init_all / rebuild 两条路径差异导致 JS "Value is null"
            self._ind_mgr.rebuild(self._chart)

            # 重放成交标记（切换周期时保留）
            self._replay_trade_markers()

            if history_loaded:
                self._status_label.setText(f"已加载 {len(self._bars)} 根历史K线")
            else:
                self._status_label.setText("无历史数据，等待实时行情")
        finally:
            self._rebuilding = False

    # ── K 线生成器 ────────────────────────────────────

    def _create_bar_generator(self) -> None:
        """根据当前周期创建 K 线生成器"""
        p = self._period
        if p.is_second:
            # 秒级
            self._bar_generator = ChartBarGenerator(
                on_bar=self._on_bar,
                second_window=p.second_window,
            )
        elif p.is_daily and p.is_window:
            # 多日窗口（2日/3日/5日）：日线 bar → update_bar 聚合
            self._bar_generator = ChartBarGenerator(
                on_bar=self._on_1min_bar,
                window=p.window,
                on_window_bar=self._on_bar,
                daily=True,
            )
        elif p.is_daily:
            # 1 日模式
            self._bar_generator = ChartBarGenerator(
                on_bar=self._on_bar,
                daily=True,
            )
        elif p.is_window:
            # 分钟/小时窗口
            self._bar_generator = ChartBarGenerator(
                on_bar=self._on_1min_bar,
                window=p.window,
                on_window_bar=self._on_bar,
                interval=p.interval,
            )
        else:
            # 1 分钟模式
            self._bar_generator = ChartBarGenerator(
                on_bar=self._on_bar,
            )

    def _on_1min_bar(self, bar: BarData) -> None:
        """1 分钟 bar 回调（仅用于多分钟窗口中间层）"""
        if self._bar_generator:
            self._bar_generator.update_bar(bar)

    def _on_bar(self, bar: BarData) -> None:
        """目标周期 bar 完成回调"""
        bar_dict = bar_to_dict(bar)

        if self._bars:
            last_time = self._bars[-1]["time"]
            if bar_dict["time"] < last_time:
                # 忽略时间早于已加载历史的 bar（行情回放等场景）
                return
            if bar_dict["time"] == last_time:
                self._bars[-1] = bar_dict
            else:
                self._bars.append(bar_dict)
        else:
            self._bars.append(bar_dict)

        # 用 bulk_run 将「副图 + 指标线 + 主图」更新打包为单次 JS 执行，
        # 防止浏览器 requestAnimationFrame 在中间态触发渲染 → "Value is null"
        with self._chart.win.bulk_run:
            self._ind_mgr.on_bar(bar_dict)
            self._update_chart_bar(bar_dict, is_new=True)

    def _handle_first_tick(self, tick: TickData) -> None:
        """首次 Tick：隐藏状态提示后切换到常规处理"""
        self._status_label.hide()
        self._signal_tick.disconnect(self._handle_first_tick)
        self._signal_tick.connect(self._handle_tick)
        self._handle_tick(tick)

    def _handle_tick(self, tick: TickData) -> None:
        """处理 Tick（主线程）

        将 tick 喂给 bar generator 更新数据模型，但不立即刷新图表。
        图表渲染由 _flush_pending_tick 定时器节流驱动（每 TICK_THROTTLE_MS 毫秒一次），
        避免高频 tick 导致 JS 队列堆积引发 "Value is null"。
        """
        if not self._bar_generator or self._rebuilding:
            return

        prev_bar_count = len(self._bars)

        self._bar_generator.update_tick(tick)

        new_bar_count = len(self._bars)

        # 产生了新 bar（on_bar 回调已执行，包括图表更新）
        if new_bar_count != prev_bar_count:
            return

        # 当前 bar 还在更新中 → 缓存最新 tick，等定时器刷新
        self._pending_tick = tick

    def _flush_pending_tick(self) -> None:
        """定时器回调：将缓存的最新 tick 刷新到图表

        每 TICK_THROTTLE_MS 毫秒执行一次。多个 tick 之间只取最后一个，
        保证图表显示最新价格，同时大幅减少 JS 调用频率。
        """
        tick = self._pending_tick
        if tick is None:
            return
        self._pending_tick = None

        if not self._bar_generator or self._rebuilding:
            return

        if self._bar_generator._daily:
            # 日线模式
            bar = self._bar_generator.bar
            if not bar:
                return
            if self._bar_generator.window > 0:
                # 多日窗口：合并 window_bar（已完成日）+ 当日 bar
                wbar = self._bar_generator.window_bar
                if wbar:
                    bar_dict = {
                        "time": wbar.datetime.strftime("%Y-%m-%d"),
                        "open": wbar.open_price,
                        "high": max(wbar.high_price, bar.high_price),
                        "low": min(wbar.low_price, bar.low_price),
                        "close": bar.close_price,
                        "volume": wbar.volume + bar.volume,
                    }
                else:
                    bar_dict = bar_to_dict(bar)
                    bar_dict["time"] = bar.datetime.strftime("%Y-%m-%d")
            else:
                # 1 日模式
                bar_dict = bar_to_dict(bar)
                bar_dict["time"] = bar.datetime.strftime("%Y-%m-%d")
        elif self._bar_generator.window > 0:
            # 窗口模式：bar 是 1 分钟中间 bar，window_bar 是目标周期在建 bar
            wbar = self._bar_generator.window_bar
            mbar = self._bar_generator.bar
            if not mbar:
                return
            if wbar:
                # 合并窗口 bar 和当前分钟 bar 的最新数据
                bar_dict = {
                    "time": wbar.datetime.replace(second=0, microsecond=0)
                        .strftime("%Y-%m-%d %H:%M:%S"),
                    "open": wbar.open_price,
                    "high": max(wbar.high_price, mbar.high_price),
                    "low": min(wbar.low_price, mbar.low_price),
                    "close": mbar.close_price,
                    "volume": wbar.volume + mbar.volume,
                }
            else:
                # 窗口刚完成，新窗口第一根分钟 bar 还在建
                bar_dict = bar_to_dict(mbar)
                bar_dict["time"] = mbar.datetime.replace(
                    second=0, microsecond=0,
                ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 秒级/1 分钟模式：直接用 bar
            bar = self._bar_generator.bar
            if not bar:
                return
            bar_dict = bar_to_dict(bar)
            normalized = ChartBarGenerator.normalize_bar_time(
                bar.datetime, self._bar_generator.second_window,
            )
            bar_dict["time"] = normalized.strftime("%Y-%m-%d %H:%M:%S")

        if self._bars:
            last_time = self._bars[-1]["time"]
            if bar_dict["time"] < last_time:
                # 忽略时间早于已加载历史的 bar（行情回放等场景）
                return
            if bar_dict["time"] == last_time:
                # 更新最后一根 bar 的 OHLCV（保持原始时间）
                self._bars[-1].update({
                    "open": bar_dict["open"],
                    "high": bar_dict["high"],
                    "low": bar_dict["low"],
                    "close": bar_dict["close"],
                    "volume": bar_dict["volume"],
                })
            else:
                # 新 bar（时间晚于最后一根），追加
                self._bars.append(bar_dict)
        else:
            self._bars.append(bar_dict)
        # 用 bulk_run 将「副图时间轴同步 + 主图更新」打包为单次 JS 执行，
        # 防止浏览器 rAF 在中间态触发渲染 → "Value is null"
        with self._chart.win.bulk_run:
            self._ind_mgr.on_tick_update(bar_dict)
            self._update_chart_bar(bar_dict, is_new=False)

    # ── 历史数据加载 ──────────────────────────────────

    def _load_history(self) -> bool:
        """从数据库加载历史 K 线数据"""
        if not self._vt_symbol:
            return False

        # 条数为 0 时不加载历史数据，仅接收实时推送
        if self._bar_count == 0:
            return False

        # 大量数据加载提示
        if self._bar_count >= 5000 or self._bar_count == -1:
            label = "全部" if self._bar_count == -1 else str(self._bar_count)
            InfoBar.info(
                title="加载中",
                content=f"正在加载 {label} 条历史数据，请稍候...",
                parent=self, duration=2000,
                position=InfoBarPosition.TOP,
            )

        bar_dicts = self._data_loader.load(
            self._vt_symbol, self._period, self._bar_count,
        )
        if not bar_dicts:
            return False

        # 使用 extend 保持与 _ind_mgr._bars 的共享引用
        self._bars.extend(bar_dicts)

        # 初始化图表
        df = pd.DataFrame(self._bars)
        self._chart.set(df)
        self._chart_initialized = True
        self._chart_ready = True

        return True

    # ── 图表更新 ──────────────────────────────────────

    def _update_chart_bar(self, bar_dict: dict, is_new: bool) -> None:
        """更新图表 K 线"""
        if not self._chart_initialized:
            df = pd.DataFrame(self._bars)
            if df.empty:
                return
            self._chart.set(df)
            self._chart_initialized = True
            self._chart_ready = True  # 图表已准备就绪，可以执行 JS 操作
        else:
            series = pd.Series(bar_dict)
            self._chart.update(series)

    # ── 指标管理（UI 事件） ──────────────────────────

    def _on_indicator_toggled(self, name: str, checked: bool) -> None:
        """指标勾选状态变化"""
        # 记录操作前的 inner_height
        old_height = self._ind_mgr.calc_inner_height()

        if checked:
            saved_params = self._settings.get("indicators", {}).get(name, {})
            self._ind_mgr.add(name, saved_params)
        else:
            self._ind_mgr.remove(name)

        self._save_settings()

        # 只在 inner_height 改变时才 rebuild（副图数量变化导致布局改变）
        new_height = self._ind_mgr.calc_inner_height()
        if new_height != old_height:
            self._rebuild_chart()

    def _on_indicator_edit(self, name: str) -> None:
        """编辑指标参数"""
        # 先关闭指标面板 Flyout
        if self._indicator_flyout:
            self._indicator_flyout.close()
            self._indicator_flyout = None

        ind = self._ind_mgr.get(name)
        if not ind:
            return

        from guanlan.ui.view.window.cta import SettingEditor
        editor = SettingEditor(ind.get_params(), strategy_name=name, parent=self)

        if editor.exec():
            setting = editor.get_setting()
            ind.update_setting(setting)
            self._save_settings()
            self._rebuild_chart()

    def _rebuild_chart(self) -> None:
        """重建图表（移除指标或参数变化时）

        销毁旧 QtChart 并重建，彻底清除 JS 端残留的线 series。
        """
        self._rebuilding = True
        try:
            self._destroy_chart_widget()
            self._create_chart_widget()

            # 重设 K 线数据
            if self._bars:
                df = pd.DataFrame(self._bars)
                self._chart.set(df)
                self._chart_initialized = True
                self._chart_ready = True  # 图表已准备就绪，可以执行 JS 操作

            # 重建所有指标
            self._ind_mgr.rebuild(self._chart)

            # 重放成交标记
            self._replay_trade_markers()
        finally:
            self._rebuilding = False

    # ── 成交标记 ──────────────────────────────────────

    def _snap_to_bar_time(self, dt: datetime) -> str:
        """将时间对齐到当前周期的 K 线起始时间"""
        if self._period.is_daily:
            # 日线模式：用交易日归整
            from guanlan.core.utils.trading_period import get_trading_date
            return get_trading_date(dt)
        elif self._period.is_second:
            normalized = ChartBarGenerator.normalize_bar_time(
                dt, self._period.second_window,
            )
        elif self._period.is_window:
            # 分钟/小时窗口：用 total_minutes 归整
            normalized = ChartBarGenerator.normalize_bar_time(
                dt, window=self._period.window,
            )
        else:
            # 1 分钟模式：截断秒
            normalized = dt.replace(second=0, microsecond=0)
        return normalized.strftime("%Y-%m-%d %H:%M:%S")

    def _handle_trade(self, trade: TradeData) -> None:
        """处理成交事件（主线程）"""
        if not self._bars:
            return

        self._trade_records.append(trade)

        time_str = self._snap_to_bar_time(trade.datetime)

        # 开仓标记
        if trade.offset == Offset.OPEN:
            if trade.direction == Direction.LONG:
                self._draw_marker(time_str, "below", "arrow_up", "#EF5350", "买多")
            else:
                self._draw_marker(time_str, "above", "arrow_down", "#26A69A", "卖空")

            self._entry_time = time_str
            self._entry_price = trade.price
            self._entry_direction = trade.direction

        # 平仓标记 + 盈亏连线
        else:
            if trade.direction == Direction.LONG:
                # 买平 → 之前是做空
                self._draw_marker(time_str, "below", "arrow_up", "#EF5350", "买平")
                if self._entry_price is not None:
                    profit = self._entry_price - trade.price
                    self._draw_profit_line(time_str, trade.price, profit)
            else:
                # 卖平 → 之前是做多
                self._draw_marker(time_str, "above", "arrow_down", "#26A69A", "卖平")
                if self._entry_price is not None:
                    profit = trade.price - self._entry_price
                    self._draw_profit_line(time_str, trade.price, profit)

            self._entry_time = None
            self._entry_price = None
            self._entry_direction = None

    def _draw_marker(
        self, time_str: str, position: str, shape: str, color: str, text: str
    ) -> None:
        """绘制信号标记"""
        try:
            self._chart.marker(
                time=time_str, position=position,
                shape=shape, color=color, text=text,
            )
        except Exception:
            pass

    def _draw_profit_line(
        self, exit_time: str, exit_price: float, profit: float
    ) -> None:
        """绘制盈亏连接线"""
        if not self._entry_time or not self._entry_price:
            return

        line_color = "#EF5350" if profit > 0 else "#26A69A"
        try:
            line = self._chart.create_line(
                name="", color=line_color, style="dashed", width=1,
                price_line=False, price_label=False,
            )
            line_data = pd.DataFrame([
                {"time": self._entry_time, "value": self._entry_price},
                {"time": exit_time, "value": exit_price},
            ])
            line.set(line_data)
            self._profit_lines.append(line)
        except Exception:
            pass

    def _replay_trade_markers(self) -> None:
        """重放缓存的成交标记（图表重建后调用）"""
        if not self._trade_records:
            return

        # 重置持仓跟踪状态，从头重放
        self._entry_time = None
        self._entry_price = None
        self._entry_direction = None
        self._profit_lines.clear()

        for trade in self._trade_records:
            time_str = self._snap_to_bar_time(trade.datetime)

            if trade.offset == Offset.OPEN:
                if trade.direction == Direction.LONG:
                    self._draw_marker(time_str, "below", "arrow_up", "#EF5350", "买多")
                else:
                    self._draw_marker(time_str, "above", "arrow_down", "#26A69A", "卖空")
                self._entry_time = time_str
                self._entry_price = trade.price
                self._entry_direction = trade.direction
            else:
                if trade.direction == Direction.LONG:
                    self._draw_marker(time_str, "below", "arrow_up", "#EF5350", "买平")
                    if self._entry_price is not None:
                        profit = self._entry_price - trade.price
                        self._draw_profit_line(time_str, trade.price, profit)
                else:
                    self._draw_marker(time_str, "above", "arrow_down", "#26A69A", "卖平")
                    if self._entry_price is not None:
                        profit = trade.price - self._entry_price
                        self._draw_profit_line(time_str, trade.price, profit)
                self._entry_time = None
                self._entry_price = None
                self._entry_direction = None

    # ── 周期切换 ──────────────────────────────────────

    def _on_unit_changed(self) -> None:
        """单位切换时更新数值预设列表"""
        unit = self._period_unit_combo.currentText()
        presets = PRESET_NUMBERS.get(unit, PRESET_NUMBERS[DEFAULT_UNIT])
        self._period_num_combo.blockSignals(True)
        self._period_num_combo.clear()
        self._period_num_combo.addItems(presets)
        self._period_num_combo.setText(presets[0] if presets else "1")
        self._period_num_combo.blockSignals(False)
        self._on_period_changed()

    def _on_period_changed(self) -> None:
        """数字或单位变更时触发"""
        num_text = self._period_num_combo.text().strip()
        unit = self._period_unit_combo.currentText()
        if not num_text or not unit:
            return

        period = f"{num_text}{unit}"
        if period == self._current_period:
            return

        p = Period.parse(period)
        if not p:
            InfoBar.warning(
                title="周期无效",
                content=Period.error_message(period),
                parent=self, position=InfoBarPosition.TOP, duration=3000,
            )
            return

        self._current_period = period
        self._period = p

        if self._vt_symbol:
            self._ind_mgr.clear_all()
            self._init_chart()
            self._save_settings()

    def _on_bar_count_changed(self) -> None:
        """历史条数变更时触发"""
        text = self._bar_count_combo.currentText()
        if text == "全部":
            count = -1
        else:
            try:
                count = int(text)
            except ValueError:
                return
        if count == self._bar_count:
            return

        self._bar_count = count
        if self._vt_symbol:
            self._init_chart()
            self._save_settings()

    # ── 持久化 ────────────────────────────────────────

    def _load_settings(self) -> None:
        """加载合约配置"""
        self._settings = chart_setting.get_setting(self._vt_symbol)

        # 方案覆盖：apply_scheme 设置的周期、条数和指标优先
        if self._scheme_override:
            self._settings["period"] = self._scheme_override["period"]
            self._settings["indicators"] = self._scheme_override["indicators"]
            if "bar_count" in self._scheme_override:
                self._settings["bar_count"] = self._scheme_override["bar_count"]

        # 恢复周期
        saved_period = self._settings.get("period", self._current_period)
        num_str, unit_str = Period.decompose(saved_period)
        period = f"{num_str}{unit_str}"
        p = Period.parse(period)
        if p:
            self._current_period = period
            self._period = p
            self._period_num_combo.blockSignals(True)
            self._period_unit_combo.blockSignals(True)
            # 先切换单位和预设列表，再设数字
            self._period_unit_combo.setCurrentText(unit_str)
            presets = PRESET_NUMBERS.get(unit_str, PRESET_NUMBERS[DEFAULT_UNIT])
            self._period_num_combo.clear()
            self._period_num_combo.addItems(presets)
            idx = self._period_num_combo.findText(num_str)
            if idx >= 0:
                self._period_num_combo.setCurrentIndex(idx)
            self._period_num_combo.setText(num_str)
            self._period_num_combo.blockSignals(False)
            self._period_unit_combo.blockSignals(False)

        # 恢复历史条数
        saved_count = self._settings.get("bar_count", DEFAULT_BAR_COUNT)
        display_text = "全部" if saved_count == -1 else str(saved_count)
        self._bar_count_combo.blockSignals(True)
        self._bar_count_combo.setCurrentText(display_text)
        self._bar_count_combo.blockSignals(False)
        if saved_count == -1:
            self._bar_count = -1
        else:
            try:
                self._bar_count = int(saved_count)
            except (ValueError, TypeError):
                self._bar_count = int(DEFAULT_BAR_COUNT)

    def _save_settings(self) -> None:
        """保存品种的周期、条数和指标参数"""
        if not self._vt_symbol:
            return

        self._settings["period"] = self._current_period
        self._settings["bar_count"] = self._bar_count
        self._settings["indicators"] = self._ind_mgr.get_settings()

        chart_setting.save_setting(self._vt_symbol, self._settings)

    # ── 视图控制 ──────────────────────────────────────

    def _on_fit_content(self) -> None:
        """自动适应视图"""
        logger.info(f"自动适应按钮被点击，_chart_ready={self._chart_ready}")
        if not self._chart_ready:
            logger.warning("图表未就绪，跳过执行")
            return
        try:
            script = f"{self._chart.id}.chart.timeScale().fitContent();"
            logger.info(f"执行 JS: {script}")
            self._chart.run_script(script)
            logger.info("执行自动适应视图成功")
        except Exception as e:
            logger.error(f"自动适应视图失败: {e}", exc_info=True)

    def _on_zoom_in(self) -> None:
        """放大视图"""
        if not self._chart_ready:
            return
        try:
            # 使用 applyOptions 修改 barSpacing 来实现缩放
            self._chart.run_script(f"""
                (function() {{
                    const currentOptions = {self._chart.id}.chart.timeScale().options();
                    const currentSpacing = currentOptions.barSpacing || 6;
                    {self._chart.id}.chart.timeScale().applyOptions({{ barSpacing: currentSpacing * 1.2 }});
                }})();
            """)
            logger.info("放大视图")
        except Exception as e:
            logger.error(f"放大视图失败: {e}")

    def _on_zoom_out(self) -> None:
        """缩小视图"""
        if not self._chart_ready:
            return
        try:
            # 使用 applyOptions 修改 barSpacing 来实现缩放
            self._chart.run_script(f"""
                (function() {{
                    const currentOptions = {self._chart.id}.chart.timeScale().options();
                    const currentSpacing = currentOptions.barSpacing || 6;
                    {self._chart.id}.chart.timeScale().applyOptions({{ barSpacing: currentSpacing / 1.2 }});
                }})();
            """)
            logger.info("缩小视图")
        except Exception as e:
            logger.error(f"缩小视图失败: {e}")

    # ── 生命周期 ──────────────────────────────────────

    def closeEvent(self, event) -> None:
        """窗口关闭"""
        self._tick_timer.stop()
        self._unregister_events()
        if self._bar_generator:
            self._bar_generator.generate()
        self._save_settings()
        event.accept()
