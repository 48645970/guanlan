# -*- coding: utf-8 -*-
"""
观澜量化 - 委托指令检查风控规则

检查合约是否存在、价格是否为最小变动价位的整数倍、委托数量是否在合约允许范围内。

Author: 海山观澜
"""

from vnpy.trader.object import OrderRequest, ContractData

from vnpy_riskmanager.template import RuleTemplate


class OrderValidityRule(RuleTemplate):
    """委托指令检查风控规则"""

    name: str = "委托指令检查"

    def check_allowed(self, req: OrderRequest, gateway_name: str) -> bool:
        """检查是否允许委托"""
        # 检查合约存在
        contract: ContractData | None = self.get_contract(req.vt_symbol)
        if not contract:
            self.write_log(f"合约代码{req.vt_symbol}不存在：{req}")
            return False

        # 检查最小价格变动
        if contract.pricetick > 0:
            pricetick: float = contract.pricetick
            remainder: float = req.price % pricetick

            if abs(remainder) > 1e-6 and abs(remainder - pricetick) > 1e-6:
                self.write_log(
                    f"价格{req.price}不是合约最小变动价位{pricetick}的整数倍：{req}"
                )
                return False

        # 检查委托数量上限
        if contract.max_volume and req.volume > contract.max_volume:
            self.write_log(
                f"委托数量{req.volume}大于合约委托数量上限{contract.max_volume}：{req}"
            )
            return False

        # 检查委托数量下限
        if req.volume < contract.min_volume:
            self.write_log(
                f"委托数量{req.volume}小于合约委托数量下限{contract.min_volume}：{req}"
            )
            return False

        return True
