# -*- coding: utf-8 -*-
"""
观澜量化 - 首页监控组件

Author: 海山观澜
"""

from PySide6.QtGui import QColor

from qfluentwidgets import isDarkTheme

from .log import LogMonitor
from .position import PositionMonitor
from .order import OrderMonitor
from .trade import TradeMonitor
from .account import AccountMonitor
from .trading import TradingPanel
from .pnl import PortfolioMonitor
from .risk import RiskMonitor
from .ai_chat import AIChatPanel
from .chart_analysis import ChartAnalysisPanel


# ── 交易方向颜色（多/空） ──

def long_color() -> QColor:
    return QColor(255, 85, 85) if isDarkTheme() else QColor(200, 50, 50)

def short_color() -> QColor:
    return QColor(85, 200, 85) if isDarkTheme() else QColor(40, 150, 40)


# ── 日志级别颜色（深色主题 / 浅色主题） ──

LEVEL_COLORS: dict[int, tuple[QColor, QColor]] = {
    10: (QColor(140, 140, 140), QColor(100, 100, 100)),   # DEBUG - 灰色
    30: (QColor(255, 185, 0), QColor(180, 130, 0)),       # WARNING - 橙色
    40: (QColor(255, 85, 85), QColor(200, 50, 50)),       # ERROR - 红色
    50: (QColor(255, 50, 50), QColor(220, 0, 0)),         # CRITICAL - 深红
}


__all__ = [
    "LogMonitor",
    "PositionMonitor",
    "OrderMonitor",
    "TradeMonitor",
    "AccountMonitor",
    "TradingPanel",
    "PortfolioMonitor",
    "RiskMonitor",
    "AIChatPanel",
    "ChartAnalysisPanel",
    "long_color",
    "short_color",
    "LEVEL_COLORS",
]
