# -*- coding: utf-8 -*-
"""
观澜量化 - 期货交易时段判断工具

Author: 海山观澜
"""

from datetime import datetime, time, timedelta, timezone
from typing import NamedTuple
from dataclasses import dataclass

# 北京时间 UTC+8
BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)


from guanlan.core.constants import (
    Exchange,
    NightType,
    SessionType,
    TradingStatus,
)


class TimeRange(NamedTuple):
    """时间范围"""
    start: time
    end: time

    def contains(self, t: time) -> bool:
        """判断时间是否在范围内"""
        # 处理跨日情况（如夜盘）
        if self.start <= self.end:
            return self.start <= t < self.end
        else:
            # 跨日：start > end（如21:00 - 02:30）
            return t >= self.start or t < self.end


@dataclass
class TradingPeriodInfo:
    """
    交易时段信息

    Attributes
    ----------
    status : TradingStatus
        当前交易状态
    session_type : SessionType
        当前时段类型
    can_order : bool
        是否可以下单
    can_trade : bool
        是否可以成交
    exchange : Exchange
        交易所
    night_type : NightType
        夜盘类型
    current_period_end : datetime | None
        当前时段结束时间
    next_period_start : datetime | None
        下一时段开始时间
    next_session_type : SessionType | None
        下一时段类型
    time_to_next : timedelta | None
        距离下一时段的时间
    """
    status: TradingStatus
    session_type: SessionType
    can_order: bool
    can_trade: bool
    exchange: Exchange
    night_type: NightType
    current_period_end: datetime | None = None
    next_period_start: datetime | None = None
    next_session_type: SessionType | None = None
    time_to_next: timedelta | None = None

    def __repr__(self) -> str:
        return (
            f"TradingPeriodInfo("
            f"status={self.status.value}, "
            f"session={self.session_type.value}, "
            f"can_order={self.can_order}, "
            f"can_trade={self.can_trade}, "
            f"exchange={self.exchange.value}, "
            f"night_type={self.night_type.value})"
        )


class TradingPeriod:
    """
    交易时段判断工具

    支持所有中国期货交易所的交易时段判断，包括：
    - 上期所(SHFE)、大商所(DCE)、郑商所(CZCE)、中金所(CFFEX)、能源中心(INE)、广期所(GFEX)
    - 日盘、夜盘、集合竞价等各种时段
    - 不同夜盘结束时间（23:00/01:00/02:30）
    """

    # 夜盘集合竞价时间（所有有夜盘的交易所统一）
    NIGHT_BIDDING = TimeRange(time(20, 55), time(21, 0))

    # 夜盘连续竞价时间（根据品种类型）
    NIGHT_SESSIONS = {
        NightType.NIGHT_23: TimeRange(time(21, 0), time(23, 0)),
        NightType.NIGHT_01: TimeRange(time(21, 0), time(1, 0)),  # 次日
        NightType.NIGHT_0230: TimeRange(time(21, 0), time(2, 30)),  # 次日
    }

    # 日盘集合竞价时间
    DAY_BIDDING = {
        # 有夜盘品种
        "with_night": TimeRange(time(8, 55), time(9, 0)),
        # 无夜盘品种
        "no_night": TimeRange(time(8, 55), time(9, 0)),
        # 中金所特殊
        Exchange.CFFEX: TimeRange(time(9, 25), time(9, 30)),
    }

    # 日盘连续竞价时间
    DAY_SESSIONS = {
        # 普通交易所（上期所、大商所、郑商所、能源中心、广期所）
        "normal": [
            TimeRange(time(9, 0), time(10, 15)),
            TimeRange(time(10, 30), time(11, 30)),
            TimeRange(time(13, 30), time(15, 0)),
        ],
        # 中金所股指期货
        Exchange.CFFEX: [
            TimeRange(time(9, 30), time(11, 30)),
            TimeRange(time(13, 0), time(15, 0)),
        ],
    }

    @classmethod
    def check_trading(
        cls,
        exchange: Exchange = Exchange.SHFE,
        night_type: NightType = NightType.NIGHT_23,
        dt: datetime | None = None,
    ) -> TradingPeriodInfo:
        """
        检查交易时段状态

        Parameters
        ----------
        exchange : Exchange, default Exchange.SHFE
            交易所类型
        night_type : NightType, default NightType.NIGHT_23
            夜盘类型（仅对有夜盘的品种有效）
        dt : datetime | None, default None
            指定时间，None 表示当前时间

        Returns
        -------
        TradingPeriodInfo
            交易时段信息对象

        Examples
        --------
        >>> # 检查上期所螺纹钢（夜盘至23:00）
        >>> info = TradingPeriod.check_trading(Exchange.SHFE, NightType.NIGHT_23)
        >>> print(info.status)
        >>> print(info.can_trade)

        >>> # 检查中金所股指（无夜盘）
        >>> info = TradingPeriod.check_trading(Exchange.CFFEX, NightType.NONE)

        >>> # 检查上期所黄金（夜盘至02:30）
        >>> info = TradingPeriod.check_trading(Exchange.SHFE, NightType.NIGHT_0230)
        """
        if dt is None:
            dt = beijing_now()

        current_time = dt.time()

        # 1. 检查夜盘时段（如果有夜盘）
        if night_type != NightType.NONE:
            # 夜盘集合竞价
            if cls.NIGHT_BIDDING.contains(current_time):
                return cls._build_period_info(
                    TradingStatus.BIDDING,
                    SessionType.PRE_MARKET,
                    True, False,  # 可以下单，不可成交
                    exchange, night_type, dt
                )

            # 夜盘连续竞价
            night_range = cls.NIGHT_SESSIONS[night_type]
            if night_range.contains(current_time):
                return cls._build_period_info(
                    TradingStatus.TRADING,
                    SessionType.CONTINUOUS,
                    True, True,  # 可以下单和成交
                    exchange, night_type, dt
                )

        # 2. 检查日盘集合竞价
        if exchange == Exchange.CFFEX:
            bidding_range = cls.DAY_BIDDING[Exchange.CFFEX]
        else:
            bidding_range = cls.DAY_BIDDING["with_night" if night_type != NightType.NONE else "no_night"]

        if bidding_range.contains(current_time):
            return cls._build_period_info(
                TradingStatus.BIDDING,
                SessionType.PRE_MARKET,
                True, False,
                exchange, night_type, dt
            )

        # 3. 检查日盘连续竞价
        if exchange == Exchange.CFFEX:
            day_ranges = cls.DAY_SESSIONS[Exchange.CFFEX]
        else:
            day_ranges = cls.DAY_SESSIONS["normal"]

        for day_range in day_ranges:
            if day_range.contains(current_time):
                return cls._build_period_info(
                    TradingStatus.TRADING,
                    SessionType.CONTINUOUS,
                    True, True,
                    exchange, night_type, dt
                )

        # 4. 检查是否在交易日的休息时段
        if cls._is_in_day_break(current_time, exchange):
            return cls._build_period_info(
                TradingStatus.BREAK,
                SessionType.BREAK,
                False, False,
                exchange, night_type, dt
            )

        # 5. 其他时间视为闭市
        return cls._build_period_info(
            TradingStatus.CLOSED,
            SessionType.CLOSED,
            False, False,
            exchange, night_type, dt
        )

    @classmethod
    def _is_in_day_break(cls, t: time, exchange: Exchange) -> bool:
        """
        判断是否在日盘休息时段

        休息时段：
        - 普通交易所：10:15-10:30, 11:30-13:30
        - 中金所：11:30-13:00
        """
        if exchange == Exchange.CFFEX:
            # 中金所只有中午休息
            return time(11, 30) <= t < time(13, 0)
        else:
            # 其他交易所
            return (time(10, 15) <= t < time(10, 30) or
                    time(11, 30) <= t < time(13, 30))

    @classmethod
    def _build_period_info(
        cls,
        status: TradingStatus,
        session_type: SessionType,
        can_order: bool,
        can_trade: bool,
        exchange: Exchange,
        night_type: NightType,
        dt: datetime,
    ) -> TradingPeriodInfo:
        """构建交易时段信息对象（包含下一时段信息）"""
        return TradingPeriodInfo(
            status=status,
            session_type=session_type,
            can_order=can_order,
            can_trade=can_trade,
            exchange=exchange,
            night_type=night_type,
            # TODO: 计算当前时段结束时间、下一时段开始时间等
            # 这部分可以在后续版本中实现
        )

    @classmethod
    def is_trading_time(
        cls,
        exchange: Exchange = Exchange.SHFE,
        night_type: NightType = NightType.NIGHT_23,
        dt: datetime | None = None,
    ) -> bool:
        """
        简化版：判断当前是否可以交易

        Parameters
        ----------
        exchange : Exchange
            交易所类型
        night_type : NightType
            夜盘类型
        dt : datetime | None
            指定时间，None 表示当前时间

        Returns
        -------
        bool
            是否可以交易

        Examples
        --------
        >>> TradingPeriod.is_trading_time(Exchange.SHFE, NightType.NIGHT_23)
        True
        """
        info = cls.check_trading(exchange, night_type, dt)
        return info.can_trade

    @classmethod
    def can_place_order(
        cls,
        exchange: Exchange = Exchange.SHFE,
        night_type: NightType = NightType.NIGHT_23,
        dt: datetime | None = None,
    ) -> bool:
        """
        简化版：判断当前是否可以下单

        Parameters
        ----------
        exchange : Exchange
            交易所类型
        night_type : NightType
            夜盘类型
        dt : datetime | None
            指定时间，None 表示当前时间

        Returns
        -------
        bool
            是否可以下单

        Examples
        --------
        >>> TradingPeriod.can_place_order(Exchange.SHFE, NightType.NIGHT_23)
        True
        """
        info = cls.check_trading(exchange, night_type, dt)
        return info.can_order


def get_trading_date(dt: datetime | None = None) -> str:
    """获取当前交易日期

    期货夜盘（20:00 之后）归属下一个交易日：
    - 周一~周四 20:00 后 → 次日
    - 周五 20:00 后 → 下周一
    - 其他时段 → 当天

    Parameters
    ----------
    dt : datetime | None
        指定时间，None 表示当前时间

    Returns
    -------
    str
        交易日期字符串，格式 "YYYY-MM-DD"
    """
    if dt is None:
        dt = beijing_now()

    if dt.hour >= 20:
        # 夜盘时段：交易日为下一个工作日
        next_day = dt.date() + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.strftime("%Y-%m-%d")

    return dt.strftime("%Y-%m-%d")
