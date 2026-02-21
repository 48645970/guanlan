# -*- coding: utf-8 -*-
"""
观澜量化 - 设置界面

Author: 海山观澜
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel

from logging import DEBUG, INFO, WARNING, ERROR

from PySide6.QtWidgets import QFileDialog

from qfluentwidgets import (
    SettingCardGroup, SwitchSettingCard, OptionsSettingCard,
    HyperlinkCard, ScrollArea, ExpandLayout, CustomColorSettingCard,
    setTheme, setThemeColor, InfoBar, SettingCard, PushSettingCard,
    ExpandGroupSettingCard, SwitchButton, ComboBox,
    LineEdit, PasswordLineEdit, SpinBox
)
from qfluentwidgets import FluentIcon as FIF

from guanlan.core.constants import APP_AUTHOR, APP_VERSION, APP_YEAR, HELP_URL
from guanlan.core.utils.system import is_win11
from guanlan.ui.common.config import cfg
from guanlan.ui.common.mixin import ThemeMixin
from guanlan.ui.common import signal_bus


class SettingInterface(ThemeMixin, ScrollArea):
    """设置界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scroll_widget = QWidget()
        self.expand_layout = ExpandLayout(self.scroll_widget)

        # 设置标题
        self.setting_label = QLabel("设置", self)

        # 个性化设置组
        self.personal_group = SettingCardGroup("个性化", self.scroll_widget)

        # Mica 效果
        self.mica_card = SwitchSettingCard(
            FIF.TRANSPARENT,
            "Mica 效果",
            "窗口和表面使用半透明材质",
            cfg.micaEnabled,
            self.personal_group
        )

        # 主题设置
        self.theme_card = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            "应用主题",
            "调整应用程序的外观",
            texts=["浅色", "深色", "跟随系统"],
            parent=self.personal_group
        )

        # 主题颜色
        self.theme_color_card = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            "主题颜色",
            "调整应用程序的主题颜色",
            self.personal_group
        )

        # DPI 缩放
        self.zoom_card = OptionsSettingCard(
            cfg.dpiScale,
            FIF.ZOOM,
            "界面缩放",
            "调整组件和字体的大小",
            texts=["100%", "125%", "150%", "175%", "200%", "跟随系统"],
            parent=self.personal_group
        )

        # 自动任务设置组
        self.auto_task_group = SettingCardGroup("自动任务", self.scroll_widget)

        self.auto_contract_card = SwitchSettingCard(
            FIF.SYNC,
            "自动更新合约",
            "交易日20:00自动刷新主力合约信息",
            cfg.autoUpdateContract,
            self.auto_task_group
        )

        self.auto_download_card = SwitchSettingCard(
            FIF.DOWNLOAD,
            "自动下载行情数据",
            "交易日20:00自动下载收藏品种的历史行情数据",
            cfg.autoDownloadData,
            self.auto_task_group
        )

        self.auto_recording_card = SwitchSettingCard(
            FIF.ALBUM,
            "自动行情记录",
            "连接行情后自动开始记录收藏品种的实时行情",
            cfg.autoDataRecording,
            self.auto_task_group
        )

        # 数据设置组
        self.data_group = SettingCardGroup("数据", self.scroll_widget)

        self.tdx_path_card = PushSettingCard(
            "选择目录",
            FIF.FOLDER,
            "通达信目录",
            cfg.get(cfg.tdxPath) or "未设置",
            self.data_group
        )

        # 交易设置组
        self.trading_group = SettingCardGroup("交易", self.scroll_widget)

        # 日志配置（可展开卡片）
        self.log_card = ExpandGroupSettingCard(
            FIF.DOCUMENT, "日志配置", "日志记录相关设置", self.trading_group
        )
        self._init_log_card()

        # 钉钉通知配置（可展开卡片）
        self.dingtalk_card = ExpandGroupSettingCard(
            FIF.CHAT, "钉钉通知", "钉钉机器人实时通知配置", self.trading_group
        )
        self._init_dingtalk_card()

        # 数据库配置（可展开卡片）
        self.db_card = ExpandGroupSettingCard(
            FIF.CLOUD, "数据库配置", "数据库连接相关设置", self.trading_group
        )
        self._init_db_card()

        # 关于组
        self.about_group = SettingCardGroup("关于", self.scroll_widget)

        # 免责声明
        self.disclaimer_card = SettingCard(
            FIF.CERTIFICATE,
            "免责声明",
            "本软件仅供学习研究，不构成投资建议，使用者自担风险，作者不承担任何损失责任",
            self.about_group
        )

        # VNPY 说明
        self.vnpy_card = HyperlinkCard(
            "https://www.vnpy.com",
            "访问官网",
            FIF.CODE,
            "基于 VNPY",
            "本项目基于 VNPY 4.3 开源量化交易框架开发，感谢 VNPY 团队的贡献",
            self.about_group
        )

        # 关于
        self.about_card = HyperlinkCard(
            HELP_URL,
            "帮助与反馈",
            FIF.INFO,
            "关于",
            f"版本 {APP_VERSION} · MIT 协议开源，可自由使用和修改",
            self.about_group
        )

        # 汉化组件内部英文文本
        self._localize_widgets()

        self._init_widget()

    def _init_log_card(self) -> None:
        """初始化日志配置卡片"""
        LOG_LEVELS = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARNING", ERROR: "ERROR"}

        # 启用日志
        sw_active = SwitchButton(self)
        sw_active.setOnText("开")
        sw_active.setOffText("关")
        sw_active.setChecked(cfg.get(cfg.logActive))
        sw_active.checkedChanged.connect(lambda v: cfg.set(cfg.logActive, v))
        self.log_card.addGroup(FIF.PLAY, "启用日志", "", sw_active)

        # 日志级别
        cb_level = ComboBox(self)
        cb_level.addItems(list(LOG_LEVELS.values()))
        current_level = cfg.get(cfg.logLevel)
        cb_level.setCurrentText(LOG_LEVELS.get(current_level, "INFO"))
        level_map = {v: k for k, v in LOG_LEVELS.items()}
        cb_level.currentTextChanged.connect(
            lambda t: cfg.set(cfg.logLevel, level_map[t])
        )
        self.log_card.addGroup(FIF.FILTER, "日志级别", "", cb_level)

        # 控制台输出
        sw_console = SwitchButton(self)
        sw_console.setOnText("开")
        sw_console.setOffText("关")
        sw_console.setChecked(cfg.get(cfg.logConsole))
        sw_console.checkedChanged.connect(lambda v: cfg.set(cfg.logConsole, v))
        self.log_card.addGroup(FIF.COMMAND_PROMPT, "控制台输出", "", sw_console)

        # 文件输出
        sw_file = SwitchButton(self)
        sw_file.setOnText("开")
        sw_file.setOffText("关")
        sw_file.setChecked(cfg.get(cfg.logFile))
        sw_file.checkedChanged.connect(lambda v: cfg.set(cfg.logFile, v))
        self.log_card.addGroup(FIF.SAVE, "文件输出", "", sw_file)

    def _init_dingtalk_card(self) -> None:
        """初始化钉钉通知配置卡片"""
        # 启用钉钉通知
        sw_active = SwitchButton(self)
        sw_active.setOnText("开")
        sw_active.setOffText("关")
        sw_active.setChecked(cfg.get(cfg.dingtalkActive))
        sw_active.checkedChanged.connect(lambda v: cfg.set(cfg.dingtalkActive, v))
        self.dingtalk_card.addGroup(FIF.SEND, "启用通知", "", sw_active)

        # Webhook 地址
        le_webhook = LineEdit(self)
        le_webhook.setText(cfg.get(cfg.dingtalkWebhook))
        le_webhook.setMinimumWidth(600)
        le_webhook.setPlaceholderText("https://oapi.dingtalk.com/robot/send?access_token=...")
        le_webhook.editingFinished.connect(
            lambda: cfg.set(cfg.dingtalkWebhook, le_webhook.text())
        )
        self.dingtalk_card.addGroup(FIF.LINK, "Webhook", "", le_webhook)

        # Secret 密钥
        le_secret = PasswordLineEdit(self)
        le_secret.setText(cfg.get(cfg.dingtalkSecret))
        le_secret.setMinimumWidth(600)
        le_secret.setPlaceholderText("SEC...")
        le_secret.editingFinished.connect(
            lambda: cfg.set(cfg.dingtalkSecret, le_secret.text())
        )
        self.dingtalk_card.addGroup(FIF.FINGERPRINT, "Secret", "", le_secret)

    def _init_db_card(self) -> None:
        """初始化数据库配置卡片"""
        DB_DRIVERS = ["arctic", "sqlite", "mysql", "postgresql", "mongodb"]

        # 数据库类型
        cb_driver = ComboBox(self)
        cb_driver.addItems(DB_DRIVERS)
        cb_driver.setCurrentText(cfg.get(cfg.databaseDriver))
        cb_driver.currentTextChanged.connect(
            lambda t: cfg.set(cfg.databaseDriver, t)
        )
        self.db_card.addGroup(FIF.LIBRARY, "数据库类型", "", cb_driver)

        # 数据库名称
        le_name = LineEdit(self)
        le_name.setText(cfg.get(cfg.databaseName))
        le_name.setMinimumWidth(600)
        le_name.editingFinished.connect(
            lambda: cfg.set(cfg.databaseName, le_name.text())
        )
        self.db_card.addGroup(FIF.LABEL, "数据库名称", "", le_name)

        # 服务器地址
        le_host = LineEdit(self)
        le_host.setText(cfg.get(cfg.databaseHost))
        le_host.setMinimumWidth(600)
        le_host.setPlaceholderText("仅非 SQLite 时需要")
        le_host.editingFinished.connect(
            lambda: cfg.set(cfg.databaseHost, le_host.text())
        )
        self.db_card.addGroup(FIF.GLOBE, "服务器地址", "", le_host)

        # 端口
        sp_port = SpinBox(self)
        sp_port.setRange(0, 65535)
        sp_port.setValue(cfg.get(cfg.databasePort))
        sp_port.setMinimumWidth(120)
        sp_port.valueChanged.connect(
            lambda v: cfg.set(cfg.databasePort, v)
        )
        self.db_card.addGroup(FIF.CONNECT, "端口", "", sp_port)

        # 用户名
        le_user = LineEdit(self)
        le_user.setText(cfg.get(cfg.databaseUser))
        le_user.setMinimumWidth(600)
        le_user.setPlaceholderText("仅非 SQLite 时需要")
        le_user.editingFinished.connect(
            lambda: cfg.set(cfg.databaseUser, le_user.text())
        )
        self.db_card.addGroup(FIF.PEOPLE, "用户名", "", le_user)

        # 密码
        le_pwd = PasswordLineEdit(self)
        le_pwd.setText(cfg.get(cfg.databasePassword))
        le_pwd.setMinimumWidth(600)
        le_pwd.setPlaceholderText("仅非 SQLite 时需要")
        le_pwd.editingFinished.connect(
            lambda: cfg.set(cfg.databasePassword, le_pwd.text())
        )
        self.db_card.addGroup(FIF.FINGERPRINT, "密码", "", le_pwd)

    def _localize_widgets(self) -> None:
        """汉化组件内部英文文本"""
        # SwitchSettingCard: Off/On → 关/开
        for card in (self.mica_card, self.auto_contract_card,
                     self.auto_download_card, self.auto_recording_card):
            self._localize_switch_card(card)

        # CustomColorSettingCard: Default color/Custom color/Choose color
        self.theme_color_card.defaultRadioButton.setText("默认颜色")
        self.theme_color_card.customRadioButton.setText("自定义颜色")
        self.theme_color_card.customLabel.setText("自定义颜色")
        self.theme_color_card.chooseColorButton.setText("选择颜色")
        self.theme_color_card.choiceLabel.setText(
            self.theme_color_card.buttonGroup.checkedButton().text()
        )
        self.theme_color_card.choiceLabel.adjustSize()

    @staticmethod
    def _localize_switch_card(card: SwitchSettingCard) -> None:
        """汉化 SwitchSettingCard 的开/关文本"""
        switch = card.switchButton
        switch._offText = "关"
        switch._onText = "开"
        switch.setText("开" if switch.isChecked() else "关")

        _original_set_value = card.setValue

        def _set_value_zh(isChecked: bool) -> None:
            _original_set_value(isChecked)
            switch.setText("开" if isChecked else "关")

        card.setValue = _set_value_zh

    def _init_widget(self):
        """初始化组件"""
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scroll_widget)
        self.setWidgetResizable(True)
        self.setObjectName("settingInterface")

        # 设置 objectName
        self.scroll_widget.setObjectName("scrollWidget")
        self.setting_label.setObjectName("settingLabel")

        # Mica 效果仅在 Windows 11 可用
        self.mica_card.setEnabled(is_win11())

        # 初始化布局
        self._init_layout()
        self._connect_signal_to_slot()

        # 初始化主题监听
        self._init_theme()

    def _init_layout(self):
        """初始化布局"""
        self.setting_label.move(36, 30)

        # 添加卡片到组
        self.personal_group.addSettingCard(self.mica_card)
        self.personal_group.addSettingCard(self.theme_card)
        self.personal_group.addSettingCard(self.theme_color_card)
        self.personal_group.addSettingCard(self.zoom_card)

        # 数据组
        self.data_group.addSettingCard(self.tdx_path_card)

        self.about_group.addSettingCard(self.disclaimer_card)
        self.about_group.addSettingCard(self.vnpy_card)
        self.about_group.addSettingCard(self.about_card)

        # 自动任务组
        self.auto_task_group.addSettingCard(self.auto_contract_card)
        self.auto_task_group.addSettingCard(self.auto_download_card)
        self.auto_task_group.addSettingCard(self.auto_recording_card)

        # 交易组
        self.trading_group.addSettingCard(self.log_card)
        self.trading_group.addSettingCard(self.dingtalk_card)
        self.trading_group.addSettingCard(self.db_card)

        # 添加组到布局
        self.expand_layout.setSpacing(28)
        self.expand_layout.setContentsMargins(36, 10, 36, 0)
        self.expand_layout.addWidget(self.personal_group)
        self.expand_layout.addWidget(self.data_group)
        self.expand_layout.addWidget(self.auto_task_group)
        self.expand_layout.addWidget(self.trading_group)
        self.expand_layout.addWidget(self.about_group)


    def _show_restart_tooltip(self):
        """显示重启提示"""
        InfoBar.success(
            "更新成功",
            "配置将在重启后生效",
            duration=1500,
            parent=self
        )

    def _on_tdx_path_clicked(self) -> None:
        """选择通达信目录"""
        folder = QFileDialog.getExistingDirectory(
            self, "选择通达信安装目录", cfg.get(cfg.tdxPath)
        )
        if not folder:
            return

        cfg.set(cfg.tdxPath, folder)
        self.tdx_path_card.setContent(folder)

    def _connect_signal_to_slot(self):
        """连接信号到槽函数"""
        cfg.appRestartSig.connect(self._show_restart_tooltip)

        # 数据
        self.tdx_path_card.clicked.connect(self._on_tdx_path_clicked)

        # 个性化
        cfg.themeChanged.connect(setTheme)
        self.theme_color_card.colorChanged.connect(lambda c: setThemeColor(c))
        self.mica_card.checkedChanged.connect(signal_bus.mica_enabled_changed)
