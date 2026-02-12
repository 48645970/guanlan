# -*- coding: utf-8 -*-
"""
观澜标题栏组件

自定义窗口标题栏，用于 GuanlanWindow

Author: 海山观澜
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint, Signal, QEvent, QObject
from PySide6.QtGui import QMouseEvent, QPixmap, QFont, QFontDatabase

from guanlan.ui.common.style import StyleSheet


class GuanlanTitleBar(QWidget):
    """
    观澜标题栏组件

    提供窗口拖动、最小化、最大化、关闭等功能
    """

    # 信号
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_pressed = False
        self._start_pos = QPoint()

        self._setup_ui()
        self._apply_styles()

        # 启用鼠标追踪
        self.setMouseTracking(True)

    def _setup_ui(self):
        """初始化 UI"""
        self.setFixedHeight(48)

        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # 窗口图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setScaledContents(True)
        self.icon_label.setObjectName("iconLabel")
        self.icon_label.hide()  # 默认隐藏，设置图标后显示
        layout.addWidget(self.icon_label)

        # 标题标签
        self.title_label = QLabel("观澜量化")
        self.title_label.setObjectName("titleLabel")
        # 设置支持中文的字体
        self._setup_title_font()

        # 窗口控制按钮
        self.min_btn = QPushButton("−")  # 最小化
        self.min_btn.setObjectName("minButton")
        self.min_btn.setFixedSize(46, 48)
        self.min_btn.clicked.connect(self.minimize_clicked.emit)

        self.max_btn = QPushButton("□")  # 最大化
        self.max_btn.setObjectName("maxButton")
        self.max_btn.setFixedSize(46, 48)
        self.max_btn.clicked.connect(self.maximize_clicked.emit)

        self.close_btn = QPushButton("×")  # 关闭
        self.close_btn.setObjectName("closeButton")
        self.close_btn.setFixedSize(46, 48)
        self.close_btn.clicked.connect(self.close_clicked.emit)

        # 添加到布局
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

        # 为所有子控件启用鼠标追踪和安装事件过滤器
        for widget in [self.icon_label, self.title_label, self.min_btn, self.max_btn, self.close_btn]:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _setup_title_font(self):
        """设置标题字体（确保支持中文）"""
        # 尝试使用系统中文字体
        font_families = [
            "Noto Sans CJK SC",      # Linux
            "WenQuanYi Micro Hei",   # Linux
            "Microsoft YaHei",        # Windows
            "PingFang SC",            # macOS
        ]

        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.Medium)

        # 查找可用的中文字体
        available_fonts = QFontDatabase.families()
        for family in font_families:
            if family in available_fonts:
                font.setFamily(family)
                break

        self.title_label.setFont(font)

    def _apply_styles(self):
        """应用样式"""
        # 从 qss 文件加载样式
        StyleSheet.apply(self, "widgets/guanlan_title_bar.qss")

    def set_title(self, title: str):
        """设置标题"""
        self.title_label.setText(title)

    def set_icon(self, icon_path: str):
        """
        设置窗口图标

        Parameters
        ----------
        icon_path : str
            图标文件路径
        """
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap)
            self.icon_label.show()
        else:
            self.icon_label.hide()

    def _reset_cursor(self):
        """重置光标为箭头"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.window():
            self.window().setCursor(Qt.CursorShape.ArrowCursor)

    def update_maximize_button(self, is_maximized: bool):
        """更新最大化按钮状态"""
        self.max_btn.setText("[=]" if is_maximized else "[ ]")

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 记录位置用于拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self._start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 拖动窗口"""
        # 在标题栏内部，确保光标是箭头
        if not self._is_pressed:
            self._reset_cursor()

        if self._is_pressed and self.window():
            # 计算移动距离
            delta = event.globalPosition().toPoint() - self._start_pos
            # 移动窗口
            self.window().move(self.window().pos() + delta)
            # 更新起始位置
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        self._is_pressed = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """鼠标双击事件 - 最大化/还原"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()

    def enterEvent(self, event):
        """鼠标进入事件 - 重置光标"""
        self._reset_cursor()
        super().enterEvent(event)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """事件过滤器 - 处理子控件的鼠标事件"""
        if event.type() == QEvent.Type.MouseMove:
            # 子控件鼠标移动时，重置光标
            self._reset_cursor()
        elif event.type() == QEvent.Type.Enter:
            # 鼠标进入子控件时，重置光标
            self._reset_cursor()

        return super().eventFilter(obj, event)
