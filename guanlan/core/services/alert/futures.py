# -*- coding: utf-8 -*-
"""
观澜量化 - 期货时段提醒服务

在关键交易时刻播放提醒音效：开盘/收盘、开盘前5分钟、收盘前5分钟。
由标题栏时钟每秒调用 check() 驱动。
非交易日自动静默（基于交易日历服务）。

Author: 海山观澜
"""

from datetime import time, date

from guanlan.core.services.sound import play as play_sound, SoundType
from guanlan.core.services.calendar import is_trading_day


# 提醒时刻表：(时, 分) → 音效类型
_ALERTS: dict[tuple[int, int], SoundType] = {
    # 日盘 - 提前5分钟
    (8, 55):  "begin_5",   # 日盘集合竞价（9:00开盘前5分钟）
    (11, 25): "end_5",     # 早盘收盘前5分钟（11:30）
    (13, 25): "begin_5",   # 午盘开盘前5分钟（13:30）
    (14, 55): "end_5",     # 日盘收盘前5分钟（15:00）
    # 日盘 - 开盘/收盘
    (9, 0):   "begin_0",   # 日盘开盘
    (11, 30): "end_0",     # 早盘收盘
    (13, 30): "begin_0",   # 午盘开盘
    (15, 0):  "end_0",     # 日盘收盘
    # 夜盘 - 提前5分钟
    (20, 55): "begin_5",   # 夜盘集合竞价（21:00开盘前5分钟）
    (22, 55): "end_5",     # 夜盘收盘前5分钟（23:00品种）
    (0, 55):  "end_5",     # 夜盘收盘前5分钟（01:00品种）
    (2, 25):  "end_5",     # 夜盘收盘前5分钟（02:30品种）
    # 夜盘 - 开盘/收盘
    (21, 0):  "begin_0",   # 夜盘开盘
    (23, 0):  "end_0",     # 夜盘收盘（23:00品种）
    (1, 0):   "end_0",     # 夜盘收盘（01:00品种）
    (2, 30):  "end_0",     # 夜盘收盘（02:30品种）
}

# 当天已触发的提醒（每天重置）
_fired: set[tuple[int, int]] = set()
_fired_date: date | None = None


def check(now: time) -> None:
    """检查当前时刻是否需要播放提醒音效

    每秒调用一次，匹配 HH:MM 触发，同一时刻每天只触发一次。
    非交易日静默（结果按天缓存，不重复查询日历）。
    """
    global _fired, _fired_date

    today = date.today()

    if _fired_date != today:
        _fired = set()
        _fired_date = today

    # 非交易日不提醒（is_trading_day 内部按天缓存）
    if not is_trading_day(today):
        return

    key = (now.hour, now.minute)
    if key in _ALERTS and key not in _fired:
        _fired.add(key)
        play_sound(_ALERTS[key])
