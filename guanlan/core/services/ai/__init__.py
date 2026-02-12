# -*- coding: utf-8 -*-
"""
观澜量化 - AI 服务模块

集成多个 AI 模型（DeepSeek、GLM 等），提供智能分析能力。

Examples
--------
>>> from guanlan.core.services.ai import get_ai_client, chat_sync
>>>
>>> # 异步调用
>>> ai = get_ai_client()
>>> response = await ai.chat("分析螺纹钢走势")
>>>
>>> # 同步调用
>>> response = chat_sync("今日市场热点")
>>>
>>> # 图片分析
>>> response = await ai.chat_with_image(
...     "分析这个 K 线形态",
...     image="screenshot.png"
... )

Author: 海山观澜
"""

from .client import AIClient, get_ai_client, reset_ai_client, chat_sync
from .config import AIConfig, get_config, reset_config
from .models import (
    MessageRole,
    Message,
    ModelConfig,
    ChatResponse,
    AIServiceError,
    ModelNotFoundError,
    ConfigError,
    APIError,
    VisionNotSupportedError,
)
from .prompts import (
    MARKET_ANALYSIS_SYSTEM,
    HOTSPOT_SEARCH_SYSTEM,
    KLINE_ANALYSIS_SYSTEM,
    KLINE_IMAGE_SYSTEM,
    format_kline_prompt,
)


__all__ = [
    # 客户端
    "AIClient",
    "get_ai_client",
    "reset_ai_client",
    "chat_sync",
    # 配置
    "AIConfig",
    "get_config",
    "reset_config",
    # 数据模型
    "MessageRole",
    "Message",
    "ModelConfig",
    "ChatResponse",
    # 异常
    "AIServiceError",
    "ModelNotFoundError",
    "ConfigError",
    "APIError",
    "VisionNotSupportedError",
    # 提示词
    "MARKET_ANALYSIS_SYSTEM",
    "HOTSPOT_SEARCH_SYSTEM",
    "KLINE_ANALYSIS_SYSTEM",
    "KLINE_IMAGE_SYSTEM",
    "format_kline_prompt",
]
