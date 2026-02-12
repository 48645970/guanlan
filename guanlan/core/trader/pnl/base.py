# -*- coding: utf-8 -*-
"""
观澜量化 - 盈亏统计数据模型

参考 VNPY PortfolioManager 设计，按「策略组合 × 合约」维度
跟踪成交并实时计算盈亏。

Author: 海山观澜
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.constant import Direction
from vnpy.trader.object import TickData, TradeData, ContractData

from guanlan.core.setting.commission import calculate_commission

if TYPE_CHECKING:
    from .engine import PortfolioEngine


class ContractResult:
    """合约级盈亏统计

    按 (reference, vt_symbol, gateway_name) 维度跟踪：
    - 开盘仓位 / 当前仓位
    - 多空成交量 / 成本
    - 交易盈亏 / 持仓盈亏 / 总盈亏
    """

    def __init__(
        self,
        engine: PortfolioEngine,
        reference: str,
        vt_symbol: str,
        gateway_name: str = "",
        open_pos: float = 0,
        commission: float = 0,
    ) -> None:
        self.engine = engine
        self.reference = reference
        self.vt_symbol = vt_symbol
        self.gateway_name = gateway_name

        self.open_pos: float = open_pos
        self.last_pos: float = open_pos

        self.trading_pnl: float = 0
        self.holding_pnl: float = 0
        self.total_pnl: float = 0

        self.trades: dict[str, TradeData] = {}
        self.new_trades: list[TradeData] = []

        self.long_volume: float = 0
        self.short_volume: float = 0
        self.long_cost: float = 0
        self.short_cost: float = 0

        self.commission: float = commission

    def update_trade(self, trade: TradeData) -> None:
        """更新成交（自动去重）"""
        if trade.vt_tradeid in self.trades:
            return
        self.trades[trade.vt_tradeid] = trade
        self.new_trades.append(trade)

        if trade.direction == Direction.LONG:
            self.last_pos += trade.volume
        else:
            self.last_pos -= trade.volume

        self.commission += calculate_commission(trade)

    def calculate_pnl(self) -> None:
        """计算盈亏（需要最新 tick 和合约信息）"""
        contract: ContractData | None = self.engine.get_contract(self.vt_symbol)
        tick: TickData | None = self.engine.get_tick(self.vt_symbol)
        if not contract or not tick:
            return

        last_price: float = tick.last_price
        size: float = contract.size

        # 累计新成交的成本
        for trade in self.new_trades:
            trade_cost: float = trade.price * trade.volume * size

            if trade.direction == Direction.LONG:
                self.long_cost += trade_cost
                self.long_volume += trade.volume
            else:
                self.short_cost += trade_cost
                self.short_volume += trade.volume

        self.new_trades.clear()

        # 交易盈亏 = 多头浮动市值 - 多头成本 + 空头成本 - 空头浮动市值
        long_value: float = self.long_volume * last_price * size
        short_value: float = self.short_volume * last_price * size
        self.trading_pnl = (long_value - self.long_cost) + (self.short_cost - short_value)

        # 持仓盈亏 = (最新价 - 昨收) × 开盘仓位 × 合约乘数
        self.holding_pnl = (last_price - tick.pre_close) * self.open_pos * size
        self.total_pnl = self.holding_pnl + self.trading_pnl

    def get_data(self) -> dict:
        """获取数据字典（用于事件推送）"""
        return {
            "reference": self.reference,
            "vt_symbol": self.vt_symbol,
            "gateway_name": self.gateway_name,
            "open_pos": self.open_pos,
            "last_pos": self.last_pos,
            "trading_pnl": self.trading_pnl,
            "holding_pnl": self.holding_pnl,
            "total_pnl": self.total_pnl,
            "long_volume": self.long_volume,
            "short_volume": self.short_volume,
            "long_cost": self.long_cost,
            "short_cost": self.short_cost,
            "commission": self.commission,
        }


class PortfolioResult:
    """组合级盈亏汇总（按 reference + gateway_name 维度）"""

    def __init__(self, reference: str, gateway_name: str = "") -> None:
        self.reference = reference
        self.gateway_name = gateway_name
        self.trading_pnl: float = 0
        self.holding_pnl: float = 0
        self.total_pnl: float = 0
        self.commission: float = 0

    def clear_pnl(self) -> None:
        """清零（每次重算前调用）"""
        self.trading_pnl = 0
        self.holding_pnl = 0
        self.total_pnl = 0
        self.commission = 0

    def get_data(self) -> dict:
        """获取数据字典（用于事件推送）"""
        return {
            "reference": self.reference,
            "gateway_name": self.gateway_name,
            "trading_pnl": self.trading_pnl,
            "holding_pnl": self.holding_pnl,
            "total_pnl": self.total_pnl,
            "commission": self.commission,
        }
