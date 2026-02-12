# -*- coding: utf-8 -*-
"""
图标工具

提供应用图标相关的工具函数

Author: 海山观澜
"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtCore import QCoreApplication

from guanlan.core.constants import RESOURCES_IMAGES_DIR

# 默认图标路径
_DEFAULT_ICON_PATH = RESOURCES_IMAGES_DIR / "logo.png"

# 应用程序类名（用于匹配 .desktop 文件的 StartupWMClass）
APP_CLASS_NAME = "guanlan"


def init_app_identity():
    """
    初始化应用程序标识

    设置 sys.argv[0] 和 applicationName 为 'guanlan'，
    使 GNOME 任务栏能匹配 .desktop 文件显示中文名称。

    必须在创建 QApplication 之前调用！
    """
    sys.argv[0] = APP_CLASS_NAME
    QCoreApplication.setApplicationName(APP_CLASS_NAME)


def set_app_icon(app=None, window=None, icon_path: str = None):
    """
    设置应用或窗口图标

    Parameters
    ----------
    app : QApplication, optional
        应用实例，设置后所有窗口都会使用此图标
    window : QWidget, optional
        窗口实例，只设置单个窗口图标
    icon_path : str, optional
        图标路径，默认使用观澜 logo
    """
    path = icon_path or str(_DEFAULT_ICON_PATH)
    if not Path(path).exists():
        return

    icon = QIcon(path)

    if app is not None:
        app.setWindowIcon(icon)

    if window is not None:
        window.setWindowIcon(icon)


def get_icon_path() -> str:
    """获取默认图标路径"""
    return str(_DEFAULT_ICON_PATH)
