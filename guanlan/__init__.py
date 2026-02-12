# -*- coding: utf-8 -*-
"""
观澜量化交易平台

Author: 海山观澜
"""

__version__ = "2.0.0"
__author__ = "海山观澜"

# 导出核心模块（便于使用）
from guanlan.core import constants
from guanlan.core.events import signal_bus

__all__ = ['constants', 'signal_bus']
