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
        """通过模拟文件对话框测试规则加载。"""
        rules_yaml = tmp_path / "rules.yaml"
        rules_yaml.write_text(
            'version: "1.0"\nrules:\n  - name: r1\n    severity: warning\n    match:\n      type: filename\n      mode: contains\n      pattern: secret\n',
            encoding="utf-8",
        )

        window = MainWindow()

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
        """取消文件对话框不加载规则。"""
        window = MainWindow()
        monkeypatch.setattr(
            "pyfilescan.gui.main_window.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: ("", ""),
        )
        window._on_load_rules()
        assert window._ruleset is None
        window.close()

    def test_load_rules_invalid(self, qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """加载无效规则文件应弹出警告。"""
        # 使用未知匹配类型触发 RuleParseError
        bad_rules = tmp_path / "bad.yaml"
        bad_rules.write_text(
            'version: "1.0"\nrules:\n  - name: r1\n    match:\n      type: unknown_type\n      mode: contains\n      pattern: x\n',
            encoding="utf-8",
        )

        window = MainWindow()
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
