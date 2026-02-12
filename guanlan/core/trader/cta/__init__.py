# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 策略引擎

Author: 海山观澜
"""

from .base import APP_NAME, EVENT_CTA_LOG, EVENT_CTA_STRATEGY, EVENT_CTA_STOPORDER
from .engine import CtaEngine
from .template import BaseParams, BaseState, CtaTemplate, CtaSignal, TargetPosTemplate

__all__ = [
    "APP_NAME",
    "EVENT_CTA_LOG",
    "EVENT_CTA_STRATEGY",
    "EVENT_CTA_STOPORDER",
    "CtaEngine",
    "BaseParams",
    "BaseState",
    "CtaTemplate",
    "CtaSignal",
    "TargetPosTemplate",
]
