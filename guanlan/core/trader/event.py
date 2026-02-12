# -*- coding: utf-8 -*-
"""
观澜量化 - 事件引擎

继承 vnpy EventEngine，解决高频事件批量到达时 GIL 饥饿问题。

CTP 连接时 ~4000+ 合约事件瞬间涌入，原版 EventEngine 连续处理
不释放 GIL，导致 UI 线程分不到时间片、界面冻死。
重载 _run 方法，每处理一批事件就主动释放 GIL。

Author: 海山观澜
"""

import time
from queue import Empty

from vnpy.event import EventEngine as VnpyEventEngine, Event


# 每处理 _YIELD_INTERVAL 个事件，释放一次 GIL
_YIELD_INTERVAL: int = 64


class EventEngine(VnpyEventEngine):
    """观澜事件引擎"""

    def _run(self) -> None:
        """事件处理循环（带 GIL 释放）"""
        count: int = 0

        while self._active:
            try:
                event: Event = self._queue.get(block=True, timeout=1)
                self._process(event)

                count += 1
                if count >= _YIELD_INTERVAL:
                    count = 0
                    time.sleep(0)
            except Empty:
                count = 0


__all__ = ["EventEngine", "Event"]
