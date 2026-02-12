# -*- coding: utf-8 -*-
"""
观澜量化 - 手续费计算

根据 contract.json 中配置的手续费率，计算成交手续费。

Author: 海山观澜
"""

from vnpy.trader.constant import Offset
from vnpy.trader.object import TradeData

from guanlan.core.utils.symbol_converter import SymbolConverter


def calculate_commission(trade: TradeData) -> float:
    """根据成交信息计算手续费

    逻辑：
    - 提取品种代码，从 AppEngine 缓存的 contracts 获取手续费配置
    - 按 offset 分三档：开仓 / 平今 / 平昨(其他)
    - 比例费率优先，否则用固定费率
    """
    commodity: str = SymbolConverter.extract_commodity(trade.symbol)
    if not commodity:
        return 0.0

    from guanlan.core.app import AppEngine
    config = AppEngine.instance().contracts.get(commodity)
    if not config:
        return 0.0

    size: float = config.get("size", 1)

    if trade.offset == Offset.OPEN:
        # 开仓
        if config.get("open_ratio", 0) != 0:
            result = config["open_ratio"] * trade.price * trade.volume * 0.0001 * size
        else:
            result = config.get("open", 0) * trade.volume

    elif trade.offset == Offset.CLOSETODAY:
        # 平今
        if config.get("close_today_ratio", 0) != 0:
            result = config["close_today_ratio"] * trade.price * trade.volume * 0.0001 * size
        else:
            result = config.get("close_today", 0) * trade.volume

    else:
        # 平昨 / 其他
        if config.get("close_ratio", 0) != 0:
            result = config["close_ratio"] * trade.price * trade.volume * 0.0001 * size
        else:
            result = config.get("close", 0) * trade.volume

    return round(result, 2)
