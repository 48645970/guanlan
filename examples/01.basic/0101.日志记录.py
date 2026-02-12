# -*- coding: utf-8 -*-
"""
日志系统示例

演示 Python logging 模块的用法：
- 控制台输出
- 文件输出
- 日志轮转
- 不同级别的日志

Author: 海山观澜
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str = "guanlan",
    log_dir: str = "logs",
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    配置日志器

    Args:
        name: 日志器名称
        log_dir: 日志文件目录
        level: 日志级别

    Returns:
        配置好的 Logger 实例
    """
    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 日志格式
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # 文件处理器（按天轮转，保留7天）
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        encoding="utf-8",
        when="midnight",  # 每天午夜轮转
        interval=1,
        backupCount=7  # 保留7天
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    return logger


def main():
    print("=" * 50)
    print("Logging 日志系统示例")
    print("=" * 50)

    # 设置日志器
    logger = setup_logger(
        name="demo",
        log_dir="../logs",
        level=logging.DEBUG
    )

    # 不同级别的日志
    logger.debug("这是 DEBUG 级别日志（仅写入文件）")
    logger.info("这是 INFO 级别日志")
    logger.warning("这是 WARNING 级别日志")
    logger.error("这是 ERROR 级别日志")
    logger.critical("这是 CRITICAL 级别日志")

    # 带变量的日志
    symbol = "rb2501"
    price = 4520.5
    logger.info(f"合约 {symbol} 最新价格: {price}")

    # 异常日志
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception("捕获到异常:")

    print()
    print(f"日志文件已保存到: ../logs/demo.log")


if __name__ == "__main__":
    main()
