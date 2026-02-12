# -*- coding: utf-8 -*-
"""
观澜量化 - 重复报单检查风控规则（多账户版）

在报单特征字符串中包含 gateway_name，
使得同一委托在不同账户上各自独立计数。

Author: 海山观澜
"""

from collections import defaultdict
from typing import Any

from vnpy.trader.object import OrderRequest

from vnpy_riskmanager.template import RuleTemplate


class DuplicateOrderRule(RuleTemplate):
    """重复报单检查风控规则（按账户独立计数）"""

    name: str = "重复报单检查"

    parameters: dict[str, str] = {
        "duplicate_order_limit": "重复报单上限",
    }

    variables: dict[str, str] = {
        "duplicate_order_count": "重复报单笔数"
    }

    def on_init(self) -> None:
        """初始化"""
        self.duplicate_order_limit: int = 10
        self.duplicate_order_count: dict[str, int] = defaultdict(int)

    def get_data(self) -> dict[str, Any]:
        """获取数据（含各账户明细）"""
        data = super().get_data()

        per_gateway: dict[str, dict[str, Any]] = {}
        for req_str, count in self.duplicate_order_count.items():
            gw = req_str.split("|", 1)[0]
            if gw not in per_gateway:
                per_gateway[gw] = {"duplicate_order_count": {}}
            per_gateway[gw]["duplicate_order_count"][req_str] = count
        data["per_gateway"] = per_gateway
        return data

    def check_allowed(self, req: OrderRequest, gateway_name: str) -> bool:
        """检查是否允许委托"""
        req_str: str = self._format_req(req, gateway_name)
        self.duplicate_order_count[req_str] += 1
        self.put_event()

        count: int = self.duplicate_order_count[req_str]
        if count >= self.duplicate_order_limit:
            self.write_log(
                f"[{gateway_name}] 重复报单笔数{count}"
                f"达到上限{self.duplicate_order_limit}：{req}"
            )
            return False

        return True

    @staticmethod
    def _format_req(req: OrderRequest, gateway_name: str) -> str:
        """将委托请求转为字符串（包含账户名）"""
        return (
            f"{gateway_name}|{req.vt_symbol}|{req.type.value}"
            f"|{req.direction.value}|{req.offset.value}"
            f"|{req.volume}@{req.price}"
        )
