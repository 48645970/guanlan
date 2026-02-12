# -*- coding: utf-8 -*-
"""
样式表管理模块

提供样式表加载和主题管理功能

Author: 海山观澜
"""

from enum import Enum
from PySide6.QtWidgets import QWidget

from guanlan.core.constants import UI_QSS_DIR
from guanlan.core.utils.logger import get_logger

logger = get_logger(__name__)


class Theme(Enum):
    """主题枚举"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class StyleSheet:
    """样式表管理类"""

    # 当前主题（默认深色）
    _current_theme = Theme.DARK

    # 样式文件根目录
    _qss_root = UI_QSS_DIR

    @classmethod
    def set_theme(cls, theme: Theme):
        """设置当前主题"""
        if theme == Theme.AUTO:
            # TODO: 可以根据系统主题自动选择
            theme = Theme.DARK
        cls._current_theme = theme

    @classmethod
    def get_theme(cls) -> Theme:
        """获取当前主题"""
        return cls._current_theme

    @classmethod
    def is_dark_theme(cls) -> bool:
        """是否为深色主题"""
        return cls._current_theme == Theme.DARK

    @classmethod
    def load(cls, qss_file: str, theme: Theme = None) -> str:
        """
        加载样式表文件

        Parameters
        ----------
        qss_file : str
            样式文件名（不含路径，如 "fluent_window.qss"）
        theme : Theme, optional
            主题，默认使用当前主题

        Returns
        -------
        str
            样式表内容
        """
        if theme is None:
            theme = cls._current_theme

        qss_path = cls._qss_root / theme.value / qss_file

        if not qss_path.exists():
            logger.warning(f"样式文件不存在: {qss_path}")
            return ""

        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"加载样式文件失败: {e}")
            return ""

    @classmethod
    def apply(cls, widget: QWidget, qss_files: str | list[str], theme: Theme = None):
        """
        应用样式表到组件

        支持单个或多个 QSS 文件，多文件时按顺序拼接。

        Parameters
        ----------
        widget : QWidget
            要应用样式的组件
        qss_files : str | list[str]
            样式文件名或文件名列表
        theme : Theme, optional
            主题，默认使用当前主题
        """
        if isinstance(qss_files, str):
            qss_files = [qss_files]

        parts = [cls.load(f, theme) for f in qss_files]
        qss_content = "\n".join(p for p in parts if p)
        if qss_content:
            widget.setStyleSheet(qss_content)

    @classmethod
    def get_color(cls, color_type: str) -> str:
        """
        获取主题颜色

        Parameters
        ----------
        color_type : str
            颜色类型（如 "background", "text", "border" 等）

        Returns
        -------
        str
            颜色值
        """
        colors = {
            Theme.DARK: {
                "background": "rgb(32, 32, 32)",
                "background_light": "rgb(243, 243, 243)",
                "text": "white",
                "text_light": "black",
                "border": "rgba(0, 0, 0, 0.18)",
                "border_light": "rgba(0, 0, 0, 0.068)",
                "content_bg": "rgba(255, 255, 255, 0.0314)",
                "content_bg_light": "rgba(255, 255, 255, 0.5)",
                "hover": "rgba(255, 255, 255, 26)",
                "pressed": "rgba(255, 255, 255, 51)",
                "close_hover": "#c42b1c",
                "close_pressed": "#a52313",
            },
            Theme.LIGHT: {
                "background": "rgb(243, 243, 243)",
                "background_light": "rgb(32, 32, 32)",
                "text": "black",
                "text_light": "white",
                "border": "rgba(0, 0, 0, 0.068)",
                "border_light": "rgba(0, 0, 0, 0.18)",
                "content_bg": "rgba(255, 255, 255, 0.5)",
                "content_bg_light": "rgba(255, 255, 255, 0.0314)",
                "hover": "rgba(0, 0, 0, 26)",
                "pressed": "rgba(0, 0, 0, 51)",
                "close_hover": "#c42b1c",
                "close_pressed": "#a52313",
            }
        }

        return colors.get(cls._current_theme, colors[Theme.DARK]).get(color_type, "")
