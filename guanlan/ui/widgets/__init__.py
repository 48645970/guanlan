# -*- coding: utf-8 -*-
"""
观澜量化 - UI 组件库

提供自定义 UI 组件

主要组件：
- WebEngineFluentWidget: 支持 WebEngine 的 FluentWidget 窗口
- 组件: HomeBanner, FeatureCard, ModuleCard 等

Author: 海山观澜
"""

from .window import WebEngineFluentWidget
from .dialog import ThemedDialog

# 从 ui.common 重新导出（方便使用）
from ..common import StyleSheet, Theme, set_app_icon, get_icon_path, init_app_identity

__all__ = [
    'WebEngineFluentWidget',
    'ThemedDialog',
    'StyleSheet',
    'Theme',
    'set_app_icon',
    'get_icon_path',
    'init_app_identity',
]
