# -*- coding: utf-8 -*-
"""
观澜量化 - 活动委托检查风控规则（多账户版）

按账户（gateway_name）独立跟踪活动委托数量，
各账户使用相同的上限阈值，互不干扰。

Author: 海山观澜
"""

from collections import defaultdict
from typing import Any

from vnpy.trader.object import OrderRequest, OrderData

from vnpy_riskmanager.template import RuleTemplate


class ActiveOrderRule(RuleTemplate):
    """活动委托数量检查风控规则（按账户独立计数）"""

    name: str = "活动委托检查"

    parameters: dict[str, str] = {
        "active_order_limit": "活动委托上限"
    }

    variables: dict[str, str] = {
        "active_order_count": "活动委托数量"
    }

    def on_init(self) -> None:
        """初始化"""
        self.active_order_limit: int = 50

        # 按账户分开的活动委托：gateway_name → {vt_orderid → OrderData}
        self._gw_orders: dict[str, dict[str, OrderData]] = defaultdict(dict)

        # 汇总显示
        self.active_order_count: int = 0

    def check_allowed(self, req: OrderRequest, gateway_name: str) -> bool:
        """检查指定账户的活动委托是否达到上限"""
        gw_count: int = len(self._gw_orders.get(gateway_name, {}))
        if gw_count >= self.active_order_limit:
            self.write_log(
                f"[{gateway_name}] 活动委托数量{gw_count}"
                f"达到上限{self.active_order_limit}：{req}"
            )
            return False

        return True

    def get_data(self) -> dict[str, Any]:
        """获取数据（含各账户明细）"""
        data = super().get_data()
        data["per_gateway"] = {
            gw: {"active_order_count": len(orders)}
            for gw, orders in self._gw_orders.items()
        }
        return data

    def on_order(self, order: OrderData) -> None:
        """委托推送"""
        gw_orders: dict = self._gw_orders[order.gateway_name]

        if order.is_active():
            gw_orders[order.vt_orderid] = order
        elif order.vt_orderid in gw_orders:
            gw_orders.pop(order.vt_orderid)

        self.active_order_count = sum(
            len(d) for d in self._gw_orders.values()
        )
        self.put_event()
