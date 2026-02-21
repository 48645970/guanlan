# -*- coding: utf-8 -*-
"""
观澜量化 - 数据库适配层

提供 get_database() 统一入口，根据观澜配置选择数据库后端。
优先使用观澜配置（cfg.databaseDriver），不依赖 vnpy 的 vt_setting.json。

Author: 海山观澜
"""

from vnpy.trader.database import BaseDatabase

from .arctic import ArcticDBDatabase

# 全局数据库单例
_database: BaseDatabase | None = None


def get_database() -> BaseDatabase:
    """获取数据库实例（根据观澜配置选择后端）

    - arctic：使用 ArcticDB（默认，嵌入式，无需外部服务）
    - sqlite / 其他：回退到 vnpy 内置的 get_database()
    """
    global _database
    if _database:
        return _database

    from guanlan.ui.common.config import cfg

    driver = cfg.get(cfg.databaseDriver)

    if driver == "arctic":
        _database = ArcticDBDatabase()
    else:
        # 回退到 vnpy 原生逻辑（sqlite / mysql / postgresql / mongodb）
        from vnpy.trader.database import get_database as vnpy_get_database
        _database = vnpy_get_database()

    return _database
