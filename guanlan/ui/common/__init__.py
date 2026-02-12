# -*- coding: utf-8 -*-
"""
观澜量化 - UI 公共模块

Author: 海山观澜
"""

from .config import cfg, load_config, save_config
from .style import StyleSheet, Theme
from .mixin import ThemeMixin
from .icon import init_app_identity, set_app_icon, get_icon_path

# signal_bus 已移到 core.events
from guanlan.core.events import signal_bus

# 从 core 重新导出常量（方便 UI 层使用）
from guanlan.core.constants import (
    APP_NAME, APP_NAME_EN, APP_VERSION, APP_AUTHOR, APP_YEAR, HELP_URL,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_WIDTH,
    InfoLevel
)

# 兼容别名
AUTHOR = APP_AUTHOR
VERSION = APP_VERSION
