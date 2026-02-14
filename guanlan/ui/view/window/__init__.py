# -*- coding: utf-8 -*-
"""
观澜量化 - 窗口模块

Author: 海山观澜
"""

from .account import AccountManagerWindow
from .advisor_trader import AdvisorTraderWindow
from .ai_settings import AISettingsWindow
from .backtest import BacktestWindow
from .contract import ContractEditDialog
from .cta import CtaStrategyWindow
from .exception import ExceptionDialog, install_exception_hook
from .portfolio import PortfolioStrategyWindow
from .risk_manager import RiskManagerDialog
from .script import ScriptTraderWindow

__all__ = [
    'AccountManagerWindow',
    'AdvisorTraderWindow',
    'AISettingsWindow',
    'BacktestWindow',
    'ContractEditDialog',
    'CtaStrategyWindow',
    'ExceptionDialog',
    'install_exception_hook',
    'PortfolioStrategyWindow',
    'RiskManagerDialog',
    'ScriptTraderWindow',
]
