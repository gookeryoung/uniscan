"""GUI 主窗口。

提供：

- 规则文件加载与展示
- 扫描路径选择
- 后台扫描触发与进度显示
- 结果树形展示（按文件分组）
- 结果导出（CSV/JSON）

设计要点：

- 扫描在 ScanWorker（QThread）中执行，避免阻塞 UI
- 结果以 QTreeWidget 展示，顶层节点为文件，子节点为规则命中
- 状态栏显示扫描统计
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QAction,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyfilescan.gui.detail_dialog import HitDetailDialog
from pyfilescan.gui.worker import ScanWorker
from pyfilescan.rules import RuleError, load_ruleset
from pyfilescan.rules.model import RuleSet
from pyfilescan.scanner import ScanReport

__all__ = ["MainWindow"]

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口：扫描器 GUI 入口。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("pyfilescan 通用文件扫描器")
        self.resize(1000, 700)

        self._ruleset: Optional[RuleSet] = None
        self._rules_path: Optional[Path] = None
        self._scan_root: Optional[Path] = None
        self._last_report: Optional[ScanReport] = None
        self._worker: Optional[ScanWorker] = None

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()

    # ----------------------------- UI 初始化 -----------------------------

    def _init_ui(self) -> None:
        """初始化中央 widget：左侧规则面板 + 右侧结果树。"""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # 顶部控制区
        top_layout = QHBoxLayout()
        self._rules_label = QLabel("规则文件: 未加载")
        self._rules_label.setStyleSheet("padding: 4px; border: 1px solid #ccc;")
        self._load_rules_btn = QPushButton("加载规则...")
        self._load_rules_btn.clicked.connect(self._on_load_rules)

        self._path_label = QLabel("扫描路径: 未选择")
        self._path_label.setStyleSheet("padding: 4px; border: 1px solid #ccc;")
        self._select_path_btn = QPushButton("选择路径...")
        self._select_path_btn.clicked.connect(self._on_select_path)

        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setEnabled(False)

        top_layout.addWidget(self._load_rules_btn)
        top_layout.addWidget(self._rules_label, stretch=1)
        top_layout.addWidget(self._select_path_btn)
        top_layout.addWidget(self._path_label, stretch=1)
        top_layout.addWidget(self._scan_btn)
        layout.addLayout(top_layout)

        # 主体：规则列表 + 结果树
        splitter = QSplitter(Qt.Horizontal)

        self._rules_tree = QTreeWidget()
        self._rules_tree.setHeaderLabels(["规则名", "严重等级", "扩展名"])
        self._rules_tree.setRootIsDecorated(False)
        splitter.addWidget(self._rules_tree)

        self._result_tree = QTreeWidget()
        self._result_tree.setHeaderLabels(["路径", "规则", "严重等级", "详情"])
        self._result_tree.setColumnWidth(0, 400)
        self._result_tree.setColumnWidth(1, 200)
        self._result_tree.itemDoubleClicked.connect(self._on_result_double_clicked)
        splitter.addWidget(self._result_tree)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

    def _init_menu(self) -> None:
        """初始化菜单栏。"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        load_rules_action = QAction("加载规则...", self)
        load_rules_action.triggered.connect(self._on_load_rules)
        file_menu.addAction(load_rules_action)

        export_csv_action = QAction("导出 CSV...", self)
        export_csv_action.triggered.connect(lambda: self._on_export("csv"))
        file_menu.addAction(export_csv_action)

        export_json_action = QAction("导出 JSON...", self)
        export_json_action.triggered.connect(lambda: self._on_export("json"))
        file_menu.addAction(export_json_action)

        quit_action = QAction("退出(&Q)", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        scan_menu = menubar.addMenu("扫描(&S)")
        select_path_action = QAction("选择扫描路径...", self)
        select_path_action.triggered.connect(self._on_select_path)
        scan_menu.addAction(select_path_action)

        self._scan_action = QAction("开始扫描", self)
        self._scan_action.setShortcut("F5")
        self._scan_action.triggered.connect(self._on_scan)
        scan_menu.addAction(self._scan_action)

        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbar(self) -> None:
        """工具栏与菜单复用 action。"""
        toolbar = self.addToolBar("主工具栏")
        toolbar.addAction(self._scan_action)

    def _init_statusbar(self) -> None:
        """状态栏：进度条 + 统计文本。"""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress)

        self._stats_label = QLabel("就绪")
        self._status_bar.addWidget(self._stats_label)

    # ----------------------------- 槽函数 -----------------------------

    def _on_load_rules(self) -> None:
        """加载规则文件。"""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "选择规则文件",
            str(self._rules_path or Path.home()),
            "YAML 文件 (*.yaml *.yml);;所有文件 (*.*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            self._ruleset = load_ruleset(path)
            self._rules_path = path
            self._rules_label.setText(f"规则文件: {path.name}")
            self._refresh_rules_tree()
            self._update_scan_button()
            self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
        except RuleError as exc:
            QMessageBox.warning(self, "规则错误", f"加载规则失败:\n{exc}")

    def _on_select_path(self) -> None:
        """选择扫描路径。"""
        path_str = QFileDialog.getExistingDirectory(
            self,
            "选择扫描目录",
            str(self._scan_root or Path.home()),
        )
        if not path_str:
            return
        self._scan_root = Path(path_str)
        self._path_label.setText(f"扫描路径: {self._scan_root.name}")
        self._update_scan_button()

    def _on_scan(self) -> None:
        """触发扫描。"""
        if self._ruleset is None or self._scan_root is None:
            return
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, "提示", "扫描正在进行中")
            return

        self._result_tree.clear()
        self._scan_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # 不确定进度
        self._stats_label.setText("扫描中...")

        self._worker = ScanWorker(
            ruleset=self._ruleset,
            root=self._scan_root,
            scan_archives=True,
            max_workers=8,
        )
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished_report.connect(self._on_scan_finished)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_scan_progress(self, scanned: int) -> None:
        """扫描进度回调。"""
        self._stats_label.setText(f"已扫描 {scanned} 个文件")

    def _on_scan_finished(self, report: ScanReport) -> None:
        """扫描完成回调。"""
        self._last_report = report
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)

        self._populate_results(report)

        stats = report.stats
        self._stats_label.setText(
            f"完成: 总计 {stats.total_files} | 扫描 {stats.scanned_files} | "
            f"命中 {stats.matched_files} | 错误 {stats.errors} | "
            f"耗时 {stats.duration_seconds:.2f}s"
        )

    def _on_scan_failed(self, error: str) -> None:
        """扫描失败回调。"""
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._stats_label.setText("扫描失败")
        QMessageBox.critical(self, "扫描失败", error)

    def _on_export(self, fmt: str) -> None:
        """导出扫描结果。"""
        if self._last_report is None:
            QMessageBox.information(self, "提示", "无可导出的扫描结果")
            return

        filter_str = "CSV 文件 (*.csv)" if fmt == "csv" else "JSON 文件 (*.json)"
        default_name = f"pyfilescan_report.{fmt}"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "导出扫描结果",
            default_name,
            filter_str,
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            content = self._format_report(self._last_report, fmt)
            path.write_text(content, encoding="utf-8")
            QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def _on_about(self) -> None:
        """关于对话框。"""
        from pyfilescan import __version__

        QMessageBox.about(
            self,
            "关于 pyfilescan",
            f"pyfilescan {__version__}\n\n通用文件扫描器\n支持多格式与压缩文件扫描\n\n技术栈: Python + PySide2",
        )

    # ----------------------------- 辅助方法 -----------------------------

    def _refresh_rules_tree(self) -> None:
        """刷新规则列表展示。"""
        self._rules_tree.clear()
        if self._ruleset is None:
            return
        for rule in self._ruleset.rules:
            item = QTreeWidgetItem([
                rule.name,
                rule.severity.value,
                ", ".join(rule.file_extensions) if rule.file_extensions else "(全部)",
            ])
            self._rules_tree.addTopLevelItem(item)

    def _populate_results(self, report: ScanReport) -> None:
        """填充结果树。"""
        self._result_tree.clear()
        for result in report.hits:
            file_item = QTreeWidgetItem([
                str(result.path),
                "",
                result.max_severity.value,
                f"{len(result.hits)} 条命中",
            ])
            # 将 ScanResult 存入 UserRole，供双击详情对话框使用
            file_item.setData(0, Qt.UserRole, result)
            for hit in result.hits:
                child = QTreeWidgetItem([
                    "",
                    hit.rule_name,
                    hit.severity.value,
                    hit.detail,
                ])
                file_item.addChild(child)
            self._result_tree.addTopLevelItem(file_item)

    def _on_result_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击结果项弹出详情对话框。"""
        # 子项双击时取其父项（文件项）的 UserRole 数据
        top_item = item.parent() if item.parent() is not None else item
        result = top_item.data(0, Qt.UserRole)
        if result is None:
            return
        dialog = HitDetailDialog(result, self)
        dialog.exec_()

    def _update_scan_button(self) -> None:
        """根据规则与路径是否就绪更新扫描按钮。"""
        ready = self._ruleset is not None and self._scan_root is not None
        self._scan_btn.setEnabled(ready)
        self._scan_action.setEnabled(ready)

    @staticmethod
    def _format_report(report: ScanReport, fmt: str) -> str:
        """格式化报告为字符串。"""
        if fmt == "json":
            data = {
                "root": str(report.root),
                "stats": asdict(report.stats),
                "hits": [
                    {
                        "path": str(r.path),
                        "size": r.size,
                        "max_severity": r.max_severity.value,
                        "rules": [asdict(h) for h in r.hits],
                    }
                    for r in report.hits
                ],
            }
            return json.dumps(data, ensure_ascii=False, indent=2)

        # CSV
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["path", "size", "severity", "rule", "detail"])
        for r in report.hits:
            for hit in r.hits:
                writer.writerow([str(r.path), r.size, hit.severity.value, hit.rule_name, hit.detail])
        return buf.getvalue()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        """关闭时终止后台线程。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)
