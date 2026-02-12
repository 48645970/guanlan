# -*- coding: utf-8 -*-
"""
观澜量化 - 风控管理配置

Author: 海山观澜
"""

from typing import Any

# 配置文件路径（相对于 .guanlan 目录）
SETTING_FILENAME: str = "config/risk.json"

# 风控规则定义
# 结构：{规则名: {字段名: (中文名, 默认值)}}
RISK_RULES: dict[str, dict[str, tuple[str, Any]]] = {
    "委托指令检查": {
        "active": ("启用规则", True),
    },
    "委托规模检查": {
        "active": ("启用规则", True),
        "order_volume_limit": ("委托数量上限", 500),
        "order_value_limit": ("委托价值上限", 1_000_000.0),
    },
    "活动委托检查": {
        "active": ("启用规则", True),
        "active_order_limit": ("活动委托上限", 50),
    },
    "每日上限检查": {
        "active": ("启用规则", True),
        "total_order_limit": ("汇总委托上限", 20_000),
        "total_cancel_limit": ("汇总撤单上限", 10_000),
        "total_trade_limit": ("汇总成交上限", 10_000),
        "contract_order_limit": ("合约委托上限", 2_000),
        "contract_cancel_limit": ("合约撤单上限", 1_000),
        "contract_trade_limit": ("合约成交上限", 1_000),
    },
    "重复报单检查": {
        "active": ("启用规则", True),
        "duplicate_order_limit": ("重复报单上限", 10),
    },
}
