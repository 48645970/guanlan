# -*- coding: utf-8 -*-
"""
观澜量化 - 图表 AI 分析面板

显示 AI 分析结果的横向面板，展示趋势、强度、建议、点位等信息。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel,
)

from qfluentwidgets import (
    BodyLabel, CaptionLabel, PrimaryPushButton,
    FluentIcon, isDarkTheme, InfoLevel, qconfig,
)

from guanlan.ui.widgets.components.badge import StatusBadge


class ChartAnalysisPanel(QFrame):
    """图表 AI 分析面板

    两行显示 AI 分析结果：
    - 第一行：图标 + 趋势、强度、建议、开仓、止损、止盈、支撑、压力 + AI 分析按钮
    - 第二行：详细分析文本
    """

    # 请求重新分析
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chartAnalysisPanel")

        self._init_ui()

    def _init_ui(self) -> None:
        """初始化界面（两行布局）"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 6, 12, 6)
        main_layout.setSpacing(4)

        # ── 整体布局（按钮 + 内容区） ──
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        # AI 分析按钮（占两行高度，使用蓝色主要按钮）
        self.refresh_btn = PrimaryPushButton("AI 分析", self)
        self.refresh_btn.setIcon(FluentIcon.ROBOT)
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.setMinimumHeight(50)  # 设置最小高度以占据两行
        self.refresh_btn.clicked.connect(self.refresh_requested)
        top_layout.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignTop)

        # 右侧内容区（两行）
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)

        # ── 第一行：标题 + 指标信息 ──
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # 标题
        self.title_label = BodyLabel("市场分析", self)
        row1.addWidget(self.title_label)

        row1.addSpacing(8)

        # 趋势标签
        self.trend_badge = StatusBadge("趋势: --", self)
        self.trend_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.trend_badge)

        # 强度标签
        self.strength_badge = StatusBadge("强度: --", self)
        self.strength_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.strength_badge)

        # 建议标签
        self.suggest_badge = StatusBadge("建议: --", self)
        self.suggest_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.suggest_badge)

        # 开仓点位标签
        self.entry_badge = StatusBadge("开仓: --", self)
        self.entry_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.entry_badge)

        # 止损价标签
        self.stop_loss_badge = StatusBadge("止损: --", self)
        self.stop_loss_badge.setLevel(InfoLevel.WARNING)
        row1.addWidget(self.stop_loss_badge)

        # 止盈价标签
        self.take_profit_badge = StatusBadge("止盈: --", self)
        self.take_profit_badge.setLevel(InfoLevel.SUCCESS)
        row1.addWidget(self.take_profit_badge)

        # 支撑位标签
        self.support_badge = StatusBadge("支撑: --", self)
        self.support_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.support_badge)

        # 压力位标签
        self.resistance_badge = StatusBadge("压力: --", self)
        self.resistance_badge.setLevel(InfoLevel.INFOAMTION)
        row1.addWidget(self.resistance_badge)

        row1.addStretch(1)

        content_layout.addLayout(row1)

        # ── 第二行：详细分析 ──
        row2 = QHBoxLayout()

        self.detail_label = CaptionLabel("等待分析...", self)
        self.detail_label.setWordWrap(True)
        row2.addWidget(self.detail_label, 1)

        content_layout.addLayout(row2)

        top_layout.addLayout(content_layout, 1)

        main_layout.addLayout(top_layout)

        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        dark = isDarkTheme()

        # 面板背景
        panel_bg = "#2d2d2d" if dark else "#f5f5f5"
        self.setStyleSheet(
            f"QFrame#chartAnalysisPanel {{"
            f"  background-color: {panel_bg};"
            f"  border-radius: 6px;"
            f"  border: 1px solid {'#3d3d3d' if dark else '#e0e0e0'};"
            f"}}"
        )

    def set_loading(self, loading: bool) -> None:
        """设置加载状态"""
        if loading:
            self.refresh_btn.setText("分析中...")
            self.refresh_btn.setEnabled(False)
            # 清空之前的分析结果，避免混淆
            self._clear_result()
        else:
            self.refresh_btn.setText("AI 分析")
            self.refresh_btn.setEnabled(True)

    def _clear_result(self) -> None:
        """清空分析结果显示"""
        # 重置所有标签为初始状态
        self.trend_badge.setText("趋势: --")
        self.trend_badge.setLevel(InfoLevel.INFOAMTION)

        self.strength_badge.setText("强度: --")
        self.strength_badge.setLevel(InfoLevel.INFOAMTION)

        self.suggest_badge.setText("建议: --")
        self.suggest_badge.setLevel(InfoLevel.INFOAMTION)

        self.entry_badge.setText("开仓: --")
        self.stop_loss_badge.setText("止损: --")
        self.take_profit_badge.setText("止盈: --")
        self.support_badge.setText("支撑: --")
        self.resistance_badge.setText("压力: --")

        self.detail_label.setText("分析中，请稍候...")

    def set_result(self, data: dict) -> None:
        """设置分析结果

        Parameters
        ----------
        data : dict
            AI 返回的分析结果，包含以下字段：
            - 趋势方向: "多头" | "空头" | "震荡"
            - 趋势强度: 1-5
            - 操作建议: "做多" | "做空" | "观望"
            - 开仓点位: float | None
            - 止损价: float | None
            - 止盈价: float | None
            - 支撑位: float
            - 压力位: float
            - 分析详情: str
        """
        # 趋势
        trend = data.get("趋势方向", "震荡")
        trend_icon = "↑" if trend == "多头" else ("↓" if trend == "空头" else "↔")
        self.trend_badge.setText(f"趋势: {trend} {trend_icon}")
        # 根据趋势设置颜色
        if trend == "多头":
            self.trend_badge.setLevel(InfoLevel.SUCCESS)
        elif trend == "空头":
            self.trend_badge.setLevel(InfoLevel.ERROR)
        else:
            self.trend_badge.setLevel(InfoLevel.INFOAMTION)

        # 强度（星级）
        strength = data.get("趋势强度", 0)
        stars = "★" * strength + "☆" * (5 - strength)
        self.strength_badge.setText(f"强度: {stars}")
        # 根据强度设置颜色
        if strength >= 4:
            self.strength_badge.setLevel(InfoLevel.SUCCESS)
        elif strength >= 3:
            self.strength_badge.setLevel(InfoLevel.INFOAMTION)
        else:
            self.strength_badge.setLevel(InfoLevel.WARNING)

        # 建议
        suggest = data.get("操作建议", "观望")
        self.suggest_badge.setText(f"建议: {suggest}")
        # 根据建议设置颜色
        if suggest == "做多":
            self.suggest_badge.setLevel(InfoLevel.SUCCESS)
        elif suggest == "做空":
            self.suggest_badge.setLevel(InfoLevel.ERROR)
        else:
            self.suggest_badge.setLevel(InfoLevel.INFOAMTION)

        # 开仓点位
        entry = data.get("开仓点位")
        if entry is not None:
            self.entry_badge.setText(f"开仓: {entry:.2f}")
        else:
            self.entry_badge.setText("开仓: --")

        # 止损价
        stop_loss = data.get("止损价")
        if stop_loss is not None:
            self.stop_loss_badge.setText(f"止损: {stop_loss:.2f}")
        else:
            self.stop_loss_badge.setText("止损: --")

        # 止盈价
        take_profit = data.get("止盈价")
        if take_profit is not None:
            self.take_profit_badge.setText(f"止盈: {take_profit:.2f}")
        else:
            self.take_profit_badge.setText("止盈: --")

        # 支撑位
        support = data.get("支撑位")
        if support is not None:
            self.support_badge.setText(f"支撑: {support:.2f}")
        else:
            self.support_badge.setText("支撑: --")

        # 压力位
        resistance = data.get("压力位")
        if resistance is not None:
            self.resistance_badge.setText(f"压力: {resistance:.2f}")
        else:
            self.resistance_badge.setText("压力: --")

        # 详细分析
        detail = data.get("分析详情", "无详细分析")
        self.detail_label.setText(detail)
