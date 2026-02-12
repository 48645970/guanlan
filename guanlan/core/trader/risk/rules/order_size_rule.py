# -*- coding: utf-8 -*-
"""
观澜量化 - 委托规模检查风控规则

检查单笔委托的数量和价值是否超出上限。

Author: 海山观澜
"""

from vnpy.trader.object import OrderRequest, ContractData

from vnpy_riskmanager.template import RuleTemplate


class OrderSizeRule(RuleTemplate):
    """委托规模检查风控规则"""

    name: str = "委托规模检查"

    parameters: dict[str, str] = {
        "order_volume_limit": "委托数量上限",
        "order_value_limit": "委托价值上限",
    }

    def on_init(self) -> None:
        """初始化"""
        self.order_volume_limit: int = 500
        self.order_value_limit: float = 1_000_000

    def check_allowed(self, req: OrderRequest, gateway_name: str) -> bool:
        """检查是否允许委托"""
        if req.volume > self.order_volume_limit:
            self.write_log(
                f"委托数量{req.volume}超过上限{self.order_volume_limit}：{req}"
            )
            return False

        contract: ContractData | None = self.get_contract(req.vt_symbol)
        if contract and req.price:
            order_value: float = req.volume * req.price * contract.size
            if order_value > self.order_value_limit:
                self.write_log(
                    f"委托价值{order_value}超过上限{self.order_value_limit}：{req}"
                )
                return False

        return True
