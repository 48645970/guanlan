# -*- coding: utf-8 -*-
"""
观澜量化 - 盈亏统计引擎

参考 VNPY PortfolioManager 设计，直连 EventEngine，
按「策略组合 × 合约 × 账户」维度实时计算盈亏。

数据持久化：
- portfolio_data.json: 每个合约的开盘/当前仓位（按日重置）
- portfolio_order.json: 委托 → 策略来源映射（按日重置）

Author: 海山观澜
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vnpy.trader.event import EVENT_ORDER, EVENT_TRADE, EVENT_TIMER
from vnpy.trader.object import (
    ContractData, OrderData, TradeData, TickData,
)

from guanlan.core.trader.gateway.ctp import EVENT_CONTRACT_INITED

from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.engine import BaseEngine, MainEngine
from guanlan.core.utils.common import load_json_file, save_json_file
from guanlan.core.utils.trading_period import get_trading_date

from .base import ContractResult, PortfolioResult


# 自定义事件类型
EVENT_PM_CONTRACT = "ePmContract"
EVENT_PM_PORTFOLIO = "ePmPortfolio"
EVENT_PM_TRADE = "ePmTrade"

# 配置文件
DATA_FILENAME: str = "config/portfolio_data.json"
ORDER_FILENAME: str = "config/portfolio_order.json"
SETTING_FILENAME: str = "config/portfolio_setting.json"


class PortfolioEngine(BaseEngine):
    """盈亏统计引擎

    监听 ORDER/TRADE/TIMER/CONTRACT 事件，计算合约级和组合级盈亏，
    通过自定义事件推送到 UI。

    通过 MainEngine.add_engine() 注册，关闭由 MainEngine.close() 统一管理。
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, "portfolio")

        self.get_tick: Callable[[str], TickData | None] = self.main_engine.get_tick
        self.get_contract: Callable[[str], ContractData | None] = self.main_engine.get_contract

        self.result_symbols: set[str] = set()
        self.order_reference_map: dict[str, str] = {}
        self.contract_results: dict[tuple[str, str, str], ContractResult] = {}
        self.portfolio_results: dict[tuple[str, str], PortfolioResult] = {}

        self.timer_count: int = 0
        self.timer_interval: int = 5

        self._load_setting()
        self._load_data()
        self._load_order()
        self._register_events()

    def _register_events(self) -> None:
        """注册事件监听"""
        self.event_engine.register(EVENT_ORDER, self._process_order_event)
        self.event_engine.register(EVENT_TRADE, self._process_trade_event)
        self.event_engine.register(EVENT_TIMER, self._process_timer_event)
        self.event_engine.register(EVENT_CONTRACT_INITED, self._process_contract_inited_event)

    def _process_order_event(self, event: Event) -> None:
        """委托事件：缓存 vt_orderid → reference 映射"""
        order: OrderData = event.data

        if order.vt_orderid not in self.order_reference_map:
            self.order_reference_map[order.vt_orderid] = order.reference
        else:
            order.reference = self.order_reference_map[order.vt_orderid]

    def _process_trade_event(self, event: Event) -> None:
        """成交事件：更新合约盈亏统计"""
        trade: TradeData = event.data

        reference: str = self.order_reference_map.get(trade.vt_orderid, "")
        if not reference:
            return

        vt_symbol: str = trade.vt_symbol
        gateway_name: str = trade.gateway_name
        key: tuple[str, str, str] = (reference, vt_symbol, gateway_name)

        contract_result = self.contract_results.get(key)
        if not contract_result:
            contract_result = ContractResult(self, reference, vt_symbol, gateway_name)
            self.contract_results[key] = contract_result

        contract_result.update_trade(trade)

        # 推送成交事件到 UI
        trade.reference = reference
        self.event_engine.put(Event(EVENT_PM_TRADE, trade))

        # 自动订阅 tick 数据
        from guanlan.core.app import AppEngine
        AppEngine.instance().subscribe(trade.vt_symbol)

    def _process_timer_event(self, event: Event) -> None:
        """定时事件：重算盈亏并推送"""
        self.timer_count += 1
        if self.timer_count < self.timer_interval:
            return
        self.timer_count = 0

        # 清零组合级盈亏
        for portfolio_result in self.portfolio_results.values():
            portfolio_result.clear_pnl()

        # 重算每个合约的盈亏，并汇总到组合
        for contract_result in self.contract_results.values():
            contract_result.calculate_pnl()

            portfolio_result = self._get_portfolio_result(contract_result.reference, contract_result.gateway_name)
            portfolio_result.trading_pnl += contract_result.trading_pnl
            portfolio_result.holding_pnl += contract_result.holding_pnl
            portfolio_result.total_pnl += contract_result.total_pnl
            portfolio_result.commission += contract_result.commission

            self.event_engine.put(Event(EVENT_PM_CONTRACT, contract_result.get_data()))

        # 推送组合级盈亏
        for portfolio_result in self.portfolio_results.values():
            self.event_engine.put(Event(EVENT_PM_PORTFOLIO, portfolio_result.get_data()))

    def _process_contract_inited_event(self, event: Event) -> None:
        """合约查询完毕：一次性批量订阅已有持仓品种的行情"""
        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        for vt_symbol in self.result_symbols:
            app.subscribe(vt_symbol)

    def _get_portfolio_result(self, reference: str, gateway_name: str) -> PortfolioResult:
        """获取或创建组合级统计"""
        key = (reference, gateway_name)
        portfolio_result = self.portfolio_results.get(key)
        if not portfolio_result:
            portfolio_result = PortfolioResult(reference, gateway_name)
            self.portfolio_results[key] = portfolio_result
        return portfolio_result

    # ── 数据持久化 ──

    def _load_data(self) -> None:
        """加载仓位数据"""
        data: dict = load_json_file(DATA_FILENAME)
        if not data:
            return

        today: str = get_trading_date()
        date_changed: bool = False

        date: str = data.pop("date", "")
        for key, d in data.items():
            parts = key.split(",")
            if len(parts) == 3:
                reference, vt_symbol, gateway_name = parts
            else:
                # 兼容旧格式（无 gateway_name）
                reference, vt_symbol = parts[0], parts[1]
                gateway_name = ""

            if date == today:
                pos: float = d["open_pos"]
                commission: float = d.get("commission", 0)
            else:
                pos = d["last_pos"]
                commission = 0
                date_changed = True

            self.result_symbols.add(vt_symbol)
            self.contract_results[(reference, vt_symbol, gateway_name)] = ContractResult(
                self, reference, vt_symbol, gateway_name, pos, commission
            )

        if date_changed:
            self._save_data()

    def _save_data(self) -> None:
        """保存仓位数据"""
        data: dict[str, Any] = {"date": get_trading_date()}

        for contract_result in self.contract_results.values():
            key = f"{contract_result.reference},{contract_result.vt_symbol},{contract_result.gateway_name}"
            data[key] = {
                "open_pos": contract_result.open_pos,
                "last_pos": contract_result.last_pos,
                "commission": contract_result.commission,
            }

        save_json_file(DATA_FILENAME, data)

    def _load_order(self) -> None:
        """加载委托映射（仅当日有效）"""
        order_data: dict = load_json_file(ORDER_FILENAME)

        date: str = order_data.get("date", "")
        today: str = get_trading_date()
        if date == today:
            self.order_reference_map = order_data.get("data", {})

    def _save_order(self) -> None:
        """保存委托映射"""
        order_data: dict[str, Any] = {
            "date": get_trading_date(),
            "data": self.order_reference_map,
        }
        save_json_file(ORDER_FILENAME, order_data)

    def _load_setting(self) -> None:
        """加载设置"""
        setting: dict = load_json_file(SETTING_FILENAME)
        if "timer_interval" in setting:
            self.timer_interval = setting["timer_interval"]

    def _save_setting(self) -> None:
        """保存设置"""
        setting: dict[str, int] = {"timer_interval": self.timer_interval}
        save_json_file(SETTING_FILENAME, setting)

    # ── 公共接口 ──

    def set_timer_interval(self, interval: int) -> None:
        """设置刷新间隔"""
        self.timer_interval = interval

    def get_timer_interval(self) -> int:
        """获取刷新间隔"""
        return self.timer_interval

    def close(self) -> None:
        """关闭引擎（保存数据）"""
        self._save_setting()
        self._save_data()
        self._save_order()
