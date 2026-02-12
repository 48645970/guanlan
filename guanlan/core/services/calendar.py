# -*- coding: utf-8 -*-
"""
观澜量化 - 交易日历服务

基于 pandas_market_calendars (SSE) 提供交易日判断，
查询结果按日期缓存，同一天内只查一次。

Author: 海山观澜
"""

from datetime import date, timedelta

from guanlan.core.utils.logger import get_simple_logger

logger = get_simple_logger("calendar", level=20)

try:
    import pandas_market_calendars as mcal
    _calendar = mcal.get_calendar("SSE")
    _available = True
except Exception:
    _calendar = None
    _available = False
    logger.warning("pandas_market_calendars 不可用，交易日判断回退为工作日判断")


# 缓存：日期 → 是否交易日
_cache: dict[date, bool] = {}


def is_trading_day(d: date | None = None) -> bool:
    """判断指定日期是否为交易日

    结果按日期缓存，同一天只查询一次。
    库不可用时回退为周一至周五。
    """
    if d is None:
        d = date.today()

    if d in _cache:
        return _cache[d]

    if _available:
        date_str = d.strftime("%Y-%m-%d")
        schedule = _calendar.schedule(start_date=date_str, end_date=date_str)
        result = len(schedule) > 0
    else:
        result = d.weekday() < 5

    _cache[d] = result
    return result


def prev_trading_day(d: date | None = None) -> date | None:
    """获取上一个交易日"""
    if d is None:
        d = date.today()

    for i in range(1, 15):
        candidate = d - timedelta(days=i)
        if is_trading_day(candidate):
            return candidate
    return None


def next_trading_day(d: date | None = None) -> date | None:
    """获取下一个交易日"""
    if d is None:
        d = date.today()

    for i in range(1, 15):
        candidate = d + timedelta(days=i)
        if is_trading_day(candidate):
            return candidate
    return None
