# -*- coding: utf-8 -*-
"""
观澜量化 - 脚本策略引擎

多脚本并发管理模式：每个脚本由独立的 ScriptRunner 包装，拥有独立的
strategy_active 标志和运行线程。脚本代码 def run(engine) 无需修改，
传入的 engine 实际是 ScriptRunner 代理对象。

配置通过 JSON 文件持久化，支持添加/移除/启停脚本。

Author: 海山观澜
"""

import sys
import importlib
import traceback
from types import ModuleType
from collections.abc import Sequence
from pathlib import Path
from threading import Thread

from vnpy.event import Event
from vnpy.trader.constant import Direction, Offset, OrderType
from vnpy.trader.object import (
    OrderRequest,
    SubscribeRequest,
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    LogData,
    CancelRequest,
)

from guanlan.core.trader.engine import BaseEngine
from guanlan.core.trader.event import EventEngine
from guanlan.core.utils.common import load_json_file, save_json_file


APP_NAME = "ScriptTrader"

EVENT_SCRIPT_LOG = "eScriptLog"
EVENT_SCRIPT_STRATEGY = "eScriptStrategy"

SETTING_FILENAME = "config/script_trader_setting.json"


class ScriptRunner:
    """脚本运行器

    每个脚本实例一个 runner，包含独立的 strategy_active 标志。
    脚本代码中 engine.strategy_active / engine.write_script_log 等
    调用实际委托到此对象。
    """

    def __init__(
        self,
        engine: "ScriptEngine",
        script_name: str,
        script_path: str,
    ) -> None:
        self._engine = engine
        self.script_name: str = script_name
        self.script_path: str = script_path

        self.strategy_active: bool = False
        self._thread: Thread | None = None

    def start(self) -> None:
        """启动脚本线程"""
        if self.strategy_active:
            return
        self.strategy_active = True

        self._thread = Thread(
            target=self._run, daemon=True,
        )
        self._thread.start()

        self.write_script_log("脚本启动")
        self._engine.put_strategy_event(self.script_name)

    def stop(self) -> None:
        """停止脚本"""
        if not self.strategy_active:
            return
        self.strategy_active = False

        if self._thread:
            self._thread.join()
        self._thread = None

        self.write_script_log("脚本停止")
        self._engine.put_strategy_event(self.script_name)

    def _run(self) -> None:
        """加载脚本模块并执行 run(self)"""
        path = Path(self.script_path)
        parent_dir = str(path.parent)
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)

        module_name = path.stem

        try:
            module: ModuleType = importlib.import_module(module_name)
            importlib.reload(module)
            module.run(self)
        except Exception:
            msg = f"触发异常已停止\n{traceback.format_exc()}"
            self.write_script_log(msg)

        self.strategy_active = False
        self._engine.put_strategy_event(self.script_name)

    # ── 代理引擎方法 ──────────────────────────────────────

    def write_script_log(self, msg: str) -> None:
        """写入脚本日志（自动加 [脚本名] 前缀）"""
        self._engine.write_script_log(f"[{self.script_name}] {msg}")

    def send_order(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        direction: Direction,
        offset: Offset,
        order_type: OrderType,
    ) -> str:
        return self._engine.send_order(
            vt_symbol, price, volume, direction, offset, order_type,
        )

    def buy(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        return self._engine.buy(vt_symbol, price, volume, order_type)

    def sell(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        return self._engine.sell(vt_symbol, price, volume, order_type)

    def short(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        return self._engine.short(vt_symbol, price, volume, order_type)

    def cover(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        return self._engine.cover(vt_symbol, price, volume, order_type)

    def cancel_order(self, vt_orderid: str) -> None:
        self._engine.cancel_order(vt_orderid)

    def subscribe(self, vt_symbols: Sequence[str]) -> None:
        self._engine.subscribe(vt_symbols)

    def get_tick(self, vt_symbol: str) -> TickData | None:
        return self._engine.get_tick(vt_symbol)

    def get_ticks(
        self, vt_symbols: Sequence[str],
    ) -> list[TickData | None]:
        return self._engine.get_ticks(vt_symbols)

    def get_order(self, vt_orderid: str) -> OrderData | None:
        return self._engine.get_order(vt_orderid)

    def get_orders(
        self, vt_orderids: Sequence[str],
    ) -> list[OrderData | None]:
        return self._engine.get_orders(vt_orderids)

    def get_trades(self, vt_orderid: str) -> list[TradeData]:
        return self._engine.get_trades(vt_orderid)

    def get_all_active_orders(self) -> list[OrderData]:
        return self._engine.get_all_active_orders()

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        return self._engine.get_contract(vt_symbol)

    def get_all_contracts(self) -> list[ContractData]:
        return self._engine.get_all_contracts()

    def get_account(self, vt_accountid: str) -> AccountData | None:
        return self._engine.get_account(vt_accountid)

    def get_all_accounts(self) -> list[AccountData]:
        return self._engine.get_all_accounts()

    def get_position(self, vt_positionid: str) -> PositionData | None:
        return self._engine.get_position(vt_positionid)

    def get_position_by_symbol(
        self, vt_symbol: str, direction: Direction,
    ) -> PositionData | None:
        return self._engine.get_position_by_symbol(vt_symbol, direction)

    def get_all_positions(self) -> list[PositionData]:
        return self._engine.get_all_positions()


class ScriptEngine(BaseEngine):
    """脚本策略引擎

    多脚本并发管理，每个脚本由 ScriptRunner 独立运行。
    配置通过 JSON 文件持久化。
    """

    def __init__(
        self,
        main_engine,
        event_engine: EventEngine,
    ) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)

        self.scripts: dict[str, ScriptRunner] = {}
        self.script_setting: dict = {}

        self.load_setting()

    # ── 配置持久化 ──────────────────────────────────────────

    def load_setting(self) -> None:
        """从 JSON 加载已保存的脚本配置（创建 runner，不自动启动）"""
        self.script_setting = load_json_file(SETTING_FILENAME)

        for script_name, config in self.script_setting.items():
            script_path = config.get("script_path", "")
            if script_name not in self.scripts:
                runner = ScriptRunner(self, script_name, script_path)
                self.scripts[script_name] = runner

    def save_setting(self) -> None:
        """保存当前脚本配置到 JSON"""
        setting: dict = {}
        for name, runner in self.scripts.items():
            setting[name] = {
                "script_path": runner.script_path,
            }
        self.script_setting = setting
        save_json_file(SETTING_FILENAME, setting)

    # ── 脚本管理 ──────────────────────────────────────────

    def add_script(self, script_name: str, script_path: str) -> bool:
        """添加脚本"""
        if script_name in self.scripts:
            self.write_script_log(f"脚本名 [{script_name}] 已存在")
            return False

        runner = ScriptRunner(self, script_name, script_path)
        self.scripts[script_name] = runner

        self.save_setting()
        self.put_strategy_event(script_name)
        self.write_script_log(f"[{script_name}] 脚本已添加")
        return True

    def remove_script(self, script_name: str) -> bool:
        """移除脚本（运行中的先停止）"""
        runner = self.scripts.get(script_name)
        if not runner:
            return False

        if runner.strategy_active:
            runner.stop()

        self.scripts.pop(script_name, None)
        self.save_setting()
        self.write_script_log(f"[{script_name}] 脚本已移除")
        return True

    def start_script(self, script_name: str) -> None:
        """启动指定脚本"""
        runner = self.scripts.get(script_name)
        if runner:
            runner.start()

    def stop_script(self, script_name: str) -> None:
        """停止指定脚本"""
        runner = self.scripts.get(script_name)
        if runner:
            runner.stop()

    def start_all_scripts(self) -> None:
        """启动所有脚本"""
        for runner in self.scripts.values():
            if not runner.strategy_active:
                runner.start()

    def stop_all_scripts(self) -> None:
        """停止所有脚本"""
        for runner in self.scripts.values():
            if runner.strategy_active:
                runner.stop()

    def close(self) -> None:
        """引擎关闭（应用退出时安全停止所有脚本）"""
        self.stop_all_scripts()

    # ── 事件推送 ──────────────────────────────────────────

    def put_strategy_event(self, script_name: str) -> None:
        """推送脚本状态变更事件"""
        runner = self.scripts.get(script_name)
        if not runner:
            return

        data = {
            "script_name": script_name,
            "script_path": runner.script_path,
            "active": runner.strategy_active,
        }
        event = Event(EVENT_SCRIPT_STRATEGY, data)
        self.event_engine.put(event)

    # ── 交易接口 ──────────────────────────────────────────

    def send_order(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        direction: Direction,
        offset: Offset,
        order_type: OrderType,
    ) -> str:
        """发送委托"""
        contract: ContractData | None = self.get_contract(vt_symbol)
        if not contract:
            return ""

        req = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            offset=offset,
            reference=APP_NAME,
        )

        vt_orderid: str = self.main_engine.send_order(
            req, contract.gateway_name
        )
        return vt_orderid

    def buy(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        """买入开仓"""
        return self.send_order(
            vt_symbol, price, volume,
            Direction.LONG, Offset.OPEN, order_type,
        )

    def sell(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        """卖出平仓"""
        return self.send_order(
            vt_symbol, price, volume,
            Direction.SHORT, Offset.CLOSE, order_type,
        )

    def short(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        """卖出开仓"""
        return self.send_order(
            vt_symbol, price, volume,
            Direction.SHORT, Offset.OPEN, order_type,
        )

    def cover(
        self,
        vt_symbol: str,
        price: float,
        volume: float,
        order_type: OrderType = OrderType.LIMIT,
    ) -> str:
        """买入平仓"""
        return self.send_order(
            vt_symbol, price, volume,
            Direction.LONG, Offset.CLOSE, order_type,
        )

    def cancel_order(self, vt_orderid: str) -> None:
        """撤单"""
        order: OrderData | None = self.get_order(vt_orderid)
        if not order:
            return

        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    # ── 查询接口 ──────────────────────────────────────────

    def subscribe(self, vt_symbols: Sequence[str]) -> None:
        """订阅行情"""
        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        for vt_symbol in vt_symbols:
            app.subscribe(vt_symbol)

    def get_tick(self, vt_symbol: str) -> TickData | None:
        """获取 Tick"""
        return self.main_engine.get_tick(vt_symbol)

    def get_ticks(
        self, vt_symbols: Sequence[str],
    ) -> list[TickData | None]:
        """批量获取 Tick"""
        return [self.main_engine.get_tick(s) for s in vt_symbols]

    def get_order(self, vt_orderid: str) -> OrderData | None:
        """获取委托"""
        return self.main_engine.get_order(vt_orderid)

    def get_orders(
        self, vt_orderids: Sequence[str],
    ) -> list[OrderData | None]:
        """批量获取委托"""
        return [self.main_engine.get_order(oid) for oid in vt_orderids]

    def get_trades(self, vt_orderid: str) -> list[TradeData]:
        """获取指定委托的成交记录"""
        all_trades: list[TradeData] = self.main_engine.get_all_trades()
        return [t for t in all_trades if t.vt_orderid == vt_orderid]

    def get_all_active_orders(self) -> list[OrderData]:
        """获取所有活动委托"""
        return self.main_engine.get_all_active_orders()

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        """获取合约"""
        return self.main_engine.get_contract(vt_symbol)

    def get_all_contracts(self) -> list[ContractData]:
        """获取所有合约"""
        return self.main_engine.get_all_contracts()

    def get_account(self, vt_accountid: str) -> AccountData | None:
        """获取账户"""
        return self.main_engine.get_account(vt_accountid)

    def get_all_accounts(self) -> list[AccountData]:
        """获取所有账户"""
        return self.main_engine.get_all_accounts()

    def get_position(self, vt_positionid: str) -> PositionData | None:
        """获取持仓"""
        return self.main_engine.get_position(vt_positionid)

    def get_position_by_symbol(
        self, vt_symbol: str, direction: Direction,
    ) -> PositionData | None:
        """按合约+方向获取持仓"""
        contract = self.main_engine.get_contract(vt_symbol)
        if not contract:
            return None

        vt_positionid = (
            f"{contract.gateway_name}.{contract.vt_symbol}.{direction.value}"
        )
        return self.main_engine.get_position(vt_positionid)

    def get_all_positions(self) -> list[PositionData]:
        """获取所有持仓"""
        return self.main_engine.get_all_positions()

    # ── 日志 ──────────────────────────────────────────────

    def write_script_log(self, msg: str) -> None:
        """写入脚本日志（推送事件 + BaseEngine 统一日志）"""
        self.write_log(msg)

        log = LogData(msg=msg, gateway_name=APP_NAME)
        event = Event(EVENT_SCRIPT_LOG, log)
        self.event_engine.put(event)
