# -*- coding: utf-8 -*-
"""
观澜量化 - UI Mixin 集合

Author: 海山观澜
"""

from PySide6.QtCore import Qt, QEvent, QRect, QPoint

from qfluentwidgets import qconfig, isDarkTheme

from guanlan.ui.common.style import StyleSheet, Theme


class CursorFixMixin:
    """FluentWidget 修复 Mixin

    修复 qframelesswindow (LinuxFramelessWindowBase) 的两个问题：

    1. 光标残留：eventFilter 全局拦截所有 MouseMove，不检查鼠标是否
       在本窗口内，导致鼠标在其他窗口移动时也会触发 resize 光标。
    2. 隐藏后拖动失效：closeEvent 中 hide() 时标题栏按钮残留 pressed
       状态，canDrag() 永远返回 False，导致窗口无法拖动。

    用法（放在 FluentWidget 前面）：

        class MyWindow(CursorFixMixin, FluentWidget):
            ...
    """

    def eventFilter(self, obj, event) -> bool:
        """仅当窗口可见且鼠标在本窗口范围内时才处理光标"""
        et = event.type()
        if et == QEvent.MouseMove:
            if not self.isVisible():
                return False
            # 将全局鼠标位置转换为窗口内的相对位置
            local_pos = self.mapFromGlobal(event.globalPos())
            # 检查相对位置是否在窗口矩形内
            if not self.rect().contains(local_pos):
                return False

        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """隐藏窗口前重置标题栏按钮状态"""
        from qframelesswindow.titlebar.title_bar_buttons import (
            TitleBarButton, TitleBarButtonState,
        )
        for btn in self.titleBar.findChildren(TitleBarButton):
            btn.setState(TitleBarButtonState.NORMAL)
        event.ignore()
        self.hide()


class ThemeMixin:
    """
    主题监听 Mixin

    使用方式：
    1. 组件继承此 Mixin（多重继承时放在第一位）
    2. 在 __init__ 末尾调用 `self._init_theme()`
    3. 默认加载 common.qss + interface.qss，独立窗口覆盖 `_qss_files`

    示例（嵌入式界面，使用默认样式）：
    ```python
    class MyInterface(ThemeMixin, ScrollArea):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_theme()  # common.qss + interface.qss
    ```

    示例（独立窗口）：
    ```python
    class MyWindow(ThemeMixin, FramelessDialog):
        _qss_files = ["common.qss", "window.qss"]

        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_theme()
    ```

    示例（专属样式）：
    ```python
    class SpecialWidget(ThemeMixin, QWidget):
        _qss_files = ["widgets/special.qss"]

        def __init__(self, parent=None):
            super().__init__(parent)
            self._init_theme()
    ```
    """

    # 样式文件列表（按顺序加载并拼接）
    _qss_files: list[str] = ["common.qss", "interface.qss"]

    def _init_theme(self) -> None:
        """初始化主题监听（在 __init__ 末尾调用）"""
        self._apply_theme_style()
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _apply_theme_style(self) -> None:
        """应用当前主题样式"""
        if self._qss_files:
            theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
            StyleSheet.apply(self, self._qss_files, theme)

    def _on_theme_changed(self) -> None:
        """
        主题变化回调

        子类可覆盖此方法添加额外逻辑：
        ```python
        def _on_theme_changed(self) -> None:
            super()._on_theme_changed()
            # 额外处理，如重绘等
            self.update()
        ```
        """
        self._apply_theme_style()

    @staticmethod
    def current_theme() -> Theme:
        """获取当前主题"""
        return Theme.DARK if isDarkTheme() else Theme.LIGHT

    @staticmethod
    def is_dark() -> bool:
        """是否为深色主题"""
        return isDarkTheme()
