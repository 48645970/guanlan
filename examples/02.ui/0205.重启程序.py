# -*- coding: utf-8 -*-
"""
应用重启示例

演示 Qt 应用的自重启机制：
- 退出码控制
- 应用重启循环
- 优雅退出处理

依赖安装:
    pip install PySide6 PySide6-Fluent-Widgets

Author: 海山观澜
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from qframelesswindow import FramelessWindow, TitleBar
from qfluentwidgets import (
    PushButton, PrimaryPushButton, setTheme, Theme,
    InfoBar, InfoBarPosition
)



class CustomTitleBar(TitleBar):
    """自定义标题栏"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(48)

        # 添加标题标签
        self.titleLabel = QLabel("观澜量化 - 应用重启演示", self)
        self.titleLabel.setStyleSheet("""
            color: white;
            font-size: 15px;
            font-weight: 500;
            margin-left: 12px;
        """)
        self.hBoxLayout.insertWidget(0, self.titleLabel)


class RestartDemoWindow(FramelessWindow):
    """重启演示窗口"""

    def __init__(self):
        super().__init__()
        self.setTitleBar(CustomTitleBar(self))
        self.setWindowTitle("观澜量化 - 应用重启演示")
        self.setMinimumSize(500, 400)
        self.resize(500, 400)

        self.restart_count = 0

        self._init_ui()

        # 默认暗色主题
        setTheme(Theme.DARK)

    def _init_ui(self):
        """初始化界面"""
        # 设置窗口背景色
        self.setStyleSheet("background-color: #1a1a1a;")

        # 创建中央容器
        container = QWidget(self)
        container.setStyleSheet("background-color: #2a2a2a; border-radius: 0px;")
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 48, 0, 0)
        self.layout().addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 标题
        title = QLabel("应用重启演示")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "本示例演示 Qt 应用的自重启机制。\n"
            "点击「重启应用」将关闭当前窗口并重新启动。\n"
            "点击「正常退出」将完全退出应用。"
        )
        desc.setStyleSheet("color: #dddddd; font-size: 14px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # 重启计数（在实际应用中可通过命令行参数传递）
        self.count_label = QLabel("当前会话: 第 1 次启动")
        self.count_label.setStyleSheet("color: #61afef; font-size: 14px; font-weight: bold;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        layout.addStretch()

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        btn_restart = PrimaryPushButton("重启应用")
        btn_restart.clicked.connect(self.restart_app)
        btn_layout.addWidget(btn_restart)

        btn_exit = PushButton("正常退出")
        btn_exit.clicked.connect(self.normal_exit)
        btn_layout.addWidget(btn_exit)

        layout.addLayout(btn_layout)

    def set_restart_count(self, count: int):
        """设置重启计数"""
        self.restart_count = count
        self.count_label.setText(f"当前会话: 第 {count} 次启动")

    def restart_app(self):
        """重启应用"""
        InfoBar.info(
            title="重启",
            content="应用即将重启...",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=1000
        )
        # 关闭所有窗口
        QApplication.processEvents()
        QApplication.closeAllWindows()

        # 使用 os.execv 重启整个 Python 进程
        python = sys.executable
        args = [python] + [sys.argv[0]] + [str(self.restart_count + 1)]
        os.execv(python, args)

    def normal_exit(self):
        """正常退出"""
        InfoBar.success(
            title="退出",
            content="应用正常退出",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=1000
        )
        QApplication.instance().exit(0)


def main():
    print("=" * 50)
    print("应用重启示例")
    print("=" * 50)

    # 从命令行参数获取重启次数（如果有）
    restart_count = 1
    if len(sys.argv) > 1:
        try:
            restart_count = int(sys.argv[1])
        except ValueError:
            pass

    print(f"第 {restart_count} 次启动...")
    print()

    app = QApplication(sys.argv[:1])  # 只传递程序名，不传递重启计数参数

    window = RestartDemoWindow()
    window.set_restart_count(restart_count)
    window.show()

    exit_code = app.exec()
    print(f"退出码: {exit_code}")
    print("应用退出")


if __name__ == "__main__":
    main()
