# -*- coding: utf-8 -*-
"""
观澜量化 - K 线周期解析

Author: 海山观澜
"""

import re

from vnpy.trader.constant import Interval

# 周期解析正则
_RE = re.compile(r"^(\d+)\s*(秒|分钟?|小?时|天|日)$")

# 预置常用数值（下拉建议，可自由输入其他值）
PRESET_NUMBERS: list[str] = ["1", "2", "5", "10", "15", "30", "60", "120"]

# 可选单位
UNITS: list[str] = ["秒", "分"]

# 默认周期
DEFAULT_NUMBER: str = "1"
DEFAULT_UNIT: str = "分"


class Period:
    """K 线周期

    封装 second_window / window / interval 三元组，
    提供解析、验证、历史数据量计算等功能。

    Examples
    --------
    >>> p = Period.parse("5分钟")
    >>> p.window
    5
    >>> p.history_minutes(200)
    1060
    """

    __slots__ = ("second_window", "window", "interval")

    def __init__(
        self, second_window: int, window: int, interval: Interval,
    ) -> None:
        self.second_window = second_window
        self.window = window
        self.interval = interval

    @classmethod
    def parse(cls, text: str) -> "Period | None":
        """解析周期文本

        Parameters
        ----------
        text : str
            周期文本，如 "10秒"、"5分钟"、"1小时"

        Returns
        -------
        Period | None
            解析成功返回 Period 实例，失败返回 None
        """
        m = _RE.match(text.strip())
        if not m:
            return None

        n = int(m.group(1))
        unit = m.group(2)

        if unit == "秒":
            if n <= 0:
                return None
            return cls(n, 0, Interval.MINUTE)

        if unit in ("分", "分钟"):
            if n <= 0:
                return None
            if n == 1:
                return cls(0, 0, Interval.MINUTE)
            # 分钟窗口必须能整除 60（VNPY 限制）
            if 60 % n != 0:
                return None
            return cls(0, n, Interval.MINUTE)

        if unit in ("时", "小时"):
            if n == 1:
                # 1小时 = 60分钟窗口
                return cls(0, 60, Interval.MINUTE)
            # 多小时无法通过分钟窗口实现（VNPY 分钟窗口要求整除 60）
            return None

        # 天/日：暂不支持
        return None

    @staticmethod
    def decompose(text: str) -> tuple[str, str]:
        """从周期文本提取数字和单位

        用于从保存的配置还原到 UI 控件。
        兼容旧格式："5分钟" → ("5", "分")，"1小时" → ("60", "分")。

        Returns
        -------
        tuple[str, str]
            (数字字符串, 单位)，解析失败返回 ("1", "分")
        """
        m = _RE.match(text.strip())
        if not m:
            return DEFAULT_NUMBER, DEFAULT_UNIT

        num = m.group(1)
        unit = m.group(2)

        if unit in ("分", "分钟"):
            return num, "分"
        if unit in ("时", "小时"):
            return str(int(num) * 60), "分"
        if unit == "秒":
            return num, "秒"

        return DEFAULT_NUMBER, DEFAULT_UNIT

    @staticmethod
    def error_message(text: str) -> str:
        """返回无效周期文本的用户提示信息"""
        m = _RE.match(text.strip())
        if m:
            unit = m.group(2)
            if unit in ("天", "日"):
                return "日线需要 daily_end 参数，暂不支持"
            if unit in ("时", "小时"):
                return "仅支持 1 小时（等同 60 分钟），多小时暂不支持"
            if unit in ("分", "分钟"):
                return "分钟数必须能整除 60（如 2/3/4/5/6/10/12/15/20/30）"
        return f"无法识别周期 \"{text}\"，支持格式：N秒/N分钟/1小时"

    @property
    def is_second(self) -> bool:
        """是否为秒级模式"""
        return self.second_window > 0

    @property
    def is_window(self) -> bool:
        """是否为窗口模式（多分钟）"""
        return self.window > 0

    def history_minutes(self, bar_count: int) -> int:
        """计算加载历史所需的分钟数

        Parameters
        ----------
        bar_count : int
            需要的 K 线根数
        """
        if self.second_window > 0:
            return (bar_count * self.second_window) // 60 + 60
        if self.window > 0:
            return bar_count * self.window + 60
        return bar_count + 60
