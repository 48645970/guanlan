# -*- coding: utf-8 -*-
"""
观澜量化 - 图表配置管理

管理品种的周期和指标参数持久化。

Author: 海山观澜
"""

from typing import Any

from guanlan.core.utils.common import load_json_file, save_json_file

# 配置文件路径（相对于 .guanlan 目录）
SYMBOL_INDICATORS_FILE: str = "config/symbol_indicators.json"


def load_all() -> dict[str, dict[str, Any]]:
    """加载所有品种的图表配置"""
    return load_json_file(SYMBOL_INDICATORS_FILE)


def get_setting(vt_symbol: str) -> dict[str, Any]:
    """获取指定品种的配置（周期 + 指标参数）"""
    all_settings = load_all()
    return all_settings.get(vt_symbol, {})


def save_setting(vt_symbol: str, setting: dict[str, Any]) -> None:
    """保存指定品种的配置"""
    all_settings = load_all()
    all_settings[vt_symbol] = setting
    save_json_file(SYMBOL_INDICATORS_FILE, all_settings)
