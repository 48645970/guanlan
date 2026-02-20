# -*- coding: utf-8 -*-
"""
AKShare 期货历史行情数据

演示使用 AKShare 获取期货历史行情：
1. 期货品种列表查询
2. 主力连续合约日线数据
3. 指定合约日线数据
4. 分钟级别数据（1/5/15/30/60 分钟）
5. 数据格式转换（统一为 VnPy BarData 格式）

AKShare 完全免费开源，数据来自新浪财经、东方财富等公开源。

接口列名参考：
  futures_main_sina:      日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 持仓量, 动态结算价
  futures_zh_daily_sina:  date, open, high, low, close, volume, hold, settle
  futures_zh_minute_sina: datetime, open, high, low, close, volume, hold

依赖安装:
    pip install akshare

Author: 海山观澜
"""

import sys
from datetime import datetime, timedelta

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("请先安装 akshare:")
    print("  pip install akshare")
    sys.exit(1)


# ── 1. 期货品种信息 ──


def demo_symbol_info():
    """查询期货品种列表"""
    print("=" * 60)
    print("1. 期货品种信息")
    print("=" * 60)

    df = ak.futures_symbol_mark()
    print(f"\n期货品种命名表（前 20 个）:")
    print(df.head(20).to_string(index=False))
    print(f"\n共 {len(df)} 个品种")


# ── 2. 主力连续合约日线 ──


def demo_main_contract():
    """获取主力连续合约日线数据

    futures_main_sina 列名:
      日期, 开盘价, 最高价, 最低价, 收盘价, 成交量, 持仓量, 动态结算价
    """
    print("\n" + "=" * 60)
    print("2. 主力连续合约日线（新浪财经）")
    print("=" * 60)

    symbol = "RB0"  # 品种代码 + 0 = 主力连续
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

    print(f"\n品种: 螺纹钢主力连续 ({symbol})")
    print(f"区间: {start_date} ~ {end_date}")

    df = ak.futures_main_sina(symbol=symbol, start_date=start_date, end_date=end_date)

    if df.empty:
        print("  未获取到数据")
        return

    print(f"数据量: {len(df)} 条")
    print(f"列名: {list(df.columns)}")
    print(f"\n最近 5 条:")
    print(df.tail().to_string(index=False))

    print(f"\n价格统计:")
    print(f"  最高: {df['收盘价'].max():.0f}")
    print(f"  最低: {df['收盘价'].min():.0f}")
    print(f"  均值: {df['收盘价'].mean():.0f}")


# ── 3. 指定合约日线 ──


def demo_contract_daily():
    """获取指定合约日线数据

    futures_zh_daily_sina 列名:
      date, open, high, low, close, volume, hold, settle
    """
    print("\n" + "=" * 60)
    print("3. 指定合约日线（新浪财经）")
    print("=" * 60)

    # 动态生成近月合约代码
    now = datetime.now()
    month = now.month + 2
    year = now.year
    if month > 12:
        month -= 12
        year += 1
    symbol = f"RB{year % 100:02d}{month:02d}"

    print(f"\n合约: {symbol}")

    df = ak.futures_zh_daily_sina(symbol=symbol)

    if df.empty:
        print("  未获取到数据")
        return

    # 按日期筛选最近 60 天
    df["date"] = pd.to_datetime(df["date"])
    cutoff = datetime.now() - timedelta(days=60)
    df = df[df["date"] >= cutoff]

    print(f"数据量: {len(df)} 条（最近 60 天）")
    print(f"列名: {list(df.columns)}")
    print(f"\n最近 5 条:")
    print(df.tail().to_string(index=False))


# ── 4. 分钟级别数据 ──


def demo_minute_data():
    """获取分钟级别数据

    futures_zh_minute_sina 列名:
      datetime, open, high, low, close, volume, hold
    """
    print("\n" + "=" * 60)
    print("4. 分钟数据（新浪财经）")
    print("=" * 60)

    # 动态生成合约代码
    now = datetime.now()
    month = now.month + 2
    year = now.year
    if month > 12:
        month -= 12
        year += 1
    symbol = f"RB{year % 100:02d}{month:02d}"

    periods = {"1": "1分钟", "5": "5分钟", "15": "15分钟", "60": "60分钟"}

    for period, name in periods.items():
        print(f"\n  {name} K 线 ({symbol}):")
        try:
            df = ak.futures_zh_minute_sina(symbol=symbol, period=period)
            if df.empty:
                print("    未获取到数据")
                continue
            print(f"    数据量: {len(df)} 条")
            print(f"    最新 3 条:")
            for _, row in df.tail(3).iterrows():
                print(f"      {row['datetime']}  O={row['open']}  H={row['high']}  "
                      f"L={row['low']}  C={row['close']}  V={row['volume']}")
        except Exception as e:
            print(f"    获取失败: {e}")


# ── 5. 数据格式转换 ──


def demo_convert_format():
    """将 akshare 数据转换为 VnPy BarData 兼容格式"""
    print("\n" + "=" * 60)
    print("5. 数据格式转换（适配 VnPy BarData）")
    print("=" * 60)

    symbol = "RB0"
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    print(f"\n获取数据: {symbol} ({start_date} ~ {end_date})")
    df = ak.futures_main_sina(symbol=symbol, start_date=start_date, end_date=end_date)

    if df.empty:
        print("  未获取到数据")
        return

    # 转换为 VnPy BarData 兼容的 dict 格式
    bars = []
    for _, row in df.iterrows():
        bar = {
            "datetime": str(row["日期"]),
            "open": float(row["开盘价"]),
            "high": float(row["最高价"]),
            "low": float(row["最低价"]),
            "close": float(row["收盘价"]),
            "volume": float(row["成交量"]),
            "open_interest": float(row["持仓量"]),
        }
        bars.append(bar)

    print(f"转换完成: {len(bars)} 条")
    print(f"\n示例（最后一条）:")
    last = bars[-1]
    for k, v in last.items():
        print(f"  {k}: {v}")

    print(f"\n前 3 条:")
    for bar in bars[:3]:
        print(f"  {bar['datetime']}  O={bar['open']:.0f}  H={bar['high']:.0f}  "
              f"L={bar['low']:.0f}  C={bar['close']:.0f}  V={bar['volume']:.0f}")


# ── 6. 多品种批量获取 ──


def demo_multi_symbols():
    """批量获取多个品种的主力连续数据"""
    print("\n" + "=" * 60)
    print("6. 多品种批量获取")
    print("=" * 60)

    symbols = {
        "RB0": "螺纹钢",
        "HC0": "热卷",
        "I0": "铁矿石",
        "J0": "焦炭",
        "OI0": "菜籽油",
        "MA0": "甲醇",
    }

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    print(f"\n区间: {start_date} ~ {end_date}")
    print(f"\n  {'品种':<8} {'代码':<6} {'数据量':<8} {'最新收盘':<10} {'30日涨跌':<10}")
    print("  " + "-" * 50)

    for code, name in symbols.items():
        try:
            df = ak.futures_main_sina(symbol=code, start_date=start_date, end_date=end_date)
            if df.empty:
                print(f"  {name:<8} {code:<6} {'无数据':<8}")
                continue

            latest_close = float(df.iloc[-1]["收盘价"])
            first_close = float(df.iloc[0]["收盘价"])
            change_pct = (latest_close / first_close - 1) * 100

            print(f"  {name:<8} {code:<6} {len(df):<8} {latest_close:<10.0f} {change_pct:+.2f}%")
        except Exception as e:
            print(f"  {name:<8} {code:<6} 失败: {e}")


# ── 主函数 ──


def main():
    print("\n" + "=" * 60)
    print("AKShare 期货历史行情数据")
    print("=" * 60)

    try:
        demo_symbol_info()
        demo_main_contract()
        demo_contract_daily()
        demo_minute_data()
        demo_convert_format()
        demo_multi_symbols()

        print("\n" + "=" * 60)
        print("所有演示完成")
        print("=" * 60)
        print("\n常用品种代码（主力连续加 0）:")
        print("  RB0=螺纹钢  HC0=热卷  I0=铁矿石  J0=焦炭")
        print("  OI0=菜籽油  MA0=甲醇  AU0=黄金  AG0=白银")
        print("  IF0=沪深300  IC0=中证500  IM0=中证1000")
        print("\n数据说明:")
        print("  - 日线数据来自新浪财经，完全免费")
        print("  - 分钟数据量有限（约最近几百根）")
        print("  - 生产环境建议自行录制 CTP 行情积累数据")

    except Exception as e:
        print(f"\n演示过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    main()
