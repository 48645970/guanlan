# -*- coding: utf-8 -*-
"""
观澜量化 - 系统工具

提供跨平台的系统信息获取功能

Author: 海山观澜
"""

import sys
import platform
from typing import NamedTuple

from PySide6.QtWidgets import QApplication


class SystemInfo(NamedTuple):
    """系统信息"""
    platform: str  # 平台：Windows/Linux/Darwin
    system: str  # 系统名称：Windows/Linux/macOS
    release: str  # 版本号
    version: str  # 详细版本
    machine: str  # 机器类型：x86_64/AMD64
    python_version: str  # Python 版本


def get_system_info() -> SystemInfo:
    """
    获取系统信息

    Returns
    -------
    SystemInfo
        系统信息对象

    Examples
    --------
    >>> info = get_system_info()
    >>> print(info.system)
    'Linux'
    >>> print(info.python_version)
    '3.13.0'
    """
    return SystemInfo(
        platform=sys.platform,
        system=platform.system(),
        release=platform.release(),
        version=platform.version(),
        machine=platform.machine(),
        python_version=platform.python_version(),
    )


def is_windows() -> bool:
    """
    判断是否为 Windows 系统

    Returns
    -------
    bool
        是否为 Windows

    Examples
    --------
    >>> is_windows()
    False
    """
    return sys.platform == "win32"


def is_linux() -> bool:
    """
    判断是否为 Linux 系统

    Returns
    -------
    bool
        是否为 Linux

    Examples
    --------
    >>> is_linux()
    True
    """
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """
    判断是否为 macOS 系统

    Returns
    -------
    bool
        是否为 macOS

    Examples
    --------
    >>> is_macos()
    False
    """
    return sys.platform == "darwin"


def is_win11() -> bool:
    """
    判断是否为 Windows 11 或更高版本

    Returns
    -------
    bool
        是否为 Windows 11+

    Examples
    --------
    >>> is_win11()
    False

    Notes
    -----
    Windows 11 的内部版本号 >= 22000
    """
    if not is_windows():
        return False

    try:
        return sys.getwindowsversion().build >= 22000  # type: ignore
    except AttributeError:
        return False


def desktop_size() -> tuple[int, int]:
    """
    获取桌面可用分辨率

    Returns
    -------
    tuple[int, int]
        (宽度, 高度) 单位：像素

    Examples
    --------
    >>> width, height = desktop_size()
    >>> print(f"屏幕分辨率: {width}x{height}")
    屏幕分辨率: 1920x1080

    Notes
    -----
    - 返回的是主屏幕的可用区域（不包括任务栏等）
    - 如果有多个屏幕，返回主屏幕的尺寸
    """
    try:
        screen = QApplication.primaryScreen()
        if screen is None:
            # 如果没有 QApplication 实例，使用备用方法
            screens = QApplication.screens()
            if screens:
                screen = screens[0]
            else:
                return (1920, 1080)  # 默认值

        geometry = screen.availableGeometry()
        return geometry.width(), geometry.height()
    except Exception:
        # 发生异常时返回默认值
        return (1920, 1080)


def screen_count() -> int:
    """
    获取屏幕数量

    Returns
    -------
    int
        屏幕数量

    Examples
    --------
    >>> screen_count()
    1
    """
    try:
        screens = QApplication.screens()
        return len(screens) if screens else 1
    except Exception:
        return 1


def all_screen_sizes() -> list[tuple[int, int]]:
    """
    获取所有屏幕的分辨率

    Returns
    -------
    list[tuple[int, int]]
        所有屏幕的 (宽度, 高度) 列表

    Examples
    --------
    >>> sizes = all_screen_sizes()
    >>> for i, (w, h) in enumerate(sizes):
    ...     print(f"屏幕 {i}: {w}x{h}")
    屏幕 0: 1920x1080
    """
    try:
        screens = QApplication.screens()
        if not screens:
            return [(1920, 1080)]

        sizes = []
        for screen in screens:
            geometry = screen.availableGeometry()
            sizes.append((geometry.width(), geometry.height()))
        return sizes
    except Exception:
        return [(1920, 1080)]


def dpi_scale() -> float:
    """
    获取 DPI 缩放比例

    Returns
    -------
    float
        DPI 缩放比例（1.0 = 100%, 1.5 = 150%）

    Examples
    --------
    >>> scale = dpi_scale()
    >>> print(f"DPI 缩放: {scale * 100}%")
    DPI 缩放: 100.0%
    """
    try:
        screen = QApplication.primaryScreen()
        if screen is None:
            screens = QApplication.screens()
            screen = screens[0] if screens else None

        if screen:
            return screen.devicePixelRatio()
        return 1.0
    except Exception:
        return 1.0


def is_dark_mode() -> bool:
    """
    判断系统是否处于深色模式

    Returns
    -------
    bool
        是否为深色模式

    Examples
    --------
    >>> is_dark_mode()
    False

    Notes
    -----
    此功能依赖于系统主题设置
    """
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPalette

        app = QApplication.instance()
        if app is None:
            return False

        palette = app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)

        # 判断窗口背景色的亮度
        brightness = (
            window_color.red() * 0.299
            + window_color.green() * 0.587
            + window_color.blue() * 0.114
        )

        # 亮度 < 128 认为是深色模式
        return brightness < 128
    except Exception:
        return False
