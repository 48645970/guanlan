# -*- coding: utf-8 -*-
"""
观澜量化 - 持仓监控面板

双击持仓行弹出确认后平仓；工具栏"一键平仓"平掉所有持仓。

Author: 海山观澜
"""

from vnpy.trader.constant import Direction, Offset, OrderType
from vnpy.trader.event import EVENT_POSITION
from vnpy.trader.object import PositionData, OrderRequest

from qfluentwidgets import MessageBox, InfoBar, InfoBarPosition

from guanlan.ui.widgets.components.button import DangerPushButton

from .base import BaseMonitor, MonitorPanel


class _PositionTable(BaseMonitor):
    """持仓表格"""

    headers = {
        "symbol":       {"display": "代码"},
        "direction":    {"display": "方向",  "color": "direction"},
        "volume":       {"display": "数量",  "format": "int"},
        "yd_volume":    {"display": "昨仓",  "format": "int"},
        "frozen":       {"display": "冻结",  "format": "int"},
        "price":        {"display": "均价",  "format": ".2f"},
        "pnl":          {"display": "盈亏",  "format": ".2f", "color": "pnl"},
        "gateway_name": {"display": "账户"},
    }
    data_key = "vt_positionid"


class PositionMonitor(MonitorPanel):
    """持仓监控面板（双击平仓 + 一键平仓）"""

    table_class = _PositionTable
    filter_fields = {"gateway_name": "账户", "symbol": "代码", "direction": "方向"}
    event_type = EVENT_POSITION

    def _init_ui(self) -> None:
        super()._init_ui()
        self._table.setToolTip("双击持仓行可一键平仓")
        self._table.itemDoubleClicked.connect(self._on_double_click)

        # 一键平仓按钮（工具栏右侧，红色警示）
        self._close_all_btn = DangerPushButton("一键平仓", self)
        self._close_all_btn.setFixedHeight(28)
        self._close_all_btn.clicked.connect(self._on_close_all)
        self._toolbar.addWidget(self._close_all_btn)

    def _on_close_all(self) -> None:
        """一键平仓：平掉所有账户的所有持仓"""
        from guanlan.core.app import AppEngine

        main_engine = AppEngine.instance().main_engine
        positions = [
            pos for pos in main_engine.get_all_positions()
            if pos.volume - pos.frozen > 0
        ]

        if not positions:
            InfoBar.warning(
                "无可平持仓", "当前无持仓或全部冻结",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        lines = [
            f"{pos.gateway_name} | {pos.symbol} {pos.direction.value} {pos.volume - pos.frozen}手"
            for pos in positions
        ]
        msg = MessageBox(
            "确认平仓",
            f"将平掉以下 {len(positions)} 笔持仓：\n\n" + "\n".join(lines),
            self.window(),
        )
        if not msg.exec():
            return

        for pos in positions:
            self._close_position(pos)

    def _on_double_click(self, item) -> None:
        """双击平仓"""
        row = item.row()
        if row < 0 or row >= len(self._table._data_by_row):
            return

        data = self._table._data_by_row[row]
        vt_positionid = data.get("vt_positionid", "")
        if not vt_positionid:
            return

        from guanlan.core.app import AppEngine

        pos = AppEngine.instance().main_engine.get_position(vt_positionid)
        if not pos:
            return

        closable = pos.volume - pos.frozen
        if closable <= 0:
            InfoBar.warning(
                "无法平仓", "无可平持仓（全部冻结）",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        msg = MessageBox(
            "确认平仓",
            f"合约: {pos.symbol}\n方向: {pos.direction.value}\n可平: {closable} 手\n账户: {pos.gateway_name}",
            self.window(),
        )
        if not msg.exec():
            return

        self._close_position(pos)

    def _close_position(self, pos: PositionData) -> None:
        """发送平仓委托"""
        from guanlan.core.app import AppEngine
        from guanlan.core.services.sound import play as play_sound

        main_engine = AppEngine.instance().main_engine
        closable = pos.volume - pos.frozen

        # 平仓方向与持仓方向相反
        if pos.direction == Direction.LONG:
            close_direction = Direction.SHORT
        else:
            close_direction = Direction.LONG

        # 取最新价作为限价
        tick = main_engine.get_tick(pos.vt_symbol)
        if not tick:
            InfoBar.error(
                "平仓失败", f"无法获取 {pos.symbol} 最新行情",
                parent=self.window(), position=InfoBarPosition.TOP,
            )
            return

        # 超价：多平用 bid-1tick，空平用 ask+1tick
        contract = main_engine.get_contract(pos.vt_symbol)
        pricetick = contract.pricetick if contract else 0.01

        if close_direction == Direction.SHORT:
            price = tick.bid_price_1 - pricetick
        else:
            price = tick.ask_price_1 + pricetick

        req = OrderRequest(
            symbol=pos.symbol,
            exchange=pos.exchange,
            direction=close_direction,
            type=OrderType.LIMIT,
            volume=closable,
            price=price,
            offset=Offset.CLOSE,
            reference="一键平仓",
        )

        main_engine.send_order(req, pos.gateway_name)
        play_sound("sell" if close_direction == Direction.SHORT else "buy")

        InfoBar.success(
            "已发送平仓委托",
            f"{pos.symbol} {closable}手 @ {price}",
            parent=self.window(), position=InfoBarPosition.TOP,
            duration=2000,
        )

    def _convert_data(self, pos: PositionData) -> dict:
        return {
            "symbol": pos.symbol,
            "direction": pos.direction.value,
            "volume": pos.volume,
            "yd_volume": pos.yd_volume,
            "frozen": pos.frozen,
            "price": pos.price,
            "pnl": pos.pnl,
            "gateway_name": pos.gateway_name,
            "vt_positionid": pos.vt_positionid,
        }
