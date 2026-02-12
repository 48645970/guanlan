# -*- coding: utf-8 -*-
"""
观澜量化 - 账户配置管理

Author: 海山观澜
"""

from typing import Any

from guanlan.core.utils.common import load_json_file, save_json_file

# 配置文件名
SETTING_FILENAME: str = "config/account.json"

# 账户字段定义：(字段名, 默认值)
ACCOUNT_FIELDS: list[tuple[str, str]] = [
    ("名称", ""),
    ("用户名", ""),
    ("密码", ""),
    ("经纪商代码", ""),
    ("交易服务器", ""),
    ("行情服务器", ""),
    ("产品名称", ""),
    ("授权编码", ""),
    ("产品信息", ""),
    ("柜台环境", "实盘"),
]

# 密码字段（需要掩码显示）
PASSWORD_FIELDS: set[str] = {"密码", "授权编码"}


def load_config() -> dict[str, Any]:
    """加载完整配置文件"""
    config = load_json_file(SETTING_FILENAME)
    if not config:
        config = {
            "说明": "CTP 多环境配置文件，支持多套连接配置",
            "默认环境": "",
            "环境列表": {},
        }
    return config


def save_config(config: dict[str, Any]) -> None:
    """保存完整配置文件"""
    save_json_file(SETTING_FILENAME, config)


def get_accounts(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """获取环境列表"""
    return config.get("环境列表", {})


def get_default_env(config: dict[str, Any]) -> str:
    """获取默认环境"""
    return config.get("默认环境", "")


def new_account() -> dict[str, str]:
    """创建空账户模板"""
    return {field: default for field, default in ACCOUNT_FIELDS}


def is_auto_login(account_data: dict[str, str]) -> bool:
    """是否自动登录"""
    return account_data.get("自动登录", "") == "1"


def set_auto_login(account_data: dict[str, str], enabled: bool) -> None:
    """设置自动登录"""
    account_data["自动登录"] = "1" if enabled else "0"


def is_market_source(account_data: dict[str, str]) -> bool:
    """是否为行情数据源"""
    return account_data.get("行情服务", "") == "1"


def set_market_source(account_data: dict[str, str], enabled: bool) -> None:
    """设置行情数据源"""
    account_data["行情服务"] = "1" if enabled else "0"


def get_display_name(env_key: str, account_data: dict[str, str]) -> str:
    """获取显示名称（优先使用名称字段，回退到环境键名）"""
    return account_data.get("名称", "") or env_key
