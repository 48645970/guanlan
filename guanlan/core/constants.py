# -*- coding: utf-8 -*-
"""
观澜量化 - 常量和枚举定义

本模块整合了：
1. 应用元数据（版本、作者、URL 等）
2. 路径常量（项目目录、资源目录等）
3. 从 VNPY 导入的通用枚举（Direction, Offset, Status, Exchange 等）
4. 观澜特有的枚举（交易时段等）

Author: 海山观澜
"""

from enum import Enum
from pathlib import Path

# ============================================================================
# 应用元数据
# ============================================================================

APP_NAME = "观澜量化"
APP_NAME_EN = "Guanlan Quant"
APP_VERSION = "2.0.0"
APP_AUTHOR = "海山观澜"
APP_YEAR = "2024-2030"

# 外部链接
HELP_URL = "https://www.zhihu.com/column/c_1760768090802171904"

# ============================================================================
# 路径常量
# ============================================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 资源目录
RESOURCES_DIR = PROJECT_ROOT / "resources"
RESOURCES_IMAGES_DIR = RESOURCES_DIR / "images"
RESOURCES_SOUNDS_DIR = RESOURCES_DIR / "sounds"

# UI 样式表目录
UI_QSS_DIR = PROJECT_ROOT / "guanlan" / "ui" / "qss"

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# 配置目录
CONFIG_DIR = PROJECT_ROOT / ".guanlan"

# ArcticDB 数据目录
ARCTIC_DATA_DIR = CONFIG_DIR / "data" / "arctic"

# CTP 流文件目录
CTP_FLOW_DIR = CONFIG_DIR / "ctp"

# ============================================================================
# UI 配置常量
# ============================================================================

DEFAULT_WINDOW_WIDTH = 1680
DEFAULT_WINDOW_HEIGHT = 960
MIN_WINDOW_WIDTH = 1230



# ============================================================================
# UI 枚举
# ============================================================================

class InfoLevel(Enum):
    """消息级别"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"

# ============================================================================
# 从 VNPY 导入通用枚举（直接使用，不重复定义）
# ============================================================================

# VNPY 核心枚举
from vnpy.trader.constant import (
    Direction,      # 交易方向：多/空/净
    Offset,         # 开平方向：开/平/平今/平昨
    Status,         # 订单状态：提交中/未成交/部分成交/全部成交/已撤销/拒单
    Product,        # 产品类型：股票/期货/期权/指数等
    OrderType,      # 订单类型：限价/市价/FAK/FOK等
    OptionType,     # 期权类型：看涨/看跌
    Exchange,       # 交易所：SHFE/DCE/CZCE/CFFEX/INE/GFEX等
    Currency,       # 货币类型：USD/HKD/CNY/CAD
    Interval,       # K线周期：1m/1h/d/w/tick
)

# VNPY CTA策略引擎枚举
from vnpy_ctastrategy.base import (
    StopOrderStatus,    # 本地停止单状态：等待中/已撤销/已触发
    EngineType,         # 引擎类型：实盘/回测
    BacktestingMode,    # 回测模式：BAR/TICK
)

# ============================================================================
# 交易时段相关枚举
# ============================================================================

class NightType(Enum):
    """
    夜盘类型枚举

    中国期货市场夜盘分为三种类型：
    - NONE: 无夜盘（股指期货、国债期货等）
    - NIGHT_23: 21:00-23:00（螺纹钢、热卷、焦炭、铁矿石、甲醇等）
    - NIGHT_01: 21:00-01:00（铜、铝、铅、锌、镍、锡）
    - NIGHT_0230: 21:00-02:30（黄金、白银、原油）
    """
    NONE = "NONE"           # 无夜盘
    NIGHT_23 = "23:00"      # 21:00-23:00
    NIGHT_01 = "01:00"      # 21:00-01:00（次日）
    NIGHT_0230 = "02:30"    # 21:00-02:30（次日）


class SessionType(Enum):
    """交易时段类型"""
    PRE_MARKET = "集合竞价"     # 集合竞价
    CONTINUOUS = "连续竞价"     # 连续竞价
    BREAK = "休市"              # 休市时段
    CLOSED = "闭市"             # 非交易日


class TradingStatus(Enum):
    """交易状态"""
    BIDDING = "竞价中"      # 集合竞价中
    TRADING = "交易中"      # 连续交易中
    BREAK = "休息中"        # 中场休息
    CLOSED = "已闭市"       # 已闭市
