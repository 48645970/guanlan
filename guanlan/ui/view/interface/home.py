# -*- coding: utf-8 -*-
"""
观澜量化 - 首页界面

Banner + 嵌入式监控面板（日志/持仓/资金 | 委托/成交/盈亏）。

Author: 海山观澜
"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QStackedWidget,
)

from qfluentwidgets import FluentIcon, Pivot

from guanlan.core.constants import HELP_URL, RESOURCES_DIR
from guanlan.core.events import signal_bus
from guanlan.ui.common.mixin import ThemeMixin
from guanlan.ui.widgets.components.banner import HomeBanner
from guanlan.ui.view.panel import (
    LogMonitor, PositionMonitor, OrderMonitor, TradeMonitor,
    AccountMonitor, TradingPanel, PortfolioMonitor, RiskMonitor,
    AIChatPanel,
)


class HomeInterface(ThemeMixin, QWidget):
    """
    首页界面

    结构：
    - Banner（标题 + 模块卡片）
    - 嵌入式监控面板（日志/持仓/资金 | 委托/成交/盈亏）
    """

    # 使用默认 common.qss + interface.qss，无需指定 _qss_files

    # 跨线程信号（EventEngine → Qt 主线程）
    _signal_strategy = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("homeInterface")

        # Banner
        banner_image = QPixmap(str(RESOURCES_DIR / "images" / "header.png"))
        self.banner = HomeBanner(
            "心在山海之外，方能观其全貌",
            banner_image,
            self
        )

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Banner（固定高度）
        layout.addWidget(self.banner)

        # 中间区域（左右各半）
        self._middle_area = QWidget(self)
        middle_layout = QHBoxLayout(self._middle_area)
        middle_layout.setContentsMargins(10, 4, 10, 4)
        middle_layout.setSpacing(8)

        # 交易 / 风控
        left_middle = self._create_trading_panel()
        middle_layout.addWidget(left_middle, 1)

        # 资金 / 盈亏
        mid_middle = self._create_account_panel()
        middle_layout.addWidget(mid_middle, 2)

        # AI 聊天助手
        ai_area = QFrame(self)
        ai_area.setObjectName("aiChatPanel")
        ai_layout = QVBoxLayout(ai_area)
        ai_layout.setContentsMargins(8, 8, 8, 8)
        self.ai_chat = AIChatPanel(ai_area)
        ai_layout.addWidget(self.ai_chat)
        middle_layout.addWidget(ai_area, 2)

        layout.addWidget(self._middle_area, 1)

        # 监控面板（占满剩余空间）
        self._monitor = QWidget(self)
        monitor_inner = QHBoxLayout(self._monitor)
        monitor_inner.setContentsMargins(10, 4, 10, 8)
        monitor_inner.setSpacing(8)

        left_panel = self._create_left_panel()
        monitor_inner.addWidget(left_panel, 1)

        right_panel = self._create_right_panel()
        monitor_inner.addWidget(right_panel, 1)

        layout.addWidget(self._monitor, 2)

        self._init_banner_cards()
        self._init_strategy_badges()
        self._init_theme()

    def _create_trading_panel(self) -> QFrame:
        """创建交易/风控面板（TAB 切换）"""
        panel = QFrame(self)
        panel.setObjectName("tradingPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        pivot = Pivot(panel)
        stacked = QStackedWidget(panel)

        self.trading_panel = TradingPanel(panel)
        self.trading_panel.setObjectName("tradingTab")
        stacked.addWidget(self.trading_panel)

        self.risk_monitor = RiskMonitor(panel)
        self.risk_monitor.setObjectName("riskTab")
        stacked.addWidget(self.risk_monitor)

        pivot.addItem(
            routeKey="tradingTab", text="交易",
            onClick=lambda: stacked.setCurrentWidget(self.trading_panel),
        )
        pivot.addItem(
            routeKey="riskTab", text="风控",
            onClick=lambda: stacked.setCurrentWidget(self.risk_monitor),
        )
        pivot.setCurrentItem("tradingTab")

        layout.addWidget(pivot)
        layout.addWidget(stacked, 1)
        return panel

    def _create_account_panel(self) -> QFrame:
        """创建资金/盈亏面板（TAB 切换）"""
        panel = QFrame(self)
        panel.setObjectName("accountPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        pivot = Pivot(panel)
        stacked = QStackedWidget(panel)

        self.account_monitor = AccountMonitor(panel)
        self.account_monitor.setObjectName("accountTab")
        stacked.addWidget(self.account_monitor)

        self.portfolio_monitor = PortfolioMonitor(panel)
        self.portfolio_monitor.setObjectName("portfolioTab")
        stacked.addWidget(self.portfolio_monitor)

        pivot.addItem(
            routeKey="accountTab", text="资金",
            onClick=lambda: stacked.setCurrentWidget(self.account_monitor),
        )
        pivot.addItem(
            routeKey="portfolioTab", text="盈亏",
            onClick=lambda: stacked.setCurrentWidget(self.portfolio_monitor),
        )
        pivot.setCurrentItem("accountTab")

        layout.addWidget(pivot)
        layout.addWidget(stacked, 1)
        return panel

    def _create_left_panel(self) -> QFrame:
        """创建左栏面板（日志 / 持仓）"""
        panel = QFrame(self)
        panel.setObjectName("logPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        pivot = Pivot(panel)
        stacked = QStackedWidget(panel)

        self.log_monitor = LogMonitor(panel)
        self.log_monitor.setObjectName("logTab")
        stacked.addWidget(self.log_monitor)

        self.position_monitor = PositionMonitor(panel)
        self.position_monitor.setObjectName("positionTab")
        stacked.addWidget(self.position_monitor)

        pivot.addItem(
            routeKey="logTab", text="日志",
            onClick=lambda: stacked.setCurrentWidget(self.log_monitor),
        )
        pivot.addItem(
            routeKey="positionTab", text="持仓",
            onClick=lambda: stacked.setCurrentWidget(self.position_monitor),
        )
        pivot.setCurrentItem("logTab")

        layout.addWidget(pivot)
        layout.addWidget(stacked, 1)
        return panel

    def _create_right_panel(self) -> QFrame:
        """创建右栏面板（委托 / 成交）"""
        panel = QFrame(self)
        panel.setObjectName("orderPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        pivot = Pivot(panel)
        stacked = QStackedWidget(panel)

        self.order_monitor = OrderMonitor(panel)
        self.order_monitor.setObjectName("orderTab")
        stacked.addWidget(self.order_monitor)

        self.trade_monitor = TradeMonitor(panel)
        self.trade_monitor.setObjectName("tradeTab")
        stacked.addWidget(self.trade_monitor)

        pivot.addItem(
            routeKey="orderTab", text="委托",
            onClick=lambda: stacked.setCurrentWidget(self.order_monitor),
        )
        pivot.addItem(
            routeKey="tradeTab", text="成交",
            onClick=lambda: stacked.setCurrentWidget(self.trade_monitor),
        )
        pivot.setCurrentItem("orderTab")

        layout.addWidget(pivot)
        layout.addWidget(stacked, 1)
        return panel

    def _init_banner_cards(self) -> None:
        """初始化 Banner 模块卡片"""
        self.banner.add_module_card(
            FluentIcon.PEOPLE,
            "账户管理",
            "Account Manager",
            "accountsInterface",
            signal_bus.switch_to_route
        )

        self.banner.add_module_card(
            FluentIcon.ROBOT,
            "AI 配置",
            "AI Settings",
            "aiSettingsInterface",
            signal_bus.switch_to_route
        )

        self._portfolio_card = self.banner.add_module_card(
            FluentIcon.TILES,
            "组合策略",
            "Portfolio Strategy",
            "portfolioStrategyInterface",
            signal_bus.switch_to_route
        )

        self._cta_card = self.banner.add_module_card(
            FluentIcon.ROBOT,
            "CTA 策略",
            "CTA Strategy",
            "ctaStrategyInterface",
            signal_bus.switch_to_route
        )

        self._script_card = self.banner.add_module_card(
            FluentIcon.COMMAND_PROMPT,
            "脚本策略",
            "Script Trader",
            "scriptTraderInterface",
            signal_bus.switch_to_route
        )

        self._advisor_card = self.banner.add_module_card(
            FluentIcon.SPEED_HIGH,
            "辅助交易",
            "Advisor Trader",
            "advisorTraderInterface",
            signal_bus.switch_to_route
        )

        self._chart_card = self.banner.add_module_card(
            FluentIcon.MARKET,
            "实时图表",
            "Realtime Chart",
            "realtimeChartInterface",
            signal_bus.switch_to_route
        )

        self.banner.add_module_card(
            FluentIcon.HISTORY,
            "策略回测",
            "Backtesting",
            "backtestInterface",
            signal_bus.switch_to_route
        )

        self.banner.add_module_card(
            FluentIcon.CERTIFICATE,
            "风控管理",
            "Risk Manager",
            "riskManagerInterface",
            signal_bus.switch_to_route
        )

        self.banner.add_link_card(
            FluentIcon.HELP,
            "作者专栏",
            "Author",
            HELP_URL
        )

    # ── 策略运行徽标 ──

    def _init_strategy_badges(self) -> None:
        """初始化策略运行数量徽标"""
        self._active_states: dict[str, dict[str, bool]] = {
            "cta": {},
            "script": {},
            "portfolio": {},
        }

        self._badge_cards: dict[str, object] = {
            "cta": self._cta_card,
            "script": self._script_card,
            "portfolio": self._portfolio_card,
        }

        self._signal_strategy.connect(self._on_strategy_event)

        from guanlan.core.app import AppEngine
        engine = AppEngine.instance().event_engine

        from guanlan.core.trader.cta import EVENT_CTA_STRATEGY
        from guanlan.core.trader.script import EVENT_SCRIPT_STRATEGY
        from guanlan.core.trader.portfolio import EVENT_PORTFOLIO_STRATEGY

        engine.register(EVENT_CTA_STRATEGY, lambda e: self._signal_strategy.emit("cta", e.data))
        engine.register(EVENT_SCRIPT_STRATEGY, lambda e: self._signal_strategy.emit("script", e.data))
        engine.register(EVENT_PORTFOLIO_STRATEGY, lambda e: self._signal_strategy.emit("portfolio", e.data))

    def _on_strategy_event(self, category: str, data: dict) -> None:
        """策略状态变更 → 更新徽标"""
        if category == "script":
            name = data.get("script_name", "")
            active = data.get("active", False)
        else:
            name = data.get("strategy_name", "")
            active = data.get("trading", False)

        states = self._active_states[category]
        states[name] = active

        count = sum(1 for v in states.values() if v)
        self._badge_cards[category].set_badge(count)

    def _on_theme_changed(self) -> None:
        """主题变化回调（覆盖基类方法）"""
        super()._on_theme_changed()
        self.banner.update()
