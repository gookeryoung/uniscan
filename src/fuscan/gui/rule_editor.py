"""规则文件编辑对话框。

提供 GUI 内嵌的 YAML 规则文件编辑器，支持选择已加载的规则文件、
编辑内容、保存并重新加载规则集，并集成正则表达式验证面板。
"""

from __future__ import annotations

import logging
import re
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

from fuscan.gui.rule_editor_ui import Ui_RuleEditorDialog
from fuscan.rules import RuleError, load_ruleset

__all__ = ["RuleEditorDialog"]

logger = logging.getLogger(__name__)

# 正则速查手册内容（Python re 模块常用语法）
_REGEX_CHEATSHEET = """\
== 字符类 ==
.          任意字符（不含换行，flags=re.S 可让其匹配换行）
\\d  \\D     数字 / 非数字
\\w  \\W     单词字符 [A-Za-z0-9_] / 非单词字符
\\s  \\S     空白 / 非空白
[abc]      任一字符
[a-z]      范围
[^abc]     排除指定字符

== 量词 ==
*          0 或多次（贪婪）
+          1 或多次（贪婪）
?          0 或 1 次
{n}        恰好 n 次
{n,}       至少 n 次
{n,m}      n 到 m 次
*? +? ??   非贪婪（最小匹配）

== 锚点 ==
^          行首
$          行尾
\\b  \\B     单词边界 / 非单词边界

== 分组与捕获 ==
(...)              捕获组（可用 \\1 反向引用）
(?:...)            非捕获组
(?P<name>...)      命名捕获组
(?P=name)          引用命名组

== 零宽断言 ==
(?=...)    正向先行断言
(?!...)    负向先行断言
(?<=...)   正向后行断言
(?<!...)   负向后行断言

== 内联修饰符 ==
(?i)       忽略大小写
(?m)       多行模式（^/$ 匹配每行）
(?s)       . 匹配换行

== 常用示例 ==
\\d{4}-\\d{2}-\\d{2}                                    日期 YYYY-MM-DD
\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b   邮箱
\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b                        IPv4 地址
1[3-9]\\d{9}                                          中国手机号
""".strip()


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
        self.regex_test_btn.clicked.connect(self._on_test_regex)
        # 回车键也触发测试
        self.regex_pattern_edit.returnPressed.connect(self._on_test_regex)

        # 初始化速查手册内容
        self.regex_cheatsheet_view.setPlainText(_REGEX_CHEATSHEET)

        # 无规则文件时的空态处理
        if not self._rules_paths:
            self.empty_label.setVisible(True)
            self.rule_editor.setEnabled(False)
            self.reload_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
        else:
            self._load_file_content(0)

        # layout 伸缩比例：
        # 0 file_layout, 1 empty_label, 2 rule_editor, 3 regex_test_group, 4 btn_layout
        # 规则编辑区与正则验证面板各占 1，按钮区固定
        self.main_layout.setStretch(0, 0)
        self.main_layout.setStretch(1, 0)
        self.main_layout.setStretch(2, 1)
        self.main_layout.setStretch(3, 1)
        self.main_layout.setStretch(4, 0)
        # 正则验证面板内部：输入行固定，文本/结果列各占 1，速查手册占 1
        self.regex_test_layout.setStretch(0, 0)
        self.regex_test_layout.setStretch(1, 1)
        self.regex_test_layout.setStretch(2, 0)
        self.regex_test_layout.setStretch(3, 1)

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

    def _on_test_regex(self) -> None:
        """对测试文本执行正则匹配并显示命中结果。

        与扫描引擎 :func:`fuscan.scanner.matchers._apply_regex` 行为一致：
        使用 ``re.compile(...).finditer(text)`` 收集所有非重叠匹配，
        显示每个命中的位置、文本与捕获组。
        """
        pattern = self.regex_pattern_edit.text().strip()
        if not pattern:
            self.regex_result_view.setPlainText("（请输入正则表达式）")
            return
        text = self.regex_test_text_edit.toPlainText()
        case_sensitive = self.regex_case_sensitive_check.isChecked()
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            self.regex_result_view.setPlainText(f"正则编译失败:\n{exc}")
            return
        # 与 matchers._apply_regex 一致：finditer 收集所有匹配
        matches = list(compiled.finditer(text))
        if not matches:
            self.regex_result_view.setPlainText(f"未命中（扫描 {len(text)} 字符）")
            return
        lines = [f"共命中 {len(matches)} 处：", ""]
        for i, m in enumerate(matches, 1):
            start, end = m.span()
            span_text = f"[{i}] {start}-{end}: {m.group(0)!r}"
            lines.append(span_text)
            groups = m.groups()
            if groups:
                lines.append(f"    捕获组: {groups}")
            named = m.groupdict()
            if named:
                lines.append(f"    命名组: {named}")
        self.regex_result_view.setPlainText("\n".join(lines))
