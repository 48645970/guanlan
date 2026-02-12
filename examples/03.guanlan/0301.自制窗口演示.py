# -*- coding: utf-8 -*-
"""
观澜自制窗口组件演示

展示 GuanlanWindow 与各种 UI 组件的兼容性

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox, QSlider
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen

from guanlan.ui.widgets import GuanlanWindow, Theme

# 尝试导入 qfluentwidgets 组件
try:
    from qfluentwidgets import (
        SubtitleLabel, PushButton, PrimaryPushButton,
        InfoBar, InfoBarPosition, setTheme, Theme as FluentTheme
    )
    HAS_QFLUENTWIDGETS = True
except ImportError:
    HAS_QFLUENTWIDGETS = False


class ComponentTestWindow(GuanlanWindow):
    """组件测试窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("观澜量化 - 组件测试")
        self.resize(850, 950)

        # 设置窗口图标
        icon_path = project_root / "ui" / "images" / "logo.png"
        self.setWindowIcon(str(icon_path))

        self._init_ui()

    def _init_ui(self):
        """初始化界面"""
        # 创建中心组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 顶部标题区域
        self._create_header(main_layout)

        # DPI 信息区域
        self._create_dpi_info(main_layout)

        # Qt 原生组件区域
        self._create_qt_components(main_layout)

        # QFluentWidgets 组件区域
        if HAS_QFLUENTWIDGETS:
            self._create_fluent_components(main_layout)
        else:
            warning_label = QLabel("⚠️ qfluentwidgets 未安装，部分组件测试不可用")
            warning_label.setStyleSheet("color: #f59e0b; padding: 10px; background-color: rgba(245, 158, 11, 0.1);")
            main_layout.addWidget(warning_label)

        main_layout.addStretch()

    def _create_header(self, parent_layout):
        """创建顶部标题"""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # 标题和主题切换按钮
        title_row = QHBoxLayout()

        title = QLabel("组件兼容性测试")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_row.addWidget(title)

        title_row.addStretch()

        # 主题切换按钮
        theme_label = QLabel("主题切换:")
        theme_label.setStyleSheet("font-size: 14px;")
        title_row.addWidget(theme_label)

        light_theme_btn = QPushButton("☀️ 浅色")
        light_theme_btn.setFixedWidth(100)
        light_theme_btn.clicked.connect(lambda: self.set_theme(Theme.LIGHT))
        title_row.addWidget(light_theme_btn)

        dark_theme_btn = QPushButton("🌙 深色")
        dark_theme_btn.setFixedWidth(100)
        dark_theme_btn.clicked.connect(lambda: self.set_theme(Theme.DARK))
        title_row.addWidget(dark_theme_btn)

        header_layout.addLayout(title_row)

        subtitle = QLabel("测试 GuanlanWindow 与各种 UI 组件的兼容性")
        subtitle.setStyleSheet("font-size: 14px; color: gray;")
        header_layout.addWidget(subtitle)

        parent_layout.addWidget(header)

    def _create_dpi_info(self, parent_layout):
        """创建 DPI 信息区域"""
        group = QGroupBox("DPI 缩放信息")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        # 获取当前屏幕
        screen = QApplication.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            device_pixel_ratio = screen.devicePixelRatio()
            physical_dpi = screen.physicalDotsPerInch()
            size = screen.size()

            # 显示信息
            info_layout = QVBoxLayout()

            info_text = f"""
📊 屏幕分辨率: {size.width()} x {size.height()} px
🔍 逻辑 DPI: {dpi:.2f}
📐 物理 DPI: {physical_dpi:.2f}
⚡ 设备像素比: {device_pixel_ratio:.2f}x
🖥️  缩放比例: {int(device_pixel_ratio * 100)}%
            """.strip()

            info_label = QLabel(info_text)
            info_label.setStyleSheet("padding: 10px; background-color: rgba(0, 120, 212, 0.1); border-radius: 4px;")
            info_layout.addWidget(info_label)

            group_layout.addLayout(info_layout)

            # 添加测试文本（不同大小）
            test_layout = QHBoxLayout()
            test_layout.addWidget(QLabel("测试文本大小:"))

            for size in [12, 14, 16, 18, 20]:
                label = QLabel(f"{size}px")
                label.setStyleSheet(f"font-size: {size}px;")
                test_layout.addWidget(label)

            test_layout.addStretch()
            group_layout.addLayout(test_layout)

            # 添加像素测试
            pixel_layout = QHBoxLayout()
            pixel_layout.addWidget(QLabel("像素测试 (应该清晰):"))

            # 创建不同大小的方块来测试像素对齐
            for size in [10, 20, 30, 40, 50]:
                box = QLabel()
                box.setFixedSize(size, size)
                box.setStyleSheet(f"background-color: #0078d4; border: 1px solid white;")
                pixel_layout.addWidget(box)

            pixel_layout.addStretch()
            group_layout.addLayout(pixel_layout)

        parent_layout.addWidget(group)

    def _create_qt_components(self, parent_layout):
        """创建 Qt 原生组件测试区域"""
        group = QGroupBox("Qt 原生组件")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        # 按钮测试
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QLabel("按钮:"))

        normal_btn = QPushButton("普通按钮")
        normal_btn.clicked.connect(lambda: print("普通按钮点击"))
        btn_layout.addWidget(normal_btn)

        primary_btn = QPushButton("主要按钮")
        primary_btn.setObjectName("primaryButton")
        primary_btn.clicked.connect(lambda: print("主要按钮点击"))
        btn_layout.addWidget(primary_btn)

        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        # 输入框测试
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入框:"))

        line_edit = QLineEdit()
        line_edit.setPlaceholderText("请输入文本...")
        input_layout.addWidget(line_edit)

        input_layout.addStretch()
        group_layout.addLayout(input_layout)

        # 文本框测试
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("文本框:"))

        text_edit = QTextEdit()
        text_edit.setPlaceholderText("多行文本输入...")
        text_edit.setMaximumHeight(80)
        text_layout.addWidget(text_edit)

        group_layout.addLayout(text_layout)

        parent_layout.addWidget(group)

    def _create_fluent_components(self, parent_layout):
        """创建 QFluentWidgets 组件测试区域"""
        group = QGroupBox("QFluentWidgets 组件")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(10)

        # SubtitleLabel 测试
        subtitle = SubtitleLabel("这是 SubtitleLabel")
        group_layout.addWidget(subtitle)

        # 按钮测试
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QLabel("Fluent 按钮:"))

        fluent_btn = PushButton("Fluent 按钮")
        fluent_btn.clicked.connect(self._on_fluent_button_click)
        btn_layout.addWidget(fluent_btn)

        primary_fluent_btn = PrimaryPushButton("主要 Fluent 按钮")
        primary_fluent_btn.clicked.connect(self._on_primary_button_click)
        btn_layout.addWidget(primary_fluent_btn)

        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        # InfoBar 测试按钮
        infobar_layout = QHBoxLayout()
        infobar_layout.addWidget(QLabel("InfoBar:"))

        success_btn = QPushButton("显示成功消息")
        success_btn.clicked.connect(self._show_success_info)
        infobar_layout.addWidget(success_btn)

        warning_btn = QPushButton("显示警告消息")
        warning_btn.clicked.connect(self._show_warning_info)
        infobar_layout.addWidget(warning_btn)

        error_btn = QPushButton("显示错误消息")
        error_btn.clicked.connect(self._show_error_info)
        infobar_layout.addWidget(error_btn)

        infobar_layout.addStretch()
        group_layout.addLayout(infobar_layout)

        parent_layout.addWidget(group)

    def _on_fluent_button_click(self):
        """Fluent 按钮点击"""
        print("Fluent 按钮点击")
        if HAS_QFLUENTWIDGETS:
            InfoBar.info(
                title='信息',
                content="Fluent 按钮被点击了！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def _on_primary_button_click(self):
        """主要按钮点击"""
        print("主要 Fluent 按钮点击")
        if HAS_QFLUENTWIDGETS:
            InfoBar.success(
                title='成功',
                content="主要 Fluent 按钮被点击了！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    def _show_success_info(self):
        """显示成功消息"""
        if HAS_QFLUENTWIDGETS:
            InfoBar.success(
                title='操作成功',
                content="这是一条成功消息！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def _show_warning_info(self):
        """显示警告消息"""
        if HAS_QFLUENTWIDGETS:
            InfoBar.warning(
                title='警告',
                content="这是一条警告消息！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def _show_error_info(self):
        """显示错误消息"""
        if HAS_QFLUENTWIDGETS:
            InfoBar.error(
                title='错误',
                content="这是一条错误消息！",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )


def main():
    print("=" * 70)
    print("观澜自制窗口 - 组件测试".center(70))
    print("=" * 70)
    print()
    print("功能特性:")
    print("  1. 使用观澜自制的 GuanlanWindow 窗口")
    print("  2. 测试 Qt 原生组件兼容性")
    print("  3. 测试 QFluentWidgets 组件兼容性")
    print("  4. 自定义标题栏、窗口拖动、大小调整")
    print("  5. 高 DPI 缩放支持")
    print()
    print("测试组件:")
    print("  - Qt 原生: QPushButton, QLineEdit, QTextEdit, QGroupBox")
    if HAS_QFLUENTWIDGETS:
        print("  - QFluentWidgets: SubtitleLabel, PushButton, PrimaryPushButton, InfoBar")
    else:
        print("  - QFluentWidgets: 未安装 (pip install pyqt-fluent-widgets)")
    print()

    # 初始化应用标识（用于 GNOME 任务栏显示中文）
    from guanlan.ui.widgets import init_app_identity, set_app_icon
    init_app_identity()

    # Qt 6 / PySide6 默认启用高 DPI 缩放，无需手动设置
    app = QApplication(sys.argv)
    set_app_icon(app)

    # 打印 DPI 信息
    screen = app.primaryScreen()
    if screen:
        print("DPI 信息:")
        print(f"  - 逻辑 DPI: {screen.logicalDotsPerInch():.2f}")
        print(f"  - 物理 DPI: {screen.physicalDotsPerInch():.2f}")
        print(f"  - 设备像素比: {screen.devicePixelRatio():.2f}x")
        print(f"  - 缩放比例: {int(screen.devicePixelRatio() * 100)}%")
        print()

    # 创建并显示窗口
    window = ComponentTestWindow()
    window.show()

    print("✅ 窗口已启动")
    print()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
