# -*- coding: utf-8 -*-
"""
观澜量化 - 行情记录引擎

基于 vnpy DataRecorder 重构，使用全局 AppEngine。
负责实时 Tick / K 线数据的录制和异步写入数据库。

Author: 海山观澜
"""

import traceback
from collections import defaultdict
from collections.abc import Callable
from copy import copy
from datetime import datetime, timedelta
from queue import Queue, Empty
from threading import Thread

from vnpy.trader.constant import Exchange
from guanlan.core.constants import CHINA_TZ
from vnpy.trader.event import EVENT_TICK, EVENT_CONTRACT, EVENT_TIMER
from vnpy.trader.object import (
    TickData, BarData, ContractData, SubscribeRequest
)
from vnpy.trader.utility import BarGenerator

from guanlan.core.trader.event import Event, EventEngine
from guanlan.core.trader.engine import MainEngine
from guanlan.core.app import AppEngine
from guanlan.core.trader.gateway import EVENT_CONTRACT_INITED
from guanlan.core.trader.database import get_database
from guanlan.core.utils.common import load_json_file, save_json_file
from guanlan.core.utils.symbol_converter import SymbolConverter

# 配置文件
SETTING_FILENAME: str = "config/recorder.json"


class DataRecorderEngine:
    """行情记录引擎

    从全局 AppEngine 获取 MainEngine 和 EventEngine，
    注册 Tick/Timer/Contract 事件，异步批量写入数据库。
    """

    def __init__(
        self,
        on_log: Callable[[str], None] | None = None,
        on_update: Callable[[list[str], list[str]], None] | None = None,
        on_bar: Callable | None = None,
    ) -> None:
        app = AppEngine.instance()
        self.main_engine: MainEngine = app.main_engine
        self.event_engine: EventEngine = app.event_engine
        self.database = get_database()

        # UI 回调
        self._on_log = on_log
        self._on_update = on_update
        self._on_bar = on_bar

        # 当前使用的网关名（由 UI 设置）
        self.gateway_name: str = ""

        # 录制配置
        self.tick_recordings: dict[str, dict] = {}
        self.bar_recordings: dict[str, dict] = {}
        self.bar_generators: dict[str, BarGenerator] = {}

        # 异步写入
        self.queue: Queue = Queue()
        self.thread: Thread = Thread(target=self._run, daemon=True)
        self.active: bool = False

        # 批量缓存
        self.timer_count: int = 0
        self.timer_interval: int = 10
        self.ticks: dict[str, list[TickData]] = defaultdict(list)
        self.bars: dict[str, list[BarData]] = defaultdict(list)

        # Tick 时间过滤
        self.filter_dt: datetime = datetime.now(CHINA_TZ)
        self.filter_window: int = 60
        self.filter_delta: timedelta = timedelta(seconds=self.filter_window)

        # Tick 计数（用于日志统计）
        self._tick_count: int = 0
        self._tick_filtered_count: int = 0

        # 加载配置（不自动启动，等 UI 调用 start_recording）
        self.load_setting()
        self.put_event()

    # ── 配置管理 ─────────────────────────────────────────

    def load_setting(self) -> None:
        """加载录制配置"""
        setting = load_json_file(SETTING_FILENAME)
        self.tick_recordings = setting.get("tick", {})
        self.bar_recordings = setting.get("bar", {})
        self.filter_window = setting.get("filter_window", 60)
        self.filter_delta = timedelta(seconds=self.filter_window)

    def save_setting(self) -> None:
        """保存录制配置"""
        setting = {
            "tick": self.tick_recordings,
            "bar": self.bar_recordings,
        }
        save_json_file(SETTING_FILENAME, setting)

    # ── 录制管理 ─────────────────────────────────────────

    def add_bar_recording(self, vt_symbol: str) -> None:
        """添加 K 线录制"""
        if vt_symbol in self.bar_recordings:
            self._write_log(f"已在K线记录列表中：{vt_symbol}")
            return

        contract = self._get_engine_contract(vt_symbol)
        if not contract:
            self._write_log(f"找不到合约：{vt_symbol}")
            return

        self.bar_recordings[vt_symbol] = {
            "symbol": contract.symbol,
            "exchange": contract.exchange.value,
            "gateway_name": contract.gateway_name,
        }

        self._subscribe(contract)
        self.save_setting()
        self.put_event()
        self._write_log(f"添加K线记录成功：{vt_symbol}")

    def remove_bar_recording(self, vt_symbol: str) -> None:
        """移除 K 线录制"""
        if vt_symbol not in self.bar_recordings:
            self._write_log(f"不在K线记录列表中：{vt_symbol}")
            return

        self.bar_recordings.pop(vt_symbol)
        self.save_setting()
        self.put_event()
        self._write_log(f"移除K线记录成功：{vt_symbol}")

    def add_tick_recording(self, vt_symbol: str) -> None:
        """添加 Tick 录制"""
        if vt_symbol in self.tick_recordings:
            self._write_log(f"已在Tick记录列表中：{vt_symbol}")
            return

        contract = self._get_engine_contract(vt_symbol)
        if not contract:
            self._write_log(f"找不到合约：{vt_symbol}")
            return

        self.tick_recordings[vt_symbol] = {
            "symbol": contract.symbol,
            "exchange": contract.exchange.value,
            "gateway_name": contract.gateway_name,
        }

        self._subscribe(contract)
        self.save_setting()
        self.put_event()
        self._write_log(f"添加Tick记录成功：{vt_symbol}")

    def remove_tick_recording(self, vt_symbol: str) -> None:
        """移除 Tick 录制"""
        if vt_symbol not in self.tick_recordings:
            self._write_log(f"不在Tick记录列表中：{vt_symbol}")
            return

        self.tick_recordings.pop(vt_symbol)
        self.save_setting()
        self.put_event()
        self._write_log(f"移除Tick记录成功：{vt_symbol}")

    def add_favorites_to_recording(self) -> None:
        """将收藏夹合约自动加入K线录制

        从本地合约配置读取收藏品种，构造 vt_symbol 并加入录制列表。
        同时更新已有记录的网关名为当前网关。
        """
        from guanlan.core.setting.contract import load_favorites, load_contracts

        favorites = load_favorites()
        contracts = load_contracts()

        if not favorites:
            return

        added: list[str] = []
        for symbol in favorites:
            if symbol not in contracts:
                continue

            contract_info = contracts[symbol]
            vt_symbol_base = contract_info.get("vt_symbol", "")
            exchange = contract_info.get("exchange", "")

            if not vt_symbol_base or not exchange:
                continue

            # 转为交易所格式，与引擎 vt_symbol 一致
            exchange_symbol = SymbolConverter.to_exchange(
                vt_symbol_base, Exchange(exchange)
            )
            vt_symbol = f"{exchange_symbol}.{exchange}"

            if vt_symbol in self.bar_recordings:
                # 更新已有记录的网关名为当前网关
                if self.gateway_name:
                    self.bar_recordings[vt_symbol]["gateway_name"] = self.gateway_name
                continue

            self.bar_recordings[vt_symbol] = {
                "symbol": vt_symbol_base,
                "exchange": exchange,
                "gateway_name": self.gateway_name,
            }
            added.append(vt_symbol)

        if added:
            self._write_log(
                f"收藏夹合约加入K线记录（{len(added)} 个）："
                + "、".join(added)
            )

        self.save_setting()
        self.put_event()

    def remove_expired(self) -> list[str]:
        """移除引擎中不存在的失效合约

        Returns
        -------
        list[str]
            被移除的 vt_symbol 列表
        """
        removed: list[str] = []

        for vt_symbol in list(self.bar_recordings.keys()):
            if not self._get_engine_contract(vt_symbol):
                self.bar_recordings.pop(vt_symbol)
                removed.append(vt_symbol)

        for vt_symbol in list(self.tick_recordings.keys()):
            if not self._get_engine_contract(vt_symbol):
                if vt_symbol not in removed:
                    removed.append(vt_symbol)
                self.tick_recordings.pop(vt_symbol)

        if removed:
            self.save_setting()
            self.put_event()
            self._write_log(
                f"已清理 {len(removed)} 个失效合约：{'、'.join(sorted(removed))}"
            )
        else:
            self._write_log("没有失效合约需要清理")

        return removed

    # ── 录制控制 ─────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self.active

    def start_recording(self) -> None:
        """开始录制：注册事件 + 启动写入线程

        批量订阅延迟到合约查询完毕后执行，避免合约未到齐时大量"不存在"。
        """
        if self.active:
            return

        self.active = True
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()
        self._register_events()

        app = AppEngine.instance()
        if app._contract_ready:
            # 合约已到齐，立即订阅
            self._subscribe_all()
        else:
            # 等合约到齐后再订阅
            self._write_log("等待合约查询完毕后批量订阅...")
            self.event_engine.register(
                EVENT_CONTRACT_INITED, self._on_contract_inited
            )

        self._write_log("开始记录")

    def _subscribe_all(self) -> None:
        """订阅录制列表中所有已在引擎中的合约

        始终使用当前网关，忽略配置中可能过期的旧网关名。
        """
        all_symbols = set(self.bar_recordings.keys()) | set(self.tick_recordings.keys())
        if not all_symbols:
            return

        subscribed = 0
        not_found: list[str] = []
        for vt_symbol in sorted(all_symbols):
            contract = self._get_engine_contract(vt_symbol)
            if contract:
                self._subscribe(contract, self.gateway_name)
                subscribed += 1
            else:
                not_found.append(vt_symbol)

        if not_found:
            self._write_log(
                f"以下合约在引擎中不存在，无法订阅：{'、'.join(not_found)}"
            )

        self._write_log(
            f"批量订阅完成：{subscribed}/{len(all_symbols)} 个合约"
        )

    def stop_recording(self) -> None:
        """停止录制：注销事件 + 刷写缓存 + 停止线程"""
        if not self.active:
            return

        self._unregister_events()
        self._flush_buffers()

        self.active = False
        if self.thread.is_alive():
            self.thread.join()

        self._write_log("停止记录")

    def close(self) -> None:
        """关闭引擎（窗口关闭时调用）"""
        self.stop_recording()

    def _flush_buffers(self) -> None:
        """将缓存中的数据全部推入写入队列"""
        for bars in self.bars.values():
            self.queue.put(("bar", bars))
        self.bars.clear()

        for ticks in self.ticks.values():
            self.queue.put(("tick", ticks))
        self.ticks.clear()

    def _run(self) -> None:
        """写入线程主循环"""
        consecutive_errors: int = 0
        max_consecutive_errors: int = 5

        while self.active:
            try:
                task_type, data = self.queue.get(timeout=1)

                if task_type == "tick":
                    self.database.save_tick_data(data, stream=True)
                elif task_type == "bar":
                    self.database.save_bar_data(data, stream=True)

                consecutive_errors = 0

            except Empty:
                continue
            except Exception:
                consecutive_errors += 1
                info = traceback.format_exc()

                if consecutive_errors >= max_consecutive_errors:
                    self.active = False
                    self._write_log(
                        f"连续写入失败 {consecutive_errors} 次，录制已停止：\n{info}"
                    )
                else:
                    self._write_log(
                        f"写入异常（第 {consecutive_errors} 次，"
                        f"连续 {max_consecutive_errors} 次后停止）：\n{info}"
                    )

    # ── 事件处理 ─────────────────────────────────────────

    def _register_events(self) -> None:
        """注册事件"""
        self.event_engine.register(EVENT_TIMER, self._on_timer)
        self.event_engine.register(EVENT_TICK, self._on_tick)
        self.event_engine.register(EVENT_CONTRACT, self._on_contract)

    def _unregister_events(self) -> None:
        """注销事件"""
        self.event_engine.unregister(EVENT_TIMER, self._on_timer)
        self.event_engine.unregister(EVENT_TICK, self._on_tick)
        self.event_engine.unregister(EVENT_CONTRACT, self._on_contract)
        # 可能尚未触发就停止了录制
        self.event_engine.unregister(
            EVENT_CONTRACT_INITED, self._on_contract_inited
        )

    def _on_timer(self, event: Event) -> None:
        """定时器事件：更新过滤时间，批量刷写"""
        self.filter_dt = datetime.now(CHINA_TZ)

        self.timer_count += 1
        if self.timer_count < self.timer_interval:
            return
        self.timer_count = 0

        # 统计本轮数据量
        bar_count = sum(len(v) for v in self.bars.values())
        tick_count = sum(len(v) for v in self.ticks.values())

        if bar_count or tick_count or self._tick_count:
            parts = []
            if self._tick_count:
                parts.append(f"收到Tick {self._tick_count} 条")
            if self._tick_filtered_count:
                parts.append(f"过滤 {self._tick_filtered_count} 条")
            if bar_count:
                parts.append(f"写入K线 {bar_count} 条")
            if tick_count:
                parts.append(f"写入Tick {tick_count} 条")
            self._write_log("、".join(parts))

        self._tick_count = 0
        self._tick_filtered_count = 0

        # 批量推入写入队列
        for bars in self.bars.values():
            self.queue.put(("bar", bars))
        self.bars.clear()

        for ticks in self.ticks.values():
            self.queue.put(("tick", ticks))
        self.ticks.clear()

    def _on_tick(self, event: Event) -> None:
        """Tick 事件：过滤并录制"""
        tick: TickData = event.data
        self._update_tick(tick)

    def _on_contract_inited(self, event: Event) -> None:
        """合约查询完毕：批量订阅并注销自身（一次性回调）"""
        self.event_engine.unregister(
            EVENT_CONTRACT_INITED, self._on_contract_inited
        )
        self._write_log("合约查询完毕，开始批量订阅")
        self._subscribe_all()

    def _on_contract(self, event: Event) -> None:
        """合约事件：自动订阅已录制合约

        始终使用当前网关，忽略配置中可能过期的旧网关名。
        """
        contract: ContractData = event.data
        vt_symbol = contract.vt_symbol

        if vt_symbol in self.tick_recordings or vt_symbol in self.bar_recordings:
            self._write_log(f"合约到达，自动订阅：{vt_symbol}")
            self._subscribe(contract, self.gateway_name)

    def _update_tick(self, tick: TickData) -> None:
        """处理单条 Tick"""
        # 过滤时间戳偏差过大的数据
        if abs(tick.datetime - self.filter_dt) >= self.filter_delta:
            self._tick_filtered_count += 1
            return

        recorded = False

        if tick.vt_symbol in self.tick_recordings:
            self.ticks[tick.vt_symbol].append(copy(tick))
            recorded = True

        if tick.vt_symbol in self.bar_recordings:
            bg = self._get_bar_generator(tick.vt_symbol)
            bg.update_tick(copy(tick))
            recorded = True

        if recorded:
            self._tick_count += 1

    # ── 辅助方法 ─────────────────────────────────────────

    def _get_engine_contract(self, vt_symbol: str) -> ContractData | None:
        """查询引擎合约（标准格式自动转为交易所格式）"""
        contract = self.main_engine.get_contract(vt_symbol)
        if contract:
            return contract

        # 标准格式 → 交易所格式再查一次
        if "." in vt_symbol:
            symbol, exchange_str = vt_symbol.rsplit(".", 1)
            try:
                exchange = Exchange(exchange_str)
                engine_symbol = SymbolConverter.to_exchange(symbol, exchange)
                return self.main_engine.get_contract(
                    f"{engine_symbol}.{exchange_str}"
                )
            except ValueError:
                pass
        return None

    def _get_bar_generator(self, vt_symbol: str) -> BarGenerator:
        """获取或创建 BarGenerator"""
        bg = self.bar_generators.get(vt_symbol)
        if not bg:
            bg = BarGenerator(self._record_bar)
            self.bar_generators[vt_symbol] = bg
        return bg

    def _record_bar(self, bar: BarData) -> None:
        """BarGenerator 回调：缓存 bar"""
        self.bars[bar.vt_symbol].append(bar)
        self._write_log(
            f"K线生成：{bar.vt_symbol} {bar.datetime.strftime('%H:%M')} "
            f"O:{bar.open_price} H:{bar.high_price} "
            f"L:{bar.low_price} C:{bar.close_price} V:{bar.volume}"
        )
        if self._on_bar:
            self._on_bar(bar)

    def _subscribe(self, contract: ContractData, gateway_name: str = "") -> None:
        """订阅行情

        Parameters
        ----------
        gateway_name : str
            网关名（保留参数兼容，实际由 AppEngine 统一管理）。
        """
        from guanlan.core.app import AppEngine
        vt_symbol = contract.vt_symbol
        self._write_log(f"订阅行情：{vt_symbol}")
        AppEngine.instance().subscribe(vt_symbol)

    def _write_log(self, msg: str) -> None:
        """写入日志"""
        if self._on_log:
            self._on_log(msg)

    def put_event(self) -> None:
        """通知 UI 更新录制列表"""
        if self._on_update:
            bar_symbols = sorted(self.bar_recordings.keys())
            tick_symbols = sorted(self.tick_recordings.keys())
            self._on_update(bar_symbols, tick_symbols)
