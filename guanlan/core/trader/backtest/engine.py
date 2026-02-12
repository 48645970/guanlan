# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 回测管理引擎

管理策略类加载、回测执行、参数优化，通过事件通知 UI。
不走 VNPY MainEngine 注册体系，由 UI 窗口按需创建。

Author: 海山观澜
"""

import importlib
import traceback
from copy import copy
from datetime import datetime
from glob import glob
from pathlib import Path
from threading import Thread
from types import ModuleType

from pandas import DataFrame

from vnpy.trader.constant import Interval
from vnpy.trader.optimize import OptimizationSetting

from guanlan.core.trader.event import Event
from guanlan.core.trader.cta.template import (
    CtaTemplate, TargetPosTemplate, BaseParams,
)

from .backtesting import BacktestingEngine

APP_NAME = "CtaBacktester"

EVENT_BACKTESTER_LOG = "eBacktesterLog"
EVENT_BACKTESTER_FINISHED = "eBacktesterFinished"
EVENT_BACKTESTER_OPT_FINISHED = "eBacktesterOptFinished"


class BacktesterEngine:
    """CTA 回测管理引擎"""

    def __init__(self) -> None:
        from guanlan.core.app import AppEngine
        self.event_engine = AppEngine.instance().event_engine

        self.classes: dict[str, type] = {}
        self.backtesting_engine: BacktestingEngine | None = None
        self.thread: Thread | None = None

        self.result_df: DataFrame | None = None
        self.result_statistics: dict | None = None
        self.result_values: list | None = None

    def init_engine(self) -> None:
        """初始化回测引擎"""
        self.write_log("初始化 CTA 回测引擎")

        self.backtesting_engine = BacktestingEngine()
        self.backtesting_engine.output = self.write_log

        self.load_strategy_class()
        self.write_log("策略文件加载完成")

    def write_log(self, msg: str) -> None:
        """发送日志事件"""
        event = Event(EVENT_BACKTESTER_LOG)
        event.data = msg
        self.event_engine.put(event)

    # ── 策略类加载 ──

    def load_strategy_class(self) -> None:
        """从 strategies/cta/ 目录加载策略类"""
        from guanlan.core.constants import PROJECT_ROOT
        path: Path = PROJECT_ROOT / "strategies" / "cta"
        self._load_from_folder(path, "strategies.cta")

    def _load_from_folder(self, path: Path, module_name: str = "") -> None:
        """扫描目录加载策略文件"""
        for suffix in ["py", "pyd", "so"]:
            pathname: str = str(path.joinpath(f"*.{suffix}"))
            for filepath in glob(pathname):
                filepath = Path(filepath)
                if filepath.stem.startswith("_"):
                    continue
                name: str = f"{module_name}.{filepath.stem}"
                self._load_from_file(name, str(filepath))

    def _load_from_file(self, module_name: str, filepath: str) -> None:
        """从文件路径加载策略类（支持热重载）"""
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module: ModuleType = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name in dir(module):
                value = getattr(module, name)
                if (
                    isinstance(value, type)
                    and issubclass(value, CtaTemplate)
                    and value not in {CtaTemplate, TargetPosTemplate}
                ):
                    self.classes[value.__name__] = value
        except Exception:
            msg = f"策略文件 {module_name} 加载失败：\n{traceback.format_exc()}"
            self.write_log(msg)

    def reload_strategy_class(self) -> None:
        """清空并重新加载策略类"""
        self.classes.clear()
        self.load_strategy_class()
        self.write_log("策略文件重载完成")

    def get_strategy_class_names(self) -> list[str]:
        """获取所有策略类名"""
        return list(self.classes.keys())

    def get_strategy_class_display_names(self) -> dict[str, str]:
        """获取策略类显示名（class_name → 中文名或类名）"""
        result: dict[str, str] = {}
        for class_name, cls in self.classes.items():
            doc = (cls.__doc__ or "").strip()
            display = doc.split("\n")[0].strip() if doc else class_name
            result[class_name] = display or class_name
        return result

    def get_default_setting(self, class_name: str) -> BaseParams:
        """获取策略类默认参数"""
        strategy_class: type = self.classes[class_name]
        return copy(strategy_class.params)

    # ── 回测 ──

    def start_backtesting(
        self,
        class_name: str,
        vt_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        slippage: float,
        size: int,
        pricetick: float,
        capital: int,
        setting: dict,
    ) -> bool:
        """启动回测（子线程）"""
        if self.thread:
            self.write_log("已有任务在运行中，请等待完成")
            return False

        self.write_log("-" * 40)
        self.thread = Thread(
            target=self._run_backtesting,
            args=(class_name, vt_symbol, interval, start, end,
                  slippage, size, pricetick, capital, setting),
        )
        self.thread.start()
        return True

    def _run_backtesting(
        self,
        class_name: str,
        vt_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        slippage: float,
        size: int,
        pricetick: float,
        capital: int,
        setting: dict,
    ) -> None:
        """实际执行回测"""
        self.result_df = None
        self.result_statistics = None

        engine = self.backtesting_engine
        engine.clear_data()

        from vnpy_ctastrategy.base import BacktestingMode
        mode = BacktestingMode.TICK if interval == Interval.TICK.value else BacktestingMode.BAR

        engine.set_parameters(
            vt_symbol=vt_symbol,
            interval=interval,
            start=start,
            end=end,
            rate=0,
            slippage=slippage,
            size=size,
            pricetick=pricetick,
            capital=capital,
            mode=mode,
        )

        strategy_class = self.classes[class_name]
        engine.add_strategy(strategy_class, setting)

        engine.load_data()
        if not engine.history_data:
            self.write_log("策略回测失败，历史数据为空")
            self.thread = None
            return

        try:
            engine.run_backtesting()
        except Exception:
            self.write_log(f"策略回测失败：\n{traceback.format_exc()}")
            self.thread = None
            return

        self.result_df = engine.calculate_result()
        self.result_statistics = engine.calculate_statistics(output=False)

        self.thread = None
        event = Event(EVENT_BACKTESTER_FINISHED)
        self.event_engine.put(event)

    # ── 参数优化 ──

    def start_optimization(
        self,
        class_name: str,
        vt_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        slippage: float,
        size: int,
        pricetick: float,
        capital: int,
        optimization_setting: OptimizationSetting,
        use_ga: bool,
        max_workers: int,
    ) -> bool:
        """启动参数优化（子线程）"""
        if self.thread:
            self.write_log("已有任务在运行中，请等待完成")
            return False

        self.write_log("-" * 40)
        self.thread = Thread(
            target=self._run_optimization,
            args=(class_name, vt_symbol, interval, start, end,
                  slippage, size, pricetick, capital,
                  optimization_setting, use_ga, max_workers),
        )
        self.thread.start()
        return True

    def _run_optimization(
        self,
        class_name: str,
        vt_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        slippage: float,
        size: int,
        pricetick: float,
        capital: int,
        optimization_setting: OptimizationSetting,
        use_ga: bool,
        max_workers: int,
    ) -> None:
        """实际执行参数优化"""
        self.result_values = None

        engine = self.backtesting_engine
        engine.clear_data()

        from vnpy_ctastrategy.base import BacktestingMode
        mode = BacktestingMode.TICK if interval == Interval.TICK.value else BacktestingMode.BAR

        engine.set_parameters(
            vt_symbol=vt_symbol,
            interval=interval,
            start=start,
            end=end,
            rate=0,
            slippage=slippage,
            size=size,
            pricetick=pricetick,
            capital=capital,
            mode=mode,
        )

        strategy_class = self.classes[class_name]
        engine.add_strategy(strategy_class, {})

        if max_workers == 0:
            max_workers = None

        if use_ga:
            self.result_values = engine.run_ga_optimization(
                optimization_setting, output=False, max_workers=max_workers,
            )
        else:
            self.result_values = engine.run_bf_optimization(
                optimization_setting, output=False, max_workers=max_workers,
            )

        self.thread = None
        self.write_log("参数优化完成")

        event = Event(EVENT_BACKTESTER_OPT_FINISHED)
        self.event_engine.put(event)

    # ── 结果查询 ──

    def get_result_df(self) -> DataFrame | None:
        return self.result_df

    def get_result_statistics(self) -> dict | None:
        return self.result_statistics

    def get_result_values(self) -> list | None:
        return self.result_values

    def get_all_trades(self) -> list:
        return self.backtesting_engine.get_all_trades()

    def get_all_orders(self) -> list:
        return self.backtesting_engine.get_all_orders()

    def get_all_daily_results(self) -> list:
        return self.backtesting_engine.get_all_daily_results()

    def get_history_data(self) -> list:
        return self.backtesting_engine.history_data
