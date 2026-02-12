# -*- coding: utf-8 -*-
"""
观澜量化 - 主引擎

继承 vnpy MainEngine，重载引擎初始化：
- LogEngine：使用观澜 cfg 配置和 loguru 日志
- DingTalkEngine：钉钉机器人通知（替代 vnpy EmailEngine）
- OmsEngine：继承 vnpy 原始实现

Author: 海山观澜
"""

from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread

from vnpy.event import Event
from vnpy.trader.engine import (
    MainEngine as VnpyMainEngine,
    BaseEngine as VnpyBaseEngine,
    OmsEngine,
)
from vnpy.trader.event import EVENT_LOG
from vnpy.trader.object import (
    LogData,
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    QuoteData,
    OrderRequest,
)
from vnpy.trader.converter import OffsetConverter

from guanlan.core.trader.event import EventEngine
from guanlan.core.utils.logger import logger, DEBUG, INFO, WARNING, ERROR, CRITICAL


class BaseEngine(VnpyBaseEngine):
    """观澜基础引擎

    继承 VNPY BaseEngine，统一 write_log 方法。
    所有引擎通过 MainEngine.add_engine() 注册，
    关闭由 MainEngine.close() 统一管理。
    """

    def __init__(
        self,
        main_engine: "MainEngine",
        event_engine: EventEngine,
        engine_name: str,
    ) -> None:
        super().__init__(main_engine, event_engine, engine_name)

    def write_log(self, msg: str, source: str = "") -> None:
        """统一日志输出"""
        self.main_engine.write_log(msg, source or self.engine_name)


class LogEngine(BaseEngine):
    """观澜日志引擎

    替代 vnpy LogEngine，使用观澜 cfg 配置和 loguru 日志。
    """

    level_map: dict[int, str] = {
        DEBUG: "DEBUG",
        INFO: "INFO",
        WARNING: "WARNING",
        ERROR: "ERROR",
        CRITICAL: "CRITICAL",
    }

    def __init__(self, main_engine: "MainEngine", event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, "log")

        # 延迟导入避免循环依赖（core ← ui）
        from guanlan.ui.common.config import cfg
        self.active: bool = cfg.get(cfg.logActive)

        self.event_engine.register(EVENT_LOG, self.process_log_event)

    def process_log_event(self, event: Event) -> None:
        """处理日志事件"""
        if not self.active:
            return

        log: LogData = event.data
        level: str | int = self.level_map.get(log.level, log.level)
        logger.bind(name=log.gateway_name).log(level, log.msg)


class DingTalkEngine(BaseEngine):
    """钉钉通知引擎

    替代 vnpy EmailEngine，通过钉钉机器人发送实时通知。
    使用后台线程异步发送，避免阻塞主线程。
    """

    def __init__(self, main_engine: "MainEngine", event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, "dingtalk")

        self.thread: Thread = Thread(target=self._run, daemon=True)
        self.queue: Queue = Queue()
        self.active: bool = False

    def send_msg(self, title: str, content: str, msg_type: str = "markdown") -> None:
        """发送钉钉消息

        Parameters
        ----------
        title : str
            消息标题
        content : str
            消息内容（支持 Markdown 格式）
        msg_type : str
            消息类型：text / markdown，默认 markdown
        """
        if not self.active:
            self._start()

        self.queue.put((title, content, msg_type))

    def _start(self) -> None:
        """启动后台发送线程"""
        from guanlan.ui.common.config import cfg

        if not cfg.get(cfg.dingtalkActive):
            self.main_engine.write_log("钉钉通知未启用")
            return

        webhook = cfg.get(cfg.dingtalkWebhook)
        secret = cfg.get(cfg.dingtalkSecret)

        if not webhook or not secret:
            self.main_engine.write_log("钉钉 Webhook 或 Secret 未配置")
            return

        try:
            from dingtalkchatbot.chatbot import DingtalkChatbot
            self._bot = DingtalkChatbot(webhook, secret=secret)
        except ImportError:
            self.main_engine.write_log("钉钉通知依赖未安装，请执行: pip install DingtalkChatbot")
            return

        self.active = True
        self.thread.start()
        self.main_engine.write_log("钉钉通知引擎已启动")

    def _run(self) -> None:
        """后台消息发送循环"""
        while self.active:
            try:
                title, content, msg_type = self.queue.get(block=True, timeout=1)

                try:
                    if msg_type == "text":
                        self._bot.send_text(content)
                    else:
                        self._bot.send_markdown(title=title, text=content)
                except Exception:
                    import traceback
                    self.main_engine.write_log(
                        f"钉钉消息发送失败: {traceback.format_exc()}"
                    )
            except Empty:
                pass

    def close(self) -> None:
        """关闭引擎"""
        if not self.active:
            return

        self.active = False
        self.thread.join()


class MainEngine(VnpyMainEngine):
    """观澜主引擎"""

    def __init__(self, event_engine: EventEngine | None = None) -> None:
        super().__init__(event_engine)

    def init_engines(self) -> None:
        """初始化引擎（使用观澜 LogEngine / DingTalkEngine 替代 vnpy 默认）"""
        self.add_engine(LogEngine)

        oms_engine: OmsEngine = self.add_engine(OmsEngine)
        self.get_tick: Callable[[str], TickData | None] = oms_engine.get_tick
        self.get_order: Callable[[str], OrderData | None] = oms_engine.get_order
        self.get_trade: Callable[[str], TradeData | None] = oms_engine.get_trade
        self.get_position: Callable[[str], PositionData | None] = oms_engine.get_position
        self.get_account: Callable[[str], AccountData | None] = oms_engine.get_account
        self.get_contract: Callable[[str], ContractData | None] = oms_engine.get_contract
        self.get_quote: Callable[[str], QuoteData | None] = oms_engine.get_quote
        self.get_all_ticks: Callable[[], list[TickData]] = oms_engine.get_all_ticks
        self.get_all_orders: Callable[[], list[OrderData]] = oms_engine.get_all_orders
        self.get_all_trades: Callable[[], list[TradeData]] = oms_engine.get_all_trades
        self.get_all_positions: Callable[[], list[PositionData]] = oms_engine.get_all_positions
        self.get_all_accounts: Callable[[], list[AccountData]] = oms_engine.get_all_accounts
        self.get_all_contracts: Callable[[], list[ContractData]] = oms_engine.get_all_contracts
        self.get_all_quotes: Callable[[], list[QuoteData]] = oms_engine.get_all_quotes
        self.get_all_active_orders: Callable[[], list[OrderData]] = oms_engine.get_all_active_orders
        self.get_all_active_quotes: Callable[[], list[QuoteData]] = oms_engine.get_all_active_quotes
        self.update_order_request: Callable[[OrderRequest, str, str], None] = oms_engine.update_order_request
        self.convert_order_request: Callable[[OrderRequest, str, bool, bool], list[OrderRequest]] = oms_engine.convert_order_request
        self.get_converter: Callable[[str], OffsetConverter | None] = oms_engine.get_converter

        dingtalk_engine: DingTalkEngine = self.add_engine(DingTalkEngine)
        self.send_dingtalk: Callable[[str, str, str], None] = dingtalk_engine.send_msg


__all__ = ["BaseEngine", "MainEngine", "LogEngine", "DingTalkEngine"]
