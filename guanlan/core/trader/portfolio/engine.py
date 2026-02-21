# -*- coding: utf-8 -*-
"""
观澜量化 - 组合策略引擎

从 CTA 引擎模式迁移，适配多合约维度：
- 一个策略注册到多个 vt_symbol
- K线切片回调 on_bars(dict[str, BarData])
- 无停止单（通过 set_target + rebalance 调仓）
- 多合约历史数据时间对齐加载
- hot 主力合约解析

Author: 海山观澜
"""

import importlib
import logging
import traceback
from collections import defaultdict
from copy import copy
from pathlib import Path
from types import ModuleType
from typing import Any
from collections.abc import Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future
from glob import glob

from vnpy.trader.object import (
    OrderRequest,
    SubscribeRequest,
    CancelRequest,
    LogData,
    TickData,
    BarData,
    OrderData,
    TradeData,
    ContractData,
)
from vnpy.trader.event import EVENT_TICK, EVENT_ORDER, EVENT_TRADE
from vnpy.trader.constant import (
    Direction,
    OrderType,
    Interval,
    Exchange,
    Offset,
)
from vnpy.trader.utility import extract_vt_symbol, round_to
from vnpy.trader.database import BaseDatabase, DB_TZ
from guanlan.core.trader.database import get_database

from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.engine import BaseEngine, MainEngine
from guanlan.core.utils.common import load_json_file, save_json_file

from .base import (
    APP_NAME,
    EVENT_PORTFOLIO_LOG,
    EVENT_PORTFOLIO_STRATEGY,
    EngineType,
)
from .template import PortfolioTemplate
from guanlan.core.trader.cta.template import BaseParams


# 配置文件路径
SETTING_FILENAME: str = "config/portfolio_strategy_setting.json"
DATA_FILENAME: str = "config/portfolio_strategy_data.json"


class PortfolioStrategyEngine(BaseEngine):
    """组合策略引擎

    管理组合策略的完整生命周期：加载、初始化、启动、停止、移除。
    一个策略可注册到多个 vt_symbol，通过 symbol_strategy_map 分发行情。

    通过 MainEngine.add_engine() 注册，关闭由 MainEngine.close() 统一管理。
    """

    engine_type: EngineType = EngineType.LIVE

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)

        self.strategy_setting: dict[str, dict] = {}
        self.strategy_data: dict[str, dict] = {}

        self.classes: dict[str, type[PortfolioTemplate]] = {}
        self.strategies: dict[str, PortfolioTemplate] = {}

        self.symbol_strategy_map: defaultdict[str, list[PortfolioTemplate]] = defaultdict(list)
        self.orderid_strategy_map: dict[str, PortfolioTemplate] = {}
        self.strategy_orderid_map: defaultdict[str, set[str]] = defaultdict(set)

        # 策略 → 交易账户映射
        self.strategy_gateway_map: dict[str, str] = {}

        self.init_executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

        self.vt_tradeids: set[str] = set()

        self.database: BaseDatabase = get_database()

    def init_engine(self) -> None:
        """初始化引擎（仅首次调用生效）"""
        if hasattr(self, "_inited") and self._inited:
            return
        self._inited = True

        self.load_strategy_class()
        self.load_strategy_setting()
        self.load_strategy_data()
        self.register_event()
        self.write_log("组合策略引擎初始化成功")

    def close(self) -> None:
        """关闭引擎"""
        self.stop_all_strategies()

    def register_event(self) -> None:
        """注册事件"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

        # 组合策略日志事件注册到日志引擎
        log_engine = self.main_engine.get_engine("log")
        if log_engine:
            self.event_engine.register(EVENT_PORTFOLIO_LOG, log_engine.process_log_event)

    # ── Tick / Order / Trade 事件处理 ──

    def process_tick_event(self, event: Event) -> None:
        """Tick 事件处理：分发到对应策略"""
        tick: TickData = event.data

        strategies: list = self.symbol_strategy_map[tick.vt_symbol]
        if not strategies:
            return

        for strategy in strategies:
            if strategy.inited:
                self.call_strategy_func(strategy, strategy.on_tick, tick)

    def process_order_event(self, event: Event) -> None:
        """委托事件处理：分发到策略的 update_order"""
        order: OrderData = event.data

        strategy: PortfolioTemplate | None = self.orderid_strategy_map.get(
            order.vt_orderid, None
        )
        if not strategy:
            return

        self.call_strategy_func(strategy, strategy.update_order, order)

    def process_trade_event(self, event: Event) -> None:
        """成交事件处理：分发到策略的 update_trade"""
        trade: TradeData = event.data

        # 成交去重
        if trade.vt_tradeid in self.vt_tradeids:
            return
        self.vt_tradeids.add(trade.vt_tradeid)

        strategy: PortfolioTemplate | None = self.orderid_strategy_map.get(
            trade.vt_orderid, None
        )
        if not strategy:
            return

        self.call_strategy_func(strategy, strategy.update_trade, trade)

        self.sync_strategy_data(strategy)
        self.put_strategy_event(strategy)

    # ── 下单 / 撤单 ──

    def send_order(
        self,
        strategy: PortfolioTemplate,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float,
        lock: bool,
        net: bool,
    ) -> list[str]:
        """发送限价委托"""
        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.write_log(f"委托失败，找不到合约：{vt_symbol}", strategy=strategy)
            return []

        gateway_name: str = strategy.gateway_name
        if not gateway_name:
            self.write_log(
                f"委托失败，策略未绑定交易账户：{strategy.strategy_name}",
                strategy=strategy,
            )
            return []

        # 价格和数量取整
        price = round_to(price, contract.pricetick)
        volume = round_to(volume, contract.min_volume)

        original_req: OrderRequest = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            offset=offset,
            type=OrderType.LIMIT,
            price=price,
            volume=volume,
            reference=f"{APP_NAME}_{strategy.strategy_name}",
        )

        # 偏移转换（锁仓/净仓）
        req_list: list[OrderRequest] = self.main_engine.convert_order_request(
            original_req, gateway_name, lock, net
        )

        vt_orderids: list[str] = []

        for req in req_list:
            vt_orderid: str = self.main_engine.send_order(req, gateway_name)

            if not vt_orderid:
                continue

            vt_orderids.append(vt_orderid)

            self.main_engine.update_order_request(req, vt_orderid, gateway_name)

            self.orderid_strategy_map[vt_orderid] = strategy
            self.strategy_orderid_map[strategy.strategy_name].add(vt_orderid)

        return vt_orderids

    def cancel_order(self, strategy: PortfolioTemplate, vt_orderid: str) -> None:
        """撤销委托"""
        order: OrderData | None = self.main_engine.get_order(vt_orderid)
        if not order:
            self.write_log(f"撤单失败，找不到委托{vt_orderid}", strategy=strategy)
            return

        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    # ── 策略管理 ──

    def add_strategy(
        self,
        class_name: str,
        strategy_name: str,
        symbols: list[str],
        gateway_name: str,
        hot: bool,
        setting: dict,
    ) -> None:
        """添加策略

        Args:
            symbols: 品种代码列表（如 ["RB", "HC"]）或完整合约列表
            hot: 是否自动解析为主力合约
        """
        if strategy_name in self.strategies:
            self.write_log(f"创建策略失败，存在重名{strategy_name}")
            return

        strategy_class: type[PortfolioTemplate] | None = self.classes.get(class_name, None)
        if not strategy_class:
            self.write_log(f"创建策略失败，找不到策略类{class_name}")
            return

        # 解析合约代码
        vt_symbols: list[str] = []
        for symbol in symbols:
            if hot:
                vt_symbol = self._resolve_hot_symbol(symbol)
                if not vt_symbol:
                    self.write_log(f"创建策略失败，主力合约解析失败：{symbol}")
                    return
            else:
                vt_symbol = symbol

            if "." not in vt_symbol:
                self.write_log(f"创建策略失败，本地代码缺失交易所后缀：{vt_symbol}")
                return

            __, exchange_str = vt_symbol.split(".")
            if exchange_str not in Exchange.__members__:
                self.write_log(f"创建策略失败，交易所后缀不正确：{vt_symbol}")
                return

            vt_symbols.append(vt_symbol)

        strategy: PortfolioTemplate = strategy_class(
            self, strategy_name, vt_symbols, gateway_name
        )
        strategy.symbols = symbols  # 保存原始输入（用于 UI 显示）
        strategy.update_setting(setting)
        self.strategies[strategy_name] = strategy

        # 绑定交易账户
        self.strategy_gateway_map[strategy_name] = gateway_name

        # 注册品种 → 策略映射（多合约）
        for vt_symbol in vt_symbols:
            strategies: list = self.symbol_strategy_map[vt_symbol]
            strategies.append(strategy)

        # 保存配置
        self.update_strategy_setting(strategy_name, symbols, hot, setting)

        self.put_strategy_event(strategy)

    def _resolve_hot_symbol(self, symbol: str) -> str:
        """解析主力合约代码"""
        try:
            from guanlan.core.setting import contract as contract_setting
            from guanlan.core.utils.symbol_converter import SymbolConverter

            contracts = contract_setting.load_contracts()
            c = contracts.get(symbol.upper())
            if c:
                vt_symbol = c.get("vt_symbol", "")
                exchange_str = c.get("exchange", "")
                if vt_symbol and exchange_str:
                    exchange = Exchange(exchange_str)
                    ex_symbol = SymbolConverter.to_exchange(vt_symbol, exchange)
                    return f"{ex_symbol}.{exchange_str}"
        except Exception:
            pass
        return ""

    def init_strategy(self, strategy_name: str) -> Future:
        """初始化策略（异步）"""
        return self.init_executor.submit(self._init_strategy, strategy_name)

    def _init_strategy(self, strategy_name: str) -> None:
        """初始化策略（在线程池中执行）"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]

        if strategy.inited:
            self._notify(strategy, "已经完成初始化，禁止重复操作")
            return

        # 检查账户连接
        from guanlan.core.app import AppEngine
        app = AppEngine.instance()
        market_gw: str = app.market_gateway
        if not market_gw or not app.is_connected(market_gw):
            self._notify(strategy, "初始化失败，行情账户未连接")
            return

        if not app.is_connected(strategy.gateway_name):
            self._notify(
                strategy, f"初始化失败，交易账户未连接：{strategy.gateway_name}"
            )
            return

        self.write_log("开始执行初始化", strategy=strategy)

        # 调用策略 on_init
        self.call_strategy_func(strategy, strategy.on_init)

        # 恢复策略状态
        data: dict | None = self.strategy_data.get(strategy_name, None)
        if data:
            strategy.update_data(data)

        # 订阅行情（多合约）
        subscribe_failed: list[str] = []
        for vt_symbol in strategy.vt_symbols:
            if not app.subscribe(vt_symbol):
                subscribe_failed.append(vt_symbol)

        if subscribe_failed:
            failed_str = ", ".join(subscribe_failed)
            self._notify(
                strategy, f"初始化失败，找不到合约：{failed_str}"
            )
            return

        # 首次初始化时记录各合约到 _hot_map
        for vt_symbol in strategy.vt_symbols:
            symbol = vt_symbol.split(".")[0] if "." in vt_symbol else vt_symbol
            if symbol not in strategy._hot_map:
                strategy._hot_map[symbol] = vt_symbol

        strategy.inited = True
        self.put_strategy_event(strategy)
        self.write_log("初始化完成", strategy=strategy)

    def start_strategy(self, strategy_name: str) -> None:
        """启动策略"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        if not strategy.inited:
            self._notify(strategy, "启动失败，请先初始化")
            return

        if strategy.trading:
            self._notify(strategy, "已经启动，请勿重复操作")
            return

        self.call_strategy_func(strategy, strategy.on_start)
        strategy.trading = True

        # 进入交易状态回调
        self.call_strategy_func(strategy, strategy.on_trading)

        self.put_strategy_event(strategy)

    def stop_strategy(self, strategy_name: str) -> None:
        """停止策略"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        if not strategy.trading:
            return

        self.call_strategy_func(strategy, strategy.on_stop)

        strategy.trading = False

        # 全撤活动委托
        strategy.cancel_all()
        self.sync_strategy_data(strategy)
        self.put_strategy_event(strategy)

    def reset_strategy(self, strategy_name: str) -> None:
        """重置策略状态"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        if strategy.trading:
            self.write_log("请先停止后再重置", strategy=strategy)
            return

        self.call_strategy_func(strategy, strategy.on_reset)
        self.put_strategy_event(strategy)

    def edit_strategy(self, strategy_name: str, setting: dict) -> None:
        """编辑策略参数"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        strategy.update_setting(setting)

        # 从现有 setting 中取 symbols 和 hot
        old_config = self.strategy_setting.get(strategy_name, {})
        symbols = old_config.get("symbols", strategy.vt_symbols)
        hot = old_config.get("hot", False)

        self.update_strategy_setting(strategy_name, symbols, hot, setting)
        self.put_strategy_event(strategy)

    def remove_strategy(self, strategy_name: str) -> bool:
        """移除策略"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        if strategy.trading:
            self.write_log("移除失败，请先停止", strategy=strategy)
            return False

        # 移除配置
        self.remove_strategy_setting(strategy_name)

        # 移除品种 → 策略映射（多合约）
        for vt_symbol in strategy.vt_symbols:
            strategies: list = self.symbol_strategy_map[vt_symbol]
            if strategy in strategies:
                strategies.remove(strategy)

        # 移除委托映射
        if strategy_name in self.strategy_orderid_map:
            vt_orderids: set = self.strategy_orderid_map.pop(strategy_name)
            for vt_orderid in vt_orderids:
                if vt_orderid in self.orderid_strategy_map:
                    self.orderid_strategy_map.pop(vt_orderid)

        # 移除交易账户映射
        self.strategy_gateway_map.pop(strategy_name, None)

        self.strategies.pop(strategy_name)

        # 清理盈亏统计中该策略的记录
        reference = f"{APP_NAME}_{strategy_name}"
        portfolio_engine = self.main_engine.engines.get("portfolio")
        if portfolio_engine:
            keys = [k for k in portfolio_engine.contract_results if k[0] == reference]
            for k in keys:
                portfolio_engine.contract_results.pop(k)
            for k in list(portfolio_engine.portfolio_results):
                if k[0] == reference:
                    has_children = any(
                        ck[0] == k[0] and ck[2] == k[1]
                        for ck in portfolio_engine.contract_results
                    )
                    if not has_children:
                        portfolio_engine.portfolio_results.pop(k)
            portfolio_engine._save_data()

        self.write_log("移除成功", strategy=strategy)
        return True

    # ── 策略类加载 ──

    def load_strategy_class(self) -> None:
        """从 strategies/portfolio/ 目录加载策略类"""
        from guanlan.core.constants import PROJECT_ROOT
        path: Path = PROJECT_ROOT / "strategies" / "portfolio"
        self.load_strategy_class_from_folder(path, "strategies.portfolio")

    def load_strategy_class_from_folder(
        self, path: Path, module_name: str = ""
    ) -> None:
        """从指定目录加载策略类"""
        for suffix in ["py", "pyd", "so"]:
            pathname: str = str(path.joinpath(f"*.{suffix}"))
            for filepath in glob(pathname):
                filepath = Path(filepath)
                if filepath.stem.startswith("_"):
                    continue
                name: str = f"{module_name}.{filepath.stem}"
                self.load_strategy_class_from_file(name, str(filepath))

    def load_strategy_class_from_file(self, module_name: str, filepath: str) -> None:
        """从文件绝对路径加载策略类"""
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module: ModuleType = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name in dir(module):
                value = getattr(module, name)
                if (
                    isinstance(value, type)
                    and issubclass(value, PortfolioTemplate)
                    and value is not PortfolioTemplate
                ):
                    self.classes[value.__name__] = value
        except Exception:
            msg: str = f"策略文件{module_name}加载失败，触发异常：\n{traceback.format_exc()}"
            self.write_log(msg)

    # ── 数据持久化 ──

    def load_strategy_data(self) -> None:
        """加载策略状态数据"""
        self.strategy_data = load_json_file(DATA_FILENAME)

    def sync_strategy_data(self, strategy: PortfolioTemplate) -> None:
        """同步策略状态到磁盘"""
        data: dict = strategy.get_state().model_dump()
        # 额外保存 pos_data / target_data / hot_map
        data["pos_data"] = dict(strategy.pos_data)
        data["target_data"] = dict(strategy.target_data)
        data["hot_map"] = dict(strategy._hot_map)

        self.strategy_data[strategy.strategy_name] = data
        save_json_file(DATA_FILENAME, self.strategy_data)

    def load_strategy_setting(self) -> None:
        """加载策略配置"""
        self.strategy_setting = load_json_file(SETTING_FILENAME)

        for strategy_name, strategy_config in self.strategy_setting.items():
            self.add_strategy(
                strategy_config["class_name"],
                strategy_name,
                strategy_config.get("symbols", strategy_config.get("vt_symbols", [])),
                strategy_config.get("gateway_name", ""),
                strategy_config.get("hot", False),
                strategy_config.get("setting", {}),
            )

    def update_strategy_setting(
        self, strategy_name: str, symbols: list[str], hot: bool, setting: dict
    ) -> None:
        """更新策略配置"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]

        self.strategy_setting[strategy_name] = {
            "class_name": strategy.__class__.__name__,
            "symbols": symbols,
            "hot": hot,
            "vt_symbols": strategy.vt_symbols,
            "gateway_name": strategy.gateway_name,
            "setting": setting,
        }
        save_json_file(SETTING_FILENAME, self.strategy_setting)

    def remove_strategy_setting(self, strategy_name: str) -> None:
        """移除策略配置"""
        if strategy_name not in self.strategy_setting:
            return

        self.strategy_setting.pop(strategy_name)
        save_json_file(SETTING_FILENAME, self.strategy_setting)

        self.strategy_data.pop(strategy_name, None)
        save_json_file(DATA_FILENAME, self.strategy_data)

    # ── 查询接口 ──

    def get_engine_type(self) -> EngineType:
        """获取引擎类型"""
        return self.engine_type

    def get_pricetick(self, strategy: PortfolioTemplate, vt_symbol: str) -> float | None:
        """获取合约最小变动价位"""
        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if contract:
            return contract.pricetick
        else:
            return None

    def get_size(self, strategy: PortfolioTemplate, vt_symbol: str) -> int | None:
        """获取合约乘数"""
        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if contract:
            return contract.size       # type: ignore
        else:
            return None

    def get_all_strategy_class_names(self) -> list[str]:
        """获取所有已加载的策略类名"""
        return list(self.classes.keys())

    def get_strategy_class_display_names(self) -> dict[str, str]:
        """获取策略类显示名（class_name → 中文名 或类名）"""
        result: dict[str, str] = {}
        for class_name, cls in self.classes.items():
            doc = (cls.__doc__ or "").strip()
            display = doc.split("\n")[0].strip() if doc else class_name
            result[class_name] = display or class_name
        return result

    def get_strategy_class_parameters(self, class_name: str) -> BaseParams:
        """获取策略类默认参数"""
        strategy_class: type[PortfolioTemplate] = self.classes[class_name]
        return copy(strategy_class.params)

    def get_strategy_parameters(self, strategy_name: str) -> BaseParams:
        """获取策略实例参数"""
        strategy: PortfolioTemplate = self.strategies[strategy_name]
        return strategy.get_params()

    # ── 历史数据（多合约时间对齐） ──

    def load_bars(
        self,
        strategy: PortfolioTemplate,
        days: int,
        interval: Interval,
    ) -> None:
        """加载多合约历史K线（时间对齐后推送 on_bars）"""
        # 逐合约加载K线
        bars_by_symbol: dict[str, list[BarData]] = {}
        all_dts: set[datetime] = set()

        for vt_symbol in strategy.vt_symbols:
            symbol, exchange = extract_vt_symbol(vt_symbol)
            end: datetime = datetime.now(DB_TZ)
            start: datetime = end - timedelta(days)

            bars: list[BarData] = self.database.load_bar_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start=start,
                end=end,
            )

            bars_by_symbol[vt_symbol] = bars

            for bar in bars:
                all_dts.add(bar.datetime)

        # 按时间排序
        sorted_dts: list[datetime] = sorted(all_dts)

        if not sorted_dts:
            return

        # 按时间对齐推送
        last_bars: dict[str, BarData] = {}

        for dt in sorted_dts:
            bars_dict: dict[str, BarData] = {}

            for vt_symbol in strategy.vt_symbols:
                bar_list: list[BarData] = bars_by_symbol[vt_symbol]

                # 查找当前时间点的K线
                bar: BarData | None = None
                while bar_list and bar_list[0].datetime == dt:
                    bar = bar_list.pop(0)

                if bar:
                    last_bars[vt_symbol] = bar
                    bars_dict[vt_symbol] = bar
                elif vt_symbol in last_bars:
                    # 缺失数据用前一根收盘价填充
                    prev_bar: BarData = last_bars[vt_symbol]
                    fill_bar = BarData(
                        symbol=prev_bar.symbol,
                        exchange=prev_bar.exchange,
                        datetime=dt,
                        interval=interval,
                        volume=0,
                        turnover=0,
                        open_interest=prev_bar.open_interest,
                        open_price=prev_bar.close_price,
                        high_price=prev_bar.close_price,
                        low_price=prev_bar.close_price,
                        close_price=prev_bar.close_price,
                        gateway_name=prev_bar.gateway_name,
                    )
                    bars_dict[vt_symbol] = fill_bar
                    last_bars[vt_symbol] = fill_bar

            if bars_dict:
                self.call_strategy_func(strategy, strategy.on_bars, bars_dict)

    # ── 批量操作 ──

    def init_all_strategies(self) -> dict[str, Future]:
        """初始化所有策略"""
        futures: dict[str, Future] = {}
        for strategy_name in self.strategies.keys():
            futures[strategy_name] = self.init_strategy(strategy_name)
        return futures

    def start_all_strategies(self) -> None:
        """启动所有策略"""
        for strategy_name in self.strategies.keys():
            self.start_strategy(strategy_name)

    def stop_all_strategies(self) -> None:
        """停止所有策略"""
        for strategy_name in self.strategies.keys():
            self.stop_strategy(strategy_name)

    # ── 事件推送 ──

    def put_strategy_event(self, strategy: PortfolioTemplate) -> None:
        """推送策略数据事件（触发 UI 刷新）"""
        data: dict = strategy.get_data()
        event: Event = Event(EVENT_PORTFOLIO_STRATEGY, data)
        self.event_engine.put(event)

    # ── 日志和通知 ──

    def write_log(
        self,
        msg: str,
        level: int = logging.INFO,
        strategy: PortfolioTemplate | None = None,
        dingtalk: bool = False,
    ) -> None:
        """写组合策略日志"""
        if strategy:
            msg = f"[{strategy.strategy_name}]  {msg}"

        log: LogData = LogData(msg=msg, gateway_name=APP_NAME)
        event: Event = Event(type=EVENT_PORTFOLIO_LOG, data=log)
        self.event_engine.put(event)

        if dingtalk:
            self.send_dingtalk(msg)

    def send_dingtalk(self, msg: str, strategy: PortfolioTemplate | None = None) -> None:
        """发送钉钉通知"""
        if strategy:
            subject: str = f"{strategy.strategy_name}"
        else:
            subject = "组合策略引擎"

        self.main_engine.send_dingtalk(subject, msg)

    # ── 内部工具 ──

    def call_strategy_func(
        self, strategy: PortfolioTemplate, func: Callable, params: Any = None
    ) -> None:
        """安全调用策略函数（异常时停止策略）"""
        try:
            if params is not None:
                func(params)
            else:
                func()
        except Exception:
            strategy.trading = False
            strategy.inited = False

            msg: str = f"触发异常已停止\n{traceback.format_exc()}"
            self._notify(strategy, msg)

    def _notify(self, strategy: PortfolioTemplate, msg: str, level: str = "error") -> None:
        """策略通知（日志 + 弹窗 + 音效）"""
        self.write_log(msg, strategy=strategy)

        from guanlan.core.events import signal_bus
        from guanlan.core.services.sound import play as play_sound

        signal_bus.show_message.emit(strategy.strategy_name, msg, level)
        if level == "error":
            play_sound("error")
