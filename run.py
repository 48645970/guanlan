# -*- coding: utf-8 -*-
"""
观澜量化 - 应用入口

Author: 海山观澜
"""

import os
import sys
from pathlib import Path

# 抑制 Qt 平台插件的透明度警告
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"

# VNPY 4.3 用 gettext 国际化，默认跟系统 locale（英文环境会显示 Long/Short）
# 强制使用中文，让枚举值回退到源字符串（多/空/开/平/未成交 等）
os.environ["LANGUAGE"] = "zh_CN"

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QLocale
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QFontDatabase, QFont
from qfluentwidgets import FluentTranslator, setTheme, setThemeColor

from guanlan.core.constants import APP_NAME, APP_NAME_EN, APP_AUTHOR
from guanlan.ui.common.config import cfg, load_config

def main() -> None:
    """应用程序入口"""
    # 加载配置
    load_config()

    # DPI 缩放配置
    dpi_scale = cfg.get(cfg.dpiScale)
    if dpi_scale != "Auto":
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(dpi_scale)

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 设置中文翻译
    locale = cfg.get(cfg.language).value
    translator = FluentTranslator(locale)
    app.installTranslator(translator)

    # 设置应用信息
    app.setApplicationName(APP_NAME_EN.lower().replace(" ", "-"))
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_AUTHOR)
    app.setOrganizationDomain("guanlan.quant")
    app.setDesktopFileName("guanlan")

    # 设置应用图标（任务栏显示）
    icon_path = PROJECT_ROOT / "ui" / "images" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 设置默认字体（优先使用内置简体中文字体）
    for font_name in ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei"]:
        if QFontDatabase.hasFamily(font_name):
            app.setFont(QFont(font_name))
            break
        
    # 设置主题
    setTheme(cfg.get(cfg.themeMode))
    setThemeColor(cfg.get(cfg.themeColor))

    # 安装全局异常捕获（必须在 QApplication 创建之后）
    from guanlan.ui.view.window.exception import install_exception_hook
    exception_dialog = install_exception_hook()  # noqa: F841  保持引用防止 GC

    # 初始化全局引擎
    from guanlan.core.app import AppEngine
    app_engine = AppEngine.instance()

    # 创建主窗口
    from guanlan.ui.view import MainWindow
    window = MainWindow()
    window.show()

    # 自动连接标记了自动登录的账户
    app_engine.auto_connect()

    # 启动事件循环
    ret = app.exec()

    # 清理全局引擎（CTP exit() 有 segfault 缺陷，用 os._exit 兜底）
    app_engine.close()

    os._exit(ret)


if __name__ == "__main__":
    main()
