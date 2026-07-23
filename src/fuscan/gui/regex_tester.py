"""正则表达式测试工具对话框。

作为独立工具窗口提供正则表达式验证能力，与扫描引擎 finditer 行为一致，
支持捕获组、命名组显示，并附带常用语法速查手册。可由主窗口「工具」菜单
直接调用，也可由规则编辑器在编辑正则规则时调用并通过 ``initial_pattern``
预填待测表达式。
"""

from __future__ import annotations

import logging
import re

from PySide2.QtCore import Slot

try:
    from PySide2.QtWidgets import QDialog, QWidget
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QDialog, QWidget  # pyrefly: ignore [missing-import]

from fuscan.gui.regex_tester_ui import Ui_RegexTesterDialog

__all__ = ["RegexTesterDialog"]

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


class RegexTesterDialog(QDialog, Ui_RegexTesterDialog):  # pyrefly: ignore [invalid-inheritance]
    """正则表达式测试工具对话框。

    独立工具窗口，提供正则表达式验证能力。与扫描引擎
    :func:`fuscan.scanner.matchers._apply_regex` 行为一致：使用
    ``re.compile(...).finditer(text)`` 收集所有非重叠匹配，显示每个命中的
    位置、文本与捕获组。

    参数：
        parent：父窗口，可为 ``None`` 表示独立顶层窗口。
        initial_pattern：初始正则表达式，便于规则编辑器预填待测内容。
    """

    _compiled: re.Pattern | None = None

    def __init__(self, parent: QWidget | None = None, initial_pattern: str = "") -> None:
        super().__init__(parent)
        self.setupUi(self)

        if initial_pattern:
            self.regex_pattern_edit.setText(initial_pattern)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """配置 .ui 无法静态表达的动态属性、初始内容与信号槽连接。"""
        self.regex_pattern_edit.textChanged.connect(self._on_pattern_changed)
        self.regex_test_text_edit.textChanged.connect(self._on_test_regex)
        self.regex_cheatsheet_view.setPlainText(_REGEX_CHEATSHEET)

    @Slot()
    def _on_pattern_changed(self) -> None:
        """正则表达式输入框内容改变时触发，更新结果视图。"""
        pattern = self.regex_pattern_edit.text().strip()
        if not pattern:
            self._compiled = None
            return

        case_sensitive = self.regex_case_sensitive_check.isChecked()
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            self._compiled = re.compile(pattern, flags)
        except re.error as exc:
            self.regex_result_view.setPlainText(f"正则编译失败:\n{exc}")
            return

        # 触发测试匹配
        self._on_test_regex()

    @Slot()
    def _on_test_regex(self) -> None:
        """对测试文本执行正则匹配并显示命中结果。

        与扫描引擎 :func:`fuscan.scanner.matchers._apply_regex` 行为一致：
        使用 ``re.compile(...).finditer(text)`` 收集所有非重叠匹配，
        显示每个命中的位置、文本与捕获组。
        """
        if not self._compiled:
            self.regex_result_view.setPlainText("（请输入正则表达式）")
            return

        text = self.regex_test_text_edit.toPlainText()
        if not text:
            self.regex_result_view.setPlainText("（请输入测试文本）")
            return

        matches = list(self._compiled.finditer(text))
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
