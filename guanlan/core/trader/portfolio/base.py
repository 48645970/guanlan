# -*- coding: utf-8 -*-
"""
观澜量化 - 组合策略基础定义

常量、EngineType 枚举、事件类型。
仅保留实盘相关内容（回测后续再做）。

Author: 海山观澜
"""

from enum import Enum


APP_NAME = "PortfolioStrategy"


class EngineType(Enum):
    LIVE = "实盘"
    BACKTESTING = "回测"


EVENT_PORTFOLIO_LOG = "ePortfolioLog"
EVENT_PORTFOLIO_STRATEGY = "ePortfolioStrategy"
