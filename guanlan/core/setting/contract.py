# -*- coding: utf-8 -*-
"""
观澜量化 - 合约配置管理

Author: 海山观澜
"""

from typing import Any

from guanlan.core.utils.common import (
    load_json_file, save_json_file,
    load_json_list, save_json_list,
    to_digit_value
)

# 配置文件路径（相对于 .guanlan 目录）
CONTRACT_FILENAME: str = "config/contract.json"
FAVORITES_FILENAME: str = "config/favorites.json"

# 表头定义
HEADERS: list[str] = [
    "", "代码", "名称", "交易所", "最小跳点", "合约乘数", "主力合约",
    "开仓(%)", "开仓", "平仓(%)", "平仓", "平今(%)", "平今"
]

# 列名映射（与 JSON 字段对应）
COLUMNS: list[str] = [
    "", "symbol", "name", "exchange", "tick", "size", "vt_symbol",
    "open_ratio", "open", "close_ratio", "close", "close_today_ratio", "close_today"
]

# 可编辑列索引（手续费字段：第 7-12 列）
EDITABLE_COLUMNS: set[int] = {7, 8, 9, 10, 11, 12}

# 编辑对话框字段定义：(字段名, JSON键, 类型, 默认值)
CONTRACT_FIELDS: list[tuple[str, str, type, Any]] = [
    ("品种代码", "symbol", str, ""),
    ("名称", "name", str, ""),
    ("交易所", "exchange", str, "SHFE"),
    ("最小跳点", "tick", float, 0.0),
    ("合约乘数", "size", int, 1),
    ("主力合约", "vt_symbol", str, ""),
    ("开仓(%)", "open_ratio", float, 0.0),
    ("开仓", "open", float, 0.0),
    ("平仓(%)", "close_ratio", float, 0.0),
    ("平仓", "close", float, 0.0),
    ("平今(%)", "close_today_ratio", float, 0.0),
    ("平今", "close_today", float, 0.0),
]

# 交易所选项
EXCHANGES: list[str] = ["SHFE", "DCE", "CZCE", "CFFEX", "INE", "GFEX"]


def load_contracts() -> dict[str, dict[str, Any]]:
    """加载合约数据"""
    return load_json_file(CONTRACT_FILENAME)


def save_contracts(contracts: dict[str, dict[str, Any]]) -> None:
    """保存合约数据"""
    save_json_file(CONTRACT_FILENAME, contracts)


def edit_contract(
    contracts: dict[str, dict[str, Any]],
    symbol: str,
    field: str,
    value: Any
) -> bool:
    """编辑单个合约字段并保存

    Parameters
    ----------
    contracts : dict
        合约数据字典（内存引用，会被修改）
    symbol : str
        品种代码
    field : str
        字段名（COLUMNS 中的值）
    value : Any
        新值

    Returns
    -------
    bool
        是否编辑成功
    """
    if symbol not in contracts:
        return False

    contracts[symbol][field] = to_digit_value(value)
    save_contracts(contracts)
    return True


def new_contract() -> dict[str, Any]:
    """创建空合约模板"""
    return {key: default for _, key, _, default in CONTRACT_FIELDS if key != "symbol"}


def add_contract(
    contracts: dict[str, dict[str, Any]],
    symbol: str,
    data: dict[str, Any]
) -> bool:
    """新增合约"""
    if symbol in contracts:
        return False
    contracts[symbol] = data
    save_contracts(contracts)
    return True


def delete_contract(
    contracts: dict[str, dict[str, Any]],
    symbol: str
) -> bool:
    """删除合约"""
    if symbol not in contracts:
        return False
    contracts.pop(symbol)
    save_contracts(contracts)
    return True


def update_contract(
    contracts: dict[str, dict[str, Any]],
    symbol: str,
    data: dict[str, Any]
) -> None:
    """更新合约全部字段"""
    contracts[symbol] = data
    save_contracts(contracts)


def load_favorites() -> list[str]:
    """加载收藏列表"""
    return load_json_list(FAVORITES_FILENAME)


def save_favorites(favorites: list[str]) -> None:
    """保存收藏列表"""
    save_json_list(FAVORITES_FILENAME, favorites)


def add_favorite(favorites: list[str], symbol: str) -> None:
    """添加收藏"""
    if symbol not in favorites:
        favorites.append(symbol)
        save_favorites(favorites)


def remove_favorite(favorites: list[str], symbol: str) -> None:
    """移除收藏"""
    if symbol in favorites:
        favorites.remove(symbol)
        save_favorites(favorites)
