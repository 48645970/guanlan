# -*- coding: utf-8 -*-
"""
观澜量化 - AI 服务客户端

Author: 海山观澜
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None  # type: ignore

from guanlan.core.services.ai.config import AIConfig, get_config
from guanlan.core.services.ai.models import (
    ModelConfig,
    ChatResponse,
    APIError,
    ModelNotFoundError,
    VisionNotSupportedError,
)
from guanlan.core.services.ai.prompts import (
    KLINE_ANALYSIS_SYSTEM,
    KLINE_IMAGE_SYSTEM,
    format_kline_prompt,
)
from guanlan.core.utils.logger import get_logger


logger = get_logger("ai_client")


class AIClient:
    """
    AI 服务客户端

    统一封装多个 AI 模型，提供简洁的调用接口。
    使用 OpenAI 兼容格式，支持 DeepSeek、GLM 等模型。

    Examples
    --------
    >>> client = AIClient()
    >>> response = await client.chat("分析螺纹钢走势")
    >>> print(response)
    """

    def __init__(self, config: AIConfig | None = None):
        """
        初始化客户端

        Parameters
        ----------
        config : AIConfig, optional
            配置对象，默认使用全局配置
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("请安装 openai 库: pip install openai>=1.0.0")

        self._config = config or get_config()
        self._clients: dict[str, AsyncOpenAI] = {}

        logger.info(f"AI 客户端初始化，可用模型: {self._config.list_models()}")

    def _get_client(self, model_name: str) -> tuple[AsyncOpenAI, ModelConfig]:
        """
        获取指定模型的 OpenAI 客户端

        Parameters
        ----------
        model_name : str
            模型名称

        Returns
        -------
        tuple[AsyncOpenAI, ModelConfig]
            客户端和配置
        """
        model_cfg = self._config.get_model_config(model_name)

        if not model_cfg.api_key:
            raise APIError(f"模型 {model_name} 未配置 API Key")

        # 复用已创建的客户端
        cache_key = f"{model_cfg.api_base}:{model_cfg.api_key[:8]}"
        if cache_key not in self._clients:
            import httpx
            # 国内 API 不需要代理，trust_env=False 忽略系统代理设置
            http_client = httpx.AsyncClient(trust_env=False)
            self._clients[cache_key] = AsyncOpenAI(
                api_key=model_cfg.api_key,
                base_url=model_cfg.api_base,
                http_client=http_client,
            )

        return self._clients[cache_key], model_cfg

    def list_models(self) -> list[str]:
        """列出所有可用模型"""
        return self._config.list_models()

    def list_vision_models(self) -> list[str]:
        """列出支持图片的模型"""
        return self._config.list_vision_models()

    def get_default_model(self) -> str:
        """获取默认模型名称"""
        return self._config.default_model

    def set_default_model(self, model_name: str) -> None:
        """设置默认模型"""
        if model_name not in self.list_models():
            raise ModelNotFoundError(f"模型不存在: {model_name}")
        self._config.default_model = model_name
        self._config.save()

    async def chat(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        发送对话请求

        Parameters
        ----------
        message : str
            用户消息
        model : str, optional
            指定模型，默认使用 default_model
        system_prompt : str, optional
            系统提示词
        history : list[dict], optional
            对话历史 [{"role": "user", "content": "..."}, ...]
        temperature : float, optional
            温度参数，覆盖配置
        max_tokens : int, optional
            最大 token 数，覆盖配置

        Returns
        -------
        str
            AI 回复内容

        Examples
        --------
        >>> response = await client.chat("今日市场热点是什么？")
        >>> response = await client.chat(
        ...     "深度分析",
        ...     model="deepseek-reasoner",
        ...     system_prompt="你是专业的量化分析师"
        ... )
        """
        model_name = model or self._config.default_model
        client, model_cfg = self._get_client(model_name)

        # 构建消息列表
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        try:
            response = await client.chat.completions.create(
                model=model_cfg.model,
                messages=messages,
                max_tokens=max_tokens or model_cfg.max_tokens,
                temperature=temperature if temperature is not None else model_cfg.temperature,
            )

            content = response.choices[0].message.content or ""
            logger.debug(f"[{model_name}] 请求成功，回复长度: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"[{model_name}] API 调用失败: {e}")
            raise APIError(f"API 调用失败: {e}")

    async def chat_stream(
        self,
        message: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        history: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """
        流式对话请求，实时返回生成内容

        Parameters
        ----------
        message : str
            用户消息
        model : str, optional
            指定模型
        system_prompt : str, optional
            系统提示词
        history : list[dict], optional
            对话历史
        temperature : float, optional
            温度参数
        max_tokens : int, optional
            最大 token 数

        Yields
        ------
        str
            实时生成的文本片段

        Examples
        --------
        >>> async for chunk in client.chat_stream("分析市场"):
        ...     print(chunk, end="", flush=True)
        """
        model_name = model or self._config.default_model
        client, model_cfg = self._get_client(model_name)

        # 构建消息列表
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        try:
            stream = await client.chat.completions.create(
                model=model_cfg.model,
                messages=messages,
                max_tokens=max_tokens or model_cfg.max_tokens,
                temperature=temperature if temperature is not None else model_cfg.temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"[{model_name}] 流式请求失败: {e}")
            raise APIError(f"流式请求失败: {e}")

    async def chat_with_image(
        self,
        message: str,
        image: str | Path | bytes,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        发送带图片的对话请求

        Parameters
        ----------
        message : str
            用户消息
        image : str | Path | bytes
            图片路径、URL 或二进制数据
        model : str, optional
            指定模型（必须支持 vision），默认自动选择
        system_prompt : str, optional
            系统提示词

        Returns
        -------
        str
            AI 回复内容

        Raises
        ------
        VisionNotSupportedError
            指定的模型不支持图片

        Examples
        --------
        >>> response = await client.chat_with_image(
        ...     "分析这个 K 线图形态",
        ...     image="/path/to/screenshot.png"
        ... )
        """
        # 自动选择或验证模型
        if model:
            model_name = model
            model_cfg = self._config.get_model_config(model_name)
            if not model_cfg.supports_vision:
                raise VisionNotSupportedError(f"模型 {model_name} 不支持图片分析")
        else:
            # 自动选择第一个支持 vision 的模型
            vision_models = self.list_vision_models()
            if not vision_models:
                raise VisionNotSupportedError("没有配置支持图片的模型")
            model_name = vision_models[0]

        client, model_cfg = self._get_client(model_name)

        # 编码图片
        image_url = self._encode_image(image)

        # 构建消息
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # GLM-4V 要求 image_url 在 text 前面
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": message},
            ]
        })

        try:
            response = await client.chat.completions.create(
                model=model_cfg.model,
                messages=messages,
                max_tokens=model_cfg.max_tokens,
            )

            content = response.choices[0].message.content or ""
            logger.debug(f"[{model_name}] 图片分析成功，回复长度: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"[{model_name}] 图片分析失败: {e}")
            raise APIError(f"图片分析失败: {e}")

    def _encode_image(self, image: str | Path | bytes) -> str:
        """
        将图片编码为 data URI 或返回 URL

        Parameters
        ----------
        image : str | Path | bytes
            图片路径、URL 或二进制数据

        Returns
        -------
        str
            data URI 或 URL
        """
        # URL 直接返回
        if isinstance(image, str) and image.startswith(("http://", "https://")):
            return image

        # 读取文件或使用二进制数据
        if isinstance(image, bytes):
            data = image
        else:
            path = Path(image)
            if not path.exists():
                raise FileNotFoundError(f"图片不存在: {image}")
            data = path.read_bytes()

        # 通过文件头检测实际 MIME 类型
        mime_type = "image/png"  # 默认
        if data[:3] == b'\xff\xd8\xff':
            mime_type = "image/jpeg"
        elif data[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            mime_type = "image/gif"
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            mime_type = "image/webp"

        base64_data = base64.b64encode(data).decode()
        logger.debug(f"图片编码: {len(data)} bytes, MIME: {mime_type}")
        return f"data:{mime_type};base64,{base64_data}"

    async def analyze_kline(
        self,
        kline_data: list[dict] | Any,  # 支持 DataFrame
        *,
        symbol: str = "",
        interval: str = "",
        strategy: str = "趋势跟踪",
        model: str | None = None,
    ) -> str:
        """
        分析 K 线数据

        Parameters
        ----------
        kline_data : list[dict] | pd.DataFrame
            K 线数据，包含 datetime, open, high, low, close, volume
        symbol : str
            合约代码
        interval : str
            时间周期（如 "1分钟", "1小时", "日线"）
        strategy : str
            分析策略类型
        model : str, optional
            指定模型

        Returns
        -------
        str
            分析结果

        Examples
        --------
        >>> data = [
        ...     {"datetime": "2025-01-01 09:00", "open": 100, "high": 105,
        ...      "low": 99, "close": 103, "volume": 1000},
        ...     # ...
        ... ]
        >>> response = await client.analyze_kline(
        ...     data, symbol="RB2505", interval="1小时"
        ... )
        """
        # 如果是 DataFrame，转换为 list[dict]
        if hasattr(kline_data, "to_dict"):
            kline_data = kline_data.to_dict("records")

        # 格式化数据为提示词
        prompt = format_kline_prompt(
            kline_data,
            symbol=symbol,
            interval=interval,
            strategy=strategy,
        )

        return await self.chat(
            prompt,
            model=model,
            system_prompt=KLINE_ANALYSIS_SYSTEM,
        )

    async def analyze_kline_image(
        self,
        image: str | Path | bytes,
        *,
        prompt: str = "分析这个 K 线图的形态和趋势，给出交易建议",
        model: str | None = None,
    ) -> str:
        """
        分析 K 线图片

        Parameters
        ----------
        image : str | Path | bytes
            K 线截图
        prompt : str
            分析提示
        model : str, optional
            指定模型（必须支持 vision）

        Returns
        -------
        str
            分析结果
        """
        return await self.chat_with_image(
            prompt,
            image,
            model=model,
            system_prompt=KLINE_IMAGE_SYSTEM,
        )


# 全局客户端实例
_client: AIClient | None = None
_client_config_path: str | Path | None = None


def get_ai_client(config_path: str | Path | None = None) -> AIClient:
    """
    获取 AI 客户端实例

    Parameters
    ----------
    config_path : str | Path | None
        配置文件路径，首次调用时指定，后续调用可省略

    Returns
    -------
    AIClient
        客户端实例

    Examples
    --------
    >>> from guanlan.core.services.ai import get_ai_client
    >>>
    >>> # 使用自定义配置
    >>> ai = get_ai_client("config/ai.json")
    >>>
    >>> # 后续调用自动复用
    >>> ai = get_ai_client()
    >>> response = await ai.chat("今日热点")
    """
    global _client, _client_config_path

    # 如果指定了新路径，重新创建客户端
    if config_path is not None and config_path != _client_config_path:
        _client_config_path = config_path
        # 重置并使用新配置
        from .config import reset_config, get_config
        reset_config()
        get_config(config_path)
        _client = AIClient()

    if _client is None:
        if config_path:
            from .config import get_config
            get_config(config_path)
        _client = AIClient()
        _client_config_path = config_path

    return _client


def reset_ai_client() -> None:
    """重置全局客户端（用于测试或切换配置）"""
    global _client, _client_config_path
    _client = None
    _client_config_path = None


def chat_sync(
    message: str,
    *,
    model: str | None = None,
    system_prompt: str | None = None,
    config_path: str | Path | None = None,
) -> str:
    """
    同步版本的对话接口

    Parameters
    ----------
    message : str
        用户消息
    model : str, optional
        指定模型
    system_prompt : str, optional
        系统提示词
    config_path : str | Path | None
        配置文件路径

    Returns
    -------
    str
        AI 回复

    Examples
    --------
    >>> from guanlan.core.services.ai import chat_sync
    >>> response = chat_sync("分析螺纹钢走势", config_path="config/ai.json")
    """
    client = get_ai_client(config_path)
    return asyncio.run(client.chat(
        message,
        model=model,
        system_prompt=system_prompt,
    ))


__all__ = [
    "AIClient",
    "get_ai_client",
    "reset_ai_client",
    "chat_sync",
]
