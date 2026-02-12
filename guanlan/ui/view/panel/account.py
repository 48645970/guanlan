# -*- coding: utf-8 -*-
"""
观澜量化 - 资金监控面板

Author: 海山观澜
"""

from vnpy.trader.event import EVENT_ACCOUNT
from vnpy.trader.object import AccountData

from .base import BaseMonitor, MonitorPanel


class _AccountTable(BaseMonitor):
    """资金表格"""

    headers = {
        "accountid":    {"display": "账号"},
        "balance":      {"display": "余额",  "format": ".2f"},
        "frozen":       {"display": "冻结",  "format": ".2f"},
        "available":    {"display": "可用",  "format": ".2f"},
        "gateway_name": {"display": "账户"},
    }
    data_key = "vt_accountid"


class AccountMonitor(MonitorPanel):
    """资金监控面板"""

    table_class = _AccountTable
    filter_fields = {"gateway_name": "账户"}
    event_type = EVENT_ACCOUNT

    def _convert_data(self, acc: AccountData) -> dict:
        return {
            "accountid": acc.accountid,
            "balance": acc.balance,
            "frozen": acc.frozen,
            "available": acc.available,
            "gateway_name": acc.gateway_name,
            "vt_accountid": acc.vt_accountid,
        }
