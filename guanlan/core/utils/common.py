# -*- coding: utf-8 -*-
"""
观澜量化 - 通用工具函数集

Author: 海山观澜
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_trader_dir(temp_name: str) -> tuple[Path, Path]:
    """
    获取观澜运行目录

    使用工程根目录下的配置目录

    Parameters
    ----------
    temp_name : str
        配置目录名称，默认为 ".guanlan"

    Returns
    -------
    tuple[Path, Path]
        (工程根目录, 配置目录路径)
    """
    # 工程根目录：guanlan/core/utils/common.py → 向上 3 级
    project_root = Path(__file__).parent.parent.parent.parent
    temp_path = project_root.joinpath(temp_name)

    # 创建配置目录（如果不存在）
    temp_path.mkdir(parents=True, exist_ok=True)

    return project_root, temp_path


# 初始化观澜目录
TRADER_DIR, TEMP_DIR = _get_trader_dir(".guanlan")


def get_file_path(filename: str) -> Path:
    """
    获取配置文件的完整路径（位于 .guanlan 目录下）

    Parameters
    ----------
    filename : str
        文件名（可以包含子目录，如 "logs/app.log"）

    Returns
    -------
    Path
        完整文件路径

    Examples
    --------
    >>> get_file_path("config.json")
    PosixPath('/home/user/.guanlan/config.json')
    >>> get_file_path("logs/app.log")
    PosixPath('/home/user/.guanlan/logs/app.log')
    """
    return TEMP_DIR.joinpath(filename)


def get_folder_path(folder_name: str) -> Path:
    """
    获取配置文件夹的完整路径（位于 .guanlan 目录下）

    如果文件夹不存在，会自动创建

    Parameters
    ----------
    folder_name : str
        文件夹名称

    Returns
    -------
    Path
        完整文件夹路径

    Examples
    --------
    >>> get_folder_path("logs")
    PosixPath('/home/user/.guanlan/logs')
    >>> get_folder_path("strategies")
    PosixPath('/home/user/.guanlan/strategies')
    """
    folder_path = TEMP_DIR.joinpath(folder_name)
    if not folder_path.exists():
        folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def random_string(length: int = 8) -> str:
    """
    生成指定长度的随机字符串（基于 UUID）

    Parameters
    ----------
    length : int, default 8
        字符串长度，最大 36（UUID 完整长度）

    Returns
    -------
    str
        随机字符串

    Examples
    --------
    >>> random_string(8)
    'a1b2c3d4'
    >>> random_string(16)
    'a1b2c3d4-e5f6-g7'

    Raises
    ------
    ValueError
        当 length 超出有效范围时
    """
    if length <= 0 or length > 36:
        raise ValueError(f"length must be between 1 and 36, got {length}")

    result = str(uuid.uuid4())[:length]
    return result


def formatted_datetime(dt: datetime | None = None) -> str:
    """
    格式化日期时间为字符串（YYYY-MM-DD HH:MM:SS）

    Parameters
    ----------
    dt : datetime | None, default None
        待格式化的日期时间，默认为当前时间

    Returns
    -------
    str
        格式化后的日期时间字符串

    Examples
    --------
    >>> formatted_datetime()
    '2025-12-25 14:30:00'
    >>> formatted_datetime(datetime(2025, 1, 1, 12, 0, 0))
    '2025-01-01 12:00:00'
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def formatted_date(dt: datetime | None = None) -> str:
    """
    格式化日期为字符串（YYYYMMDD）

    Parameters
    ----------
    dt : datetime | None, default None
        待格式化的日期，默认为当前日期

    Returns
    -------
    str
        格式化后的日期字符串

    Examples
    --------
    >>> formatted_date()
    '20251225'
    >>> formatted_date(datetime(2025, 1, 1))
    '20250101'
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d")


def to_digit_value(value: Any, decimals: int = 2) -> int | float | Any:
    """
    智能转换数字类型，支持整数、浮点数和字符串

    Parameters
    ----------
    value : Any
        待转换的值
    decimals : int, default 2
        浮点数保留的小数位数

    Returns
    -------
    int | float | Any
        转换后的值，无法转换时返回原值

    Examples
    --------
    >>> to_digit_value("123")
    123
    >>> to_digit_value("123.45")
    123.45
    >>> to_digit_value("-123.45")
    -123.45
    >>> to_digit_value(123.456, decimals=2)
    123.46
    >>> to_digit_value("abc")
    'abc'
    """
    # 已经是数字类型
    if isinstance(value, (int, float)):
        return round(value, decimals)

    # 字符串类型处理
    str_value = str(value)

    # 处理负号
    is_negative = str_value.startswith('-')
    check_value = str_value[1:] if is_negative else str_value

    # 检查是否为整数
    if check_value.isdigit():
        return int(value)

    # 检查是否为浮点数
    if check_value.replace('.', '', 1).isdigit():
        parts = check_value.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return round(float(value), decimals)

    # 无法转换，返回原值
    return value


def load_json_file(filename: str) -> dict[str, Any]:
    """
    从 JSON 文件加载配置数据（字典类型）

    Parameters
    ----------
    filename : str
        JSON 文件名（位于 .guanlan 目录下）

    Returns
    -------
    dict[str, Any]
        加载的数据字典，文件不存在时创建空文件并返回空字典

    Examples
    --------
    >>> data = load_json_file('config.json')
    >>> print(data)
    {'key': 'value'}

    Notes
    -----
    - 文件路径为 ~/.guanlan/<filename>
    - 如果文件不存在，会自动创建空的 JSON 文件
    - 如果文件内容无效，会抛出 json.JSONDecodeError
    """
    filepath = get_file_path(filename)

    if filepath.exists():
        with open(filepath, mode="r", encoding="UTF-8") as f:
            data = json.load(f)
        return data
    else:
        # 文件不存在，创建空文件
        save_json_file(filename, {})
        return {}


def save_json_file(filename: str, data: dict[str, Any]) -> None:
    """
    保存字典数据到 JSON 文件

    Parameters
    ----------
    filename : str
        JSON 文件名（位于 .guanlan 目录下）
    data : dict[str, Any]
        待保存的字典数据

    Examples
    --------
    >>> save_json_file('config.json', {'key': 'value'})

    Raises
    ------
    TypeError
        当数据无法 JSON 序列化时
    OSError
        当文件无法写入时

    Notes
    -----
    - 文件路径为 ~/.guanlan/<filename>
    - 自动格式化 JSON（4 空格缩进）
    - 支持中文字符（ensure_ascii=False）
    - 自动创建父目录
    """
    filepath = get_file_path(filename)

    # 确保父目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, mode="w", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def load_json_list(filename: str) -> list[Any]:
    """
    从 JSON 文件加载配置数据（列表类型）

    Parameters
    ----------
    filename : str
        JSON 文件名（位于 .guanlan 目录下）

    Returns
    -------
    list[Any]
        加载的数据列表，文件不存在时创建空文件并返回空列表

    Examples
    --------
    >>> data = load_json_list('favorites.json')
    >>> print(data)
    ['SHFE.rb2505', 'SHFE.hc2505']

    Notes
    -----
    - 文件路径为 ~/.guanlan/<filename>
    - 如果文件不存在，会自动创建空的 JSON 文件
    - 如果文件内容无效，会抛出 json.JSONDecodeError
    """
    filepath = get_file_path(filename)

    if filepath.exists():
        with open(filepath, mode="r", encoding="UTF-8") as f:
            data = json.load(f)
        return data
    else:
        # 文件不存在，创建空文件
        save_json_list(filename, [])
        return []


def save_json_list(filename: str, data: list[Any]) -> None:
    """
    保存列表数据到 JSON 文件

    Parameters
    ----------
    filename : str
        JSON 文件名（位于 .guanlan 目录下）
    data : list[Any]
        待保存的列表数据

    Examples
    --------
    >>> save_json_list('favorites.json', ['SHFE.rb2505', 'SHFE.hc2505'])

    Raises
    ------
    TypeError
        当数据无法 JSON 序列化时
    OSError
        当文件无法写入时

    Notes
    -----
    - 文件路径为 ~/.guanlan/<filename>
    - 自动格式化 JSON（4 空格缩进）
    - 支持中文字符（ensure_ascii=False）
    - 自动创建父目录
    """
    filepath = get_file_path(filename)

    # 确保父目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, mode="w", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )
