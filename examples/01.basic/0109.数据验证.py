# -*- coding: utf-8 -*-
"""
Pydantic 参数模型示例

演示策略参数/状态定义：
- BaseModel 模型定义
- Field 字段约束（ge/le/title）
- Literal 类型枚举
- model_validator 自定义验证

使用前需要：
1. pip install pydantic

Author: 海山观澜
"""

from typing import Literal


def main():
    print("=" * 50)
    print("Pydantic 参数模型测试")
    print("=" * 50)

    try:
        from pydantic import BaseModel, Field, model_validator
    except ImportError:
        print("请先安装 pydantic: pip install pydantic")
        return

    # 定义模型类
    class BaseParams(BaseModel):
        """策略参数基类"""
        model_config = {"extra": "allow", "validate_assignment": True}

        @model_validator(mode='after')
        def check_all_fields_have_title(self):
            """验证所有字段都有 title"""
            for field_name, field_info in self.model_fields.items():
                if not field_info.title:
                    raise ValueError(f"字段 '{field_name}' 必须定义 title")
            return self

    class BaseState(BaseModel):
        """策略状态基类"""
        model_config = {"validate_assignment": True}
        pos: int = Field(default=0, title="持仓")

    # ============ 用户定义的参数和状态 ============

    class Params(BaseParams):
        """策略参数"""
        fast_period: int = Field(default=5, title="快均线周期", ge=1, le=100)
        slow_period: int = Field(default=20, title="慢均线周期", ge=1, le=200)
        order_volume: int = Field(default=1, title="下单手数", ge=1)
        # Literal 类型会自动生成下拉框
        direction: Literal["多", "空", "双向"] = Field(default="双向", title="交易方向")
        auto_change_hot: Literal["是", "否"] = Field(default="否", title="自动换月")

    class State(BaseState):
        """策略状态"""
        fast_ma: float = Field(default=0.0, title="快均线")
        slow_ma: float = Field(default=0.0, title="慢均线")
        signal: str = Field(default="", title="当前信号")

    # 创建参数实例
    params = Params()
    print(f"\n默认参数: {params.model_dump()}")

    # 修改参数
    params.fast_period = 10
    params.slow_period = 30
    print(f"修改后参数: {params.model_dump()}")

    # 验证约束
    try:
        params.fast_period = 0  # 违反 ge=1
    except Exception as e:
        print(f"\n验证错误（预期）: {e}")

    # 创建状态实例
    state = State()
    print(f"\n默认状态: {state.model_dump()}")

    # 更新状态
    state.fast_ma = 4520.5
    state.slow_ma = 4515.2
    state.signal = "金叉做多"
    state.pos = 1
    print(f"更新后状态: {state.model_dump()}")

    # 遍历字段元数据
    print("\n字段元数据:")
    for name, field_info in Params.model_fields.items():
        print(f"  {name}: title={field_info.title}, type={field_info.annotation}")

    print("\nPydantic 环境正常！")


if __name__ == "__main__":
    main()
