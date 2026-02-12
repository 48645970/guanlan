# -*- coding: utf-8 -*-
"""
QFluentWidgets 基础示例

演示 Fluent Design 风格：
- FluentWindow 主窗口
- InfoBar 消息提示
- 主题切换（明/暗）

依赖安装:
    pip install PySide6 PySide6-Fluent-Widgets

Author: 海山观澜
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from qfluentwidgets import (
    FluentWindow, SubtitleLabel, PushButton, InfoBar,
    InfoBarPosition, setTheme, Theme, PrimaryPushButton
)

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class MainWindow(FluentWindow):
    """Fluent Design 风格主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("观澜量化 - Fluent Design 测试")
        self.setMinimumSize(500, 400)

        # 创建内容区域
        self.home_widget = QWidget()
        self.home_widget.setObjectName("homeWidget")
        layout = QVBoxLayout(self.home_widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 标题
        title = SubtitleLabel("QFluentWidgets 环境正常！")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 按钮测试
        btn_info = PushButton("显示信息提示")
        btn_info.clicked.connect(self.show_info)
        layout.addWidget(btn_info)

        btn_success = PrimaryPushButton("显示成功提示")
        btn_success.clicked.connect(self.show_success)
        layout.addWidget(btn_success)

        # 主题切换
        self.btn_theme = PushButton("切换浅色主题")
        self.btn_theme.clicked.connect(self.toggle_theme)
        layout.addWidget(self.btn_theme)

        layout.addStretch()

        # 添加到导航
        self.addSubInterface(self.home_widget, "home", "首页")

        # 默认暗色主题
        setTheme(Theme.DARK)

    def show_info(self):
        InfoBar.info(
            title="提示",
            content="这是一个信息提示框",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )

    def show_success(self):
        InfoBar.success(
            title="成功",
            content="QFluentWidgets 工作正常！",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000
        )

    def toggle_theme(self):
        from qfluentwidgets import isDarkTheme
        if isDarkTheme():
            setTheme(Theme.LIGHT)
            self.btn_theme.setText("切换暗色主题")
        else:
            setTheme(Theme.DARK)
            self.btn_theme.setText("切换浅色主题")


def main():

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
