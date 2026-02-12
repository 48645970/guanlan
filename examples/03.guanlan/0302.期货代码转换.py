# -*- coding: utf-8 -*-
"""
观澜量化 - 期货代码转换演示

Author: 海山观澜
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from guanlan.core.constants import Exchange
from guanlan.core.utils.symbol_converter import SymbolConverter


def demo_basic_usage():
    """基础使用示例"""
    print("\n" + "=" * 60)
    print("基础使用示例")
    print("=" * 60)

    # 场景1: 从CTP接收行情数据，转换为统一格式存储
    print("\n场景1: CTP返回的行情数据，转为统一格式")
    ctp_symbol = "rb2505"  # CTP返回的原始格式
    standard_symbol = SymbolConverter.to_standard(ctp_symbol, Exchange.SHFE)
    print(f"  CTP格式: {ctp_symbol}")
    print(f"  统一格式: {standard_symbol}")

    # 场景2: 发送订单到交易所，转换为交易所格式
    print("\n场景2: 发送订单到交易所，转为交易所格式")
    user_input = "RB2505"  # 用户输入的统一格式
    exchange_symbol = SymbolConverter.to_exchange(user_input, Exchange.SHFE)
    print(f"  统一格式: {user_input}")
    print(f"  交易所格式: {exchange_symbol}")

    # 场景3: 提取品种信息
    print("\n场景3: 提取品种代码")
    commodity = SymbolConverter.extract_commodity("RB2505")
    print(f"  合约代码: RB2505")
    print(f"  品种代码: {commodity}")

    # 场景4: 提取年月信息
    print("\n场景4: 提取年月信息")
    year, month = SymbolConverter.extract_date("RB2505")
    print(f"  合约代码: RB2505")
    print(f"  年月信息: 20{year}年{month}月")

    # 场景5: 验证格式
    print("\n场景5: 验证格式")
    is_valid = SymbolConverter.validate("rb2505", Exchange.SHFE)
    print(f"  合约代码: rb2505")
    print(f"  格式验证: {'有效' if is_valid else '无效'}")


def demo_all_exchanges():
    """各交易所转换示例"""
    print("\n" + "=" * 60)
    print("各交易所转换示例")
    print("=" * 60)

    exchanges = [
        ("上期所", "rb2505", Exchange.SHFE),
        ("大商所", "i2505", Exchange.DCE),
        ("郑商所", "TA505", Exchange.CZCE),
        ("中金所", "IF2412", Exchange.CFFEX),
        ("能源中心", "sc2505", Exchange.INE),
        ("广期所", "si2505", Exchange.GFEX),
    ]

    for name, exchange_symbol, exchange in exchanges:
        standard = SymbolConverter.to_standard(exchange_symbol, exchange)
        back = SymbolConverter.to_exchange(standard, exchange)
        print(f"\n{name} ({exchange.value}):")
        print(f"  交易所格式: {exchange_symbol}")
        print(f"  统一格式: {standard}")
        print(f"  转换回去: {back}")


def demo_czce_special():
    """郑商所特殊处理示例"""
    print("\n" + "=" * 60)
    print("郑商所特殊处理示例（3位 ↔ 4位转换）")
    print("=" * 60)

    czce_symbols = ["TA505", "MA509", "OI605", "RM501", "SR512"]

    for czce_symbol in czce_symbols:
        # 转为统一格式（4位）
        standard = SymbolConverter.to_standard(czce_symbol, Exchange.CZCE)
        print(f"\n{czce_symbol} (CZCE 3位) -> {standard} (统一 4位)")

        # 转回CZCE格式（3位）
        back = SymbolConverter.to_exchange(standard, Exchange.CZCE)
        print(f"{standard} (统一 4位) -> {back} (CZCE 3位)")


def demo_batch_processing():
    """批量处理示例"""
    print("\n" + "=" * 60)
    print("批量处理示例")
    print("=" * 60)

    # 批量转换CTP合约列表
    print("\n批量转换 SHFE 合约:")
    ctp_symbols = ["rb2505", "au2506", "cu2412", "ag2503"]

    standard_symbols = [
        SymbolConverter.to_standard(s, Exchange.SHFE)
        for s in ctp_symbols
    ]

    print(f"  CTP格式: {ctp_symbols}")
    print(f"  统一格式: {standard_symbols}")


def demo_error_handling():
    """错误处理示例"""
    print("\n" + "=" * 60)
    print("错误处理示例")
    print("=" * 60)

    def safe_convert(symbol: str, exchange: Exchange) -> str | None:
        """安全的转换函数，带错误处理"""
        try:
            return SymbolConverter.to_standard(symbol, exchange)
        except ValueError as e:
            print(f"  转换失败: {symbol} - {e}")
            return None

    # 测试各种错误情况
    print("\n测试错误输入:")

    # 空字符串
    safe_convert("", Exchange.SHFE)

    # 格式不匹配
    safe_convert("invalid", Exchange.SHFE)

    # 大小写错误
    result = SymbolConverter.validate("RB2505", Exchange.SHFE)
    print(f"  大小写错误 (RB2505 for SHFE): {'有效' if result else '无效'}")

    # 不支持的交易所
    try:
        SymbolConverter.to_standard("rb2505", Exchange.SSE)  # 股票交易所
    except ValueError as e:
        print(f"  不支持的交易所: {e}")


def demo_real_world_scenario():
    """真实场景模拟：模拟CTP数据处理流程"""
    print("\n" + "=" * 60)
    print("真实场景: 模拟CTP数据处理流程")
    print("=" * 60)

    # 模拟从CTP接收的合约列表
    print("\n步骤1: 从CTP接收合约数据")
    ctp_contracts = [
        {"symbol": "rb2505", "exchange": "SHFE", "last_price": 3850.0},
        {"symbol": "TA505", "exchange": "CZCE", "last_price": 5680.0},
        {"symbol": "IF2412", "exchange": "CFFEX", "last_price": 4123.5},
        {"symbol": "i2505", "exchange": "DCE", "last_price": 825.5},
    ]

    for contract in ctp_contracts:
        print(f"  {contract['symbol']}.{contract['exchange']} - 价格: {contract['last_price']}")

    # 转换为统一格式存储
    print("\n步骤2: 转换为统一格式存储")
    standard_contracts = []
    for contract in ctp_contracts:
        exchange = Exchange(contract["exchange"])
        standard_symbol = SymbolConverter.to_standard(contract["symbol"], exchange)
        standard_contracts.append({
            "symbol": standard_symbol,
            "exchange": exchange,
            "last_price": contract["last_price"]
        })
        print(f"  {standard_symbol}.{exchange.value} - 价格: {contract['last_price']}")

    # 模拟用户下单
    print("\n步骤3: 用户下单 (使用统一格式)")
    user_order = {
        "symbol": "RB2505",
        "exchange": Exchange.SHFE,
        "direction": "买入",
        "price": 3851.0,
        "volume": 1
    }
    print(f"  用户订单: {user_order['symbol']} {user_order['direction']} @{user_order['price']}")

    # 转换为交易所格式发送给CTP
    print("\n步骤4: 转换为交易所格式发送给CTP")
    exchange_symbol = SymbolConverter.to_exchange(user_order["symbol"], user_order["exchange"])
    ctp_order = {
        "symbol": exchange_symbol,
        "exchange": user_order["exchange"].value,
        "direction": user_order["direction"],
        "price": user_order["price"],
        "volume": user_order["volume"]
    }
    print(f"  CTP订单: {ctp_order['symbol']}.{ctp_order['exchange']} {ctp_order['direction']} @{ctp_order['price']}")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print(" SymbolConverter 使用示例")
    print(" 期货代码转换工具演示")
    print("=" * 60)

    demo_basic_usage()
    demo_all_exchanges()
    demo_czce_special()
    demo_batch_processing()
    demo_error_handling()
    demo_real_world_scenario()

    print("\n" + "=" * 60)
    print("示例演示完成！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
