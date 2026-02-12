# -*- coding: utf-8 -*-
"""
观澜量化 - 通用工具函数演示

演示 core.utils.common 模块的各项功能

Author: 海山观澜
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guanlan.core.utils.common import (
    get_file_path,
    get_folder_path,
    random_string,
    formatted_datetime,
    formatted_date,
    to_digit_value,
    load_json_file,
    save_json_file,
    load_json_list,
    save_json_list,
    TEMP_DIR,
)


def demo_path():
    """演示路径处理"""
    print("=" * 60)
    print("1. get_file_path() & get_folder_path() - 配置文件路径管理")
    print("=" * 60)

    # 显示配置目录
    print(f"观澜配置目录: {TEMP_DIR}")
    print()

    # 获取配置文件路径
    config_path = get_file_path('config.json')
    print(f"配置文件路径: {config_path}")

    # 获取日志文件路径（带子目录）
    log_file = get_file_path('logs/app.log')
    print(f"日志文件路径: {log_file}")

    # 获取策略配置路径
    strategy_config = get_file_path('strategies/my_strategy.json')
    print(f"策略配置路径: {strategy_config}")

    print()

    # 获取文件夹路径（自动创建）
    logs_dir = get_folder_path('logs')
    print(f"日志目录: {logs_dir} (存在: {logs_dir.exists()})")

    strategies_dir = get_folder_path('strategies')
    print(f"策略目录: {strategies_dir} (存在: {strategies_dir.exists()})")

    data_dir = get_folder_path('data')
    print(f"数据目录: {data_dir} (存在: {data_dir.exists()})")

    print()


def demo_random_string():
    """演示随机字符串生成"""
    print("=" * 60)
    print("2. random_string() - 随机字符串生成")
    print("=" * 60)

    # 默认长度（8）
    str1 = random_string()
    print(f"默认长度(8): {str1}")

    # 自定义长度
    str2 = random_string(16)
    print(f"自定义长度(16): {str2}")

    # 短字符串
    str3 = random_string(4)
    print(f"短字符串(4): {str3}")

    # 长字符串（UUID 完整长度）
    str4 = random_string(36)
    print(f"完整 UUID(36): {str4}")

    # 错误处理演示
    try:
        invalid = random_string(50)
    except ValueError as e:
        print(f"错误处理: {e}")

    print()


def demo_datetime_format():
    """演示日期时间格式化"""
    print("=" * 60)
    print("3. formatted_datetime() & formatted_date() - 日期时间格式化")
    print("=" * 60)

    # 当前时间
    now_datetime = formatted_datetime()
    now_date = formatted_date()
    print(f"当前日期时间: {now_datetime}")
    print(f"当前日期: {now_date}")

    # 指定时间
    custom_dt = datetime(2025, 1, 1, 12, 30, 45)
    custom_datetime = formatted_datetime(custom_dt)
    custom_date = formatted_date(custom_dt)
    print(f"指定日期时间: {custom_datetime}")
    print(f"指定日期: {custom_date}")

    print()


def demo_digit_conversion():
    """演示数字类型转换"""
    print("=" * 60)
    print("4. to_digit_value() - 数字类型转换")
    print("=" * 60)

    test_cases = [
        # (输入, 小数位, 说明)
        ("123", 2, "整数字符串"),
        ("123.45", 2, "浮点数字符串"),
        ("-123.45", 2, "负数浮点数"),
        (123.456, 2, "浮点数(保留2位)"),
        (123.456, 4, "浮点数(保留4位)"),
        ("abc", 2, "非数字字符串"),
        ("123abc", 2, "混合字符串"),
        (0, 2, "零"),
        (-100, 2, "负整数"),
    ]

    for value, decimals, desc in test_cases:
        result = to_digit_value(value, decimals)
        result_type = type(result).__name__
        print(f"{desc:20s}: {str(value):15s} -> {result:15} (type: {result_type})")

    print()


def demo_json_operations():
    """演示 JSON 文件操作（字典类型）"""
    print("=" * 60)
    print("5. load_json_file() & save_json_file() - JSON 字典操作")
    print("=" * 60)

    # 测试文件名（自动保存到 .guanlan 目录）
    test_file = "test_config.json"

    # 保存数据
    test_data = {
        "app_name": "观澜量化",
        "version": "2.0",
        "features": ["策略引擎", "行情系统", "交易接口"],
        "settings": {
            "auto_start": True,
            "log_level": "INFO",
            "max_orders": 100,
        },
    }

    print(f"保存数据到: {get_file_path(test_file)}")
    save_json_file(test_file, test_data)
    print("保存成功！")

    # 加载数据
    print(f"\n从文件加载数据...")
    loaded_data = load_json_file(test_file)
    print("加载成功！")
    print(f"应用名称: {loaded_data.get('app_name')}")
    print(f"版本: {loaded_data.get('version')}")
    print(f"功能列表: {loaded_data.get('features')}")
    print(f"设置: {loaded_data.get('settings')}")

    # 加载不存在的文件（会自动创建空文件）
    print(f"\n加载不存在的文件...")
    empty_data = load_json_file("empty_config.json")
    print(f"返回空字典: {empty_data}")

    print()


def demo_json_list_operations():
    """演示 JSON 文件操作（列表类型）"""
    print("=" * 60)
    print("6. load_json_list() & save_json_list() - JSON 列表操作")
    print("=" * 60)

    # 测试文件名（自动保存到 .guanlan 目录）
    favorites_file = "test_favorites.json"

    # 保存收藏列表
    favorites_data = [
        "SHFE.rb2505",
        "SHFE.hc2505",
        "DCE.i2505",
        "CZCE.MA505",
        "CFFEX.IF2501",
    ]

    print(f"保存收藏列表到: {get_file_path(favorites_file)}")
    save_json_list(favorites_file, favorites_data)
    print("保存成功！")

    # 加载收藏列表
    print(f"\n从文件加载收藏列表...")
    loaded_favorites = load_json_list(favorites_file)
    print("加载成功！")
    print(f"收藏合约数量: {len(loaded_favorites)}")
    print(f"收藏列表:")
    for i, symbol in enumerate(loaded_favorites, 1):
        print(f"  {i}. {symbol}")

    # 加载不存在的文件（会自动创建空文件）
    print(f"\n加载不存在的列表文件...")
    empty_list = load_json_list("empty_list.json")
    print(f"返回空列表: {empty_list}")

    # 演示列表操作
    print(f"\n演示列表操作...")
    print(f"添加新合约...")
    loaded_favorites.append("SHFE.cu2505")
    save_json_list(favorites_file, loaded_favorites)
    print(f"当前收藏数量: {len(load_json_list(favorites_file))}")

    print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "观澜量化 - 通用工具函数演示" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    # 执行各项演示
    demo_path()
    demo_random_string()
    demo_datetime_format()
    demo_digit_conversion()
    demo_json_operations()
    demo_json_list_operations()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
