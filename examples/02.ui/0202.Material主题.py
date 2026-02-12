# -*- coding: utf-8 -*-
"""
Material Design 主题演示

演示 qt_material 库的 Material Design 主题：
- Google Material Design 风格
- 多种预设主题切换
- 深色和浅色模式
- 丰富的组件样式

依赖安装:
    pip install PySide6 qt-material

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QCheckBox,
    QSlider, QLineEdit, QTextEdit, QGroupBox, QRadioButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

try:
    from qt_material import apply_stylesheet, list_themes
    HAS_QT_MATERIAL = True
except ImportError:
    HAS_QT_MATERIAL = False


class MaterialDemoWindow(QMainWindow):
    """Material Design 主题演示窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("观澜量化 - Material Design 主题演示")
        self.resize(800, 700)

        if not HAS_QT_MATERIAL:
            self._show_error()
            return

        self._init_ui()

        # 默认应用深色蓝色主题
        self._apply_theme("dark_blue.xml")

    def _show_error(self):
        """显示错误信息"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        error_label = QLabel(
            "⚠️ 缺少依赖\n\n"
            "请先安装 qt-material:\n"
            "pip install qt-material"
        )
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("font-size: 16px; padding: 50px;")
        layout.addWidget(error_label)

    def _init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 标题
        title = QLabel("🎨 Material Design 主题演示")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 主题选择器
        theme_group = QGroupBox("主题设置")
        theme_layout = QHBoxLayout(theme_group)

        theme_layout.addWidget(QLabel("主题:"))

        self.theme_combo = QComboBox()
        # 获取所有可用主题
        themes = list_themes()
        for theme in themes:
            # 只显示主题名称，不显示 .xml 后缀
            display_name = theme.replace('.xml', '').replace('_', ' ').title()
            self.theme_combo.addItem(display_name, theme)

        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)

        theme_layout.addStretch()
        layout.addWidget(theme_group)

        # 组件演示区
        demo_group = QGroupBox("组件预览")
        demo_layout = QVBoxLayout(demo_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QLabel("按钮:"))
        btn_layout.addWidget(QPushButton("普通按钮"))
        btn_layout.addWidget(QPushButton("主按钮"))
        btn_disabled = QPushButton("禁用按钮")
        btn_disabled.setEnabled(False)
        btn_layout.addWidget(btn_disabled)
        btn_layout.addStretch()
        demo_layout.addLayout(btn_layout)

        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度条:"))
        progress = QProgressBar()
        progress.setValue(60)
        progress_layout.addWidget(progress)
        demo_layout.addLayout(progress_layout)

        # 滑块
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("滑块:"))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setValue(50)
        slider_layout.addWidget(slider)
        demo_layout.addLayout(slider_layout)

        # 复选框
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(QLabel("复选框:"))
        cb1 = QCheckBox("选项 1")
        cb1.setChecked(True)
        checkbox_layout.addWidget(cb1)
        checkbox_layout.addWidget(QCheckBox("选项 2"))
        checkbox_layout.addWidget(QCheckBox("选项 3"))
        checkbox_layout.addStretch()
        demo_layout.addLayout(checkbox_layout)

        # 单选框
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(QLabel("单选框:"))
        rb1 = QRadioButton("选项 A")
        rb1.setChecked(True)
        radio_layout.addWidget(rb1)
        radio_layout.addWidget(QRadioButton("选项 B"))
        radio_layout.addWidget(QRadioButton("选项 C"))
        radio_layout.addStretch()
        demo_layout.addLayout(radio_layout)

        # 输入框
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("输入框:"))
        line_edit = QLineEdit()
        line_edit.setPlaceholderText("请输入内容...")
        input_layout.addWidget(line_edit)
        demo_layout.addLayout(input_layout)

        # 下拉框
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("下拉框:"))
        combo = QComboBox()
        combo.addItems(["选项 1", "选项 2", "选项 3", "选项 4"])
        combo_layout.addWidget(combo)
        combo_layout.addStretch()
        demo_layout.addLayout(combo_layout)

        # 文本框
        text_layout = QVBoxLayout()
        text_layout.addWidget(QLabel("文本框:"))
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("多行文本输入...")
        text_edit.setMaximumHeight(100)
        text_layout.addWidget(text_edit)
        demo_layout.addLayout(text_layout)

        layout.addWidget(demo_group)

        # 说明
        info = QLabel(
            "💡 提示：\n"
            "• Material Design 是 Google 设计的视觉语言\n"
            "• qt-material 提供了多种预设主题\n"
            "• 支持深色和浅色模式\n"
            "• 主题名称格式：颜色_模式（如 dark_blue, light_pink）"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch()

    def _on_theme_changed(self):
        """主题改变事件"""
        theme_file = self.theme_combo.currentData()
        if theme_file:
            self._apply_theme(theme_file)

    def _apply_theme(self, theme_file: str):
        """应用主题"""
        try:
            apply_stylesheet(QApplication.instance(), theme=theme_file)
            print(f"✅ 已切换到主题: {theme_file}")
        except Exception as e:
            print(f"❌ 切换主题失败: {e}")


def main():
    print("=" * 60)
    print("Material Design 主题演示")
    print("=" * 60)

    if not HAS_QT_MATERIAL:
        print("\n⚠️  缺少依赖: qt-material")
        print("安装方法: pip install qt-material")
        print()
    else:
        print("\n可用主题:")
        themes = list_themes()
        for i, theme in enumerate(themes, 1):
            display_name = theme.replace('.xml', '').replace('_', ' ').title()
            theme_type = "🌙 深色" if 'dark' in theme.lower() else "☀️  浅色"
            print(f"  {i:2d}. {theme_type} {display_name}")
        print()

    # 初始化应用标识（用于 GNOME 任务栏显示中文）
    from guanlan.ui.widgets import init_app_identity, set_app_icon
    init_app_identity()

    app = QApplication(sys.argv)
    set_app_icon(app)

    window = MaterialDemoWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
