# -*- coding: utf-8 -*-
"""
观澜量化 - 图表方案管理

管理图表方案（合约 + 周期 + 指标配置）的持久化。

Author: 海山观澜
"""

from typing import Any

from guanlan.core.utils.common import load_json_file, save_json_file

# 配置文件路径（相对于 .guanlan 目录）
CHART_SCHEMES_FILE: str = "config/chart_schemes.json"


def load_schemes() -> dict[str, dict[str, Any]]:
    """加载全部方案"""
    return load_json_file(CHART_SCHEMES_FILE)


def save_scheme(name: str, data: dict[str, Any]) -> None:
    """保存方案"""
    schemes = load_schemes()
    schemes[name] = data
    save_json_file(CHART_SCHEMES_FILE, schemes)


def delete_scheme(name: str) -> None:
    """删除方案"""
    schemes = load_schemes()
    schemes.pop(name, None)
    save_json_file(CHART_SCHEMES_FILE, schemes)


def rename_scheme(old_name: str, new_name: str) -> None:
    """重命名方案"""
    schemes = load_schemes()
    if old_name in schemes:
        schemes[new_name] = schemes.pop(old_name)
        save_json_file(CHART_SCHEMES_FILE, schemes)
