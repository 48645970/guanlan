# -*- coding: utf-8 -*-
"""
观澜量化 - AI 图表分析工作线程

在后台调用 AI 服务分析图表指标状态，通过信号返回结果。

Author: 海山观澜
"""

import asyncio
import json

from PySide6.QtCore import Signal, QThread

from guanlan.core.utils.logger import get_logger

logger = get_logger(__name__)


class AIAnalysisWorker(QThread):
    """AI 分析工作线程"""

    analysis_finished = Signal(dict)
    analysis_error = Signal(str)

    def __init__(
        self,
        state: dict,
        symbol: str,
        current_price: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._symbol = symbol
        self._current_price = current_price

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._analyze())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def _analyze(self) -> None:
        from guanlan.core.services.ai import get_ai_client
        from guanlan.core.services.ai.prompts import (
            CHART_ANALYSIS_SYSTEM,
            format_chart_analysis_prompt,
        )

        try:
            prompt = format_chart_analysis_prompt(
                self._state,
                self._symbol,
                self._current_price,
            )

            ai = get_ai_client()
            response = await ai.chat(
                prompt,
                system_prompt=CHART_ANALYSIS_SYSTEM,
                model=None,
            )

            data = json.loads(response)
            self.analysis_finished.emit(data)

        except json.JSONDecodeError as e:
            logger.error(f"AI 返回格式错误: {e}, response={response[:200]}")
            self.analysis_error.emit("AI 返回格式错误，请检查日志")
        except Exception as e:
            logger.error(f"AI 分析失败: {e}")
            self.analysis_error.emit(str(e))
