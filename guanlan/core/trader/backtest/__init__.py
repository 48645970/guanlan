# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 回测模块

Author: 海山观澜
"""

from .engine import (
    APP_NAME,
    EVENT_BACKTESTER_LOG,
    EVENT_BACKTESTER_FINISHED,
    EVENT_BACKTESTER_OPT_FINISHED,
    BacktesterEngine,
)

__all__ = [
    "APP_NAME",
    "EVENT_BACKTESTER_LOG",
    "EVENT_BACKTESTER_FINISHED",
    "EVENT_BACKTESTER_OPT_FINISHED",
    "BacktesterEngine",
]
