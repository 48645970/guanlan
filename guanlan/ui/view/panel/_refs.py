# -*- coding: utf-8 -*-
"""
观澜量化 - 委托来源缓存

CTP 回报不带 reference 字段，需在首次收到时缓存，
后续委托更新和成交事件可查询。

Author: 海山观澜
"""

_order_references: dict[str, str] = {}


def cache_order_reference(vt_orderid: str, reference: str) -> None:
    """缓存委托来源"""
    if reference:
        _order_references[vt_orderid] = reference


def get_order_reference(vt_orderid: str) -> str:
    """获取委托来源"""
    return _order_references.get(vt_orderid, "")
