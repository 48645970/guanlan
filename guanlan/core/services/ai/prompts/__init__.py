# -*- coding: utf-8 -*-
"""
观澜量化 - AI 提示词模板

Author: 海山观澜
"""

from .market import (
    MARKET_ANALYSIS_SYSTEM,
    HOTSPOT_SEARCH_SYSTEM,
)
from .kline import (
    KLINE_ANALYSIS_SYSTEM,
    KLINE_IMAGE_SYSTEM,
    format_kline_prompt,
)

__all__ = [
    "MARKET_ANALYSIS_SYSTEM",
    "HOTSPOT_SEARCH_SYSTEM",
    "KLINE_ANALYSIS_SYSTEM",
    "KLINE_IMAGE_SYSTEM",
    "format_kline_prompt",
]
