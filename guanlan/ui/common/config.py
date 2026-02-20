# -*- coding: utf-8 -*-
"""
观澜量化 - 配置管理模块

基于 QFluentWidgets QConfig 实现配置的自动持久化。

Author: 海山观澜
"""

from enum import Enum
from logging import DEBUG, INFO, WARNING, ERROR
from pathlib import Path

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor
from tzlocal import get_localzone_name
from qfluentwidgets import (
    qconfig, QConfig, ConfigItem, OptionsConfigItem, BoolValidator,
    OptionsValidator, RangeConfigItem, RangeValidator, Theme,
    ConfigSerializer, ColorConfigItem, EnumSerializer
)

# 从 core 导入常量
from guanlan.core.constants import (
    APP_NAME, APP_VERSION, APP_AUTHOR, APP_YEAR, HELP_URL,
    DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_WIDTH,
    CONFIG_DIR
)
from guanlan.core.utils.logger import get_logger

logger = get_logger(__name__)


class Language(Enum):
    """语言枚举"""
    CHINESE_SIMPLIFIED = QLocale(QLocale.Chinese, QLocale.China)
    ENGLISH = QLocale(QLocale.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """语言序列化器"""

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO


class GuanlanConfig(QConfig):
    """
    观澜应用配置

    特性：
    - 自动序列化/反序列化 JSON
    - 类型验证
    - 值变化触发信号
    - 与 SettingCard 无缝集成
    """

    # ==================== 窗口配置 ====================
    windowWidth = ConfigItem("Window", "Width", DEFAULT_WINDOW_WIDTH)
    windowHeight = ConfigItem("Window", "Height", DEFAULT_WINDOW_HEIGHT)
    windowMinWidth = ConfigItem("Window", "MinWidth", MIN_WINDOW_WIDTH)
    windowX = ConfigItem("Window", "X", -1)  # -1 表示居中显示（仅 Windows）
    windowY = ConfigItem("Window", "Y", -1)  # -1 表示居中显示（仅 Windows）
    windowMaximized = ConfigItem("Window", "Maximized", False, BoolValidator())

    # Mica 效果（仅 Windows 11）
    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", False, BoolValidator())

    # DPI 缩放
    dpiScale = OptionsConfigItem(
        "MainWindow", "DpiScale", "Auto",
        OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]),
        restart=True
    )

    # 语言设置
    language = OptionsConfigItem(
        "MainWindow", "Language", Language.AUTO,
        OptionsValidator(Language),
        LanguageSerializer(),
        restart=True
    )

    # ==================== 主题配置 ====================
    themeMode = OptionsConfigItem(
        "Theme", "Mode", Theme.DARK,
        OptionsValidator(Theme),
        EnumSerializer(Theme),
        restart=False
    )
    themeColor = ColorConfigItem(
        "Theme", "Color", QColor(0, 153, 188)
    )

    # 亚克力模糊半径
    blurRadius = RangeConfigItem(
        "Material", "AcrylicBlurRadius", 15,
        RangeValidator(0, 40)
    )

    # ==================== 交易配置 ====================
    defaultAccount = ConfigItem("Trading", "DefaultAccount", "")
    autoConnect = ConfigItem("Trading", "AutoConnect", False, BoolValidator())
    confirmOrder = ConfigItem("Trading", "ConfirmOrder", True, BoolValidator())

    # ==================== 策略配置 ====================
    strategyPath = ConfigItem("Strategy", "Path", "user_strategies/")
    autoLoadStrategies = ConfigItem("Strategy", "AutoLoad", True, BoolValidator())
    maxStrategies = RangeConfigItem("Strategy", "MaxCount", 20, RangeValidator(1, 100))

    # ==================== 日志配置 ====================
    logActive = ConfigItem("Log", "Active", True, BoolValidator())
    logLevel = OptionsConfigItem(
        "Log", "Level", INFO,
        OptionsValidator([DEBUG, INFO, WARNING, ERROR]),
        restart=True
    )
    logConsole = ConfigItem("Log", "Console", True, BoolValidator())
    logFile = ConfigItem("Log", "File", True, BoolValidator())

    # ==================== 数据库配置 ====================
    databaseTimezone = ConfigItem("Database", "Timezone", get_localzone_name())
    databaseDriver = OptionsConfigItem(
        "Database", "Driver", "sqlite",
        OptionsValidator(["sqlite", "mysql", "postgresql", "mongodb"]),
        restart=True
    )
    databaseName = ConfigItem("Database", "Name", "database.db")
    databaseHost = ConfigItem("Database", "Host", "")
    databasePort = RangeConfigItem(
        "Database", "Port", 0, RangeValidator(0, 65535)
    )
    databaseUser = ConfigItem("Database", "User", "")
    databasePassword = ConfigItem("Database", "Password", "")

    # ==================== 钉钉通知配置 ====================
    dingtalkActive = ConfigItem("DingTalk", "Active", False, BoolValidator())
    dingtalkWebhook = ConfigItem("DingTalk", "Webhook", "")
    dingtalkSecret = ConfigItem("DingTalk", "Secret", "")

    # ==================== 声音配置 ====================
    enableSound = ConfigItem("Sound", "Enable", True, BoolValidator())
    soundVolume = RangeConfigItem("Sound", "Volume", 80, RangeValidator(0, 100))

    # ==================== 自动任务配置 ====================
    autoUpdateContract = ConfigItem("AutoTask", "UpdateContract", True, BoolValidator())
    autoDownloadData = ConfigItem("AutoTask", "DownloadData", True, BoolValidator())
    autoDataRecording = ConfigItem("AutoTask", "DataRecording", False, BoolValidator())

    # ==================== 数据配置 ====================
    tdxPath = ConfigItem("Data", "TdxPath", "")

    # ==================== 更新配置 ====================
    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())


# ==================== 配置实例 ====================
cfg = GuanlanConfig()

# 配置文件路径
CONFIG_FILE = CONFIG_DIR / "config" / "setting.json"


def load_config():
    """加载配置"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    qconfig.load(str(CONFIG_FILE), cfg)


def save_config():
    """保存配置"""
    try:
        qconfig.save()
    except Exception as e:
        logger.warning(f"配置保存失败: {e}")
