"""规则文件编辑对话框。

提供 GUI 内嵌的 YAML 规则文件编辑器，支持选择已加载的规则文件、
编辑内容、保存并重新加载规则集，并提供入口调用独立的正则表达式测试工具。
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

try:
    from PySide2.QtCore import Signal
    from PySide2.QtWidgets import (
        QDialog,
        QMessageBox,
        QWidget,
    )
except ImportError:  # pragma: no cover
    from PySide6.QtCore import Signal  # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import (  # pyrefly: ignore [missing-import]
        QDialog,
        QMessageBox,
        QWidget,
    )

from fuscan.gui.regex_tester import RegexTesterDialog
from fuscan.gui.rule_editor_ui import Ui_RuleEditorDialog
from fuscan.rules import RuleError, load_ruleset

__all__ = ["RuleEditorDialog"]

logger = logging.getLogger(__name__)


class RuleEditorDialog(QDialog, Ui_RuleEditorDialog):  # pyrefly: ignore [invalid-inheritance]
    """规则文件编辑对话框。

    信号：

    - ``rules_saved``：规则文件保存后发射，携带被修改的文件路径
    """

    rules_saved = Signal(str)

    def __init__(
        self,
        rules_paths: list[Path],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rules_paths = rules_paths
        self.setupUi(self)
        self._configure_ui()

    def _configure_ui(self) -> None:
        """配置 .ui 无法静态表达的动态属性、初始内容与信号槽连接。"""
        # 填充文件下拉框
        for path in self._rules_paths:
            self.file_combo.addItem(path.name, str(path))

        # 信号槽连接
        self.file_combo.currentIndexChanged.connect(self._on_file_changed)
        self.reload_btn.clicked.connect(self._on_reload)
        self.save_btn.clicked.connect(self._on_save)
        self.regex_tester_btn.clicked.connect(self._on_open_regex_tester)

        # 无规则文件时的空态处理
        if not self._rules_paths:
            self.empty_label.setVisible(True)
            self.rule_editor.setEnabled(False)
            self.reload_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
        else:
            self._load_file_content(0)

        # layout 伸缩比例：
        # 0 file_layout, 1 empty_label, 2 rule_editor, 3 btn_layout
        # 规则编辑区占主要空间，其余固定
        self.main_layout.setStretch(0, 0)
        self.main_layout.setStretch(1, 0)
        self.main_layout.setStretch(2, 1)
        self.main_layout.setStretch(3, 0)

    def _on_file_changed(self, index: int) -> None:
        """切换文件时加载对应内容。"""
        self._load_file_content(index)

    def _load_file_content(self, index: int) -> None:
        """加载指定索引的文件内容到编辑器。"""
        if index < 0 or index >= len(self._rules_paths):
            self.rule_editor.setPlainText("")
            return
        path = self._rules_paths[index]
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("读取规则文件失败 %s", path, exc_info=True)
            self.rule_editor.setPlainText(f"读取文件失败: {exc}")
            self.rule_editor.setEnabled(False)
            return
        self.rule_editor.setPlainText(content)
        self.rule_editor.setEnabled(True)

    def _on_reload(self) -> None:
        """放弃修改，从文件重新加载。"""
        idx = self.file_combo.currentIndex()
        self._load_file_content(idx)

    def _on_save(self) -> None:
        """保存当前编辑内容到文件，验证后通知主窗口重新加载。"""
        idx = self.file_combo.currentIndex()
        if idx < 0 or idx >= len(self._rules_paths):
            return
        path = self._rules_paths[idx]
        content = self.rule_editor.toPlainText()

        # 验证 YAML 语法
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            QMessageBox.warning(self, "YAML 语法错误", f"YAML 解析失败:\n{exc}")
            return

        # 验证规则可加载
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"写入文件失败:\n{exc}")
            return

        # 验证规则解析
        try:
            load_ruleset(path)
        except RuleError as exc:
            QMessageBox.warning(
                self,
                "规则解析错误",
                f"文件已保存但规则解析失败:\n{exc}\n\n请修正后重新保存。",
            )
            self.rules_saved.emit(str(path))  # pyrefly: ignore [missing-attribute]
            return

        self.rules_saved.emit(str(path))  # pyrefly: ignore [missing-attribute]
        QMessageBox.information(self, "保存成功", f"规则文件已保存并重新加载:\n{path.name}")

    def _on_open_regex_tester(self) -> None:
        """打开独立的正则表达式测试工具窗口。

        以模态方式弹出 ``RegexTesterDialog``，便于用户在编辑规则时
        验证正则表达式是否符合预期。
        """
        dialog = RegexTesterDialog(parent=self)
        dialog.exec_()
