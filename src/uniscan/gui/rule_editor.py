"""规则文件编辑对话框。

提供 GUI 内嵌的 YAML 规则文件编辑器，支持选择已加载的规则文件、
编辑内容、保存并重新加载规则集。
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from PySide2.QtCore import Signal
from PySide2.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from uniscan.rules import RuleError, load_ruleset

__all__ = ["RuleEditorDialog"]

logger = logging.getLogger(__name__)


class RuleEditorDialog(QDialog):
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
        self.setWindowTitle("规则编辑器")
        self.resize(700, 500)
        self._init_ui()
        if rules_paths:
            self._file_combo.setCurrentIndex(0)

    def _init_ui(self) -> None:
        """初始化对话框布局。"""
        layout = QVBoxLayout(self)

        # 文件选择栏
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("规则文件:"))
        self._file_combo = QComboBox()
        for path in self._rules_paths:
            self._file_combo.addItem(path.name, str(path))
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        file_layout.addWidget(self._file_combo, stretch=1)
        layout.addLayout(file_layout)

        if not self._rules_paths:
            layout.addWidget(QLabel("（未加载任何规则文件）"))
            self._editor = QTextEdit()
            self._editor.setEnabled(False)
            layout.addWidget(self._editor, stretch=1)
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(self.accept)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)
            return

        # 编辑区
        self._editor = QTextEdit()
        self._editor.setFontFamily("Consolas")
        self._editor.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 13px;")
        layout.addWidget(self._editor, stretch=1)

        # 按钮栏
        btn_layout = QHBoxLayout()
        reload_btn = QPushButton("重新加载")
        reload_btn.setToolTip("放弃修改，从文件重新加载内容")
        reload_btn.clicked.connect(self._on_reload)
        btn_layout.addWidget(reload_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("保存并应用")
        save_btn.setToolTip("保存文件并重新加载规则集")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._load_file_content(0)

    def _on_file_changed(self, index: int) -> None:
        """切换文件时加载对应内容。"""
        self._load_file_content(index)

    def _load_file_content(self, index: int) -> None:
        """加载指定索引的文件内容到编辑器。"""
        if index < 0 or index >= len(self._rules_paths):
            self._editor.setPlainText("")
            return
        path = self._rules_paths[index]
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("读取规则文件失败 %s", path, exc_info=True)
            self._editor.setPlainText(f"读取文件失败: {exc}")
            self._editor.setEnabled(False)
            return
        self._editor.setPlainText(content)
        self._editor.setEnabled(True)

    def _on_reload(self) -> None:
        """放弃修改，从文件重新加载。"""
        idx = self._file_combo.currentIndex()
        self._load_file_content(idx)

    def _on_save(self) -> None:
        """保存当前编辑内容到文件，验证后通知主窗口重新加载。"""
        idx = self._file_combo.currentIndex()
        if idx < 0 or idx >= len(self._rules_paths):
            return
        path = self._rules_paths[idx]
        content = self._editor.toPlainText()

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
            self.rules_saved.emit(str(path))
            return

        self.rules_saved.emit(str(path))
        QMessageBox.information(self, "保存成功", f"规则文件已保存并重新加载:\n{path.name}")
