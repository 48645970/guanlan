# -*- coding: utf-8 -*-
"""
观澜量化 - 每日上限检查风控规则（多账户版）

按账户（gateway_name）独立跟踪委托/撤单/成交笔数，
各账户使用相同的上限阈值，互不干扰。
显示变量为所有账户的汇总值。

Author: 海山观澜
"""

from collections import defaultdict
from typing import Any

from vnpy.trader.object import OrderRequest, OrderData, TradeData
from vnpy.trader.constant import Status

from vnpy_riskmanager.template import RuleTemplate


class DailyLimitRule(RuleTemplate):
    """每日上限检查风控规则（按账户独立计数）"""

    name: str = "每日上限检查"

    parameters: dict[str, str] = {
        "total_order_limit": "汇总委托上限",
        "total_cancel_limit": "汇总撤单上限",
        "total_trade_limit": "汇总成交上限",
        "contract_order_limit": "合约委托上限",
        "contract_cancel_limit": "合约撤单上限",
        "contract_trade_limit": "合约成交上限"
    }

    variables: dict[str, str] = {
        "total_order_count": "汇总委托笔数",
        "total_cancel_count": "汇总撤单笔数",
        "total_trade_count": "汇总成交笔数",
        "contract_order_count": "合约委托笔数",
        "contract_cancel_count": "合约撤单笔数",
        "contract_trade_count": "合约成交笔数"
    }

    def on_init(self) -> None:
        """初始化"""
        # 默认参数
        self.total_order_limit: int = 20_000
        self.total_cancel_limit: int = 10_000
        self.total_trade_limit: int = 10_000
        self.contract_order_limit: int = 2_000
        self.contract_cancel_limit: int = 1_000
        self.contract_trade_limit: int = 1_000

        # 按账户分开的委托号/成交号记录
        self._gw_orderids: dict[str, set[str]] = defaultdict(set)
        self._gw_cancel_ids: dict[str, set[str]] = defaultdict(set)
        self._gw_tradeids: dict[str, set[str]] = defaultdict(set)

        # 按账户分开的合约级计数
        self._gw_contract_order: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._gw_contract_cancel: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._gw_contract_trade: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # 汇总显示变量
        self.total_order_count: int = 0
        self.total_cancel_count: int = 0
        self.total_trade_count: int = 0
        self.contract_order_count: dict[str, int] = defaultdict(int)
        self.contract_cancel_count: dict[str, int] = defaultdict(int)
        self.contract_trade_count: dict[str, int] = defaultdict(int)

    def get_data(self) -> dict[str, Any]:
        """获取数据（含各账户明细）"""
        data = super().get_data()

        all_gws: set[str] = set()
        all_gws.update(self._gw_orderids)
        all_gws.update(self._gw_cancel_ids)
        all_gws.update(self._gw_tradeids)

        per_gateway: dict[str, dict[str, Any]] = {}
        for gw in all_gws:
            per_gateway[gw] = {
                "total_order_count": len(self._gw_orderids.get(gw, set())),
                "total_cancel_count": len(self._gw_cancel_ids.get(gw, set())),
                "total_trade_count": len(self._gw_tradeids.get(gw, set())),
                "contract_order_count": dict(self._gw_contract_order.get(gw, {})),
                "contract_cancel_count": dict(self._gw_contract_cancel.get(gw, {})),
                "contract_trade_count": dict(self._gw_contract_trade.get(gw, {})),
            }
        data["per_gateway"] = per_gateway
        return data

    def check_allowed(self, req: OrderRequest, gateway_name: str) -> bool:
        """检查指定账户是否超出每日上限"""
        # ── 合约级检查 ──
        gw_co = self._gw_contract_order[gateway_name]
        co_count: int = gw_co.get(req.vt_symbol, 0)
        if co_count >= self.contract_order_limit:
            self.write_log(
                f"[{gateway_name}] 合约委托笔数{co_count}"
                f"达到上限{self.contract_order_limit}：{req}"
            )
            return False

        gw_cc = self._gw_contract_cancel[gateway_name]
        cc_count: int = gw_cc.get(req.vt_symbol, 0)
        if cc_count >= self.contract_cancel_limit:
            self.write_log(
                f"[{gateway_name}] 合约撤单笔数{cc_count}"
                f"达到上限{self.contract_cancel_limit}：{req}"
            )
            return False

        gw_ct = self._gw_contract_trade[gateway_name]
        ct_count: int = gw_ct.get(req.vt_symbol, 0)
        if ct_count >= self.contract_trade_limit:
            self.write_log(
                f"[{gateway_name}] 合约成交笔数{ct_count}"
                f"达到上限{self.contract_trade_limit}：{req}"
            )
            return False

        # ── 汇总级检查 ──
        gw_order_count: int = len(self._gw_orderids.get(gateway_name, set()))
        if gw_order_count >= self.total_order_limit:
            self.write_log(
                f"[{gateway_name}] 汇总委托笔数{gw_order_count}"
                f"达到上限{self.total_order_limit}：{req}"
            )
            return False

        gw_cancel_count: int = len(self._gw_cancel_ids.get(gateway_name, set()))
        if gw_cancel_count >= self.total_cancel_limit:
            self.write_log(
                f"[{gateway_name}] 汇总撤单笔数{gw_cancel_count}"
                f"达到上限{self.total_cancel_limit}：{req}"
            )
            return False

        gw_trade_count: int = len(self._gw_tradeids.get(gateway_name, set()))
        if gw_trade_count >= self.total_trade_limit:
            self.write_log(
                f"[{gateway_name}] 汇总成交笔数{gw_trade_count}"
                f"达到上限{self.total_trade_limit}：{req}"
            )
            return False

        return True

    def on_order(self, order: OrderData) -> None:
        """委托推送"""
        gw: str = order.gateway_name
        gw_orderids: set = self._gw_orderids[gw]

        if order.vt_orderid not in gw_orderids:
            gw_orderids.add(order.vt_orderid)
            self._gw_contract_order[gw][order.vt_symbol] += 1
            self._update_display()
        elif (
            order.status == Status.CANCELLED
            and order.vt_orderid not in self._gw_cancel_ids[gw]
        ):
            self._gw_cancel_ids[gw].add(order.vt_orderid)
            self._gw_contract_cancel[gw][order.vt_symbol] += 1
            self._update_display()

    def on_trade(self, trade: TradeData) -> None:
        """成交推送"""
        gw: str = trade.gateway_name
        if trade.vt_tradeid in self._gw_tradeids[gw]:
            return

        self._gw_tradeids[gw].add(trade.vt_tradeid)
        self._gw_contract_trade[gw][trade.vt_symbol] += 1
        self._update_display()

    def _update_display(self) -> None:
        """更新汇总显示变量"""
        self.total_order_count = sum(
            len(s) for s in self._gw_orderids.values()
        )
        self.total_cancel_count = sum(
            len(s) for s in self._gw_cancel_ids.values()
        )
        self.total_trade_count = sum(
            len(s) for s in self._gw_tradeids.values()
        )

        self.contract_order_count = self._aggregate(self._gw_contract_order)
        self.contract_cancel_count = self._aggregate(self._gw_contract_cancel)
        self.contract_trade_count = self._aggregate(self._gw_contract_trade)

        self.put_event()

    @staticmethod
    def _aggregate(
        gw_counts: dict[str, dict[str, int]],
    ) -> dict[str, int]:
        """按合约汇总各账户计数"""
        result: dict[str, int] = defaultdict(int)
        for gw_data in gw_counts.values():
            for symbol, count in gw_data.items():
                result[symbol] += count
        return result
