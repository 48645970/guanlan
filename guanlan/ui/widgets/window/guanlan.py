# -*- coding: utf-8 -*-
"""
观澜窗口

基于 Qt 原始 QMainWindow 的观澜自定义窗口

Author: 海山观澜
"""

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QObject, QRectF, QSize
from PySide6.QtGui import QIcon, QColor, QMouseEvent, QPixmap, QPainter

from guanlan.ui.common.style import StyleSheet, Theme
from guanlan.ui.common.icon import get_icon_path
from guanlan.ui.widgets.components.title_bar import GuanlanTitleBar


class GuanlanWindow(QMainWindow):
    """
    观澜窗口

    基于标准 QMainWindow，带自定义观澜样式标题栏。
    使用无边框设计，但保留 QMainWindow 基类。

    特性：
    - 基于 QMainWindow，稳定可靠
    - 自定义观澜样式标题栏
    - 支持窗口拖动、最小化、最大化、关闭
    - 支持窗口边缘拖动调整大小
    - 支持深色/浅色主题切换
    - 与 WebEngine 完全兼容
    - 保留所有 QMainWindow 的功能

    使用示例：
    ```python
    from guanlan.ui.widgets import GuanlanWindow, Theme

    class MyWindow(GuanlanWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("我的窗口")
            self.resize(800, 600)

            # 创建中心组件
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # ... 添加布局和组件
    ```
    """

    def __init__(self, parent=None, enable_translucent_background: bool = True):
        """
        初始化观澜窗口

        Parameters
        ----------
        parent : QWidget, optional
            父组件
        enable_translucent_background : bool, optional
            是否启用透明背景（默认 True）
            注意：使用 QWebEngineView 时建议设置为 False
        """
        super().__init__(parent)

        # 设置无边框窗口（保留 QMainWindow 基类）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        # 保存透明背景设置
        self._enable_translucent_background = enable_translucent_background

        # 圆角半径
        self._border_radius = 12

        # 设置窗口属性（启用透明背景以显示圆角和阴影）
        # WebEngine 需要非透明背景才能正常渲染
        # 注意：某些 Linux 窗口管理器（如 Wayland）可能不完全支持透明背景
        # 这会产生 "plugin does not support setting window opacity" 警告，但不影响功能
        if enable_translucent_background:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 窗口调整大小相关
        self._resize_border = 5  # 调整大小的边框宽度
        self._resize_margin = 10  # 外边距（包括阴影区域）
        self._is_resizing = False
        self._resize_direction = None
        self._resize_start_pos = QPoint()
        self._resize_start_geometry = QRect()

        # 创建主容器（用于添加边距以显示阴影）
        self._main_container = QWidget()
        self._main_container.setObjectName("mainContainer")
        main_layout = QVBoxLayout(self._main_container)
        # 为阴影留出空间（仅在启用透明背景时）
        margin = 10 if enable_translucent_background else 0
        main_layout.setContentsMargins(margin, margin, margin, margin)

        # 创建中心容器
        self._central_widget = QWidget()
        self._central_widget.setObjectName("centralWidget")
        self._central_layout = QVBoxLayout(self._central_widget)
        self._central_layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.setSpacing(0)

        main_layout.addWidget(self._central_widget)

        # 创建标题栏
        self._title_bar = GuanlanTitleBar(self)
        self._title_bar.minimize_clicked.connect(self.showMinimized)
        self._title_bar.maximize_clicked.connect(self._toggle_maximize)
        self._title_bar.close_clicked.connect(self.close)
        self._central_layout.addWidget(self._title_bar)

        # 创建内容容器（供子类使用）
        self._content_widget = QWidget()
        self._content_widget.setObjectName("contentWidget")
        self._central_layout.addWidget(self._content_widget)

        # 设置中心组件
        super().setCentralWidget(self._main_container)

        # 添加阴影效果（仅在启用透明背景时）
        if enable_translucent_background:
            self._setup_shadow()

        # 应用默认样式
        self._apply_styles()

        # 同步初始 QFluentWidgets 主题
        self._sync_qfluentwidgets_theme()

        # 启用鼠标追踪（用于调整大小时更新光标）
        self.setMouseTracking(True)
        self._main_container.setMouseTracking(True)
        self._central_widget.setMouseTracking(True)
        self._content_widget.setMouseTracking(True)

        # 安装事件过滤器以捕获所有子组件的鼠标移动
        self._main_container.installEventFilter(self)
        self._central_widget.installEventFilter(self)
        self._content_widget.installEventFilter(self)

        # 设置最小尺寸
        self.setMinimumSize(400, 300)

        # 设置默认图标
        icon_path = get_icon_path()
        if Path(icon_path).exists():
            self.setWindowIcon(icon_path)

        # 设置默认窗口标题（确保任务栏有标题显示）
        self.setWindowTitle("观澜量化")

    def _setup_shadow(self):
        """设置窗口阴影效果"""
        # 只在非最大化状态下显示阴影
        shadow = QGraphicsDropShadowEffect(self._central_widget)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._central_widget.setGraphicsEffect(shadow)

    def _update_rounded_mask(self):
        """更新圆角遮罩（非透明背景模式）"""
        if self._enable_translucent_background or self.isMaximized():
            # 透明背景或最大化时不需要遮罩
            self.clearMask()
            return

        # 获取窗口大小和设备像素比
        size = self.size()
        dpr = self.devicePixelRatio()

        # 创建高分辨率位图（使用设备像素比）
        pixmap_size = QSize(int(size.width() * dpr), int(size.height() * dpr))
        pixmap = QPixmap(pixmap_size)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        # 使用 QPainter 绘制抗锯齿的圆角矩形
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setBrush(Qt.GlobalColor.white)
        painter.setPen(Qt.PenStyle.NoPen)

        # 绘制圆角矩形
        rect = QRectF(0, 0, size.width(), size.height())
        painter.drawRoundedRect(rect, self._border_radius, self._border_radius)
        painter.end()

        # 从 pixmap 创建遮罩
        self.setMask(pixmap.mask())

    def _apply_styles(self):
        """应用 Fluent 样式"""
        # 从 qss 文件加载样式
        StyleSheet.apply(self, "widgets/guanlan_window.qss")

    def _sync_qfluentwidgets_theme(self):
        """同步 QFluentWidgets 主题"""
        try:
            from qfluentwidgets import setTheme, Theme as FluentTheme
            current_theme = StyleSheet.get_theme()
            if current_theme == Theme.DARK:
                setTheme(FluentTheme.DARK)
            elif current_theme == Theme.LIGHT:
                setTheme(FluentTheme.LIGHT)
        except ImportError:
            # QFluentWidgets 未安装，忽略
            pass

    def set_theme(self, theme: Theme):
        """
        切换主题

        Parameters
        ----------
        theme : Theme
            主题（LIGHT 或 DARK）
        """
        StyleSheet.set_theme(theme)
        self._apply_styles()
        # 更新标题栏样式
        if hasattr(self, '_title_bar'):
            self._title_bar._apply_styles()
        # 同步 QFluentWidgets 主题
        self._sync_qfluentwidgets_theme()

    def is_dark_theme(self) -> bool:
        """是否为深色主题"""
        return StyleSheet.is_dark_theme()

    def _toggle_maximize(self):
        """切换最大化/还原"""
        if self.isMaximized():
            self.showNormal()
            self._title_bar.update_maximize_button(False)
            # 还原阴影边距（仅在启用透明背景时）
            margin = 10 if self._enable_translucent_background else 0
            self._main_container.layout().setContentsMargins(margin, margin, margin, margin)
        else:
            self.showMaximized()
            self._title_bar.update_maximize_button(True)
            # 最大化时移除边距
            self._main_container.layout().setContentsMargins(0, 0, 0, 0)

        # 更新圆角遮罩
        self._update_rounded_mask()

    def setCentralWidget(self, widget: QWidget):
        """
        设置中心组件（重写以使用内容容器）

        Parameters
        ----------
        widget : QWidget
            中心组件
        """
        # 清空内容容器的现有布局
        if self._content_widget.layout():
            old_layout = self._content_widget.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QWidget().setLayout(old_layout)

        # 创建新布局并添加组件
        layout = QVBoxLayout(self._content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

        # 为新组件启用鼠标追踪和事件过滤
        widget.setMouseTracking(True)
        widget.installEventFilter(self)

    def setWindowTitle(self, title: str):
        """
        设置窗口标题（重写以更新标题栏）

        Parameters
        ----------
        title : str
            窗口标题
        """
        super().setWindowTitle(title)
        if hasattr(self, '_title_bar'):
            self._title_bar.set_title(title)

    def setWindowIcon(self, icon):
        """
        设置窗口图标（重写以更新标题栏）

        Parameters
        ----------
        icon : QIcon or str
            窗口图标或图标文件路径
        """
        if isinstance(icon, str):
            # 如果是字符串路径
            super().setWindowIcon(QIcon(icon))
            if hasattr(self, '_title_bar'):
                self._title_bar.set_icon(icon)
        else:
            # 如果是 QIcon 对象
            super().setWindowIcon(icon)
            # 从 QIcon 获取 pixmap 并设置
            if hasattr(self, '_title_bar') and not icon.isNull():
                pixmap = icon.pixmap(20, 20)
                if not pixmap.isNull():
                    # 保存临时文件或直接使用 pixmap
                    self._title_bar.icon_label.setPixmap(pixmap)
                    self._title_bar.icon_label.show()

    def _get_resize_direction(self, pos: QPoint) -> str | None:
        """
        获取鼠标位置对应的调整大小方向

        Parameters
        ----------
        pos : QPoint
            鼠标位置

        Returns
        -------
        str | None
            调整方向或 None
        """
        if self.isMaximized():
            return None

        # 检查是否在标题栏区域内（标题栏内部不允许调整大小）
        title_bar_rect = self._title_bar.geometry()
        # 将标题栏坐标转换为窗口坐标
        title_bar_global = self._title_bar.mapTo(self, QPoint(0, 0))
        title_bar_window_rect = QRect(
            title_bar_global.x(),
            title_bar_global.y(),
            title_bar_rect.width(),
            title_bar_rect.height()
        )

        # 如果鼠标在标题栏内部区域（不在边缘），不允许调整大小
        if title_bar_window_rect.contains(pos):
            # 检查是否在标题栏的边缘区域
            margin = self._resize_margin
            border = self._resize_border
            title_x = pos.x() - title_bar_global.x()
            title_y = pos.y() - title_bar_global.y()

            # 只允许在标题栏顶部边缘调整大小
            if title_y >= margin + border:
                # 在标题栏内部，不是边缘区域
                return None

        rect = self.rect()
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        margin = self._resize_margin
        border = self._resize_border

        # 检测四个角
        if x < margin + border and y < margin + border:
            return "top-left"
        elif x > w - margin - border and y < margin + border:
            return "top-right"
        elif x < margin + border and y > h - margin - border:
            return "bottom-left"
        elif x > w - margin - border and y > h - margin - border:
            return "bottom-right"
        # 检测四条边
        elif x < margin + border:
            return "left"
        elif x > w - margin - border:
            return "right"
        elif y < margin + border:
            return "top"
        elif y > h - margin - border:
            return "bottom"

        return None

    def _update_cursor(self, direction: str | None):
        """更新鼠标光标"""
        if direction == "top" or direction == "bottom":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif direction == "left" or direction == "right":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction == "top-left" or direction == "bottom-right":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction == "top-right" or direction == "bottom-left":
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            direction = self._get_resize_direction(event.position().toPoint())
            if direction:
                self._is_resizing = True
                self._resize_direction = direction
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self._is_resizing:
            self._resize_window(event.globalPosition().toPoint())
        else:
            # 检测鼠标是否在调整大小区域
            direction = self._get_resize_direction(event.position().toPoint())
            self._update_cursor(direction)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """鼠标离开窗口事件 - 重置光标"""
        if not self._is_resizing:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """事件过滤器 - 处理子组件的鼠标移动事件"""
        if event.type() == QEvent.Type.MouseMove and not self._is_resizing:
            # 将子组件坐标转换为窗口坐标
            mouse_event = event
            global_pos = mouse_event.globalPosition().toPoint()
            window_pos = self.mapFromGlobal(global_pos)

            # 检测是否在调整大小区域
            direction = self._get_resize_direction(window_pos)
            self._update_cursor(direction)

        return super().eventFilter(obj, event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_resizing = False
            self._resize_direction = None
            # 释放后更新光标状态
            direction = self._get_resize_direction(event.position().toPoint())
            self._update_cursor(direction)
        super().mouseReleaseEvent(event)

    def _resize_window(self, global_pos: QPoint):
        """调整窗口大小"""
        if not self._resize_direction:
            return

        delta = global_pos - self._resize_start_pos
        geo = QRect(self._resize_start_geometry)

        # 根据方向调整几何形状
        if "left" in self._resize_direction:
            geo.setLeft(geo.left() + delta.x())
        if "right" in self._resize_direction:
            geo.setRight(geo.right() + delta.x())
        if "top" in self._resize_direction:
            geo.setTop(geo.top() + delta.y())
        if "bottom" in self._resize_direction:
            geo.setBottom(geo.bottom() + delta.y())

        # 限制最小尺寸
        if geo.width() < self.minimumWidth():
            if "left" in self._resize_direction:
                geo.setLeft(geo.right() - self.minimumWidth())
            else:
                geo.setRight(geo.left() + self.minimumWidth())

        if geo.height() < self.minimumHeight():
            if "top" in self._resize_direction:
                geo.setTop(geo.bottom() - self.minimumHeight())
            else:
                geo.setBottom(geo.top() + self.minimumHeight())

        self.setGeometry(geo)

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 初始化圆角遮罩
        self._update_rounded_mask()

    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 更新圆角遮罩
        self._update_rounded_mask()

    def closeEvent(self, event):
        """窗口关闭事件 - 清理资源"""
        # 清理所有子组件的事件过滤器
        for child in self.findChildren(QWidget):
            child.removeEventFilter(self)

        # 接受关闭事件
        event.accept()
