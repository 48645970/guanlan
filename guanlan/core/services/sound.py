# -*- coding: utf-8 -*-
"""
观澜量化 - 音频播放服务

使用 pygame.mixer.Sound 实现多通道并行播放，多个音效互不打断。
Sound 对象按文件路径缓存，避免重复加载。

Author: 海山观澜
"""

from pathlib import Path
from typing import Literal

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from guanlan.core.utils.logger import get_simple_logger


logger = get_simple_logger("sound", level=20)


# 预定义音效类型
SoundType = Literal[
    "buy",        # 买入下单
    "sell",       # 卖出下单
    "con_buy",    # 买入成交（开多）
    "con_sell",   # 卖出成交（开空）
    "con_close",  # 平仓成交
    "cancel",     # 撤单
    "error",      # 错误
    "alarm",      # 报警
    "connect",    # 账户连接
    "disconnect", # 账户断开
    "begin_5",    # 开盘前5分钟
    "end_5",      # 收盘前5分钟
    "begin_0",    # 开盘
    "end_0",      # 收盘
]


class SoundPlayer:
    """音频播放器（单例模式）

    使用 pygame.mixer.Sound 多通道播放，音效互不打断。

    Examples
    --------
    >>> player = SoundPlayer.get_instance()
    >>> player.play("buy")
    >>> player.set_volume(0.5)
    """

    _instance: "SoundPlayer | None" = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if not PYGAME_AVAILABLE:
            logger.warning("pygame 库未安装，音频播放功能不可用")
            self._available = False
            self._initialized = True
            return

        try:
            pygame.mixer.init()
            self._available = True
            self._volume = 1.0
            self._cache: dict[str, "pygame.mixer.Sound"] = {}

            from guanlan.core.constants import RESOURCES_SOUNDS_DIR
            self._sound_dir = RESOURCES_SOUNDS_DIR

            logger.info(f"音频播放器初始化成功，音频目录: {self._sound_dir}")

        except Exception as e:
            logger.error(f"音频播放器初始化失败: {e}")
            self._available = False

        self._initialized = True

    @classmethod
    def get_instance(cls) -> "SoundPlayer":
        """获取播放器实例"""
        return cls()

    def is_available(self) -> bool:
        """检查播放器是否可用"""
        return self._available

    def set_volume(self, volume: float) -> None:
        """设置音量（0.0 - 1.0），对后续播放生效"""
        if not self._available:
            return
        self._volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        """获取当前音量"""
        return self._volume

    def play(self, sound_type: SoundType) -> None:
        """播放预定义音效"""
        if not self._available:
            return
        self.play_file(f"{sound_type}.wav")

    def play_file(self, filename: str) -> None:
        """播放指定音频文件（多通道，互不打断）"""
        if not self._available:
            return

        try:
            file_path = self._sound_dir / filename
            key = str(file_path)

            sound = self._cache.get(key)
            if sound is None:
                if not file_path.exists():
                    logger.warning(f"音频文件不存在: {file_path}")
                    return
                sound = pygame.mixer.Sound(str(file_path))
                self._cache[key] = sound

            sound.set_volume(self._volume)

            sound.play()

        except Exception as e:
            logger.error(f"播放音频失败: {e}")

    def stop(self) -> None:
        """停止所有通道播放"""
        if not self._available:
            return
        try:
            pygame.mixer.stop()
        except Exception as e:
            logger.error(f"停止播放失败: {e}")

    def is_playing(self) -> bool:
        """检查是否有通道正在播放"""
        if not self._available:
            return False
        try:
            return pygame.mixer.get_busy()
        except Exception as e:
            logger.error(f"检查播放状态失败: {e}")
            return False


# ── 便捷函数 ──

_player: SoundPlayer | None = None


def get_player() -> SoundPlayer:
    """获取全局播放器实例"""
    global _player
    if _player is None:
        _player = SoundPlayer.get_instance()
    return _player


def play(sound_type: SoundType) -> None:
    """播放预定义音效"""
    get_player().play(sound_type)


def play_file(filename: str) -> None:
    """播放音频文件"""
    get_player().play_file(filename)


__all__ = [
    "SoundType",
    "SoundPlayer",
    "get_player",
    "play",
    "play_file",
]
