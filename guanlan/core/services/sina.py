# -*- coding: utf-8 -*-
"""
观澜量化 - 新浪主力合约刷新服务

从新浪财经 API 获取期货主力合约数据。
直接使用 nf_{品种代码}{YYMM} 接口，无需维护分类键映射。

Author: 海山观澜
"""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import requests

from guanlan.core.setting.contract import save_contracts
from guanlan.core.utils.logger import get_logger

logger = get_logger(__name__)

# 新浪行情接口请求头
_HEADERS: dict[str, str] = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# 持仓量在行情字符串中的索引
_POSITION_INDEX: int = 13


def fetch_main_contract(
    code: str,
    contracts: dict[str, dict[str, Any]]
) -> bool:
    """从新浪行情接口获取单个品种的主力合约

    通过连续合约(code+"0")的持仓量，在所有月份合约中匹配主力。

    Parameters
    ----------
    code : str
        品种代码（如 "RB"）
    contracts : dict
        合约数据字典（会被修改）

    Returns
    -------
    bool
        是否获取成功
    """
    try:
        # 构造查询列表：连续合约 + 未来24个月的月份合约
        now = datetime.now()
        symbols = [f"{code}0"]
        for offset in range(24):
            y = now.year + (now.month + offset - 1) // 12
            m = (now.month + offset - 1) % 12 + 1
            symbols.append(f"{code}{str(y)[2:]}{m:02d}")

        query = ",".join(f"nf_{s}" for s in symbols)
        url = f"https://hq.sinajs.cn/list={query}"

        r = requests.get(url, headers=_HEADERS, timeout=10)
        if r.status_code != 200:
            return False

        # 解析连续合约的持仓量
        target_position = ""
        month_contracts: dict[str, str] = {}

        for line in r.text.strip().split(";"):
            if '="' not in line:
                continue
            key_part, _, val = line.partition('="')
            val = val.rstrip('"')
            if not val:
                continue

            fields = val.split(",")
            if len(fields) <= _POSITION_INDEX:
                continue

            # 从 var hq_str_nf_RB0 提取 RB0
            symbol = key_part.rsplit("nf_", 1)[-1]
            position = fields[_POSITION_INDEX]

            if symbol == f"{code}0":
                target_position = position
            else:
                month_contracts[symbol] = position

        # 找持仓量匹配的月份合约即为主力
        if target_position:
            for symbol, position in month_contracts.items():
                if position == target_position:
                    contracts[code]["vt_symbol"] = symbol
                    return True

        return False

    except Exception as e:
        logger.warning("获取 %s 主力合约失败: %s", code, e)
        return False


def refresh_all(
    contracts: dict[str, dict[str, Any]],
    on_complete: Callable[[int, int], None] | None = None,
) -> None:
    """多线程批量刷新所有品种的主力合约

    Parameters
    ----------
    contracts : dict
        合约数据字典
    on_complete : Callable[[int, int], None] | None
        完成回调，参数为 (总数, 失败数)
    """
    logger.info("开始刷新主力合约")

    task_count = len(contracts)

    if task_count == 0:
        if on_complete:
            on_complete(0, 0)
        return

    lock = threading.Lock()
    total = 0
    errors = 0

    def _callback(future):
        nonlocal total, errors
        with lock:
            total += 1
            if not future.result():
                errors += 1
            done = total == task_count

        # 全部完成（在锁外执行，避免死锁）
        if done:
            save_contracts(contracts)
            logger.info("主力合约刷新完成: 总数=%d, 失败=%d", total, errors)
            if on_complete:
                on_complete(total, errors)

    with ThreadPoolExecutor(max_workers=10) as pool:
        for code in contracts:
            future = pool.submit(fetch_main_contract, code, contracts)
            future.add_done_callback(_callback)
