# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 策略模板

BaseParams: 策略参数基类（Pydantic 模型，类型校验 + 序列化）
BaseState: 策略状态基类（Pydantic 模型，运行时数据持久化）
BaseVars: 策略临时变量基类（仅 UI 展示，不持久化）
CtaTemplate: 基础策略模板
CtaSignal: 信号组件模板
TargetPosTemplate: 目标仓位模板（自动拆单）

Author: 海山观澜
"""

import logging
from abc import ABC, abstractmethod
from typing import Any
from collections.abc import Callable

from pydantic import BaseModel, Field

from vnpy.trader.constant import Interval, Direction, Offset
from vnpy.trader.object import BarData, TickData, OrderData, TradeData

from .base import StopOrder, EngineType


class BaseParams(BaseModel, validate_assignment=True):
    """策略参数基类

    继承此类定义策略可调参数，支持类型校验和约束。

    示例::

        class MyParams(BaseParams):
            fast_window: int = Field(default=10, title="快线周期", ge=1, le=200)
            slow_window: int = Field(default=20, title="慢线周期", ge=1, le=500)
    """

    auto_trade: bool = Field(default=True, title="自动发单")

    def __init__(self, /, setting: dict | None = None, **data: Any) -> None:
        super().__init__(**data)

        if setting is None:
            return

        for name in self.model_fields:
            if name in setting:
                setattr(self, name, setting[name])


class BaseState(BaseModel, validate_assignment=True):
    """策略状态基类

    继承此类定义策略运行时状态（持久化到磁盘）。

    示例::

        class MyState(BaseState):
            fast_ma0: float = Field(default=0.0, title="快线当前值")
    """

    hot: str = Field(default="", title="当前合约")
    pos: int = Field(default=0, title="持仓")


class BaseVars(BaseModel, validate_assignment=True):
    """策略临时变量（仅 UI 展示，不持久化）

    用于向 UI 输出信号方向、强度、交易提示等实时信息。
    CTA / 组合策略可选用，辅助交易必用。
    """

    direction: int = Field(default=0, title="方向")
    strength: int = Field(default=0, title="信号强度", ge=0, le=100)
    tip: str = Field(default="", title="交易提示")
    suggest_price: float = Field(default=0.0, title="建议价格")
    suggest_volume: int = Field(default=0, title="建议数量")
    allow_open_long: bool = Field(default=False, title="允许开多")
    allow_open_short: bool = Field(default=False, title="允许开空")


class CtaTemplate(ABC):
    """CTA 策略模板"""

    author: str = ""
    params = BaseParams()
    state = BaseState()
    vars = BaseVars()

    log_level = logging.DEBUG

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,
        gateway_name: str,
    ) -> None:
        self.cta_engine: Any = cta_engine
        self.strategy_name: str = strategy_name
        self.vt_symbol: str = vt_symbol
        self.gateway_name: str = gateway_name

        self.inited: bool = False
        self.trading: bool = False
        self.advisor: bool = False

        # 类变量 → 实例变量（避免多实例共享同一个 Pydantic 对象）
        self.params = self.__class__.params.model_copy(deep=True)
        self.state = self.__class__.state.model_copy(deep=True)
        self.vars = self.__class__.vars.model_copy(deep=True)

        # 换月保护标志（不持久化，重启后由策略重新检测）
        self._rolling: bool = False

        # 信号回调（辅助模式下由窗口绑定）
        self._on_signal: Callable | None = None

    def update_setting(self, setting: dict) -> None:
        """更新策略参数"""
        for name in self.params.model_fields:
            if name in setting:
                setattr(self.params, name, setting[name])

    def update_data(self, data: dict) -> None:
        """更新策略状态（从磁盘恢复）"""
        for name in self.state.model_fields:
            if name in data:
                setattr(self.state, name, data[name])

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
        strategy_data: dict = {
            "strategy_name": self.strategy_name,
            "vt_symbol": self.vt_symbol,
            "inited": self.inited,
            "trading": self.trading,
            "class_name": self.__class__.__name__,
            "author": self.author,
            "gateway_name": self.gateway_name,
            "params": self.get_params(),
            "state": self.get_state(),
            "vars": self.get_vars(),
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

    def on_bar(self, bar: BarData) -> None:
        """K 线数据更新回调"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交数据更新回调"""
        pass

    def on_order(self, order: OrderData) -> None:
        """委托数据更新回调"""
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新回调"""
        pass

    # ── 交易接口 ──

    def buy(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list:
        """买入开多"""
        return self.send_order(
            Direction.LONG, Offset.OPEN, price, volume, stop, lock, net
        )

    def sell(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list:
        """卖出平多"""
        return self.send_order(
            Direction.SHORT, Offset.CLOSE, price, volume, stop, lock, net
        )

    def short(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list:
        """卖出开空"""
        return self.send_order(
            Direction.SHORT, Offset.OPEN, price, volume, stop, lock, net
        )

    def cover(
        self,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list:
        """买入平空"""
        return self.send_order(
            Direction.LONG, Offset.CLOSE, price, volume, stop, lock, net
        )

    def send_order(
        self,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        stop: bool = False,
        lock: bool = False,
        net: bool = False,
    ) -> list:
        """发送委托

        辅助模式（advisor=True）或关闭自动发单（auto_trade=False）时不下单。
        换月期间拦截所有开仓单，只允许平仓。
        """
        if self.advisor or not self.params.auto_trade:
            return []
        if self._rolling and offset == Offset.OPEN:
            self.write_log(
                f"换月中，拦截开仓单: {direction.value} {volume}手",
                level=logging.WARNING,
            )
            return []
        if self.trading:
            vt_orderids: list = self.cta_engine.send_order(
                self, direction, offset, price, volume, stop, lock, net
            )
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str) -> None:
        """撤销委托"""
        if self.trading:
            self.cta_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """撤销所有委托"""
        if self.trading:
            self.cta_engine.cancel_all(self)

    # ── 换月保护 ──

    @property
    def rolling(self) -> bool:
        """是否正在换月"""
        return self._rolling

    def need_rollover(self) -> bool:
        """检查是否需要换月（有持仓且合约已变更）"""
        return bool(
            self.state.hot
            and self.state.hot != self.vt_symbol
            and self.state.pos != 0
        )

    def begin_rollover(self) -> None:
        """进入换月状态（禁止开仓，只允许平仓）"""
        self._rolling = True
        self.write_log(f"开始换月: {self.state.hot} → {self.vt_symbol}")

    def complete_rollover(self) -> None:
        """完成换月（更新合约记录，恢复正常交易）"""
        old = self.state.hot
        self.state.hot = self.vt_symbol
        self._rolling = False
        self.sync_data()
        self.write_log(f"换月完成: {old} → {self.vt_symbol}")

    # ── 工具方法 ──

    def write_log(self, msg: str, level: int = logging.INFO, dingtalk: bool = False) -> None:
        """写日志（辅助模式下不广播到 CTA 引擎）"""
        if self.advisor:
            return
        self.cta_engine.write_log(msg, level, self, dingtalk)

    def get_engine_type(self) -> EngineType:
        """获取引擎类型（实盘/回测）"""
        return self.cta_engine.get_engine_type()

    def get_pricetick(self) -> float:
        """获取合约最小价格变动"""
        return self.cta_engine.get_pricetick(self)

    def get_size(self) -> int:
        """获取合约乘数"""
        return self.cta_engine.get_size(self)

    def get_account(self):
        """获取账户信息"""
        return self.cta_engine.get_account(self)

    def load_bar(
        self,
        days: int,
        interval: Interval = Interval.MINUTE,
        callback: Callable | None = None,
        use_database: bool = False,
    ) -> None:
        """加载历史 K 线数据"""
        if not callback:
            callback = self.on_bar

        bars: list[BarData] = self.cta_engine.load_bar(
            self.vt_symbol, days, interval, callback, use_database
        )

        for bar in bars:
            callback(bar)

    def load_tick(self, days: int) -> None:
        """加载历史 Tick 数据"""
        ticks: list[TickData] = self.cta_engine.load_tick(
            self.vt_symbol, days, self.on_tick
        )

        for tick in ticks:
            self.on_tick(tick)

    def set_signal_callback(self, callback: Callable) -> None:
        """注册信号回调（辅助模式下由窗口绑定）"""
        self._on_signal = callback

    def put_signal(self) -> None:
        """推送信号给 UI（辅助模式下通过回调通知窗口）"""
        if self._on_signal:
            self._on_signal(self.vars)

    def put_event(self) -> None:
        """推送策略数据更新事件（触发 UI 刷新）

        辅助模式下不推送到 CTA 引擎，避免产生多余卡片。
        """
        if self.inited and not self.advisor:
            self.cta_engine.put_strategy_event(self)

    def send_dingtalk(self, msg: str) -> None:
        """发送钉钉通知（辅助模式下不发送）"""
        if self.inited and not self.advisor:
            self.cta_engine.send_dingtalk(msg, self)

    def sync_data(self) -> None:
        """同步策略数据到磁盘（辅助模式下不持久化）"""
        if self.trading and not self.advisor:
            self.cta_engine.sync_strategy_data(self)


class CtaSignal(ABC):
    """CTA 信号组件"""

    def __init__(self) -> None:
        self.signal_pos = 0

    def on_tick(self, tick: TickData) -> None:
        """Tick 数据更新回调"""
        pass

    @abstractmethod
    def on_bar(self, bar: BarData) -> None:
        """K 线数据更新回调"""
        pass

    def set_signal_pos(self, pos: int) -> None:
        """设置信号仓位"""
        self.signal_pos = pos

    def get_signal_pos(self) -> Any:
        """获取信号仓位"""
        return self.signal_pos


class TargetPosTemplate(CtaTemplate):
    """目标仓位策略模板

    自动计算目标仓位与当前仓位的差值，拆分为买/卖/开空/平空单。
    """

    tick_add = 1

    last_tick: TickData | None = None
    last_bar: BarData | None = None
    target_pos = 0

    def __init__(
        self,
        cta_engine: Any,
        strategy_name: str,
        vt_symbol: str,
        gateway_name: str,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, gateway_name)

        self.active_orderids: list[str] = []
        self.cancel_orderids: list[str] = []

    def on_tick(self, tick: TickData) -> None:
        """Tick 数据更新回调"""
        self.last_tick = tick

    def on_bar(self, bar: BarData) -> None:
        """K 线数据更新回调"""
        self.last_bar = bar

    def on_order(self, order: OrderData) -> None:
        """委托数据更新回调"""
        vt_orderid: str = order.vt_orderid

        if not order.is_active():
            if vt_orderid in self.active_orderids:
                self.active_orderids.remove(vt_orderid)

            if vt_orderid in self.cancel_orderids:
                self.cancel_orderids.remove(vt_orderid)

    def check_order_finished(self) -> bool:
        """检查是否所有委托已完成"""
        return not self.active_orderids

    def set_target_pos(self, target_pos: int) -> None:
        """设置目标仓位"""
        self.target_pos = target_pos
        self.trade()

    def trade(self) -> None:
        """执行交易"""
        if not self.check_order_finished():
            self.cancel_old_order()
        else:
            self.send_new_order()

    def cancel_old_order(self) -> None:
        """撤销旧委托"""
        for vt_orderid in self.active_orderids:
            if vt_orderid not in self.cancel_orderids:
                self.cancel_order(vt_orderid)
                self.cancel_orderids.append(vt_orderid)

    def send_new_order(self) -> None:
        """发送新委托（根据目标仓位差值自动拆单）"""
        pos_change = self.target_pos - self.state.pos
        if not pos_change:
            return

        long_price: float = 0
        short_price: float = 0

        if self.last_tick:
            if pos_change > 0:
                long_price = self.last_tick.ask_price_1 + self.tick_add
                if self.last_tick.limit_up:
                    long_price = min(long_price, self.last_tick.limit_up)
            else:
                short_price = self.last_tick.bid_price_1 - self.tick_add
                if self.last_tick.limit_down:
                    short_price = max(short_price, self.last_tick.limit_down)

        elif self.last_bar:
            if pos_change > 0:
                long_price = self.last_bar.close_price + self.tick_add
            else:
                short_price = self.last_bar.close_price - self.tick_add

        if self.active_orderids:
            return

        if pos_change > 0:
            if self.state.pos < 0:
                if pos_change < abs(self.state.pos):
                    vt_orderids = self.cover(long_price, pos_change)
                else:
                    vt_orderids = self.cover(long_price, abs(self.state.pos))
            else:
                vt_orderids = self.buy(long_price, abs(pos_change))
        else:
            if self.state.pos > 0:
                if abs(pos_change) < self.state.pos:
                    vt_orderids = self.sell(short_price, abs(pos_change))
                else:
                    vt_orderids = self.sell(short_price, abs(self.state.pos))
            else:
                vt_orderids = self.short(short_price, abs(pos_change))
        self.active_orderids.extend(vt_orderids)
