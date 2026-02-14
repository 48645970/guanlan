# -*- coding: utf-8 -*-
"""
观澜量化 - 图表模拟验证

启动完整应用框架，用模拟 Tick 替代实盘行情推送到 EventEngine，
走完整数据链路验证 ChartWindow。

模拟速度：每 50ms 推一个 Tick，时间步长 3 秒，
约 1 秒形成一根 1 分钟 K 线，快速积累数据验证指标。

删除本文件即可还原，不影响任何生产代码。

使用方法：
    cd /home/jerry/dev/05.gulanlan
    source venv/bin/activate
    python examples/02.ui/0208.图表模拟验证.py

Author: 海山观澜
"""

import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)  # pywebview 的 base_uri() 依赖 CWD

os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"
os.environ["LANGUAGE"] = "zh_CN"

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

from vnpy.trader.constant import Exchange
from vnpy.trader.event import EVENT_TICK
from vnpy.trader.object import TickData

from guanlan.core.trader.event import Event


class MockTickPusher:
    """模拟行情推送器

    生成随机 Tick 通过 EventEngine 推送，
    ChartWindow 通过正常的事件链路接收。

    时间步长 3 秒 + 推送间隔 50ms → 约 1 秒钟产生一根 1 分钟 K 线。
    """

    def __init__(self, event_engine, symbol: str = "OI605",
                 exchange: Exchange = Exchange.CZCE,
                 interval_ms: int = 50,
                 time_step_sec: int = 3) -> None:
        self._event_engine = event_engine
        self._symbol = symbol
        self._exchange = exchange

        self._price = 8200.0
        self._volume = 100000
        self._time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        self._time_step = timedelta(seconds=time_step_sec)
        self._count = 0

        self._timer = QTimer()
        self._timer.timeout.connect(self._push_tick)
        self._timer.start(interval_ms)

        print(f"[模拟行情] {symbol}.{exchange.value} | "
              f"间隔={interval_ms}ms 时间步长={time_step_sec}s")

    def _push_tick(self) -> None:
        self._time += self._time_step
        self._price = round(self._price + random.gauss(0, 4), 1)
        self._volume += random.randint(1, 20)
        self._count += 1

        tick = TickData(
            symbol=self._symbol,
            exchange=self._exchange,
            datetime=self._time,
            gateway_name="MOCK",
            last_price=self._price,
            high_price=round(self._price + abs(random.gauss(0, 2)), 1),
            low_price=round(self._price - abs(random.gauss(0, 2)), 1),
            volume=self._volume,
            turnover=self._volume * self._price,
            open_interest=50000.0,
        )

        self._event_engine.put(Event(EVENT_TICK, tick))

        if self._count % 100 == 0:
            print(f"[模拟行情] Tick #{self._count} | "
                  f"时间={self._time.strftime('%H:%M:%S')} 价格={self._price}")

    def stop(self) -> None:
        self._timer.stop()


def main() -> None:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    setTheme(Theme.DARK)

    from guanlan.core.app import AppEngine
    app_engine = AppEngine.instance()

    from guanlan.ui.view.window.chart import ChartWindow
    chart = ChartWindow()
    chart.set_symbol("OI605.CZCE")
    chart.show()

    pusher = MockTickPusher(
        app_engine.event_engine,
        symbol="OI605",
        exchange=Exchange.CZCE,
        interval_ms=50,
        time_step_sec=3,  # 每 tick 跳 3 秒，约 1 秒出一根 1 分钟 K 线
    )

    ret = app.exec()
    pusher.stop()
    app_engine.close()
    os._exit(ret)


if __name__ == "__main__":
    main()
