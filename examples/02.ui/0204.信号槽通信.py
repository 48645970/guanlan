# -*- coding: utf-8 -*-
"""
信号与插槽示例

演示 PySide6 自定义信号的用法：
- 自定义 Signal 定义
- 信号参数传递
- Slot 装饰器使用
- lambda 连接方式

依赖安装:
    pip install PySide6 PySide6-Fluent-Widgets

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, Slot
from qframelesswindow import FramelessWindow, TitleBar
from qfluentwidgets import (
    PushButton, PrimaryPushButton, TextEdit, setTheme, Theme,
    InfoBar, InfoBarPosition
)


class CustomTitleBar(TitleBar):
    """自定义标题栏"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(48)

        # 添加标题标签
        self.titleLabel = QLabel("观澜量化 - 信号与插槽演示", self)
        self.titleLabel.setStyleSheet("""
            color: white;
            font-size: 15px;
            font-weight: 500;
            margin-left: 12px;
        """)
        self.hBoxLayout.insertWidget(0, self.titleLabel)


class SignalDemoWindow(FramelessWindow):
    """信号与插槽演示窗口"""

    # 自定义信号：可以携带多个参数
    message_signal = Signal(str, str)  # (sender, message)
    counter_signal = Signal(int)  # (count)

    def __init__(self):
        super().__init__()
        self.setTitleBar(CustomTitleBar(self))
        self.setWindowTitle("观澜量化 - 信号与插槽演示")
        self.setMinimumSize(600, 500)
        self.resize(600, 500)

        self.counter = 0

        self._init_ui()

        # 连接信号到槽函数
        self.message_signal.connect(self.on_message_received)
        self.counter_signal.connect(self.on_counter_changed)

        # 默认暗色主题
        setTheme(Theme.DARK)

        # 初始日志
        self.log("信号演示窗口已初始化")
        self.log("- message_signal: 携带 (sender, message) 两个字符串参数")
        self.log("- counter_signal: 携带 (count) 一个整数参数")
        self.log("-" * 40)

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
        title = QLabel("自定义信号与插槽演示")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 日志输出区域
        self.log_output = TextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("信号触发日志...")
        layout.addWidget(self.log_output)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # 按钮1：触发消息信号
        btn_message = PushButton("发送消息信号")
        btn_message.clicked.connect(
            lambda: self.message_signal.emit("按钮1", "这是一条测试消息")
        )
        btn_layout.addWidget(btn_message)

        # 按钮2：触发计数信号
        btn_counter = PrimaryPushButton("计数器 +1")
        btn_counter.clicked.connect(self.increment_counter)
        btn_layout.addWidget(btn_counter)

        # 按钮3：带参数的 lambda
        btn_custom = PushButton("自定义参数")
        btn_custom.clicked.connect(
            lambda: self.on_custom_click(name="观澜", value=42)
        )
        btn_layout.addWidget(btn_custom)

        layout.addLayout(btn_layout)

    def log(self, message: str):
        """添加日志"""
        self.log_output.append(message)

    def increment_counter(self):
        """增加计数器并发射信号"""
        self.counter += 1
        self.counter_signal.emit(self.counter)

    @Slot(str, str)
    def on_message_received(self, sender: str, message: str):
        """消息信号的槽函数"""
        self.log(f"[消息信号] 发送者: {sender}, 内容: {message}")
        InfoBar.success(
            title="收到消息",
            content=f"来自 {sender}: {message}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

    @Slot(int)
    def on_counter_changed(self, count: int):
        """计数器信号的槽函数"""
        self.log(f"[计数信号] 当前计数: {count}")

    def on_custom_click(self, name: str, value: int):
        """自定义参数的处理函数"""
        self.log(f"[自定义] name={name}, value={value}")
        InfoBar.info(
            title="自定义参数",
            content=f"name={name}, value={value}",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )


def main():
    print("=" * 50)
    print("信号与插槽演示")
    print("=" * 50)
    print("演示内容：")
    print("  1. 自定义 Signal 定义和发射")
    print("  2. Slot 装饰器使用")
    print("  3. lambda 连接方式传递参数")
    print()

    app = QApplication(sys.argv)

    window = SignalDemoWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
