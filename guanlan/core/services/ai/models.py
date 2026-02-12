# -*- coding: utf-8 -*-
"""
观澜量化 - AI 服务数据模型

Author: 海山观澜
"""

from dataclasses import dataclass, field
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str

    def to_dict(self) -> dict:
        """转换为 API 请求格式"""
        return {
            "role": self.role.value,
            "content": self.content
        }


@dataclass
class ModelConfig:
    """单个模型配置"""
    api_base: str
    api_key: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    supports_vision: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        """从字典创建配置"""
        return cls(
            api_base=data.get("api_base", ""),
            api_key=data.get("api_key", ""),
            model=data.get("model", ""),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            supports_vision=data.get("supports_vision", False),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "api_base": self.api_base,
            "api_key": self.api_key,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "supports_vision": self.supports_vision,
        }


@dataclass
class ChatResponse:
    """对话响应"""
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


class AIServiceError(Exception):
    """AI 服务异常基类"""
    pass


class ModelNotFoundError(AIServiceError):
    """模型不存在"""
    pass


class ConfigError(AIServiceError):
    """配置错误"""
    pass


class APIError(AIServiceError):
    """API 调用失败"""
    pass


class VisionNotSupportedError(AIServiceError):
    """模型不支持图片"""
    pass


__all__ = [
    "MessageRole",
    "Message",
    "ModelConfig",
    "ChatResponse",
    "AIServiceError",
    "ModelNotFoundError",
    "ConfigError",
    "APIError",
    "VisionNotSupportedError",
]
