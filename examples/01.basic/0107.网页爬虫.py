# -*- coding: utf-8 -*-
"""
期货行情爬虫示例

演示 requests 库获取网络数据：
- HTTP 请求头设置
- 新浪期货行情接口
- 数据解析处理

使用前需要：
1. pip install requests

Author: 海山观澜
"""

import time


def get_sina_future_quote(symbol: str) -> dict | None:
    """
    获取新浪期货实时行情

    Args:
        symbol: 合约代码，如 rb2501, au2412

    Returns:
        行情数据字典，失败返回 None

    数据来源:
        http://vip.stock.finance.sina.com.cn/quotes_service/view/qihuohangqing.html
    """
    try:
        import requests
    except ImportError:
        print("请先安装 requests: pip install requests")
        return None

    # 构造请求 URL
    subscribe_code = f"nf_{symbol}"
    timestamp = round(time.time() * 1000)
    url = f"https://hq.sinajs.cn/rn={timestamp}&list={subscribe_code}"

    # 请求头（模拟浏览器 - 2025年需要正确的 Referer）
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Host": "hq.sinajs.cn",
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        # 解析响应数据
        # 格式: var hq_str_nf_rb2501="螺纹钢2501,150000,3690.000,...";
        text = response.text.strip()
        if "=" not in text or '""' in text:
            print(f"未找到合约 {symbol} 的数据")
            return None

        # 提取数据部分
        data_str = text.split("=")[1].strip('"').strip(";").strip('"')
        fields = data_str.split(",")

        if len(fields) < 18:
            print(f"数据格式异常: {text[:100]}")
            return None

        # 解析为字典
        quote = {
            "name": fields[0],           # 名称
            "open": float(fields[2]),    # 开盘价
            "high": float(fields[3]),    # 最高价
            "low": float(fields[4]),     # 最低价
            "pre_close": float(fields[5]),  # 昨收
            "bid": float(fields[6]),     # 买一价
            "ask": float(fields[7]),     # 卖一价
            "last": float(fields[8]),    # 最新价
            "settle": float(fields[9]),  # 结算价
            "pre_settle": float(fields[10]),  # 昨结算
            "bid_vol": int(fields[11]),  # 买一量
            "ask_vol": int(fields[12]),  # 卖一量
            "open_interest": float(fields[13]),  # 持仓量
            "volume": int(fields[14]),   # 成交量
            "exchange": fields[15],      # 交易所
            "product": fields[16],       # 品种
            "date": fields[17],          # 日期
        }
        return quote

    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except (IndexError, ValueError) as e:
        print(f"解析失败: {e}")
        return None


def main():
    print("=" * 50)
    print("期货行情爬虫示例")
    print("=" * 50)

    # 测试合约列表（使用主力连续合约：品种大写+0）
    # RB-螺纹钢, AU-黄金, CU-铜, AG-白银, AL-铝
    symbols = ["AU0", "AG0", "CU0", "AL0"]

    for symbol in symbols:
        print(f"\n获取 {symbol} 行情...")
        quote = get_sina_future_quote(symbol)

        if quote:
            print(f"  品种: {quote['product']} ({quote['name']})")
            print(f"  最新: {quote['last']:.2f}")
            print(f"  涨跌: {quote['last'] - quote['pre_settle']:+.2f}")
            print(f"  开盘: {quote['open']:.2f}  最高: {quote['high']:.2f}")
            print(f"  最低: {quote['low']:.2f}  昨结: {quote['pre_settle']:.2f}")
            print(f"  成交: {quote['volume']}  持仓: {quote['open_interest']:.0f}")

    print("\n爬虫示例完成！")


if __name__ == "__main__":
    main()
