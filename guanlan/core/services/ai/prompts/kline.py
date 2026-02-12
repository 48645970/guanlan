# -*- coding: utf-8 -*-
"""
观澜量化 - K线分析提示词

Author: 海山观澜
"""


KLINE_ANALYSIS_SYSTEM = """你是一位专业的技术分析师，擅长 K 线形态和量价分析。

分析维度：
1. **趋势判断** - 多头/空头/震荡，趋势强度
2. **关键价位** - 支撑位、压力位、突破位
3. **形态识别** - 头肩顶/底、双顶/底、三角形、旗形等
4. **量价关系** - 放量/缩量，量价配合情况
5. **技术指标** - 均线、MACD、KDJ 等信号
6. **交易建议** - 入场点、止损位、目标位

请基于数据给出客观分析，并标注置信度。"""


KLINE_IMAGE_SYSTEM = """你是一位专业的技术分析师，擅长从 K 线图中识别交易机会。

请分析图片中的 K 线走势：

1. **整体趋势** - 描述当前趋势方向和阶段
2. **形态识别** - 识别图中的技术形态
3. **关键位置** - 标注重要的支撑和压力
4. **量能分析** - 如果有成交量，分析量价关系
5. **交易建议** - 给出操作建议和风险提示

请用专业但易懂的语言进行分析。"""


KLINE_DATA_TEMPLATE = """
## K 线数据分析

**合约**: {symbol}
**周期**: {interval}
**数据范围**: {start_time} ~ {end_time}
**K线数量**: {count} 根

### 最近 {recent_count} 根 K 线

{kline_table}

### 统计信息

- 最高价: {high_max}
- 最低价: {low_min}
- 价格波动: {price_range} ({price_range_pct}%)
- 平均成交量: {avg_volume}

---

请按照「{strategy}」策略进行分析，给出交易建议。
"""


def format_kline_prompt(
    kline_data: list[dict],
    symbol: str = "",
    interval: str = "",
    strategy: str = "趋势跟踪",
    recent_count: int = 20,
) -> str:
    """
    格式化 K 线数据为提示词

    Parameters
    ----------
    kline_data : list[dict]
        K 线数据列表，每条包含 datetime, open, high, low, close, volume
    symbol : str
        合约代码
    interval : str
        时间周期
    strategy : str
        分析策略
    recent_count : int
        显示最近 N 根 K 线

    Returns
    -------
    str
        格式化后的提示词
    """
    if not kline_data:
        return "无 K 线数据"

    # 取最近的数据
    recent_data = kline_data[-recent_count:] if len(kline_data) > recent_count else kline_data

    # 构建表格
    lines = ["| 时间 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |"]
    lines.append("|------|------|------|------|------|--------|")

    for bar in recent_data:
        dt = bar.get("datetime", "")
        if hasattr(dt, "strftime"):
            dt = dt.strftime("%m-%d %H:%M")
        lines.append(
            f"| {dt} | {bar.get('open', 0):.2f} | "
            f"{bar.get('high', 0):.2f} | {bar.get('low', 0):.2f} | "
            f"{bar.get('close', 0):.2f} | {bar.get('volume', 0):.0f} |"
        )

    kline_table = "\n".join(lines)

    # 统计信息
    all_highs = [bar.get("high", 0) for bar in kline_data]
    all_lows = [bar.get("low", 0) for bar in kline_data]
    all_volumes = [bar.get("volume", 0) for bar in kline_data]

    high_max = max(all_highs) if all_highs else 0
    low_min = min(all_lows) if all_lows else 0
    price_range = high_max - low_min
    price_range_pct = (price_range / low_min * 100) if low_min > 0 else 0
    avg_volume = sum(all_volumes) / len(all_volumes) if all_volumes else 0

    # 时间范围
    start_time = kline_data[0].get("datetime", "")
    end_time = kline_data[-1].get("datetime", "")
    if hasattr(start_time, "strftime"):
        start_time = start_time.strftime("%Y-%m-%d %H:%M")
    if hasattr(end_time, "strftime"):
        end_time = end_time.strftime("%Y-%m-%d %H:%M")

    return KLINE_DATA_TEMPLATE.format(
        symbol=symbol or "未知",
        interval=interval or "未知",
        start_time=start_time,
        end_time=end_time,
        count=len(kline_data),
        recent_count=len(recent_data),
        kline_table=kline_table,
        high_max=f"{high_max:.2f}",
        low_min=f"{low_min:.2f}",
        price_range=f"{price_range:.2f}",
        price_range_pct=f"{price_range_pct:.2f}",
        avg_volume=f"{avg_volume:.0f}",
        strategy=strategy,
    )


__all__ = [
    "KLINE_ANALYSIS_SYSTEM",
    "KLINE_IMAGE_SYSTEM",
    "KLINE_DATA_TEMPLATE",
    "format_kline_prompt",
]
