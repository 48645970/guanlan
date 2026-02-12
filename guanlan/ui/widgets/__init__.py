# -*- coding: utf-8 -*-
"""
观澜量化 - UI 组件库

提供自定义 UI 组件，用于替代 QFluentWidgets 以解决兼容性问题

主要组件：
- GuanlanWindow: 基于 QMainWindow 的观澜自定义窗口
- GuanlanTitleBar: 观澜标题栏组件
- 组件: HomeBanner, FeatureCard, ModuleCard 等

Author: 海山观澜
"""

from .window import GuanlanWindow
from .components import GuanlanTitleBar
from .dialog import ThemedDialog

# 从 ui.common 重新导出（方便使用）
from ..common import StyleSheet, Theme, set_app_icon, get_icon_path, init_app_identity

__all__ = [
    'GuanlanWindow',
    'GuanlanTitleBar',
    'ThemedDialog',
    'StyleSheet',
    'Theme',
    'set_app_icon',
    'get_icon_path',
    'init_app_identity',
]
