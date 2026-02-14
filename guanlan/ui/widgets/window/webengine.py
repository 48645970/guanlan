# -*- coding: utf-8 -*-
"""
WebEngine 兼容 FluentWidget 窗口

解决 qframelesswindow 在 Linux 上与 QWebEngineView 的兼容性问题：
LinuxFramelessWindowBase._initFrameless() 会在 QCoreApplication 上安装
全局事件过滤器处理窗口边缘缩放，但 Chromium 子进程的内部事件经过该
Python 事件过滤器时会导致 segfault。

本类在首次实例化时 monkey-patch _initFrameless，将所有 FramelessWindow
的事件过滤器从 QCoreApplication 移到窗口自身，一劳永逸。

Author: 海山观澜
"""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from qfluentwidgets import FluentWidget

from guanlan.ui.common.mixin import CursorFixMixin


class WebEngineFluentWidget(CursorFixMixin, FluentWidget):
    """支持 QWebEngineView 的 FluentWidget

    所有需要嵌入 QWebEngineView（如 lightweight-charts）的窗口，
    继承此类代替 FluentWidget 即可，无需额外处理。
    """

    _patched: bool = False

    def __init__(self, parent=None) -> None:
        # 首次实例化时，全局修补所有 FramelessWindow
        if not WebEngineFluentWidget._patched:
            self._apply_global_patch()
            WebEngineFluentWidget._patched = True

        super().__init__(parent)

        # 修补自身（super().__init__ 中 _initFrameless 已被 patch，
        # 但首个实例的 super().__init__ 调用在 patch 之前，需要手动补救）
        QCoreApplication.instance().removeEventFilter(self)
        self.installEventFilter(self)

    @staticmethod
    def _apply_global_patch() -> None:
        """Monkey-patch LinuxFramelessWindowBase，修复所有 FramelessWindow 实例"""
        if sys.platform != "linux":
            return

        from qframelesswindow.linux import LinuxFramelessWindowBase
        _orig = LinuxFramelessWindowBase._initFrameless

        def _patched(self):
            _orig(self)
            QCoreApplication.instance().removeEventFilter(self)
            self.installEventFilter(self)

        LinuxFramelessWindowBase._initFrameless = _patched

        # 修补已存在的 FramelessWindow 实例（如主窗口）
        app = QCoreApplication.instance()
        if app is None:
            return

        for widget in app.topLevelWidgets():
            if isinstance(widget, LinuxFramelessWindowBase):
                app.removeEventFilter(widget)
                widget.installEventFilter(widget)
