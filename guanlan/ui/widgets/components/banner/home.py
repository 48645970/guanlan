# -*- coding: utf-8 -*-
"""
观澜量化 - 首页 Banner 组件

包含渐变背景、标题和链接卡片。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, QRectF, QUrl, Signal
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPainterPath,
    QLinearGradient, QDesktopServices
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from qfluentwidgets import (
    IconWidget, FluentIcon, TextWrap, SingleDirectionScrollArea, isDarkTheme
)

from guanlan.core.events import signal_bus
from guanlan.ui.common.mixin import ThemeMixin

class LinkCard(QFrame):
    """链接卡片 - 点击可打开外部链接"""

    def __init__(self, icon, title: str, content: str, url: str, parent=None):
        super().__init__(parent=parent)
        self.url = QUrl(url)
        self._init_card(icon, title, content)

    def _init_card(self, icon, title: str, content: str) -> None:
        """初始化卡片"""
        self.setFixedSize(168, 140)
        self.setCursor(Qt.PointingHandCursor)

        # 图标
        if isinstance(icon, str):
            self.icon_widget = IconWidget(self)
            self.icon_widget.setIcon(QPixmap(icon))
        elif isinstance(icon, QPixmap):
            self.icon_widget = IconWidget(self)
            self.icon_widget.setIcon(icon)
        else:
            self.icon_widget = IconWidget(icon, self)

        self.icon_widget.setFixedSize(44, 44)

        # 标题和副标题
        self.title_label = QLabel(title, self)
        self.content_label = QLabel(content, self)
        self.url_widget = IconWidget(FluentIcon.LINK, self)
        self.url_widget.setFixedSize(14, 14)

        # 布局
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.addWidget(self.icon_widget)
        layout.addSpacing(12)
        layout.addWidget(self.title_label)
        layout.addSpacing(2)
        layout.addWidget(self.content_label)
        layout.addStretch()
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.url_widget.move(144, 116)

        self.title_label.setObjectName("titleLabel")
        self.content_label.setObjectName("contentLabel")

    def mouseReleaseEvent(self, event) -> None:
        """点击打开链接"""
        super().mouseReleaseEvent(event)
        QDesktopServices.openUrl(self.url)
        # 发送消息提示
        signal_bus.show_message.emit("使用帮助", "已在浏览器中打开", "success")


class _BadgeLabel(QLabel):
    """卡片内置徽标（红色圆形 + 白色数字）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(20, 20)
        self.setObjectName("badgeCount")

    def set_count(self, count: int) -> None:
        """设置数量，0 时隐藏"""
        if count > 0:
            self.setText(str(count))
            self.show()
        else:
            self.hide()


class ModuleCard(QFrame):
    """模块卡片 - 点击触发信号进行内部导航"""

    def __init__(self, icon, title: str, content: str, route: str, signal: Signal, parent=None):
        super().__init__(parent=parent)
        self.route = route
        self.signal = signal
        self._init_card(icon, title, content)

    def _init_card(self, icon, title: str, content: str) -> None:
        """初始化卡片"""
        self.setFixedSize(168, 140)
        self.setCursor(Qt.PointingHandCursor)

        # 图标
        if isinstance(icon, str):
            self.icon_widget = IconWidget(self)
            self.icon_widget.setIcon(QPixmap(icon))
        elif isinstance(icon, QPixmap):
            self.icon_widget = IconWidget(self)
            self.icon_widget.setIcon(icon)
        else:
            self.icon_widget = IconWidget(icon, self)

        self.icon_widget.setFixedSize(44, 44)

        # 标题和副标题
        self.title_label = QLabel(title, self)
        self.content_label = QLabel(content, self)

        # 徽标（绝对定位，右上角）
        self._badge = _BadgeLabel(self)

        # 布局
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.addWidget(self.icon_widget)
        layout.addSpacing(12)
        layout.addWidget(self.title_label)
        layout.addSpacing(2)
        layout.addWidget(self.content_label)
        layout.addStretch()
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.title_label.setObjectName("titleLabel")
        self.content_label.setObjectName("contentLabel")

    def set_badge(self, count: int) -> None:
        """设置徽标数量"""
        self._badge.set_count(count)

    def resizeEvent(self, event) -> None:
        """保持徽标在右上角"""
        super().resizeEvent(event)
        self._badge.move(self.width() - 28, 14)

    def mouseReleaseEvent(self, event) -> None:
        """点击触发导航信号"""
        super().mouseReleaseEvent(event)
        self.signal.emit(self.route)


class LinkCardView(ThemeMixin, SingleDirectionScrollArea):
    """链接卡片视图 - 水平滚动区域"""

    # 样式文件路径
    _qss_files = ["widgets/link_card.qss"]

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Horizontal)

        self.view = QWidget(self)
        self.h_layout = QHBoxLayout(self.view)

        self.h_layout.setContentsMargins(28, 0, 0, 0)  # 与标题对齐
        self.h_layout.setSpacing(12)
        self.h_layout.setAlignment(Qt.AlignLeft)

        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.view.setObjectName("view")

        # 设置固定高度（与卡片高度一致）
        self.setFixedHeight(140)

        # 初始化主题监听
        self._init_theme()

    def add_card(self, icon, title: str, content: str, url: str) -> None:
        """添加链接卡片（外部链接）"""
        card = LinkCard(icon, title, content, url, self.view)
        self.h_layout.addWidget(card, 0, Qt.AlignLeft)

    def add_module_card(self, icon, title: str, content: str, route: str, signal: Signal) -> ModuleCard:
        """添加模块卡片（内部导航）"""
        card = ModuleCard(icon, title, content, route, signal, self.view)
        self.h_layout.addWidget(card, 0, Qt.AlignLeft)
        return card


class HomeBanner(QWidget):
    """首页 Banner - 带渐变背景和链接卡片"""

    def __init__(self, title: str, banner_image: QPixmap = None, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(280)

        self.banner = banner_image if banner_image else QPixmap()
        self.title_label = QLabel(title, self)
        self.link_card_view = LinkCardView(self)

        self._init_widget()

    def _init_widget(self) -> None:
        """初始化组件"""
        self.title_label.setObjectName("bannerLabel")

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 10, 0, 6)
        layout.addWidget(self.title_label)
        layout.addSpacing(30)  # 标题与卡片间距
        layout.addWidget(self.link_card_view)
        layout.addStretch()
        layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def add_link_card(self, icon, title: str, content: str, url: str) -> None:
        """添加链接卡片（外部链接）"""
        self.link_card_view.add_card(icon, title, content, url)

    def add_module_card(self, icon, title: str, content: str, route: str, signal: Signal) -> ModuleCard:
        """添加模块卡片（内部导航）"""
        return self.link_card_view.add_module_card(icon, title, content, route, signal)

    def paintEvent(self, event) -> None:
        """绘制渐变背景和 Banner 图片（与 QFluentWidgets Gallery 一致）"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.SmoothPixmapTransform | QPainter.Antialiasing
        )
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        w, h = self.width(), self.height()
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h - 50, 50, 50))
        path.addRect(QRectF(w - 50, 0, 50, 50))
        path.addRect(QRectF(w - 50, h - 50, 50, 50))
        path = path.simplified()

        # 先绘制渐变背景
        gradient = QLinearGradient(0, 0, 0, h)
        if not isDarkTheme():
            gradient.setColorAt(0, QColor(207, 216, 228, 255))
            gradient.setColorAt(1, QColor(207, 216, 228, 0))
        else:
            gradient.setColorAt(0, QColor(0, 0, 0, 255))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.fillPath(path, QBrush(gradient))

        # 再绘制 Banner 图片
        if not self.banner.isNull():
            pixmap = self.banner.scaled(
                self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            painter.fillPath(path, QBrush(pixmap))
