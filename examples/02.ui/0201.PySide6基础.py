# -*- coding: utf-8 -*-
"""
PySide6 基础示例

演示 Qt 环境验证：
- QMainWindow 主窗口
- QLabel 标签组件
- QVBoxLayout 垂直布局

依赖安装:
    pip install PySide6

Author: 海山观澜
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class MainWindow(QMainWindow):
    """简单的主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("观澜量化 - PySide6 测试")
        self.setMinimumSize(400, 300)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)

        # 布局
        layout = QVBoxLayout(central)

        # 标签
        label = QLabel("PySide6 环境正常！")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 24px; color: #4CAF50;")
        layout.addWidget(label)

        # 版本信息
        from PySide6 import __version__ as pyside_version
        version_label = QLabel(f"PySide6 版本: {pyside_version}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
