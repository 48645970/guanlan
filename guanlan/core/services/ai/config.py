# -*- coding: utf-8 -*-
"""
观澜量化 - AI 服务配置管理

Author: 海山观澜
"""

import copy
import json
from pathlib import Path

from guanlan.core.services.ai.models import ModelConfig, ConfigError
from guanlan.core.utils.logger import get_logger


logger = get_logger("ai_config")


# 默认配置模板
DEFAULT_CONFIG = {
    "default_model": "deepseek-chat",
    "models": {
        "deepseek-chat": {
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-chat",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_vision": False
        },
        "deepseek-reasoner": {
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-reasoner",
            "max_tokens": 8192,
            "temperature": 0.7,
            "supports_vision": False
        },
        "glm-4v-flash": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "",
            "model": "glm-4v-flash",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_vision": True
        },
        "glm-4.7-flash": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "",
            "model": "glm-4.7-flash",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_vision": False
        },
        "glm-4.6v-flash": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "",
            "model": "glm-4.6v-flash",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_vision": True
        }
    }
}


def _get_default_config_path() -> Path:
    """获取默认配置文件路径"""
    from guanlan.core.constants import CONFIG_DIR
    return CONFIG_DIR / "config" / "ai.json"


class AIConfig:
    """
    AI 服务配置管理

    负责加载、保存、验证配置文件。

    Examples
    --------
    >>> # 使用默认路径 (~/.vntrader/ai_service_setting.json)
    >>> config = AIConfig()
    >>>
    >>> # 指定配置文件路径
    >>> config = AIConfig("config/ai.json")
    >>>
    >>> config.list_models()
    ['deepseek-chat', 'deepseek-reasoner', 'glm-4v-flash']
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        初始化配置管理器

        Parameters
        ----------
        config_path : str | Path | None
            配置文件路径，None 则使用默认路径
        """
        if config_path is None:
            self._filepath = _get_default_config_path()
        else:
            self._filepath = Path(config_path)

        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        """加载配置文件"""
        if self._filepath.exists():
            try:
                with open(self._filepath, encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"配置加载成功: {self._filepath}")
            except Exception as e:
                logger.error(f"配置加载失败: {e}")
                self._data = copy.deepcopy(DEFAULT_CONFIG)
        else:
            # 创建默认配置
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            self.save()
            logger.info(f"已创建默认配置: {self._filepath}")

    def save(self) -> None:
        """保存配置到文件"""
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info(f"配置保存成功: {self._filepath}")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
            raise ConfigError(f"配置保存失败: {e}")

    @property
    def default_model(self) -> str:
        """获取默认模型名称"""
        return self._data.get("default_model", "deepseek-chat")

    @default_model.setter
    def default_model(self, model_name: str) -> None:
        """设置默认模型"""
        if model_name not in self.list_models():
            raise ConfigError(f"模型不存在: {model_name}")
        self._data["default_model"] = model_name

    def list_models(self) -> list[str]:
        """列出所有模型名称"""
        return list(self._data.get("models", {}).keys())

    def list_vision_models(self) -> list[str]:
        """列出支持图片的模型"""
        models = []
        for name, cfg in self._data.get("models", {}).items():
            if cfg.get("supports_vision", False):
                models.append(name)
        return models

    def get_model_config(self, model_name: str) -> ModelConfig:
        """
        获取指定模型配置

        Parameters
        ----------
        model_name : str
            模型名称

        Returns
        -------
        ModelConfig
            模型配置对象

        Raises
        ------
        ConfigError
            模型不存在时抛出
        """
        models = self._data.get("models", {})
        if model_name not in models:
            raise ConfigError(f"模型不存在: {model_name}")
        return ModelConfig.from_dict(models[model_name])

    def add_model(self, name: str, config: ModelConfig) -> None:
        """
        添加模型配置

        Parameters
        ----------
        name : str
            模型名称
        config : ModelConfig
            模型配置
        """
        if "models" not in self._data:
            self._data["models"] = {}
        self._data["models"][name] = config.to_dict()
        logger.info(f"已添加模型: {name}")

    def update_model(self, name: str, **kwargs) -> None:
        """
        更新模型配置

        Parameters
        ----------
        name : str
            模型名称
        **kwargs
            要更新的配置项
        """
        models = self._data.get("models", {})
        if name not in models:
            raise ConfigError(f"模型不存在: {name}")

        for key, value in kwargs.items():
            if key in models[name]:
                models[name][key] = value
        logger.info(f"已更新模型配置: {name}")

    def remove_model(self, name: str) -> None:
        """
        移除模型配置

        Parameters
        ----------
        name : str
            模型名称
        """
        models = self._data.get("models", {})
        if name in models:
            del models[name]
            logger.info(f"已移除模型: {name}")

    def validate(self) -> list[str]:
        """
        验证配置完整性

        Returns
        -------
        list[str]
            缺少 API Key 的模型列表
        """
        missing = []
        for name, cfg in self._data.get("models", {}).items():
            if not cfg.get("api_key"):
                missing.append(name)
        return missing


# 全局配置实例
_config: AIConfig | None = None
_config_path: str | Path | None = None


def get_config(config_path: str | Path | None = None) -> AIConfig:
    """
    获取配置实例

    Parameters
    ----------
    config_path : str | Path | None
        配置文件路径，首次调用时指定，后续调用可省略

    Returns
    -------
    AIConfig
        配置管理器实例

    Examples
    --------
    >>> # 使用自定义路径
    >>> config = get_config("config/ai.json")
    >>>
    >>> # 后续调用自动复用
    >>> config = get_config()
    """
    global _config, _config_path

    # 如果指定了新路径，重新加载
    if config_path is not None and config_path != _config_path:
        _config_path = config_path
        _config = AIConfig(config_path)

    # 首次调用或需要创建
    if _config is None:
        _config = AIConfig(_config_path)

    return _config


def reset_config() -> None:
    """重置全局配置（用于测试或切换配置文件）"""
    global _config, _config_path
    _config = None
    _config_path = None


__all__ = [
    "AIConfig",
    "get_config",
    "reset_config",
    "DEFAULT_CONFIG",
]
