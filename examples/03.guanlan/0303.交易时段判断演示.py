# -*- coding: utf-8 -*-
"""
观澜量化 - 交易时段判断演示

演示功能：
1. core.utils.trading_period 模块 - 期货交易时段判断
2. pandas_market_calendars 库 - 交易日历查询

依赖安装:
    pip install pandas_market_calendars

Author: 海山观澜
"""

import sys
from pathlib import Path
from datetime import datetime, date, time, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guanlan.core.utils.trading_period import TradingPeriod
from guanlan.core.constants import (
    Exchange,
    NightType,
    TradingStatus,
    SessionType,
)

# pandas_market_calendars 是可选依赖
try:
    import pandas_market_calendars as mcal
    import pandas as pd
    HAS_MCAL = True
except ImportError:
    HAS_MCAL = False


def demo_basic_check():
    """演示基本的交易时段判断"""
    print("=" * 70)
    print("1. 基本交易时段判断")
    print("=" * 70)

    # 当前时间
    now = datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查上期所螺纹钢（夜盘至23:00）
    print(">>> 检查上期所螺纹钢（夜盘至23:00）")
    info = TradingPeriod.check_trading(Exchange.SHFE, NightType.NIGHT_23)
    print(f"  交易状态: {info.status.value}")
    print(f"  时段类型: {info.session_type.value}")
    print(f"  可以下单: {info.can_order}")
    print(f"  可以成交: {info.can_trade}")
    print()

    # 检查中金所股指（无夜盘）
    print(">>> 检查中金所股指期货（无夜盘）")
    info = TradingPeriod.check_trading(Exchange.CFFEX, NightType.NONE)
    print(f"  交易状态: {info.status.value}")
    print(f"  时段类型: {info.session_type.value}")
    print(f"  可以下单: {info.can_order}")
    print(f"  可以成交: {info.can_trade}")
    print()

    # 检查上期所黄金（夜盘至02:30）
    print(">>> 检查上期所黄金（夜盘至02:30）")
    info = TradingPeriod.check_trading(Exchange.SHFE, NightType.NIGHT_0230)
    print(f"  交易状态: {info.status.value}")
    print(f"  时段类型: {info.session_type.value}")
    print(f"  可以下单: {info.can_order}")
    print(f"  可以成交: {info.can_trade}")
    print()

    # 检查大商所铁矿石（夜盘至23:00）
    print(">>> 检查大商所铁矿石（夜盘至23:00）")
    info = TradingPeriod.check_trading(Exchange.DCE, NightType.NIGHT_23)
    print(f"  交易状态: {info.status.value}")
    print(f"  时段类型: {info.session_type.value}")
    print(f"  可以下单: {info.can_order}")
    print(f"  可以成交: {info.can_trade}")
    print()


def demo_all_exchanges():
    """演示所有交易所的判断"""
    print("=" * 70)
    print("2. 所有交易所当前状态")
    print("=" * 70)

    exchanges_config = [
        (Exchange.SHFE, NightType.NIGHT_23, "上期所（螺纹钢）"),
        (Exchange.DCE, NightType.NIGHT_23, "大商所（铁矿石）"),
        (Exchange.CZCE, NightType.NIGHT_23, "郑商所（甲醇）"),
        (Exchange.CFFEX, NightType.NONE, "中金所（股指）"),
        (Exchange.INE, NightType.NIGHT_0230, "能源中心（原油）"),
        (Exchange.GFEX, NightType.NONE, "广期所"),
    ]

    for exchange, night_type, name in exchanges_config:
        info = TradingPeriod.check_trading(exchange, night_type)
        print(f"{name:20s} | 状态: {info.status.value:8s} | "
              f"下单: {'✓' if info.can_order else '✗'} | "
              f"交易: {'✓' if info.can_trade else '✗'}")

    print()


def demo_night_types():
    """演示不同夜盘类型"""
    print("=" * 70)
    print("3. 不同夜盘类型示例")
    print("=" * 70)

    night_types_examples = [
        (NightType.NONE, "无夜盘", "股指期货、国债期货"),
        (NightType.NIGHT_23, "21:00-23:00", "螺纹钢、热卷、焦炭、铁矿石、甲醇等"),
        (NightType.NIGHT_01, "21:00-01:00", "铜、铝、铅、锌、镍、锡"),
        (NightType.NIGHT_0230, "21:00-02:30", "黄金、白银、原油"),
    ]

    for night_type, time_range, examples in night_types_examples:
        print(f"{night_type.value:8s} | {time_range:18s} | 品种: {examples}")

    print()


def demo_specific_times():
    """演示特定时间点的判断"""
    print("=" * 70)
    print("4. 特定时间点判断（上期所螺纹钢）")
    print("=" * 70)

    test_times = [
        ("08:50:00", "早盘前"),
        ("08:58:00", "集合竞价"),
        ("09:05:00", "早盘交易"),
        ("10:20:00", "上午休息"),
        ("10:35:00", "上午交易"),
        ("11:35:00", "午休"),
        ("13:35:00", "午盘交易"),
        ("15:05:00", "日盘结束"),
        ("20:50:00", "夜盘准备"),
        ("20:58:00", "夜盘竞价"),
        ("21:05:00", "夜盘交易"),
        ("23:05:00", "夜盘结束"),
    ]

    for time_str, desc in test_times:
        # 构造今天的特定时间
        h, m, s = map(int, time_str.split(":"))
        test_dt = datetime.now().replace(hour=h, minute=m, second=s)

        info = TradingPeriod.check_trading(
            Exchange.SHFE,
            NightType.NIGHT_23,
            test_dt
        )

        print(f"{time_str} ({desc:10s}) | "
              f"状态: {info.status.value:8s} | "
              f"时段: {info.session_type.value:8s} | "
              f"下单: {'✓' if info.can_order else '✗'} | "
              f"交易: {'✓' if info.can_trade else '✗'}")

    print()


def demo_simplified_api():
    """演示简化版API"""
    print("=" * 70)
    print("5. 简化版API使用")
    print("=" * 70)

    # 判断是否可以交易
    can_trade = TradingPeriod.is_trading_time(Exchange.SHFE, NightType.NIGHT_23)
    print(f"当前是否可以交易: {can_trade}")

    # 判断是否可以下单
    can_order = TradingPeriod.can_place_order(Exchange.SHFE, NightType.NIGHT_23)
    print(f"当前是否可以下单: {can_order}")

    print()


def demo_cffex_special():
    """演示中金所特殊时段"""
    print("=" * 70)
    print("6. 中金所特殊时段（不同于其他交易所）")
    print("=" * 70)

    test_times_cffex = [
        ("09:20:00", "集合竞价前"),
        ("09:28:00", "集合竞价中"),
        ("09:35:00", "上午交易"),
        ("11:35:00", "午休"),
        ("13:05:00", "午盘交易"),
        ("15:05:00", "闭市"),
    ]

    print("中金所交易时间特点：")
    print("  - 集合竞价: 9:25-9:30")
    print("  - 上午交易: 9:30-11:30")
    print("  - 下午交易: 13:00-15:00（比其他交易所提前30分钟）")
    print()

    for time_str, desc in test_times_cffex:
        h, m, s = map(int, time_str.split(":"))
        test_dt = datetime.now().replace(hour=h, minute=m, second=s)

        info = TradingPeriod.check_trading(
            Exchange.CFFEX,
            NightType.NONE,
            test_dt
        )

        print(f"{time_str} ({desc:10s}) | "
              f"状态: {info.status.value:8s} | "
              f"时段: {info.session_type.value:8s}")

    print()


# ============================================================
# 以下是 pandas_market_calendars 交易日历演示
# ============================================================

def demo_calendar_list():
    """演示获取可用日历列表"""
    if not HAS_MCAL:
        return

    print("=" * 70)
    print("7. 交易日历 - 可用交易所")
    print("=" * 70)

    calendars = mcal.get_calendar_names()
    print(f"共有 {len(calendars)} 个交易所日历可用")

    common = {
        "SSE": "上海证券交易所",
        "SZSE": "深圳证券交易所",
        "XHKG": "香港交易所",
        "NYSE": "纽约证券交易所",
        "NASDAQ": "纳斯达克",
    }

    print("\n常用交易所:")
    for code, name in common.items():
        status = "✓" if code in calendars else "✗"
        print(f"  {status} {code:8} - {name}")
    print()


def demo_china_calendar():
    """演示中国A股交易日历"""
    if not HAS_MCAL:
        return

    print("=" * 70)
    print("8. 交易日历 - 中国A股 (SSE)")
    print("=" * 70)

    sse = mcal.get_calendar('SSE')
    year = datetime.now().year

    # 获取全年交易日
    schedule = sse.schedule(start_date=f'{year}-01-01', end_date=f'{year}-12-31')
    print(f"\n{year}年交易日统计:")
    print(f"  全年交易日: {len(schedule)} 天")

    # 按月统计
    print(f"\n{year}年各月交易日:")
    for month in range(1, 13):
        start = f'{year}-{month:02d}-01'
        if month == 12:
            end = f'{year}-12-31'
        else:
            end = f'{year}-{month+1:02d}-01'
        month_schedule = sse.schedule(start_date=start, end_date=end)
        month_days = len([d for d in month_schedule.index if d.month == month])
        print(f"  {month:2d}月: {month_days:2d} 天", end="")
        if month % 4 == 0:
            print()
    print()


def demo_is_trading_day():
    """演示判断交易日"""
    if not HAS_MCAL:
        return

    print("=" * 70)
    print("9. 交易日历 - 判断交易日")
    print("=" * 70)

    sse = mcal.get_calendar('SSE')
    today = date.today()

    print("\n最近7天交易状态:")
    for i in range(-3, 4):
        check_date = today + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')
        weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][check_date.weekday()]

        schedule = sse.schedule(start_date=date_str, end_date=date_str)
        is_trading = len(schedule) > 0

        marker = " ← 今天" if i == 0 else ""
        status = "交易日" if is_trading else "休市  "
        print(f"  {date_str} {weekday} {status}{marker}")
    print()


def demo_trading_days_range():
    """演示获取交易日区间"""
    if not HAS_MCAL:
        return

    print("=" * 70)
    print("10. 交易日历 - 交易日区间")
    print("=" * 70)

    sse = mcal.get_calendar('SSE')
    today = date.today()

    # 最近10个交易日
    print("\n最近10个交易日:")
    end_date = today.strftime('%Y-%m-%d')
    start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    schedule = sse.schedule(start_date=start_date, end_date=end_date)

    recent_days = schedule.tail(10)
    for idx in recent_days.index:
        weekday = ['周一','周二','周三','周四','周五','周六','周日'][idx.weekday()]
        print(f"  {idx.strftime('%Y-%m-%d')} {weekday}")

    # 未来5个交易日
    print("\n未来5个交易日:")
    start_date = today.strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=15)).strftime('%Y-%m-%d')
    schedule = sse.schedule(start_date=start_date, end_date=end_date)

    future_days = schedule.head(5)
    for idx in future_days.index:
        weekday = ['周一','周二','周三','周四','周五','周六','周日'][idx.weekday()]
        print(f"  {idx.strftime('%Y-%m-%d')} {weekday}")
    print()


def demo_practical_calendar():
    """演示交易日历实际应用"""
    if not HAS_MCAL:
        return

    print("=" * 70)
    print("11. 交易日历 - 实际应用")
    print("=" * 70)

    sse = mcal.get_calendar('SSE')
    today = date.today()

    # 获取上一个交易日
    print("\n实用功能:")
    start_date = (today - timedelta(days=10)).strftime('%Y-%m-%d')
    end_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    schedule = sse.schedule(start_date=start_date, end_date=end_date)
    if len(schedule) > 0:
        last_trading_day = schedule.index[-1]
        print(f"  上一个交易日: {last_trading_day.strftime('%Y-%m-%d')}")

    # 获取下一个交易日
    start_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=10)).strftime('%Y-%m-%d')
    schedule = sse.schedule(start_date=start_date, end_date=end_date)
    if len(schedule) > 0:
        next_trading_day = schedule.index[0]
        print(f"  下一个交易日: {next_trading_day.strftime('%Y-%m-%d')}")

    # 计算交易日间隔
    date1 = today - timedelta(days=30)
    date2 = today
    schedule = sse.schedule(
        start_date=date1.strftime('%Y-%m-%d'),
        end_date=date2.strftime('%Y-%m-%d')
    )
    print(f"\n交易日间隔计算:")
    print(f"  {date1} 到 {date2}")
    print(f"  自然日: {(date2 - date1).days} 天")
    print(f"  交易日: {len(schedule)} 天")
    print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "观澜量化 - 交易时段判断演示" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 第一部分：期货交易时段判断
    print("【第一部分：期货交易时段判断】")
    print()
    demo_basic_check()
    demo_all_exchanges()
    demo_night_types()
    demo_specific_times()
    demo_simplified_api()
    demo_cffex_special()

    # 第二部分：交易日历（需要 pandas_market_calendars）
    if HAS_MCAL:
        print("\n")
        print("【第二部分：交易日历 (pandas_market_calendars)】")
        print()
        demo_calendar_list()
        demo_china_calendar()
        demo_is_trading_day()
        demo_trading_days_range()
        demo_practical_calendar()
    else:
        print("\n")
        print("=" * 70)
        print("提示: 安装 pandas_market_calendars 可获得交易日历功能")
        print("  pip install pandas_market_calendars")
        print("=" * 70)

    print("\n")
    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    print()
    print("参考资料：")
    print("- 期货交易时间: https://www.shfe.com.cn/")
    print("- 交易日历库: https://github.com/rsheftel/pandas_market_calendars")


if __name__ == "__main__":
    main()
