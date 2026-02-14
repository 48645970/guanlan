# -*- coding: utf-8 -*-
"""
观澜量化 - 图表分析提示词

用于技术指标分析的系统提示词和用户提示词构建。

Author: 海山观澜
"""


CHART_ANALYSIS_SYSTEM = """你是专业的量化交易分析师。
根据提供的技术指标状态，分析当前市场趋势并给出交易建议。

必须返回严格的 JSON 格式，不要包含任何其他文本：
{
  "趋势方向": "多头" | "空头" | "震荡",
  "趋势强度": 1-5 (整数),
  "操作建议": "做多" | "做空" | "观望",
  "开仓点位": 建议的入场价格 (float, 观望时为 null),
  "止损价": 建议的止损价格 (float, 观望时为 null),
  "止盈价": 建议的止盈价格 (float, 观望时为 null),
  "支撑位": 当前支撑位 (float),
  "压力位": 当前压力位 (float),
  "分析详情": "详细的技术分析说明 (string)"
}

分析要点：
1. 综合多个指标判断趋势方向和强度
2. 开仓点位应基于当前价格和趋势判断，略优于当前价
3. 止损价要合理，一般为开仓价的 2-3% 左右
4. 止盈价要符合风险收益比，建议至少 1:2 (止盈距离是止损距离的 2 倍)
5. 支撑位和压力位基于技术指标计算，如布林带、均线等
6. 如果建议观望，开仓/止损/止盈设为 null
7. 分析详情要简洁专业，重点说明判断依据

示例输出：
{
  "趋势方向": "多头",
  "趋势强度": 4,
  "操作建议": "做多",
  "开仓点位": 1235.5,
  "止损价": 1220.0,
  "止盈价": 1265.0,
  "支撑位": 1230.0,
  "压力位": 1250.0,
  "分析详情": "MACD 金叉且位于零轴上方，DIF 和 DEA 均向上发散，显示多头动能强劲。MA5 上穿 MA20 形成金叉，短期均线多头排列。建议在 1235.5 附近做多，止损设在 MA20 下方 1220.0，目标价位 1265.0。"
}
"""


def format_chart_analysis_prompt(state: dict, symbol: str, current_price: float) -> str:
    """构建图表分析用户提示词

    Parameters
    ----------
    state : dict
        指标状态字典，格式：
        {
            "指标名": {
                "values": {"线名": 数值, ...},
                "signal": {"type": "long/short", "text": "信号描述"} | None
            },
            ...
        }
    symbol : str
        合约代码
    current_price : float
        当前价格

    Returns
    -------
    str
        用户提示词

    Examples
    --------
    >>> state = {
    ...     "MACD": {
    ...         "values": {"DIF": 0.52, "DEA": 0.31, "MACD": 0.21},
    ...         "signal": {"type": "long", "text": "MACD金叉"}
    ...     },
    ...     "双均线交叉": {
    ...         "values": {"MA5": 1234.5, "MA20": 1230.2},
    ...         "signal": {"type": "long", "text": "金叉"}
    ...     }
    ... }
    >>> prompt = format_chart_analysis_prompt(state, "rb2505", 1235.0)
    """
    lines = [
        f"合约: {symbol}",
        f"当前价格: {current_price:.2f}",
        "",
        "技术指标状态:",
    ]

    for name, data in state.items():
        # 格式化数值
        values = data.get("values", {})
        values_parts = []
        for k, v in values.items():
            if v is not None:
                values_parts.append(f"{k}={v:.2f}")
            else:
                values_parts.append(f"{k}=None")
        values_str = ", ".join(values_parts)

        # 格式化信号
        signal = data.get("signal")
        if signal:
            signal_type = signal.get("type", "")
            signal_text = signal.get("text", "")
            signal_str = f"{signal_text} ({signal_type})"
        else:
            signal_str = "无信号"

        lines.append(f"- {name}: {values_str} | 信号: {signal_str}")

    lines.append("")
    lines.append("请基于以上指标状态，返回 JSON 格式的分析结果。")

    return "\n".join(lines)
