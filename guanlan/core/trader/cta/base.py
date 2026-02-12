# -*- coding: utf-8 -*-
"""
观澜量化 - CTA 策略基础定义

常量、StopOrder 数据类、事件类型。
仅保留实盘相关内容（回测后续再做）。

Author: 海山观澜
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from vnpy.trader.constant import Direction, Offset


APP_NAME = "CtaStrategy"
STOPORDER_PREFIX = "STOP"


class StopOrderStatus(Enum):
    WAITING = "等待中"
    CANCELLED = "已撤销"
    TRIGGERED = "已触发"


class EngineType(Enum):
    LIVE = "实盘"
    BACKTESTING = "回测"


@dataclass
class StopOrder:
    vt_symbol: str
    direction: Direction
    offset: Offset
    price: float
    volume: float
    stop_orderid: str
    strategy_name: str
    datetime: datetime
    gateway_name: str = ""
    lock: bool = False
    net: bool = False
    vt_orderids: list[str] = field(default_factory=list)
    status: StopOrderStatus = StopOrderStatus.WAITING


EVENT_CTA_LOG = "eCtaLog"
EVENT_CTA_STRATEGY = "eCtaStrategy"
EVENT_CTA_STOPORDER = "eCtaStopOrder"
