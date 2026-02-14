# -*- coding: utf-8 -*-
"""
观澜量化 - 图表方案对话框

包含保存方案对话框和方案管理对话框。

Author: 海山观澜
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, LineEdit,
    TransparentToolButton, FluentIcon, InfoBar, InfoBarPosition,
    MessageBox,
)

from guanlan.core.setting import chart_scheme


class SaveSchemeDialog(MessageBoxBase):
    """保存方案对话框"""

    def __init__(self, default_name: str, parent=None) -> None:
        super().__init__(parent)

        self.widget.setMinimumWidth(360)

        title = SubtitleLabel("保存方案")
        self.viewLayout.addWidget(title)

        self._name_edit = LineEdit(self)
        self._name_edit.setPlaceholderText("请输入方案名称")
        self._name_edit.setText(default_name)
        self._name_edit.selectAll()
        self._name_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self._name_edit)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

    def get_name(self) -> str:
        """获取输入的方案名称"""
        return self._name_edit.text().strip()

    def validate(self) -> bool:
        """校验输入"""
        name = self.get_name()
        if not name:
            InfoBar.warning(
                "提示", "方案名称不能为空",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return False

        schemes = chart_scheme.load_schemes()
        if name in schemes:
            InfoBar.warning(
                "提示", f"方案 \"{name}\" 已存在，请换个名称",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return False

        return True

    def _onYesButtonClicked(self):
        """重写确认按钮点击"""
        if self.validate():
            super()._onYesButtonClicked()


class _SchemeRow(QWidget):
    """方案管理列表中的单行"""

    def __init__(self, name: str, parent: "SchemeManagerDialog") -> None:
        super().__init__(parent)
        self._name = name
        self._manager = parent

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._label = BodyLabel(name)
        layout.addWidget(self._label)
        layout.addStretch()

        # 重命名按钮
        btn_rename = TransparentToolButton(FluentIcon.EDIT)
        btn_rename.setFixedSize(30, 30)
        btn_rename.setIconSize(QSize(14, 14))
        btn_rename.setToolTip("重命名")
        btn_rename.clicked.connect(self._on_rename)
        layout.addWidget(btn_rename)

        # 删除按钮
        btn_delete = TransparentToolButton(FluentIcon.DELETE)
        btn_delete.setFixedSize(30, 30)
        btn_delete.setIconSize(QSize(14, 14))
        btn_delete.setToolTip("删除")
        btn_delete.clicked.connect(self._on_delete)
        layout.addWidget(btn_delete)

    def _on_rename(self) -> None:
        """重命名方案"""
        dlg = _RenameDialog(self._name, self._manager)
        if dlg.exec():
            new_name = dlg.get_name()
            chart_scheme.rename_scheme(self._name, new_name)
            self._name = new_name
            self._label.setText(new_name)

    def _on_delete(self) -> None:
        """删除方案"""
        dlg = MessageBox(
            "确认删除",
            f"确定要删除方案 \"{self._name}\" 吗？",
            self._manager,
        )
        dlg.yesButton.setText("删除")
        dlg.cancelButton.setText("取消")
        if dlg.exec():
            chart_scheme.delete_scheme(self._name)
            self.setParent(None)
            self.deleteLater()


class _RenameDialog(MessageBoxBase):
    """重命名对话框"""

    def __init__(self, old_name: str, parent=None) -> None:
        super().__init__(parent)
        self._old_name = old_name

        self.widget.setMinimumWidth(320)

        title = SubtitleLabel("重命名方案")
        self.viewLayout.addWidget(title)

        self._name_edit = LineEdit(self)
        self._name_edit.setText(old_name)
        self._name_edit.selectAll()
        self._name_edit.setClearButtonEnabled(True)
        self.viewLayout.addWidget(self._name_edit)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

    def get_name(self) -> str:
        return self._name_edit.text().strip()

    def _onYesButtonClicked(self):
        name = self.get_name()
        if not name:
            InfoBar.warning(
                "提示", "名称不能为空",
                parent=self, duration=2000, position=InfoBarPosition.TOP,
            )
            return
        if name != self._old_name:
            schemes = chart_scheme.load_schemes()
            if name in schemes:
                InfoBar.warning(
                    "提示", f"方案 \"{name}\" 已存在",
                    parent=self, duration=2000, position=InfoBarPosition.TOP,
                )
                return
        super()._onYesButtonClicked()


class SchemeManagerDialog(MessageBoxBase):
    """方案管理对话框"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.widget.setMinimumWidth(400)

        title = SubtitleLabel("方案管理")
        self.viewLayout.addWidget(title)
        self.viewLayout.addSpacing(8)

        # 方案列表容器
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        schemes = chart_scheme.load_schemes()
        if not schemes:
            empty = BodyLabel("暂无保存的方案")
            empty.setAlignment(Qt.AlignCenter)
            self._container_layout.addWidget(empty)
        else:
            for name in schemes:
                row = _SchemeRow(name, self)
                self._container_layout.addWidget(row)

        self._container_layout.addStretch()
        self.viewLayout.addWidget(self._container)

        # 只需要关闭按钮
        self.yesButton.setText("关闭")
        self.cancelButton.hide()

    def _onYesButtonClicked(self):
        """关闭按钮直接关闭"""
        self.accept()
        self.accepted.emit()
