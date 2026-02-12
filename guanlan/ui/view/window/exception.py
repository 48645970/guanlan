# -*- coding: utf-8 -*-
"""
观澜量化 - 全局异常处理窗口

捕获主线程和后台线程的未处理异常，弹窗显示详细信息。
通过 Signal 机制保证线程安全。

Author: 海山观澜
"""

import sys
import types
import threading
import traceback

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication

from qfluentwidgets import (
    BodyLabel, PushButton, TextEdit, FluentIcon, FluentWidget,
    isDarkTheme, qconfig,
)

from guanlan.core.utils.logger import logger
from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.common.mixin import CursorFixMixin
from guanlan.ui.common.style import StyleSheet, Theme


class ExceptionDialog(CursorFixMixin, FluentWidget):
    """全局异常处理窗口

    任何线程的未处理异常都会通过 Signal 安全地在主线程弹窗显示。
    """

    _exception_signal = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()
        self._exception_signal.connect(self._show_exception)

    def _init_ui(self) -> None:
        """初始化界面"""
        self.setWindowTitle("程序异常")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(720, 500)

        # 标题栏
        self.titleBar.setFixedHeight(48)
        self.titleBar.vBoxLayout.insertStretch(0, 1)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()

        icon_path = get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            self.titleBar.setIcon(icon)

        # 内容容器
        self._content_widget = QWidget(self)
        self._content_widget.setObjectName("dialogContent")

        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(20, 20, 20, 16)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(self._content_widget)

        # 提示标签
        self.tip_label = BodyLabel("程序发生未处理的异常，以下为详细信息：")
        content_layout.addWidget(self.tip_label)

        # 异常信息文本框
        self.text_edit = TextEdit(self)
        self.text_edit.setReadOnly(True)
        content_layout.addWidget(self.text_edit, 1)

        # 按钮
        copy_btn = PushButton("复制", self, FluentIcon.COPY)
        copy_btn.clicked.connect(self._copy_text)

        close_btn = PushButton("关闭", self, FluentIcon.CLOSE)
        close_btn.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        content_layout.addLayout(btn_layout)

        # 应用主题样式
        self._apply_content_style()
        qconfig.themeChanged.connect(self._apply_content_style)

    def _apply_content_style(self) -> None:
        """应用内容区域样式"""
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        StyleSheet.apply(self._content_widget, [
            "common.qss", "window.qss",
        ], theme)

    def _show_exception(self, msg: str) -> None:
        """显示异常信息"""
        self.text_edit.setText(msg)
        self.show()
        self.raise_()
        self.activateWindow()

    def _copy_text(self) -> None:
        """复制异常信息到剪贴板"""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_edit.toPlainText())


def install_exception_hook() -> ExceptionDialog:
    """安装全局异常钩子

    捕获主线程（sys.excepthook）和后台线程（threading.excepthook）的
    未处理异常，通过弹窗显示并写入日志。

    必须在 QApplication 创建之后调用。
    返回 ExceptionDialog 实例，调用方需保持引用防止被 GC 回收。
    """
    dialog = ExceptionDialog()

    def excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: types.TracebackType | None,
    ) -> None:
        """主线程异常钩子"""
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
            "主线程未处理异常"
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

        msg = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        dialog._exception_signal.emit(msg)

    def threading_excepthook(args: threading.ExceptHookArgs) -> None:
        """后台线程异常钩子"""
        if args.exc_value and args.exc_traceback:
            logger.opt(
                exception=(args.exc_type, args.exc_value, args.exc_traceback)
            ).critical("后台线程未处理异常")
            sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)

        msg = "".join(
            traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback
            )
        )
        dialog._exception_signal.emit(msg)

    sys.excepthook = excepthook
    threading.excepthook = threading_excepthook

    return dialog
