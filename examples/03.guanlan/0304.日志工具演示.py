# -*- coding: utf-8 -*-
"""
观澜量化 - 日志工具演示

演示 core.utils.logger 模块的各项功能

Author: 海山观澜
"""

import sys
from pathlib import Path
import time

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guanlan.core.utils.logger import (
    get_logger,
    get_simple_logger,
    get_file_logger,
    logger as default_logger,
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)


def demo_default_logger():
    """演示默认日志记录器"""
    print("=" * 70)
    print("1. 默认日志记录器（输出到控制台和文件）")
    print("=" * 70)

    default_logger.info("这是一条信息日志")
    default_logger.debug("这是一条调试日志（默认不显示）")
    default_logger.warning("这是一条警告日志")
    default_logger.error("这是一条错误日志")
    default_logger.critical("这是一条严重错误日志")

    print()


def demo_custom_logger():
    """演示自定义日志记录器"""
    print("=" * 70)
    print("2. 自定义日志记录器（不同模块、不同级别）")
    print("=" * 70)

    # 策略模块日志（DEBUG 级别）
    strategy_logger = get_logger("strategy", level=DEBUG)
    strategy_logger.debug("策略初始化完成")
    strategy_logger.info("策略开始运行")
    strategy_logger.warning("仓位接近上限")

    print()

    # 交易模块日志（INFO 级别）
    trade_logger = get_logger("trade", level=INFO)
    trade_logger.debug("这条调试日志不会显示（级别太低）")
    trade_logger.info("提交买入订单：SHFE.rb2505 @ 3500")
    trade_logger.info("订单成交：SHFE.rb2505, 10手")

    print()

    # 风控模块日志（WARNING 级别）
    risk_logger = get_logger("risk", level=WARNING)
    risk_logger.info("这条信息日志不会显示（级别太低）")
    risk_logger.warning("持仓风险度: 75%")
    risk_logger.error("触发风控限制，禁止开仓")

    print()


def demo_simple_logger():
    """演示简化日志记录器（仅控制台）"""
    print("=" * 70)
    print("3. 简化日志记录器（仅控制台输出）")
    print("=" * 70)

    console_logger = get_simple_logger("console_test", level=DEBUG)
    console_logger.info("这是仅输出到控制台的日志")
    console_logger.debug("适用于临时调试")
    console_logger.warning("不会写入日志文件")

    print()


def demo_file_logger():
    """演示文件日志记录器（仅文件）"""
    print("=" * 70)
    print("4. 文件日志记录器（仅文件输出）")
    print("=" * 70)

    file_logger = get_file_logger("background_task", level=INFO)
    file_logger.info("后台任务开始执行")
    file_logger.info("处理数据：1000条记录")
    file_logger.info("后台任务完成")

    print("文件日志记录器不会输出到控制台")
    print("日志已保存到文件（查看 .guanlan/logs/ 目录）")
    print()


def demo_different_levels():
    """演示不同日志级别"""
    print("=" * 70)
    print("5. 不同日志级别演示")
    print("=" * 70)

    levels = [
        (DEBUG, "DEBUG"),
        (INFO, "INFO"),
        (WARNING, "WARNING"),
        (ERROR, "ERROR"),
        (CRITICAL, "CRITICAL"),
    ]

    for level, name in levels:
        test_logger = get_logger(f"level_test_{name}", level=level, file=False)
        print(f"\n>>> 日志级别: {name} (值={level})")
        test_logger.debug(f"  [DEBUG] 这是 DEBUG 级别")
        test_logger.info(f"  [INFO] 这是 INFO 级别")
        test_logger.warning(f"  [WARNING] 这是 WARNING 级别")
        test_logger.error(f"  [ERROR] 这是 ERROR 级别")
        test_logger.critical(f"  [CRITICAL] 这是 CRITICAL 级别")

    print()


def demo_real_scenario():
    """演示真实场景：策略运行日志"""
    print("=" * 70)
    print("6. 真实场景：策略运行日志")
    print("=" * 70)

    strategy_log = get_logger("CTA_Strategy_Demo", level=DEBUG)

    strategy_log.info("=" * 50)
    strategy_log.info("策略启动")
    strategy_log.info("=" * 50)

    strategy_log.debug("加载策略参数...")
    strategy_log.debug("参数: entry_window=15, exit_window=30")

    strategy_log.info("连接交易接口...")
    time.sleep(0.1)
    strategy_log.info("交易接口连接成功")

    strategy_log.info("订阅行情: SHFE.rb2505, SHFE.hc2505")
    time.sleep(0.1)

    strategy_log.info("接收行情: SHFE.rb2505, 最新价=3520")
    strategy_log.debug("计算信号: MA15=3515, MA30=3500")

    strategy_log.warning("信号触发: 金叉，准备买入")
    strategy_log.info("提交订单: 买入 SHFE.rb2505, 数量=10手, 价格=3520")

    time.sleep(0.1)
    strategy_log.info("订单成交: SHFE.rb2505, 成交价=3520, 数量=10手")

    strategy_log.info("当前持仓: SHFE.rb2505 多头10手")
    strategy_log.debug("持仓盈亏: +0")

    time.sleep(0.1)
    strategy_log.info("接收行情: SHFE.rb2505, 最新价=3530")
    strategy_log.info("浮动盈亏: +1000元")

    strategy_log.info("=" * 50)
    strategy_log.info("策略运行正常")
    strategy_log.info("=" * 50)

    print()


def demo_log_location():
    """显示日志文件位置"""
    print("=" * 70)
    print("7. 日志文件位置")
    print("=" * 70)

    from guanlan.core.utils.common import get_folder_path

    log_dir = get_folder_path("logs")
    print(f"日志目录: {log_dir}")
    print(f"目录存在: {log_dir.exists()}")

    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            print(f"\n当前日志文件:")
            for log_file in sorted(log_files):
                size = log_file.stat().st_size
                print(f"  - {log_file.name} ({size} 字节)")
        else:
            print("\n当前没有日志文件")

    print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 22 + "观澜量化 - 日志工具演示" + " " * 22 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 执行各项演示
    demo_default_logger()
    demo_custom_logger()
    demo_simple_logger()
    demo_file_logger()
    demo_different_levels()
    demo_real_scenario()
    demo_log_location()

    print("=" * 70)
    print("演示完成！")
    print("=" * 70)
    print()
    print("提示：")
    print("- 日志文件保存在 ~/.guanlan/logs/ 目录")
    print("- 文件名格式：<模块名>_YYYYMMDD.log")
    print("- 日志每天自动轮转，默认保留30天")


if __name__ == "__main__":
    main()
