# -*- coding: utf-8 -*-
"""
观澜量化 - 对话框基类

提供主题感知的样式支持。
子类在 _init_theme() 中传入需要应用样式的控件，自动跟随主题切换。

Author: 海山观澜
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from qfluentwidgets import MessageBoxBase, isDarkTheme, qconfig

from guanlan.ui.common.style import StyleSheet, Theme


class ThemedDialog(MessageBoxBase):
    """带主题支持的对话框基类"""

    _qss_files: list[str] = ["common.qss"]

    def _init_theme(self, *panels: QWidget) -> None:
        """初始化主题样式

        Parameters
        ----------
        *panels : QWidget
            需要应用主题样式的控件
        """
        self._themed_panels = panels
        self._apply_theme_style()
        qconfig.themeChanged.connect(self._apply_theme_style)

    def _apply_theme_style(self) -> None:
        """应用主题样式到已注册的控件"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        for panel in self._themed_panels:
            panel.setAttribute(Qt.WA_StyledBackground, True)
            StyleSheet.apply(panel, self._qss_files, theme)
