# -*- coding: utf-8 -*-
"""
观澜量化 - 指标基类

BaseIndicatorParams: 指标参数基类（Pydantic 模型）
BaseIndicator: 指标模板抽象基类

参照 CtaTemplate 的 Pydantic 模式设计：
- 参数用 BaseModel + Field(title=...) 约束
- 类变量声明 + __init__ 中 model_copy 实例隔离
- on_init / on_bar 生命周期回调

Author: 海山观澜
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    import numpy as np


class BaseIndicatorParams(BaseModel, validate_assignment=True):
    """指标参数基类

    继承此类定义指标可调参数，支持类型校验和约束。

    示例::

        class MyParams(BaseIndicatorParams):
            period: int = Field(default=20, title="周期", ge=1, le=500)
    """
    pass


class BaseIndicator(ABC):
    """指标模板

    参照 CtaTemplate 设计：
    - Pydantic 参数模型 + Field 约束
    - 类变量声明 + __init__ 中 model_copy 实例隔离
    - on_init / on_bar 生命周期回调
    """

    author: str = ""
    overlay: bool = True              # True=主图叠加, False=副图独立
    params = BaseIndicatorParams()

    @property
    def lookback(self) -> int:
        """最小计算数据量（K 线根数）

        指标至少需要多少根 K 线才能产生有效输出。
        子类应根据自身参数重写此属性。

        返回 0 表示无最低要求，有数据即可计算。
        """
        return 0

    @property
    def display_offset(self) -> int:
        """显示偏移量（K 线根数）

        切换指标时，从当前 K 线往前回溯多少根开始显示指标线。
        避免指标只从当前位置开始画线，而是自动向前延伸。

        默认 100 根，子类可重写以自定义显示范围。
        返回 0 表示从当前位置开始显示。
        """
        return 100

    def __init__(self) -> None:
        # 类变量 → 实例变量（避免多实例共享）
        self.params = self.__class__.params.model_copy(deep=True)
        self.inited: bool = False

    def update_setting(self, setting: dict) -> None:
        """更新参数"""
        for name in self.params.model_fields:
            if name in setting:
                setattr(self.params, name, setting[name])

    @classmethod
    def get_class_parameters(cls) -> BaseIndicatorParams:
        """获取指标类默认参数"""
        return cls.params

    def get_params(self) -> BaseIndicatorParams:
        """获取指标实例参数"""
        return self.params

    def _get_compute_window(self, data: list, window_factor: int = 3, min_size: int = 100) -> list:
        """获取计算窗口数据（性能优化）

        子类在 _compute_bar 中应该使用窗口数据而不是全部历史，
        以避免随着数据累积计算时间线性增长。

        Args:
            data: 完整历史数据列表
            window_factor: 窗口大小倍数（相对于 lookback），默认 3
            min_size: 最小窗口大小，默认 100

        Returns:
            窗口数据（最近的 N 根）

        示例::

            def _compute_bar(self, bar):
                self._closes.append(bar["close"])
                # 只用最近的窗口数据计算，而不是全部
                window = self._get_compute_window(self._closes)
                closes = np.array(window)
                ma = MA(closes, self.params.period)
                return {"MA": ma[-1]}
        """
        window_size = max(self.lookback * window_factor, min_size)
        return data[-window_size:]

    def _clean_nan(self, data: dict[str, list | "np.ndarray"]) -> dict[str, list]:
        """清理数据中的 NaN 值，转换为 None

        Args:
            data: 原始数据，值可以是 list 或 numpy array，可能包含 NaN

        Returns:
            清理后的数据，NaN 转换为 None
        """
        import numpy as np
        cleaned = {}
        for name, values in data.items():
            if isinstance(values, np.ndarray):
                cleaned[name] = [None if np.isnan(v) else v for v in values]
            else:
                # 已经是 list，检查每个元素
                cleaned[name] = [
                    None if (isinstance(v, float) and np.isnan(v)) else v
                    for v in values
                ]
        return cleaned

    def _filter_by_lookback(self, data: dict[str, list]) -> dict[str, list]:
        """根据 lookback 过滤数据，前面不足的部分设为 None

        此方法用于处理指标库（如 MyTT）在数据不足时仍返回不准确值的问题。
        子类在 on_init 中计算完指标后，可调用此方法统一处理。

        Args:
            data: 指标原始数据，格式 {"线名": [值列表], ...}

        Returns:
            过滤后的数据，前 lookback-1 个值强制为 None

        示例::

            def on_init(self, bars):
                # 计算原始数据
                raw_data = {"MA5": ma5_array, "MA20": ma20_array}
                # 自动过滤前面不足 lookback 的值
                return self._filter_by_lookback(raw_data)
        """
        min_bars = self.lookback

        # lookback=0 表示无最低要求，直接返回原始数据
        if min_bars == 0:
            return data

        filtered = {}
        for name, values in data.items():
            if not values:
                filtered[name] = []
                continue

            # 数据总量不足 lookback，全部设为 None
            if len(values) < min_bars:
                filtered[name] = [None] * len(values)
            else:
                # 数据足够，前 lookback-1 个设为 None，后面保留原值
                filtered[name] = [None] * (min_bars - 1) + values[min_bars - 1:]

        return filtered

    @abstractmethod
    def lines(self) -> list[dict]:
        """声明线定义

        返回线的描述列表，每条线包含 name/color/width 等属性。
        图表根据此信息创建 Line 对象。

        Returns:
            [{"name": "MA5", "color": "#FFFFFF", "width": 1}, ...]
        """
        pass

    def reference_lines(self) -> list[dict]:
        """副图参考线（可选，如 RSI 的超买超卖线）

        Returns:
            [{"price": 70, "color": "#EF5350", "style": "dashed"}, ...]
        """
        return []

    def on_init(self, bars: list[dict]) -> dict[str, list]:
        """历史数据初始化（模板方法，自动处理数据对齐）

        此方法不应被子类重写。子类应实现 _compute_init() 方法。

        批量计算历史 K 线的指标值，用于首次加载图表。
        只计算 display_offset 根数据用于显示，不计算全部历史。

        Args:
            bars: K 线数据列表 [{time, open, high, low, close, volume}, ...]

        Returns:
            各线的完整数据 {"MA5": [值列表], "MA20": [值列表]}
        """
        # 性能优化：只计算需要显示的数据
        # display_offset 控制显示范围，无需计算全部历史
        # 例如：有 10000 根历史，只计算最近 100 根用于初始显示

        # 1. 子类计算原始数据（可能包含 NaN）
        raw_data = self._compute_init(bars)

        # 2. 自动清理 NaN → None
        cleaned_data = self._clean_nan(raw_data)

        # 3. 自动根据 lookback 过滤前面不足的数据
        return self._filter_by_lookback(cleaned_data)

    @abstractmethod
    def _compute_init(self, bars: list[dict]) -> dict[str, list | "np.ndarray"]:
        """计算历史数据的指标值（子类实现）

        子类只需实现计算逻辑，返回原始数据即可，不需要关心：
        - NaN 转换（基类自动处理）
        - lookback 过滤（基类自动处理）
        - 数据对齐（基类自动处理）

        Args:
            bars: K 线数据列表 [{time, open, high, low, close, volume}, ...]

        Returns:
            原始指标数据，值可以是 list 或 numpy array，可以包含 NaN
            {"MA5": array([...]), "MA20": array([...])}
        """
        pass

    def on_bar(self, bar: dict) -> dict[str, float | None]:
        """新 K 线更新（模板方法，自动处理数据对齐）

        此方法不应被子类重写。子类应实现 _compute_bar() 方法。

        逐根计算指标最新值，用于实时更新。
        性能优化：子类只需要保留 lookback 窗口的数据即可。

        Args:
            bar: 单根 K 线 {time, open, high, low, close, volume}

        Returns:
            各线的最新值 {"MA5": 100.5, "MA20": 99.8}
        """
        # 性能优化：只保留必要的计算窗口
        # 子类应该只用最近 lookback 根数据计算，而不是全部历史

        # 子类计算原始值（可能包含 NaN）
        raw_data = self._compute_bar(bar)

        # 自动清理 NaN → None
        import numpy as np
        cleaned_data = {}
        for name, value in raw_data.items():
            if isinstance(value, float) and np.isnan(value):
                cleaned_data[name] = None
            else:
                cleaned_data[name] = value

        return cleaned_data

    @abstractmethod
    def _compute_bar(self, bar: dict) -> dict[str, float]:
        """计算单根 K 线的指标值（子类实现）

        子类只需实现计算逻辑，返回原始数据即可，不需要关心：
        - NaN 转换（基类自动处理）
        - lookback 检查（子类可选，基类不强制）

        Args:
            bar: 单根 K 线 {time, open, high, low, close, volume}

        Returns:
            原始指标值，可以包含 NaN
            {"MA5": 100.5, "MA20": 99.8}
        """
        pass

    def get_signals(self, bars: list[dict]) -> list[dict]:
        """批量扫描信号（历史初始化时调用）

        Returns:
            [{"time": "...", "type": "long", "text": "金叉"}, ...]

        type: "long"=做多信号, "short"=做空信号
        text: 指标自定义描述
        """
        return []

    def on_bar_signal(self, bar: dict) -> dict | None:
        """逐 bar 信号检测（实时更新时，在 on_bar 之后调用）

        Returns:
            {"type": "long", "text": "金叉"} 或 None
        """
        return None
