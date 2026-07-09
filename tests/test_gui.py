"""GUI 烟雾测试。

使用 ``gui`` marker 标记，CI 无 GUI 环境时可通过 ``-m "not gui"`` 跳过。
需要 QApplication 环境（offscreen 平台）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# 设置离屏平台，避免无显示器环境报错
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.gui

try:
    from PySide2.QtWidgets import QApplication

    from pyfilescan.gui.main_window import MainWindow
    from pyfilescan.gui.worker import ScanWorker
    from pyfilescan.rules import load_ruleset
    from pyfilescan.rules.model import (
        LeafMatch,
        MatchMode,
        MatchTarget,
        Rule,
        RuleSet,
        Severity,
    )

    PYSIDE2_AVAILABLE = True
except ImportError:
    PYSIDE2_AVAILABLE = False

if not PYSIDE2_AVAILABLE:
    pytest.skip("PySide2 未安装，跳过 GUI 测试", allow_module_level=True)


@pytest.fixture(scope="module")
def qapp() -> QApplication:  # type: ignore[misc]
    """模块级 QApplication fixture。"""
    app = QApplication.instance() or QApplication([])
    yield app


def _build_ruleset() -> RuleSet:
    return RuleSet(
        version="1.0",
        rules=(
            Rule(
                name="敏感文件名",
                severity=Severity.WARNING,
                match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="secret"),
            ),
        ),
    )


class TestMainWindow:
    def test_window_creation(self, qapp: QApplication) -> None:
        window = MainWindow()
        assert window.windowTitle().startswith("pyfilescan")
        assert window._scan_btn is not None
        assert window._rules_tree is not None
        assert window._result_tree is not None
        window.close()

    def test_scan_button_disabled_initially(self, qapp: QApplication) -> None:
        window = MainWindow()
        assert not window._scan_btn.isEnabled()
        window.close()

    def test_load_ruleset_updates_rules_tree(self, qapp: QApplication, tmp_path: Path) -> None:
        """加载规则后规则树应展示规则。"""
        rules_yaml = tmp_path / "rules.yaml"
        rules_yaml.write_text(
            """
version: "1.0"
rules:
  - name: 敏感名
    severity: warning
    match:
      type: filename
      mode: contains
      pattern: secret
""",
            encoding="utf-8",
        )
        window = MainWindow()
        rs = load_ruleset(rules_yaml)
        window._ruleset = rs
        window._rules_path = rules_yaml
        window._refresh_rules_tree()
        assert window._rules_tree.topLevelItemCount() == 1
        item = window._rules_tree.topLevelItem(0)
        assert item.text(0) == "敏感名"
        window.close()

    def test_populate_results_displays_hits(self, qapp: QApplication, tmp_path: Path) -> None:
        """结果树应展示命中项。"""
        from pyfilescan.scanner import Scanner

        # 准备测试文件
        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
        (tmp_path / "normal.txt").write_text("y", encoding="utf-8")

        rs = _build_ruleset()
        scanner = Scanner(rs)
        report = scanner.scan(tmp_path)

        window = MainWindow()
        window._populate_results(report)
        assert window._result_tree.topLevelItemCount() == 1
        item = window._result_tree.topLevelItem(0)
        assert "secret.txt" in item.text(0)
        window.close()

    def test_export_csv(self, qapp: QApplication, tmp_path: Path) -> None:
        """CSV 导出应写入文件。"""
        from pyfilescan.scanner import Scanner

        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
        rs = _build_ruleset()
        scanner = Scanner(rs)
        report = scanner.scan(tmp_path)

        window = MainWindow()
        window._last_report = report
        out_path = tmp_path / "out.csv"
        content = MainWindow._format_report(report, "csv")
        out_path.write_text(content, encoding="utf-8")
        assert out_path.exists()
        text = out_path.read_text(encoding="utf-8")
        assert "secret.txt" in text
        window.close()

    def test_export_json(self, qapp: QApplication, tmp_path: Path) -> None:
        """JSON 导出应写入文件。"""
        from pyfilescan.scanner import Scanner

        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
        rs = _build_ruleset()
        scanner = Scanner(rs)
        report = scanner.scan(tmp_path)

        window = MainWindow()
        window._last_report = report
        out_path = tmp_path / "out.json"
        content = MainWindow._format_report(report, "json")
        out_path.write_text(content, encoding="utf-8")
        import json

        data = json.loads(content)
        assert "hits" in data
        assert len(data["hits"]) >= 1
        window.close()

    def test_load_rules_via_dialog(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """通过模拟文件对话框测试规则加载（关闭通用规则后仅加载用户规则）。"""
        rules_yaml = tmp_path / "rules.yaml"
        rules_yaml.write_text(
            'version: "1.0"\nrules:\n  - name: r1\n    severity: warning\n    match:\n      type: filename\n      mode: contains\n      pattern: secret\n',
            encoding="utf-8",
        )

        window = MainWindow()
        # 关闭通用规则，确保仅加载用户规则
        window._use_builtin_checkbox.setChecked(False)

        # mock QFileDialog.getOpenFileName 返回规则文件路径
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(rules_yaml), ""),
        )

        window._on_load_rules()
        assert window._ruleset is not None
        assert window._rules_path == rules_yaml
        assert "rules.yaml" in window._rules_label.text()
        assert window._rules_tree.topLevelItemCount() == 1
        window.close()

    def test_load_rules_cancelled(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """取消文件对话框不改变当前规则集。"""
        window = MainWindow()
        # 启动时已加载通用规则
        assert window._ruleset is not None
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: ("", ""),
        )
        window._on_load_rules()
        # 取消后规则集仍保留
        assert window._ruleset is not None
        window.close()

    def test_load_rules_invalid(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """加载无效规则文件应弹出警告且保留原规则集。"""
        # 使用未知匹配类型触发 RuleParseError
        bad_rules = tmp_path / "bad.yaml"
        bad_rules.write_text(
            'version: "1.0"\nrules:\n  - name: r1\n    match:\n      type: unknown_type\n      mode: contains\n      pattern: x\n',
            encoding="utf-8",
        )

        window = MainWindow()
        # 关闭通用规则，使初始 ruleset 为 None
        window._use_builtin_checkbox.setChecked(False)
        assert window._ruleset is None
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(bad_rules), ""),
        )
        warned = {"called": False}
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QMessageBox.warning",
            lambda *args, **kwargs: warned.update(called=True),
        )
        window._on_load_rules()
        assert window._ruleset is None
        assert warned["called"]
        window.close()

    def test_select_path_via_dialog(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """通过模拟对话框选择扫描路径。"""
        window = MainWindow()
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getExistingDirectory",
            lambda *args, **kwargs: str(tmp_path),
        )
        window._on_select_path()
        assert window._scan_root == tmp_path
        window.close()

    def test_update_scan_button_state(self, qapp: QApplication, tmp_path: Path) -> None:
        """扫描按钮状态随规则与路径就绪变化。"""
        window = MainWindow()
        assert not window._scan_btn.isEnabled()

        # 仅设置规则
        window._ruleset = _build_ruleset()
        window._update_scan_button()
        assert not window._scan_btn.isEnabled()

        # 设置路径
        window._scan_root = tmp_path
        window._update_scan_button()
        assert window._scan_btn.isEnabled()
        window.close()

    def test_refresh_rules_tree_empty(self, qapp: QApplication) -> None:
        """无规则集时规则树为空。"""
        window = MainWindow()
        window._ruleset = None
        window._refresh_rules_tree()
        assert window._rules_tree.topLevelItemCount() == 0
        window.close()

    def test_close_event_terminates_worker(self, qapp: QApplication, tmp_path: Path) -> None:
        """closeEvent 应安全终止后台线程。"""
        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
        window = MainWindow()
        # 不启动 worker，直接关闭
        window.close()
        assert window._worker is None or not window._worker.isRunning()


class TestBuiltinRulesToggle:
    """通用规则开关测试。"""

    def test_builtin_loaded_at_startup(self, qapp: QApplication) -> None:
        """启动时应默认加载内置通用规则。"""
        window = MainWindow()
        assert window._ruleset is not None
        assert len(window._ruleset.rules) > 0
        assert window._use_builtin is True
        assert window._use_builtin_checkbox.isChecked()
        # 规则树应非空
        assert window._rules_tree.topLevelItemCount() > 0
        window.close()

    def test_uncheck_builtin_clears_ruleset(self, qapp: QApplication) -> None:
        """取消勾选通用规则且无用户规则时 ruleset 为 None。"""
        window = MainWindow()
        window._use_builtin_checkbox.setChecked(False)
        assert window._use_builtin is False
        assert window._ruleset is None
        assert window._rules_tree.topLevelItemCount() == 0
        # 扫描按钮应禁用
        assert not window._scan_btn.isEnabled()
        window.close()

    def test_recheck_builtin_reloads_ruleset(self, qapp: QApplication) -> None:
        """重新勾选通用规则应重新加载规则集。"""
        window = MainWindow()
        window._use_builtin_checkbox.setChecked(False)
        assert window._ruleset is None
        window._use_builtin_checkbox.setChecked(True)
        assert window._ruleset is not None
        assert len(window._ruleset.rules) > 0
        window.close()

    def test_builtin_label_updated_on_toggle(self, qapp: QApplication) -> None:
        """切换通用规则开关时标签应更新。"""
        window = MainWindow()
        assert "通用规则" in window._rules_label.text()
        window._use_builtin_checkbox.setChecked(False)
        assert "未加载" in window._rules_label.text()
        window._use_builtin_checkbox.setChecked(True)
        assert "通用规则" in window._rules_label.text()
        window.close()

    def test_load_user_rules_with_builtin(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """勾选通用规则时加载用户规则应合并。"""
        rules_yaml = tmp_path / "rules.yaml"
        rules_yaml.write_text(
            'version: "1.0"\nrules:\n  - name: 用户规则1\n    severity: warning\n    match:\n      type: filename\n      mode: contains\n      pattern: secret\n',
            encoding="utf-8",
        )

        window = MainWindow()
        builtin_count = window._rules_tree.topLevelItemCount()

        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(rules_yaml), ""),
        )
        window._on_load_rules()
        # 合并后规则数应大于内置规则数
        assert window._rules_tree.topLevelItemCount() > builtin_count
        assert "通用规则" in window._rules_label.text()
        assert "rules.yaml" in window._rules_label.text()
        window.close()

    def test_scan_enabled_with_builtin_only(self, qapp: QApplication, tmp_path: Path) -> None:
        """仅加载内置规则并选择路径后扫描按钮应可用。"""
        window = MainWindow()
        assert window._ruleset is not None
        # 未选路径时按钮禁用
        assert not window._scan_btn.isEnabled()
        # 选择路径后按钮启用
        window._scan_root = tmp_path
        window._update_scan_button()
        assert window._scan_btn.isEnabled()
        window.close()


class TestScanWorker:
    def test_worker_runs_scan(self, qapp: QApplication, tmp_path: Path) -> None:
        """ScanWorker 应在后台完成扫描。"""
        from PySide2.QtCore import QEventLoop, QTimer

        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")

        rs = _build_ruleset()
        worker = ScanWorker(ruleset=rs, root=tmp_path)

        results: list = []
        worker.finished_report.connect(lambda r: results.append(r))  # noqa: PLW0108
        worker.start()

        # 通过事件循环等待 finished 信号
        loop = QEventLoop()
        worker.finished.connect(loop.quit)
        QTimer.singleShot(10000, loop.quit)  # 超时保护
        loop.exec_()

        worker.wait(2000)
        assert not worker.isRunning()
        assert len(results) == 1
        report = results[0]
        assert report.stats.matched_files >= 1

    def test_worker_handles_invalid_path(self, qapp: QApplication, tmp_path: Path) -> None:
        """无效路径应正常完成（Scanner 返回空报告）。"""
        from PySide2.QtCore import QEventLoop, QTimer

        rs = _build_ruleset()
        worker = ScanWorker(ruleset=rs, root=tmp_path / "nonexistent")

        results: list = []
        errors: list = []
        worker.finished_report.connect(lambda r: results.append(r))  # noqa: PLW0108
        worker.failed.connect(lambda msg: errors.append(msg))  # noqa: PLW0108
        worker.start()

        loop = QEventLoop()
        worker.finished.connect(loop.quit)
        QTimer.singleShot(10000, loop.quit)
        loop.exec_()

        worker.wait(2000)
        assert not worker.isRunning()
        # 无效路径返回空报告，不应有 error
        assert len(errors) == 0


class TestLaunchApp:
    def test_launch_creates_window_and_returns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """launch 应创建 QApplication 与 MainWindow 并进入事件循环。"""
        from pyfilescan.gui import app as app_module

        created: list = []

        class FakeApp:
            def __init__(self, args):  # type: ignore[no-untyped-def]
                created.append(self)
                self._app_name = None

            def setApplicationName(self, name: str) -> None:
                self._app_name = name

            def exec_(self) -> int:
                return 0

            @staticmethod
            def instance() -> None:
                return None

        shown: list = []

        class FakeMainWindow:
            def __init__(self):  # type: ignore[no-untyped-def]
                shown.append(self)

            def show(self) -> None:
                pass

            def close(self) -> None:
                pass

        monkeypatch.setattr(app_module, "QApplication", FakeApp)
        monkeypatch.setattr(app_module, "MainWindow", FakeMainWindow)

        rc = app_module.launch(["test"])
        assert rc == 0
        assert len(created) == 1
        assert len(shown) == 1

    def test_launch_reuses_existing_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """已有 QApplication 实例时复用，不创建新实例。"""
        from pyfilescan.gui import app as app_module

        existing_app = type("ExistingApp", (), {"exec_": lambda self: 0, "setApplicationName": lambda self, n: None})()
        created: list = []

        class FakeApp:
            def __init__(self, args):  # type: ignore[no-untyped-def]
                created.append(self)

            def setApplicationName(self, name: str) -> None:
                pass

            def exec_(self) -> int:
                return 0

            @staticmethod
            def instance():
                return existing_app

        shown: list = []

        class FakeMainWindow:
            def __init__(self):  # type: ignore[no-untyped-def]
                shown.append(self)

            def show(self) -> None:
                pass

            def close(self) -> None:
                pass

        monkeypatch.setattr(app_module, "QApplication", FakeApp)
        monkeypatch.setattr(app_module, "MainWindow", FakeMainWindow)

        rc = app_module.launch(["test"])
        assert rc == 0
        assert len(created) == 0  # 复用现有实例，不创建新的
        assert len(shown) == 1


class TestHitDetailDialogHelpers:
    """详情对话框辅助函数测试。"""

    def test_format_size_bytes(self) -> None:
        from pyfilescan.gui.detail_dialog import _format_size

        assert _format_size(0) == "0 B"
        assert _format_size(512) == "512 B"
        assert _format_size(1023) == "1023 B"

    def test_format_size_kb(self) -> None:
        from pyfilescan.gui.detail_dialog import _format_size

        assert _format_size(1024) == "1.0 KB"
        assert _format_size(2048) == "2.0 KB"

    def test_format_size_mb(self) -> None:
        from pyfilescan.gui.detail_dialog import _format_size

        assert _format_size(1024 * 1024) == "1.0 MB"

    def test_format_size_gb(self) -> None:
        from pyfilescan.gui.detail_dialog import _format_size

        assert "GB" in _format_size(1024 * 1024 * 1024)

    def test_extract_keywords_contains(self) -> None:
        from pyfilescan.gui.detail_dialog import _extract_keywords
        from pyfilescan.scanner import RuleHit

        hits = (
            RuleHit("r1", Severity.WARNING, "包含 'password'"),
            RuleHit("r2", Severity.CRITICAL, "包含 'secret'"),
        )
        kws = _extract_keywords(hits)
        assert "password" in kws
        assert "secret" in kws

    def test_extract_keywords_regex(self) -> None:
        from pyfilescan.gui.detail_dialog import _extract_keywords
        from pyfilescan.scanner import RuleHit

        hits = (RuleHit("r", Severity.CRITICAL, "正则命中: 'AKIA1234'"),)
        kws = _extract_keywords(hits)
        assert "AKIA1234" in kws

    def test_extract_keywords_dedup(self) -> None:
        from pyfilescan.gui.detail_dialog import _extract_keywords
        from pyfilescan.scanner import RuleHit

        hits = (
            RuleHit("r1", Severity.WARNING, "包含 'password'"),
            RuleHit("r2", Severity.WARNING, "包含 'password'"),
        )
        kws = _extract_keywords(hits)
        assert kws.count("password") == 1

    def test_extract_keywords_no_match(self) -> None:
        from pyfilescan.gui.detail_dialog import _extract_keywords
        from pyfilescan.scanner import RuleHit

        hits = (RuleHit("r", Severity.INFO, "完全相等"),)
        kws = _extract_keywords(hits)
        assert kws == []

    def test_build_preview_html_no_keywords(self) -> None:
        from pyfilescan.gui.detail_dialog import _build_preview_html

        result = _build_preview_html("hello world", [])
        assert "hello" in result
        assert "<span" not in result

    def test_build_preview_html_with_keywords(self) -> None:
        from pyfilescan.gui.detail_dialog import _build_preview_html

        result = _build_preview_html("hello password world", ["password"])
        assert "span" in result
        assert "background-color: yellow" in result

    def test_build_preview_html_escapes_html(self) -> None:
        from pyfilescan.gui.detail_dialog import _build_preview_html

        result = _build_preview_html("<script>alert(1)</script>", [])
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_build_preview_html_case_insensitive(self) -> None:
        from pyfilescan.gui.detail_dialog import _build_preview_html

        result = _build_preview_html("PASSWORD password Password", ["password"])
        # 所有大小的 password 都应被高亮（3 次匹配 = 6 个 span 标签：开+关）
        assert result.count("<span") == 3


class TestHitDetailDialog:
    """详情对话框测试。"""

    def test_dialog_shows_file_info(self, qapp: QApplication, tmp_path: Path) -> None:
        """对话框应展示文件路径、大小等信息。"""
        from pyfilescan.gui.detail_dialog import HitDetailDialog
        from pyfilescan.scanner import RuleHit, ScanResult

        path = tmp_path / "secret.txt"
        path.write_text("my password here", encoding="utf-8")

        result = ScanResult(
            path=path,
            size=path.stat().st_size,
            hits=(RuleHit("r1", Severity.WARNING, "包含 'password'"),),
        )
        dialog = HitDetailDialog(result)
        info_text = dialog._info_label.text()
        assert "secret.txt" in info_text
        assert "命中规则数" in info_text
        dialog.close()

    def test_dialog_hits_table(self, qapp: QApplication, tmp_path: Path) -> None:
        """命中规则表应正确显示。"""
        from pyfilescan.gui.detail_dialog import HitDetailDialog
        from pyfilescan.scanner import RuleHit, ScanResult

        path = tmp_path / "test.txt"
        path.write_text("content", encoding="utf-8")
        result = ScanResult(
            path=path,
            size=7,
            hits=(
                RuleHit("rule-a", Severity.WARNING, "包含 'a'"),
                RuleHit("rule-b", Severity.CRITICAL, "包含 'b'"),
            ),
        )
        dialog = HitDetailDialog(result)
        assert dialog._hits_table.rowCount() == 2
        assert dialog._hits_table.item(0, 0).text() == "rule-a"
        assert dialog._hits_table.item(1, 0).text() == "rule-b"
        dialog.close()

    def test_dialog_preview_highlights_keywords(self, qapp: QApplication, tmp_path: Path) -> None:
        """内容预览应高亮关键词。"""
        from pyfilescan.gui.detail_dialog import HitDetailDialog
        from pyfilescan.scanner import RuleHit, ScanResult

        path = tmp_path / "data.txt"
        path.write_text("the password is secret123", encoding="utf-8")
        result = ScanResult(
            path=path,
            size=len("the password is secret123"),
            hits=(
                RuleHit("r1", Severity.WARNING, "包含 'password'"),
                RuleHit("r2", Severity.CRITICAL, "正则命中: 'secret123'"),
            ),
        )
        dialog = HitDetailDialog(result)
        html = dialog._preview.toHtml()
        assert "password" in html
        assert "span" in html  # 有高亮标签
        dialog.close()

    def test_dialog_preview_empty_file(self, qapp: QApplication, tmp_path: Path) -> None:
        """空文件预览应显示提示。"""
        from pyfilescan.gui.detail_dialog import HitDetailDialog
        from pyfilescan.scanner import RuleHit, ScanResult

        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        result = ScanResult(
            path=path,
            size=0,
            hits=(RuleHit("r", Severity.WARNING, "包含 'x'"),),
        )
        dialog = HitDetailDialog(result)
        text = dialog._preview.toPlainText()
        assert "为空" in text or "二进制" in text
        dialog.close()

    def test_dialog_preview_nonexistent_file(self, qapp: QApplication, tmp_path: Path) -> None:
        """文件不存在时预览应显示错误提示。"""
        from pyfilescan.gui.detail_dialog import HitDetailDialog
        from pyfilescan.scanner import RuleHit, ScanResult

        result = ScanResult(
            path=tmp_path / "nonexistent.txt",
            size=0,
            hits=(RuleHit("r", Severity.WARNING, "包含 'x'"),),
        )
        dialog = HitDetailDialog(result)
        assert "无法读取" in dialog._preview.toPlainText()
        dialog.close()

    def test_double_click_opens_dialog(
        self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """双击结果项应弹出详情对话框。"""
        from pyfilescan.gui import main_window as mw_module
        from pyfilescan.scanner import Scanner

        (tmp_path / "secret.txt").write_text("password", encoding="utf-8")
        rs = _build_ruleset()
        scanner = Scanner(rs)
        report = scanner.scan(tmp_path)

        window = MainWindow()
        window._populate_results(report)

        # 模拟 exec_ 避免模态阻塞
        called = {"count": 0}

        def fake_exec(self) -> int:  # type: ignore[no-untyped-def]
            called["count"] += 1
            return 1

        monkeypatch.setattr(mw_module.HitDetailDialog, "exec_", fake_exec)

        # 双击顶层项
        top_item = window._result_tree.topLevelItem(0)
        window._on_result_double_clicked(top_item, 0)
        assert called["count"] == 1

        # 双击子项也应触发
        if top_item.childCount() > 0:
            child_item = top_item.child(0)
            window._on_result_double_clicked(child_item, 0)
            assert called["count"] == 2

        window.close()

    def test_double_click_no_data_does_nothing(self, qapp: QApplication) -> None:
        """无双击数据时不弹对话框。"""
        from PySide2.QtWidgets import QTreeWidgetItem

        window = MainWindow()
        # 创建一个没有 UserRole 数据的项
        item = QTreeWidgetItem(["test", "", "", ""])
        window._result_tree.addTopLevelItem(item)
        # 不应抛异常
        window._on_result_double_clicked(item, 0)
        window.close()
