# -*- coding: utf-8 -*-
"""
观澜量化 - 风格化按钮组件

提供不同语义的按钮变体，样式通过 QSS 类名选择器匹配，
统一定义在 widgets/styled_button.qss 中，支持 dark/light 主题。

Author: 海山观澜
"""

from qfluentwidgets import PushButton

from guanlan.ui.common.style import StyleSheet

_QSS_FILE = "widgets/styled_button.qss"


class DangerPushButton(PushButton):
    """危险操作按钮（红色警示）"""

    def _postInit(self):
        super()._postInit()
        StyleSheet.apply(self, _QSS_FILE)
