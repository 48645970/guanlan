# -*- coding: utf-8 -*-
"""
MyTT 技术指标库演示

演示使用 MyTT 库计算各类技术指标：
- 核心函数：MA, EMA, REF, HHV, LLV, CROSS 等
- 趋势指标：MACD, EXPMA, BOLL
- 震荡指标：KDJ, RSI, CCI, WR
- 其他指标：ATR, OBV, BIAS

MyTT 是通达信/同花顺指标公式的 Python 实现，
不依赖 ta-lib，纯 Python 代码，高性能。

依赖安装:
    pip install MyTT

Author: 海山观澜
"""

import numpy as np

try:
    from MyTT import (
        # 核心函数
        MA, EMA, SMA, REF,
        HHV, LLV, STD,
        SUM, COUNT, CROSS,
        IF, MAX, MIN, ABS,
        SLOPE, BARSLAST,
        # 技术指标
        MACD, KDJ, RSI, BOLL,
        CCI, WR, ATR, BIAS,
        OBV, EXPMA, BBI, PSY,
        MTM, ROC, TRIX, MFI,
    )
    HAS_MYTT = True
except ImportError:
    HAS_MYTT = False


def generate_sample_data(days=100):
    """生成模拟K线数据"""
    np.random.seed(42)

    # 模拟价格走势
    base_price = 100.0
    returns = np.random.randn(days) * 0.02  # 2% 日波动
    close = base_price * np.cumprod(1 + returns)

    # 生成 OHLC
    high = close * (1 + np.abs(np.random.randn(days)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(days)) * 0.01)
    open_price = (close + np.roll(close, 1)) / 2
    open_price[0] = base_price

    # 成交量
    volume = np.random.randint(100000, 500000, days).astype(float)

    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def demo_core_functions():
    """演示核心函数"""
    print("=" * 60)
    print("1. 核心函数演示")
    print("=" * 60)

    data = generate_sample_data(50)
    close = data["close"]
    high = data["high"]
    low = data["low"]

    print("\n【移动平均线】")
    ma5 = MA(close, 5)
    ma10 = MA(close, 10)
    ema12 = EMA(close, 12)
    print(f"  最新收盘价: {close[-1]:.2f}")
    print(f"  MA5: {ma5[-1]:.2f}")
    print(f"  MA10: {ma10[-1]:.2f}")
    print(f"  EMA12: {ema12[-1]:.2f}")

    print("\n【历史引用 REF】")
    print(f"  昨日收盘: {REF(close, 1)[-1]:.2f}")
    print(f"  3日前收盘: {REF(close, 3)[-1]:.2f}")

    print("\n【极值函数】")
    print(f"  10日最高价: {HHV(high, 10)[-1]:.2f}")
    print(f"  10日最低价: {LLV(low, 10)[-1]:.2f}")
    print(f"  20日标准差: {STD(close, 20)[-1]:.2f}")

    print("\n【条件统计】")
    up_days = COUNT(close > REF(close, 1), 10)
    print(f"  近10日上涨天数: {int(up_days[-1])}")

    print("\n【金叉判断 CROSS】")
    golden_cross = CROSS(ma5, ma10)
    death_cross = CROSS(ma10, ma5)
    last_golden = BARSLAST(golden_cross)
    print(f"  MA5上穿MA10(金叉): {bool(golden_cross[-1])}")
    print(f"  MA10上穿MA5(死叉): {bool(death_cross[-1])}")
    if not np.isnan(last_golden[-1]):
        print(f"  距上次金叉: {int(last_golden[-1])} 天")


def demo_trend_indicators():
    """演示趋势指标"""
    print("\n" + "=" * 60)
    print("2. 趋势指标演示")
    print("=" * 60)

    data = generate_sample_data(100)
    close = data["close"]
    high = data["high"]
    low = data["low"]

    print("\n【MACD 指标】")
    dif, dea, macd = MACD(close, 12, 26, 9)
    print(f"  DIF (快线): {dif[-1]:.4f}")
    print(f"  DEA (慢线): {dea[-1]:.4f}")
    print(f"  MACD 柱状: {macd[-1]:.4f}")

    # 判断 MACD 状态
    if dif[-1] > dea[-1]:
        print("  状态: DIF > DEA, 多头趋势")
    else:
        print("  状态: DIF < DEA, 空头趋势")

    print("\n【布林带 BOLL】")
    upper, mid, lower = BOLL(close, 20, 2)
    print(f"  上轨: {upper[-1]:.2f}")
    print(f"  中轨: {mid[-1]:.2f}")
    print(f"  下轨: {lower[-1]:.2f}")
    print(f"  当前价: {close[-1]:.2f}")

    # 判断布林位置
    if close[-1] > upper[-1]:
        print("  位置: 超买区域（价格在上轨之上）")
    elif close[-1] < lower[-1]:
        print("  位置: 超卖区域（价格在下轨之下）")
    else:
        pct = (close[-1] - lower[-1]) / (upper[-1] - lower[-1]) * 100
        print(f"  位置: 通道内 {pct:.1f}%")

    print("\n【EXPMA 指标】")
    exp1, exp2 = EXPMA(close, 12, 50)
    print(f"  EXPMA12: {exp1[-1]:.2f}")
    print(f"  EXPMA50: {exp2[-1]:.2f}")


def demo_oscillator_indicators():
    """演示震荡指标"""
    print("\n" + "=" * 60)
    print("3. 震荡指标演示")
    print("=" * 60)

    data = generate_sample_data(100)
    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]

    print("\n【KDJ 指标】")
    k, d, j = KDJ(close, high, low, 9, 3, 3)
    print(f"  K值: {k[-1]:.2f}")
    print(f"  D值: {d[-1]:.2f}")
    print(f"  J值: {j[-1]:.2f}")

    # 判断超买超卖
    if j[-1] > 100:
        print("  状态: 超买（J > 100）")
    elif j[-1] < 0:
        print("  状态: 超卖（J < 0）")
    elif k[-1] > d[-1]:
        print("  状态: 多头（K > D）")
    else:
        print("  状态: 空头（K < D）")

    print("\n【RSI 指标】")
    rsi6 = RSI(close, 6)
    rsi12 = RSI(close, 12)
    rsi24 = RSI(close, 24)
    print(f"  RSI6: {rsi6[-1]:.2f}")
    print(f"  RSI12: {rsi12[-1]:.2f}")
    print(f"  RSI24: {rsi24[-1]:.2f}")

    # 判断 RSI 状态
    if rsi6[-1] > 80:
        print("  状态: 超买区域")
    elif rsi6[-1] < 20:
        print("  状态: 超卖区域")
    else:
        print("  状态: 正常区域")

    print("\n【CCI 指标】")
    cci = CCI(close, high, low, 14)
    print(f"  CCI: {cci[-1]:.2f}")
    if cci[-1] > 100:
        print("  状态: 超买（CCI > 100）")
    elif cci[-1] < -100:
        print("  状态: 超卖（CCI < -100）")
    else:
        print("  状态: 震荡区间")

    print("\n【WR 威廉指标】")
    wr1, wr2 = WR(close, high, low, 10, 6)
    print(f"  WR10: {wr1[-1]:.2f}")
    print(f"  WR6: {wr2[-1]:.2f}")

    print("\n【PSY 心理线】")
    psy, psyma = PSY(close, 12, 6)
    print(f"  PSY: {psy[-1]:.2f}")
    print(f"  PSYMA: {psyma[-1]:.2f}")


def demo_other_indicators():
    """演示其他指标"""
    print("\n" + "=" * 60)
    print("4. 其他常用指标")
    print("=" * 60)

    data = generate_sample_data(100)
    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]

    print("\n【ATR 真实波幅】")
    atr = ATR(close, high, low, 14)
    print(f"  ATR14: {atr[-1]:.4f}")
    print(f"  波动率: {atr[-1] / close[-1] * 100:.2f}%")

    print("\n【BIAS 乖离率】")
    bias1, bias2, bias3 = BIAS(close, 6, 12, 24)
    print(f"  BIAS6: {bias1[-1]:.2f}%")
    print(f"  BIAS12: {bias2[-1]:.2f}%")
    print(f"  BIAS24: {bias3[-1]:.2f}%")

    print("\n【OBV 能量潮】")
    obv = OBV(close, volume)
    print(f"  OBV: {obv[-1]:,.0f}")

    print("\n【BBI 多空指标】")
    bbi = BBI(close, 3, 6, 12, 20)
    print(f"  BBI: {bbi[-1]:.2f}")
    if close[-1] > bbi[-1]:
        print("  状态: 价格在BBI上方，多头")
    else:
        print("  状态: 价格在BBI下方，空头")

    print("\n【MTM 动量指标】")
    mtm, mtmma = MTM(close, 12, 6)
    print(f"  MTM: {mtm[-1]:.4f}")
    print(f"  MTMMA: {mtmma[-1]:.4f}")

    print("\n【ROC 变动率】")
    roc, rocma = ROC(close, 12, 6)
    print(f"  ROC: {roc[-1]:.2f}%")
    print(f"  ROCMA: {rocma[-1]:.2f}%")


def demo_tongdaxin_formula():
    """演示通达信公式转换"""
    print("\n" + "=" * 60)
    print("5. 通达信公式转换示例")
    print("=" * 60)

    data = generate_sample_data(100)
    CLOSE = data["close"]
    HIGH = data["high"]
    LOW = data["low"]
    OPEN = data["open"]
    VOL = data["volume"]

    print("\n通达信公式写法 vs Python (MyTT) 写法:")
    print("-" * 60)

    # 示例1: 连续上涨
    print("\n【连续上涨判断】")
    print("  通达信: VAR1:=C>REF(C,1) AND C>REF(C,2);")
    print("  Python: VAR1 = (CLOSE>REF(CLOSE,1)) & (CLOSE>REF(CLOSE,2))")
    VAR1 = (CLOSE > REF(CLOSE, 1)) & (CLOSE > REF(CLOSE, 2))
    print(f"  结果: 今日是否连续两天上涨 = {bool(VAR1[-1])}")

    # 示例2: 放量上涨
    print("\n【放量上涨】")
    print("  通达信: 放量上涨:=C>REF(C,1) AND V>REF(V,1)*1.5;")
    print("  Python: 放量上涨 = (CLOSE>REF(CLOSE,1)) & (VOL>REF(VOL,1)*1.5)")
    放量上涨 = (CLOSE > REF(CLOSE, 1)) & (VOL > REF(VOL, 1) * 1.5)
    print(f"  结果: 今日是否放量上涨 = {bool(放量上涨[-1])}")

    # 示例3: 突破N日新高
    print("\n【突破20日新高】")
    print("  通达信: 突破新高:=C>=HHV(H,20);")
    print("  Python: 突破新高 = CLOSE >= HHV(HIGH, 20)")
    突破新高 = CLOSE >= HHV(HIGH, 20)
    print(f"  结果: 今日是否突破20日新高 = {bool(突破新高[-1])}")

    # 示例4: MACD金叉
    print("\n【MACD金叉】")
    print("  通达信: 金叉:=CROSS(DIF,DEA);")
    print("  Python: DIF,DEA,_=MACD(CLOSE); 金叉=CROSS(DIF,DEA)")
    DIF, DEA, _ = MACD(CLOSE, 12, 26, 9)
    MACD金叉 = CROSS(DIF, DEA)
    print(f"  结果: 今日是否MACD金叉 = {bool(MACD金叉[-1])}")

    # 示例5: 自定义选股公式
    print("\n【综合选股条件】")
    print("  通达信公式:")
    print("    MA5:=MA(C,5);")
    print("    MA10:=MA(C,10);")
    print("    MA20:=MA(C,20);")
    print("    多头排列:=MA5>MA10 AND MA10>MA20;")
    print("    RSI低位:=RSI(C,6)<30;")
    print("    选股:=多头排列 AND RSI低位;")

    MA5 = MA(CLOSE, 5)
    MA10 = MA(CLOSE, 10)
    MA20 = MA(CLOSE, 20)
    多头排列 = (MA5 > MA10) & (MA10 > MA20)
    RSI低位 = RSI(CLOSE, 6) < 30
    选股 = 多头排列 & RSI低位

    print(f"\n  Python结果:")
    print(f"    MA5={MA5[-1]:.2f}, MA10={MA10[-1]:.2f}, MA20={MA20[-1]:.2f}")
    print(f"    多头排列: {bool(多头排列[-1])}")
    print(f"    RSI6: {RSI(CLOSE, 6)[-1]:.2f}, RSI低位: {bool(RSI低位[-1])}")
    print(f"    符合选股条件: {bool(选股[-1])}")


def demo_practical_usage():
    """演示实际应用场景"""
    print("\n" + "=" * 60)
    print("6. 实际应用场景")
    print("=" * 60)

    data = generate_sample_data(100)
    CLOSE = data["close"]
    HIGH = data["high"]
    LOW = data["low"]
    VOL = data["volume"]

    print("\n【综合技术分析报告】")
    print("-" * 40)

    # 趋势分析
    ma5 = MA(CLOSE, 5)
    ma10 = MA(CLOSE, 10)
    ma20 = MA(CLOSE, 20)

    print(f"当前价格: {CLOSE[-1]:.2f}")
    print(f"\n趋势指标:")
    print(f"  MA5: {ma5[-1]:.2f}")
    print(f"  MA10: {ma10[-1]:.2f}")
    print(f"  MA20: {ma20[-1]:.2f}")

    if ma5[-1] > ma10[-1] > ma20[-1]:
        print("  均线状态: 多头排列 ↑")
    elif ma5[-1] < ma10[-1] < ma20[-1]:
        print("  均线状态: 空头排列 ↓")
    else:
        print("  均线状态: 震荡整理 ─")

    # MACD
    dif, dea, macd = MACD(CLOSE, 12, 26, 9)
    print(f"\nMACD:")
    print(f"  DIF: {dif[-1]:.4f}")
    print(f"  DEA: {dea[-1]:.4f}")
    if dif[-1] > dea[-1] and dif[-1] > 0:
        print("  信号: 强势多头")
    elif dif[-1] > dea[-1]:
        print("  信号: 弱势多头")
    elif dif[-1] < 0:
        print("  信号: 强势空头")
    else:
        print("  信号: 弱势空头")

    # 超买超卖
    rsi = RSI(CLOSE, 6)
    k, d, j = KDJ(CLOSE, HIGH, LOW, 9, 3, 3)

    print(f"\n超买超卖:")
    print(f"  RSI6: {rsi[-1]:.2f}", end="")
    if rsi[-1] > 80:
        print(" (超买)")
    elif rsi[-1] < 20:
        print(" (超卖)")
    else:
        print(" (正常)")

    print(f"  KDJ-J: {j[-1]:.2f}", end="")
    if j[-1] > 100:
        print(" (超买)")
    elif j[-1] < 0:
        print(" (超卖)")
    else:
        print(" (正常)")

    # 波动率
    atr = ATR(CLOSE, HIGH, LOW, 14)
    upper, mid, lower = BOLL(CLOSE, 20, 2)
    boll_width = (upper[-1] - lower[-1]) / mid[-1] * 100

    print(f"\n波动率:")
    print(f"  ATR14: {atr[-1]:.4f} ({atr[-1]/CLOSE[-1]*100:.2f}%)")
    print(f"  布林带宽: {boll_width:.2f}%")

    # 总结
    print("\n" + "-" * 40)
    score = 0
    reasons = []

    if ma5[-1] > ma10[-1] > ma20[-1]:
        score += 2
        reasons.append("均线多头+2")
    elif ma5[-1] < ma10[-1] < ma20[-1]:
        score -= 2
        reasons.append("均线空头-2")

    if dif[-1] > dea[-1]:
        score += 1
        reasons.append("MACD多头+1")
    else:
        score -= 1
        reasons.append("MACD空头-1")

    if rsi[-1] < 30:
        score += 1
        reasons.append("RSI超卖+1")
    elif rsi[-1] > 70:
        score -= 1
        reasons.append("RSI超买-1")

    print(f"综合评分: {score:+d}")
    print(f"评分依据: {', '.join(reasons)}")


def main():
    print("=" * 60)
    print("MyTT 技术指标库演示")
    print("=" * 60)

    if not HAS_MYTT:
        print("\n[错误] 未安装 MyTT 库")
        print("安装方法: pip install MyTT")
        print("\nMyTT 是通达信公式的 Python 实现")
        print("GitHub: https://github.com/mpquant/MyTT")
        return

    print("\nMyTT 将通达信、同花顺等指标公式移植到 Python")
    print("核心优势: 不依赖 ta-lib，纯 Python 实现，高性能")

    # 运行各项演示
    demo_core_functions()
    demo_trend_indicators()
    demo_oscillator_indicators()
    demo_other_indicators()
    demo_tongdaxin_formula()
    demo_practical_usage()

    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
