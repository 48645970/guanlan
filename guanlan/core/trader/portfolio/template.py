# -*- coding: utf-8 -*-
"""
观澜量化 - 组合策略模板

PortfolioTemplate: 多合约策略基类
- 多合约列表 vt_symbols
- 各合约持仓 pos_data + 目标仓位 target_data
- set_target / rebalance_portfolio 调仓机制
- on_bars(dict[str, BarData]) K线切片回调

复用 CTA 的 BaseParams / BaseState 两层数据模型。

Author: 海山观澜
"""

import logging
from abc import ABC, abstractmethod
from typing import Any
from collections import defaultdict
from collections.abc import Callable

from vnpy.trader.constant import Interval, Direction, Offset
from vnpy.trader.object import BarData, TickData, OrderData, TradeData

from guanlan.core.trader.cta.template import BaseParams, BaseState, BaseVars
from .base import EngineType


class PortfolioTemplate(ABC):
    """组合策略模板"""

    author: str = ""
    params = BaseParams()
    state = BaseState()
    vars = BaseVars()

    log_level = logging.DEBUG

    def __init__(
        self,
        portfolio_engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        gateway_name: str,
    ) -> None:
        self.portfolio_engine: Any = portfolio_engine
        self.strategy_name: str = strategy_name
        self.vt_symbols: list[str] = vt_symbols
        self.gateway_name: str = gateway_name
        self.symbols: list[str] = vt_symbols  # 原始输入，由引擎覆盖

        self.inited: bool = False
        self.trading: bool = False

        # 类变量 → 实例变量（避免多实例共享同一个 Pydantic 对象）
        self.params = self.__class__.params.model_copy(deep=True)
        self.state = self.__class__.state.model_copy(deep=True)
        self.vars = self.__class__.vars.model_copy(deep=True)

        # 各合约持仓和目标仓位
        self.pos_data: dict[str, float] = defaultdict(float)
        self.target_data: dict[str, float] = defaultdict(float)

        # 多合约换月：品种代码 → 当前合约（内部管理，state.hot 仅用于显示）
        self._hot_map: dict[str, str] = {}
        self._rolling_symbols: set[str] = set()

        # 委托缓存
        self.orders: dict[str, OrderData] = {}
        self.active_orderids: set[str] = set()

    def update_setting(self, setting: dict) -> None:
        """更新策略参数"""
        for name in self.params.model_fields:
            if name in setting:
                setattr(self.params, name, setting[name])

    def update_data(self, data: dict) -> None:
        """更新策略状态（从磁盘恢复）"""
        # 恢复 state 字段
        for name in self.state.model_fields:
            if name in data:
                setattr(self.state, name, data[name])

        # 恢复 pos_data / target_data / _hot_map
        if "pos_data" in data:
            self.pos_data.update(data["pos_data"])
        if "target_data" in data:
            self.target_data.update(data["target_data"])
        if "hot_map" in data:
            self._hot_map.update(data["hot_map"])

    @classmethod
    def get_class_parameters(cls) -> "BaseParams":
        """获取策略类默认参数"""
        return cls.params

    def get_params(self) -> "BaseParams":
        """获取策略实例参数"""
        return self.params

    def get_state(self) -> "BaseState":
        """获取策略状态"""
        return self.state

    def get_vars(self) -> "BaseVars":
        """获取策略临时变量"""
        return self.vars

    def get_data(self) -> dict:
        """获取策略数据（用于 UI 推送）"""
        # 同步 state.hot 显示字符串
        self._sync_hot_display()

        strategy_data: dict = {
            "strategy_name": self.strategy_name,
            "symbols": self.symbols,
            "vt_symbols": self.vt_symbols,
            "inited": self.inited,
            "trading": self.trading,
            "class_name": self.__class__.__name__,
            "author": self.author,
            "gateway_name": self.gateway_name,
            "params": self.get_params(),
            "state": self.get_state(),
            "vars": self.get_vars(),
            "pos_data": dict(self.pos_data),
            "target_data": dict(self.target_data),
            "hot_map": dict(self._hot_map),
        }
        return strategy_data

    # ── 生命周期回调 ──

    @abstractmethod
    def on_init(self) -> None:
        """策略初始化回调"""
        pass

    def on_start(self) -> None:
        """策略启动回调"""
        pass

    def on_trading(self) -> None:
        """进入交易状态回调（on_start 之后、trading=True 之后调用）"""
        pass

    def on_reset(self) -> None:
        """重置策略状态回调"""
        pass

    def on_stop(self) -> None:
        """策略停止回调"""
        pass

    def on_tick(self, tick: TickData) -> None:
        """Tick 数据更新回调"""
        pass

    @abstractmethod
    def on_bars(self, bars: dict[str, BarData]) -> None:
        """K线切片回调（多合约同一时间点的K线）"""
        pass

    # ── 成交/委托内部更新 ──

    def update_trade(self, trade: TradeData) -> None:
        """成交数据更新（内部自动更新 pos_data）"""
        if trade.direction == Direction.LONG:
            self.pos_data[trade.vt_symbol] += trade.volume
        else:
            self.pos_data[trade.vt_symbol] -= trade.volume

    def update_order(self, order: OrderData) -> None:
        """委托数据更新（内部维护 active_orderids）"""
        self.orders[order.vt_orderid] = order

        if order.is_active():
            self.active_orderids.add(order.vt_orderid)
        elif order.vt_orderid in self.active_orderids:
            self.active_orderids.discard(order.vt_orderid)

    # ── 交易接口 ──

    def buy(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """买入开多"""
        return self.send_order(vt_symbol, Direction.LONG, Offset.OPEN, price, volume, lock, net)

    def sell(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """卖出平多"""
        return self.send_order(vt_symbol, Direction.SHORT, Offset.CLOSE, price, volume, lock, net)

    def short(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """卖出开空"""
        return self.send_order(vt_symbol, Direction.SHORT, Offset.OPEN, price, volume, lock, net)

    def cover(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """买入平空"""
        return self.send_order(vt_symbol, Direction.LONG, Offset.CLOSE, price, volume, lock, net)

    def send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        lock: bool = False,
        net: bool = False,
    ) -> list[str]:
        """发送委托"""
        if self.trading:
            vt_orderids: list[str] = self.portfolio_engine.send_order(
                self, vt_symbol, direction, offset, price, volume, lock, net
            )
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str) -> None:
        """撤销委托"""
        if self.trading:
            self.portfolio_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """撤销所有活动委托"""
        if not self.trading:
            return

        for vt_orderid in list(self.active_orderids):
            self.cancel_order(vt_orderid)

    # ── 目标仓位调仓 ──

    def get_pos(self, vt_symbol: str) -> int:
        """获取指定合约持仓"""
        return self.pos_data.get(vt_symbol, 0)

    def get_target(self, vt_symbol: str) -> int:
        """获取指定合约目标仓位"""
        return self.target_data.get(vt_symbol, 0)

    def set_target(self, vt_symbol: str, target: int) -> None:
        """设置指定合约目标仓位"""
        self.target_data[vt_symbol] = target

    def rebalance_portfolio(self, bars: dict[str, BarData]) -> None:
        """根据目标仓位执行调仓交易"""
        self.cancel_all()

        for vt_symbol in self.vt_symbols:
            target: int = self.target_data.get(vt_symbol, 0)
            pos: int = self.pos_data.get(vt_symbol, 0)
            diff: int = target - pos

            if diff == 0:
                continue

            bar: BarData | None = bars.get(vt_symbol, None)
            if not bar:
                continue

            if diff > 0:
                direction = Direction.LONG
                offset = Offset.OPEN

                # 先平空再开多
                if pos < 0:
                    if abs(pos) >= diff:
                        offset = Offset.CLOSE
                    else:
                        # 先平空仓
                        cover_volume = abs(pos)
                        price = self.calculate_price(vt_symbol, Direction.LONG, bar.close_price)
                        self.cover(vt_symbol, price, cover_volume)

                        # 再开多仓
                        open_volume = diff - cover_volume
                        if open_volume > 0:
                            price = self.calculate_price(vt_symbol, Direction.LONG, bar.close_price)
                            self.buy(vt_symbol, price, open_volume)
                        continue

                price = self.calculate_price(vt_symbol, direction, bar.close_price)
                if offset == Offset.CLOSE:
                    self.cover(vt_symbol, price, abs(diff))
                else:
                    self.buy(vt_symbol, price, abs(diff))

            else:
                direction = Direction.SHORT
                offset = Offset.OPEN

                # 先平多再开空
                if pos > 0:
                    if pos >= abs(diff):
                        offset = Offset.CLOSE
                    else:
                        # 先平多仓
                        sell_volume = pos
                        price = self.calculate_price(vt_symbol, Direction.SHORT, bar.close_price)
                        self.sell(vt_symbol, price, sell_volume)

                        # 再开空仓
                        open_volume = abs(diff) - sell_volume
                        if open_volume > 0:
                            price = self.calculate_price(vt_symbol, Direction.SHORT, bar.close_price)
                            self.short(vt_symbol, price, open_volume)
                        continue

                price = self.calculate_price(vt_symbol, direction, bar.close_price)
                if offset == Offset.CLOSE:
                    self.sell(vt_symbol, price, abs(diff))
                else:
                    self.short(vt_symbol, price, abs(diff))

    def calculate_price(
        self,
        vt_symbol: str,
        direction: Direction,
        reference: float,
    ) -> float:
        """计算调仓委托价格（子类可重载加滑点）"""
        return reference

    # ── 换月保护 ──

    @property
    def rolling(self) -> bool:
        """是否有任意合约正在换月"""
        return bool(self._rolling_symbols)

    def rolling_symbols(self) -> set[str]:
        """获取正在换月的合约集合"""
        return set(self._rolling_symbols)

    def need_rollover(self, vt_symbol: str) -> bool:
        """检查指定合约是否需要换月（有持仓且合约已变更）"""
        old = self._hot_map.get(vt_symbol)
        return bool(
            old
            and old != vt_symbol
            and self.pos_data.get(old, 0) != 0
        )

    def begin_rollover(self, vt_symbol: str) -> None:
        """指定合约进入换月状态"""
        old = self._hot_map.get(vt_symbol, "")
        self._rolling_symbols.add(vt_symbol)
        self.write_log(f"开始换月: {old} → {vt_symbol}")

    def complete_rollover(self, vt_symbol: str) -> None:
        """指定合约完成换月"""
        old = self._hot_map.get(vt_symbol, "")
        # 用品种代码作 key（从 vt_symbol 截取）
        symbol = vt_symbol.split(".")[0] if "." in vt_symbol else vt_symbol
        self._hot_map[symbol] = vt_symbol
        self._rolling_symbols.discard(vt_symbol)
        self._sync_hot_display()
        self.sync_data()
        self.write_log(f"换月完成: {old} → {vt_symbol}")

    def _sync_hot_display(self) -> None:
        """将 _hot_map 同步到 state.hot 用于 UI 显示"""
        if self._hot_map:
            self.state.hot = ", ".join(self._hot_map.values())
        else:
            self.state.hot = ""

    # ── 工具方法 ──

    def get_order(self, vt_orderid: str) -> OrderData | None:
        """查询委托数据"""
        return self.orders.get(vt_orderid, None)

    def get_all_active_orderids(self) -> list[str]:
        """获取全部活动委托号"""
        return list(self.active_orderids)

    def write_log(self, msg: str, level: int = logging.INFO, dingtalk: bool = False) -> None:
        """写日志"""
        self.portfolio_engine.write_log(msg, level, self, dingtalk)

    def get_engine_type(self) -> EngineType:
        """获取引擎类型"""
        return self.portfolio_engine.get_engine_type()

    def get_pricetick(self, vt_symbol: str) -> float:
        """获取合约最小价格变动"""
        return self.portfolio_engine.get_pricetick(self, vt_symbol)

    def get_size(self, vt_symbol: str) -> int:
        """获取合约乘数"""
        return self.portfolio_engine.get_size(self, vt_symbol)

    def load_bars(
        self,
        days: int,
        interval: Interval = Interval.MINUTE,
    ) -> None:
        """加载多合约历史K线数据（时间对齐后推送 on_bars）"""
        self.portfolio_engine.load_bars(self, days, interval)

    def put_event(self) -> None:
        """推送策略数据更新事件（触发 UI 刷新）"""
        if self.inited:
            self.portfolio_engine.put_strategy_event(self)

    def send_dingtalk(self, msg: str) -> None:
        """发送钉钉通知"""
        if self.inited:
            self.portfolio_engine.send_dingtalk(msg, self)

    def sync_data(self) -> None:
        """同步策略数据到磁盘"""
        if self.trading:
            self.portfolio_engine.sync_strategy_data(self)
