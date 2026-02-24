# -*- coding: utf-8 -*-
"""
观澜量化 - 日志工具

基于 loguru 的日志管理工具，提供：
- 文件日志（按天轮转，保留30天，统一写入 guanlan.log）
- 控制台日志（支持彩色输出）
- 按模块名称区分日志来源

全局 handler 只初始化一次，各模块通过 get_logger(name) 获取带
名称绑定的 logger 实例，共享同一套控制台 + 文件输出。

Author: 海山观澜
"""

import sys
from datetime import timedelta, timezone
from typing import Any

from loguru import logger as _logger

from guanlan.core.utils.common import get_folder_path

# 北京时间 UTC+8
_BEIJING_TZ = timezone(timedelta(hours=8))


# 日志级别常量（兼容标准 logging）
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

# 日志级别映射
LEVEL_MAP = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

# 全局初始化标志
_initialized: bool = False


def _setup(level: int = INFO) -> None:
    """一次性初始化全局日志 handler（控制台 + 文件）

    仅在首次调用 get_logger 时执行，后续调用跳过。
    所有模块共享同一套 handler，通过 {extra[name]} 区分来源。
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    level_name = LEVEL_MAP.get(level, "INFO")

    # 移除 loguru 默认的 stderr handler
    _logger.remove()

    # 强制北京时间：通过 patcher 将 record["time"] 转为 UTC+8
    def _beijing_patcher(record):
        record["time"] = record["time"].astimezone(_BEIJING_TZ)

    # 设置默认 extra，防止第三方库（如 VNPY）未 bind name 时 KeyError
    _logger.configure(extra={"name": "unknown"}, patcher=_beijing_patcher)

    # 控制台彩色格式
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[name]: <12}</cyan> | "
        "<level>{message}</level>"
    )
    _logger.add(
        sink=sys.stdout,
        level=level_name,
        format=console_format,
        colorize=True,
    )

    # 文件输出（统一写入 guanlan.log）
    log_dir = get_folder_path("logs")
    log_file = log_dir / "guanlan.log"

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{extra[name]: <12} | "
        "{message}"
    )
    _logger.add(
        sink=log_file,
        level=level_name,
        format=file_format,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )


def get_logger(name: str = "guanlan", level: int = INFO, **_kwargs) -> Any:
    """获取日志记录器

    Parameters
    ----------
    name : str, default "guanlan"
        模块名称，显示在日志的来源字段中
    level : int, default INFO
        日志级别（仅首次调用时生效，用于初始化全局 handler）

    Returns
    -------
    logger
        loguru 日志记录器实例（带 name 绑定）

    Examples
    --------
    >>> logger = get_logger("my_module")
    >>> logger.info("这是一条信息日志")
    """
    _setup(level)
    return _logger.bind(name=name)


def get_simple_logger(name: str = "guanlan", level: int = INFO) -> Any:
    """获取日志记录器（同 get_logger，保留兼容）"""
    return get_logger(name=name, level=level)


def get_file_logger(name: str = "guanlan", level: int = INFO) -> Any:
    """获取日志记录器（同 get_logger，保留兼容）"""
    return get_logger(name=name, level=level)


# 默认全局 logger 实例
logger = get_logger("guanlan", level=INFO)


__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "get_logger",
    "get_simple_logger",
    "get_file_logger",
    "logger",
]
