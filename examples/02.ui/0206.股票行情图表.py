# -*- coding: utf-8 -*-
"""
观澜量化 - 东财行情 K 线图演示

演示功能：
- 使用 efinance 免费获取 A 股/港股/美股 K 线数据
- 使用 lightweight-charts-python 显示交互式 K 线图
- 后台线程数据获取，避免界面卡顿
- 支持股票代码输入，一键查询
- 显示成交量柱状图

依赖安装：pip install efinance lightweight-charts

Author: 海山观澜
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Signal, QObject

from qfluentwidgets import (
    PushButton, LineEdit, BodyLabel, setTheme, Theme,
    InfoBar, InfoBarPosition, FluentIcon
)

from guanlan.ui.widgets.window import WebEngineFluentWidget

# 尝试导入依赖库
try:
    from lightweight_charts.widgets import QtChart
    HAS_LIGHTWEIGHT_CHARTS = True
except ImportError:
    HAS_LIGHTWEIGHT_CHARTS = False
    QtChart = None

try:
    import efinance as ef
    HAS_EFINANCE = True
except ImportError:
    HAS_EFINANCE = False


class DataFetcher(QObject):
    """数据获取器（后台线程）"""
    data_ready = Signal(object, str)  # (DataFrame, stock_name)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def fetch(self, code: str):
        """后台获取数据"""
        self.executor.submit(self._do_fetch, code)

    def _do_fetch(self, code: str):
        """执行数据获取"""
        if not HAS_EFINANCE:
            self.error.emit("efinance 未安装")
            return

        try:
            # 获取股票日K数据
            df = ef.stock.get_quote_history(code)
            if df is None or df.empty:
                self.error.emit(f"未找到股票: {code}")
                return

            # 获取股票名称
            stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else code

            # 转换为 lightweight-charts 格式
            chart_df = pd.DataFrame({
                'time': pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d'),
                'open': df['开盘'].astype(float),
                'high': df['最高'].astype(float),
                'low': df['最低'].astype(float),
                'close': df['收盘'].astype(float),
                'volume': df['成交量'].astype(float)
            })

            # 取最近 200 条数据
            chart_df = chart_df.tail(200).reset_index(drop=True)

            self.data_ready.emit(chart_df, stock_name)

        except Exception as e:
            self.error.emit(str(e))


class StockChartWindow(WebEngineFluentWidget):
    """股票 K 线图窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("东财行情图表 - 观澜量化")
        self.resize(1200, 800)

        # 数据获取器
        self.fetcher = DataFetcher()
        self.fetcher.data_ready.connect(self._on_data_ready)
        self.fetcher.error.connect(self._on_error)

        # 内容容器
        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        layout.addWidget(content)

        # 工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        toolbar.setFixedHeight(48)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 8, 16, 8)
        toolbar_layout.setSpacing(12)

        # 股票代码输入
        label = BodyLabel("股票代码:")
        label.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(label)

        self.code_input = LineEdit()
        self.code_input.setPlaceholderText("例如: 600519")
        self.code_input.setText("600519")
        self.code_input.setFixedWidth(120)
        self.code_input.returnPressed.connect(self._fetch_data)
        toolbar_layout.addWidget(self.code_input)

        # 获取按钮
        fetch_btn = PushButton("获取数据")
        fetch_btn.setIcon(FluentIcon.DOWNLOAD)
        fetch_btn.clicked.connect(self._fetch_data)
        toolbar_layout.addWidget(fetch_btn)

        # 状态标签
        self.status_label = BodyLabel("")
        self.status_label.setStyleSheet("color: #8b949e;")
        toolbar_layout.addWidget(self.status_label)

        toolbar_layout.addStretch()
        content_layout.addWidget(toolbar)

        # 创建图表容器
        self.chart_container = QWidget()
        chart_layout = QVBoxLayout(self.chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        # 创建图表
        self.chart = QtChart(self.chart_container)
        chart_layout.addWidget(self.chart.get_webview(), 1)

        content_layout.addWidget(self.chart_container, 1)

    def _fetch_data(self):
        """获取股票数据"""
        code = self.code_input.text().strip()
        if not code:
            InfoBar.warning(
                title="提示",
                content="请输入股票代码",
                parent=self,
                position=InfoBarPosition.TOP
            )
            return

        self.status_label.setText(f"正在获取 {code} 数据...")
        self.fetcher.fetch(code)

    def _on_data_ready(self, df: pd.DataFrame, stock_name: str):
        """数据获取成功"""
        self.status_label.setText(f"{stock_name} - 共 {len(df)} 条数据")

        # 设置图表数据
        self.chart.set(df)

        InfoBar.success(
            title="成功",
            content=f"已加载 {stock_name} 的 K 线数据",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000
        )

    def _on_error(self, error: str):
        """数据获取失败"""
        self.status_label.setText("")
        InfoBar.error(
            title="错误",
            content=error,
            parent=self,
            position=InfoBarPosition.TOP
        )


def main():
    # 检查依赖
    if not HAS_LIGHTWEIGHT_CHARTS or not HAS_EFINANCE:
        print("\n" + "=" * 60)
        print("依赖库缺失，无法运行此示例")
        print("=" * 60)

        missing_deps = []
        if not HAS_LIGHTWEIGHT_CHARTS:
            missing_deps.append("lightweight-charts")
        if not HAS_EFINANCE:
            missing_deps.append("efinance")

        print(f"\n请运行以下命令安装依赖：")
        print(f"  pip install {' '.join(missing_deps)}")
        print()
        return

    app = QApplication(sys.argv)
    setTheme(Theme.DARK)

    window = StockChartWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
