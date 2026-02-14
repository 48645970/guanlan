# -*- coding: utf-8 -*-
"""
观澜量化 - 指标注册表

@register_indicator 装饰器自动注册指标类。

Author: 海山观澜
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseIndicator

_INDICATOR_REGISTRY: dict[str, type[BaseIndicator]] = {}


def register_indicator(name: str):
    """装饰器：注册指标类"""
    def decorator(cls: type[BaseIndicator]) -> type[BaseIndicator]:
        _INDICATOR_REGISTRY[name] = cls
        return cls
    return decorator


def get_indicator(name: str) -> type[BaseIndicator]:
    """获取指标类"""
    return _INDICATOR_REGISTRY[name]


def get_all_indicators() -> dict[str, type[BaseIndicator]]:
    """获取所有已注册指标"""
    return dict(_INDICATOR_REGISTRY)
