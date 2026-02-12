# -*- coding: utf-8 -*-
"""
观澜量化 - 主窗口

基于 QFluentWidgets FluentWindow 构建的主窗口框架。

Author: 海山观澜
"""

import random
import sys
from datetime import datetime, timezone, timedelta

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, SplashScreen,
    SystemThemeListener, isDarkTheme, InfoBar, InfoBarPosition,
    BodyLabel,
)
from qfluentwidgets import FluentIcon as FIF

from guanlan.core.constants import APP_NAME, RESOURCES_DIR
from guanlan.ui.common.config import cfg, save_config
from guanlan.ui.common import signal_bus
from guanlan.ui.widgets.components.badge import ConnectionIndicator
from guanlan.ui.view.interface.home import HomeInterface
from guanlan.ui.view.interface.contract import ContractInterface
from guanlan.ui.view.interface.contract_query import ContractQueryInterface
from guanlan.ui.view.interface.data_manager import DataManagerInterface
from guanlan.ui.view.interface.data_recorder import DataRecorderInterface
from guanlan.ui.view.interface.setting import SettingInterface


class MainWindow(FluentWindow):
    """
    观澜主窗口

    基于 QFluentWidgets FluentWindow 构建。
    """

    def __init__(self):
        super().__init__()

        # 已开子窗口注册表（key → QWidget）
        self._child_windows: dict[str, QWidget] = {}
        # 持久子窗口注册表（单例，隐藏/显示，不销毁）
        self._persistent_windows: dict[str, QWidget] = {}

        # 初始化窗口
        self._init_window()

        # 创建系统主题监听器
        self.theme_listener = SystemThemeListener(self)

        # 创建引擎（通过 add_engine 注册，在 UI 界面之前启动）
        from guanlan.core.app import AppEngine
        from guanlan.core.trader.pnl import PortfolioEngine
        from guanlan.core.trader.portfolio import PortfolioStrategyEngine
        from guanlan.core.trader.cta import CtaEngine
        from guanlan.core.trader.script import ScriptEngine
        from guanlan.core.trader.risk import RiskEngine
        main_engine = AppEngine.instance().main_engine
        main_engine.add_engine(PortfolioEngine)
        main_engine.add_engine(PortfolioStrategyEngine)
        main_engine.add_engine(CtaEngine)
        main_engine.add_engine(ScriptEngine)
        main_engine.add_engine(RiskEngine)

        # 创建子界面
        self._create_interfaces()

        # 启用亚克力效果（仅 Windows 支持）
        if sys.platform == "win32":
            self.navigationInterface.setAcrylicEnabled(True)

        # 连接信号槽
        self._connect_signals()

        # 初始化导航
        self._init_navigation()

        # 初始化完成，关闭闪屏
        self.splash_screen.finish()

        # 启动主题监听
        self.theme_listener.start()

    def _init_window(self) -> None:
        """初始化窗口"""
        # 窗口大小（从配置读取）
        self.resize(
            cfg.get(cfg.windowWidth),
            cfg.get(cfg.windowHeight)
        )
        self.setMinimumWidth(cfg.get(cfg.windowMinWidth))

        # 恢复窗口位置（仅 Windows，Linux 下 Wayland 不支持）
        if sys.platform == "win32":
            saved_x = cfg.get(cfg.windowX)
            saved_y = cfg.get(cfg.windowY)

            if saved_x >= 0 and saved_y >= 0:
                # 使用保存的位置
                self.move(saved_x, saved_y)
            else:
                # 首次启动，居中显示
                desktop = QApplication.primaryScreen().availableGeometry()
                w, h = desktop.width(), desktop.height()
                self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        else:
            # Linux/macOS：居中显示（不保存位置）
            desktop = QApplication.primaryScreen().availableGeometry()
            w, h = desktop.width(), desktop.height()
            self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # 标题栏按钮居中（原始布局按钮贴顶）
        self.titleBar.vBoxLayout.insertStretch(0, 1)

        # 窗口图标和标题
        icon_path = RESOURCES_DIR / "images" / "logo.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        self.setWindowTitle(APP_NAME)
        self.titleBar.setTitle(APP_NAME)

        # 设置 Mica 效果（仅 Windows 11）
        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))

        # 创建闪屏（随机选择闪屏图片）
        splash_images = list((RESOURCES_DIR / "images").glob("splash_screen_*.png"))
        if splash_images:
            splash_path = random.choice(splash_images)
            splash_icon = QIcon(str(splash_path))
        else:
            splash_icon = self.windowIcon()

        # 标题栏时钟
        self._clock_label = BodyLabel("", self.titleBar)
        self._clock_label.setObjectName("clockLabel")
        self._update_clock()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        # 标题栏行情连接状态指示器
        self._connection_indicator = ConnectionIndicator(self.titleBar)
        self._connection_indicator.setConnected(False, "行情未连接")

        # 插入到窗口按钮之前：时钟 → 间距 → 指示器 → 间距
        idx = self.titleBar.hBoxLayout.count() - 1
        self.titleBar.hBoxLayout.insertWidget(
            idx, self._clock_label, 0, Qt.AlignVCenter
        )
        self.titleBar.hBoxLayout.insertSpacing(idx + 1, 16)
        self.titleBar.hBoxLayout.insertWidget(
            idx + 2, self._connection_indicator, 0, Qt.AlignVCenter
        )
        self.titleBar.hBoxLayout.insertSpacing(idx + 3, 12)

        self.splash_screen = SplashScreen(splash_icon, self)
        self.splash_screen.setIconSize(QSize(600, 400))
        self.splash_screen.raise_()


    def _create_interfaces(self) -> None:
        """创建子界面"""
        self.home_interface = HomeInterface(self)
        self.contract_interface = ContractInterface(self)
        self.contract_query_interface = ContractQueryInterface(self)
        self.data_manager_interface = DataManagerInterface(self)
        self.data_recorder_interface = DataRecorderInterface(self)
        self.setting_interface = SettingInterface(self)

    def _init_navigation(self) -> None:
        """初始化导航栏"""
        # 首页
        self.addSubInterface(
            self.home_interface,
            FIF.HOME,
            "首页"
        )

        # 合约管理
        self.addSubInterface(
            self.contract_interface,
            FIF.PIN,
            "合约管理"
        )

        # 标的查询
        self.addSubInterface(
            self.contract_query_interface,
            FIF.SEARCH,
            "标的查询"
        )

        # 数据管理
        self.addSubInterface(
            self.data_manager_interface,
            FIF.LIBRARY,
            "数据管理"
        )

        # 行情记录
        self.addSubInterface(
            self.data_recorder_interface,
            FIF.ALBUM,
            "行情记录"
        )

        # 添加分隔符
        self.navigationInterface.addSeparator()

        # 设置（底部）
        self.addSubInterface(
            self.setting_interface,
            FIF.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM
        )

    def _connect_signals(self) -> None:
        """连接信号槽"""
        # 导航信号
        signal_bus.navigate_to.connect(self._navigate_to)
        signal_bus.switch_to_route.connect(self._switch_to_route)
        signal_bus.exit_app.connect(self.close)

        # 账户信号
        from guanlan.core.events import signal_bus as core_signal_bus
        from guanlan.core.services.sound import play as play_sound
        core_signal_bus.account_connected.connect(
            lambda _: (self._update_market_status(), play_sound("connect"))
        )
        core_signal_bus.account_disconnected.connect(
            lambda _: (self._update_market_status(), play_sound("disconnect"))
        )

        # UI 信号
        signal_bus.mica_enabled_changed.connect(self.setMicaEffectEnabled)
        signal_bus.show_message.connect(self._show_message)
        signal_bus.support_signal.connect(self._on_support)

    def _navigate_to(self, route: str) -> None:
        """导航到指定界面"""
        # 对话框路由：弹出对话框而非切换界面
        if route == "riskManagerInterface":
            self._show_risk_manager()
            return
        if route == "accountsInterface":
            self._show_account_manager()
            return
        if route == "ctaStrategyInterface":
            self._show_cta_manager()
            return
        if route == "scriptTraderInterface":
            self._show_script_manager()
            return
        if route == "portfolioStrategyInterface":
            self._show_portfolio_strategy_manager()
            return
        if route == "backtestInterface":
            self._show_backtest_manager()
            return
        if route == "advisorTraderInterface":
            self._show_advisor_trader()
            return
        if route == "dataManagerInterface":
            self.switchTo(self.data_manager_interface)
            return
        if route == "tickRecorderInterface":
            self.switchTo(self.data_recorder_interface)
            return
        # 根据 route 查找并切换界面
        for interface in self.findChildren(QWidget):
            if interface.objectName() == route:
                self.stackedWidget.setCurrentWidget(interface)
                break

    def _switch_to_route(self, route: str) -> None:
        """处理路由切换"""
        self._navigate_to(route)

    def _show_message(self, title: str, content: str, level: str) -> None:
        """显示消息提示（跟随当前活动窗口）"""
        parent = QApplication.activeWindow() or self
        if level == "success":
            InfoBar.success(title, content, parent=parent, position=InfoBarPosition.TOP)
        elif level == "error":
            InfoBar.error(title, content, parent=parent, position=InfoBarPosition.TOP)
        elif level == "warning":
            InfoBar.warning(title, content, parent=parent, position=InfoBarPosition.TOP)
        else:
            InfoBar.info(title, content, parent=parent, position=InfoBarPosition.TOP)

    _WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

    _BJT = timezone(timedelta(hours=8))

    # 主力合约自动刷新时间
    _CONTRACT_REFRESH_TIME: tuple[int, int] = (8, 55)

    def _update_clock(self) -> None:
        """更新标题栏时钟（北京时间）+ 交易时段提醒 + 主力合约自动刷新"""
        now = datetime.now(self._BJT)
        weekday = self._WEEKDAYS[now.weekday()]
        self._clock_label.setText(f"{now:%Y-%m-%d %H:%M:%S} {weekday}")

        from guanlan.core.services.alert import futures
        futures.check(now.time())

        # 每个交易日 08:55 自动刷新主力合约
        key = (now.hour, now.minute)
        today = now.date()
        if (key == self._CONTRACT_REFRESH_TIME
                and getattr(self, "_contract_refresh_date", None) != today):
            from guanlan.core.services.calendar import is_trading_day
            if is_trading_day(today):
                self._contract_refresh_date = today
                signal_bus.contract_auto_refresh.emit()

    def _update_market_status(self) -> None:
        """更新标题栏行情连接状态指示器"""
        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        market_gw = app.market_gateway

        if market_gw and app.is_connected(market_gw):
            self._connection_indicator.setConnected(
                True, f"行情已连接: {market_gw}"
            )
        else:
            self._connection_indicator.setConnected(False, "行情未连接")

    def _show_risk_manager(self) -> None:
        """显示风控管理对话框"""
        from guanlan.ui.view.window import RiskManagerDialog
        dialog = RiskManagerDialog(self)
        dialog.exec()

    # ── 子窗口管理 ────────────────────────────────────────

    def _show_child_window(self, key: str, factory: callable) -> QWidget:
        """显示或创建子窗口

        已存在则激活，不存在则通过 factory 创建并注册。
        窗口关闭时自动从注册表移除。

        Parameters
        ----------
        key : str
            窗口唯一标识
        factory : callable
            创建窗口的工厂函数，返回 QWidget
        """
        window = self._child_windows.get(key)
        if window is not None:
            if window.isMinimized():
                window.setWindowState(
                    window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
                )
            window.show()
            window.raise_()
            window.activateWindow()
            return window

        window = factory()
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.destroyed.connect(lambda: self._child_windows.pop(key, None))
        self._child_windows[key] = window
        window.show()
        return window

    def _show_persistent_window(self, key: str, factory: callable) -> QWidget:
        """显示或创建持久子窗口（单例，隐藏/显示，不销毁）

        Parameters
        ----------
        key : str
            窗口唯一标识
        factory : callable
            创建窗口的工厂函数，返回 QWidget
        """
        window = self._persistent_windows.get(key)
        if window is None:
            window = factory()
            self._persistent_windows[key] = window

        if window.isMinimized():
            window.setWindowState(
                window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive
            )
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _close_all_child_windows(self) -> None:
        """关闭所有已开子窗口"""
        for window in list(self._child_windows.values()):
            window.close()
        self._child_windows.clear()

    def _show_account_manager(self) -> None:
        """显示账户管理窗口"""
        from guanlan.ui.view.window import AccountManagerWindow
        self._show_persistent_window("account", AccountManagerWindow)

    def _show_cta_manager(self) -> None:
        """显示 CTA 策略管理窗口"""
        from guanlan.ui.view.window import CtaStrategyWindow
        self._show_persistent_window("cta", CtaStrategyWindow)

    def _show_script_manager(self) -> None:
        """显示脚本策略管理窗口"""
        from guanlan.ui.view.window import ScriptTraderWindow
        self._show_persistent_window("script", ScriptTraderWindow)

    def _show_backtest_manager(self) -> None:
        """显示 CTA 回测窗口"""
        from guanlan.ui.view.window import BacktestWindow
        self._show_persistent_window("backtest", BacktestWindow)

    _advisor_seq: int = 0
    _advisor_count: int = 0

    def _show_advisor_trader(self) -> None:
        """打开辅助交易窗口（每次新建实例，支持多开）"""
        MainWindow._advisor_seq += 1
        key = f"advisor_trader_{MainWindow._advisor_seq}"

        def factory():
            from guanlan.ui.view.window import AdvisorTraderWindow
            w = AdvisorTraderWindow()
            w.destroyed.connect(self._on_advisor_closed)
            return w

        self._show_child_window(key, factory)
        MainWindow._advisor_count += 1
        self.home_interface._advisor_card.set_badge(MainWindow._advisor_count)

    def _on_advisor_closed(self) -> None:
        """辅助交易窗口关闭"""
        MainWindow._advisor_count = max(0, MainWindow._advisor_count - 1)
        self.home_interface._advisor_card.set_badge(MainWindow._advisor_count)

    def _show_portfolio_strategy_manager(self) -> None:
        """显示组合策略管理窗口"""
        from guanlan.ui.view.window import PortfolioStrategyWindow
        self._show_persistent_window("portfolio", PortfolioStrategyWindow)

    def _on_support(self) -> None:
        """打开支持页面"""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from guanlan.core.constants import HELP_URL
        QDesktopServices.openUrl(QUrl(HELP_URL))

    def showEvent(self, event) -> None:
        """窗口显示事件"""
        super().showEvent(event)

        # 恢复最大化状态（仅 Windows）
        if sys.platform == "win32" and cfg.get(cfg.windowMaximized):
            QTimer.singleShot(0, self.showMaximized)

    def resizeEvent(self, event) -> None:
        """窗口大小变化"""
        super().resizeEvent(event)
        if hasattr(self, "splash_screen"):
            self.splash_screen.resize(self.size())

    def closeEvent(self, event) -> None:
        """关闭事件"""
        # 关闭持久子窗口
        for window in self._persistent_windows.values():
            if hasattr(window, "_unregister_events"):
                window._unregister_events()
            window.deleteLater()
        self._persistent_windows.clear()

        # 关闭其他子窗口
        self._close_all_child_windows()

        # 停止主题监听器
        if hasattr(self, "theme_listener") and self.theme_listener.isRunning():
            self.theme_listener.terminate()
            self.theme_listener.wait()

        # 保存窗口状态（仅 Windows）
        if sys.platform == "win32":
            is_maximized = self.isMaximized()
            cfg.set(cfg.windowMaximized, is_maximized)

            # 保存窗口大小和位置（仅在非最大化状态下保存）
            if not is_maximized:
                cfg.set(cfg.windowWidth, self.width())
                cfg.set(cfg.windowHeight, self.height())
                cfg.set(cfg.windowX, self.x())
                cfg.set(cfg.windowY, self.y())
        else:
            # Linux/macOS：只保存窗口大小
            cfg.set(cfg.windowWidth, self.width())
            cfg.set(cfg.windowHeight, self.height())

        # 保存配置
        save_config()

        # 接受关闭事件
        event.accept()

    def _onThemeChangedFinished(self) -> None:
        """主题切换完成回调"""
        super()._onThemeChangedFinished()

        # 重试 Mica 效果
        if self.isMicaEffectEnabled():
            QTimer.singleShot(
                100,
                lambda: self.windowEffect.setMicaEffect(self.winId(), isDarkTheme())
            )
