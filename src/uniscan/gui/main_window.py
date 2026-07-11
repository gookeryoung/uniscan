"""GUI 主窗口。

提供 GitHub Desktop 风格的 5 区布局：

1. 菜单栏（文件/扫描/视图/帮助）
2. 主操作区（扫描模式/目标/规则/扫描按钮/进度/统计）
3. 列表区（QTabWidget 切换扫描结果/规则文件/扫描历史 + 底部操作区）
4. 详情区（操作栏 QStackedWidget 两态 + 主体 QStackedWidget 两态）
5. 底部操作区（备注输入框 + 按钮组）

设计要点：

- GitHub Desktop 风格：5 区布局，详情区两态切换（QStackedWidget 持久化）
- 扫描在 ScanWorker（QThread）中执行，避免阻塞 UI
- 结果以 QTreeWidget 展示（QAbstractItemView 迁移见后续迭代）
- 详情区嵌入命中预览（文件信息+命中表+内容预览+命中导航）
"""

from __future__ import annotations

import csv
import datetime
import enum
import html
import io
import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from PySide2.QtCore import Qt
from PySide2.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide2.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from uniscan.builtin import load_with_builtin
from uniscan.config import MAX_HISTORY, Config, load_config, save_config
from uniscan.extractors import extract_content
from uniscan.gui.detail_dialog import HitDetailDialog
from uniscan.gui.worker import ScanWorker
from uniscan.rules import RuleError, load_ruleset, merge_multiple_rulesets
from uniscan.rules.model import RuleSet
from uniscan.scanner import ScanReport, list_drives
from uniscan.scanner.result import RuleHit, ScanResult

__all__ = ["MainWindow", "ScanState"]

logger = logging.getLogger(__name__)

# 内容预览最大字符数，避免大文件阻塞 UI
_PREVIEW_MAX_CHARS = 100 * 1024

# 从 detail 中提取关键词的正则，匹配单引号包裹的内容
_KEYWORD_RE = re.compile(r"'([^']+)'")

# 内容预览 pre 标签样式
_PREVIEW_STYLE = (
    "font-family: Consolas, 'Courier New', monospace; font-size: 12px; white-space: pre-wrap; word-wrap: break-word;"
)

# 关键词高亮 span 样式
_HIGHLIGHT_STYLE = "background-color: yellow; color: black;"


def _format_size(size: int) -> str:
    """将字节数格式化为人类可读字符串。"""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _extract_keywords(hits: Sequence[RuleHit]) -> List[str]:
    """从命中规则的 detail 字段中提取关键词。

    detail 形如 "包含 'password'" / "正则命中: 'AKIA...'"，
    提取单引号内的模式用于内容高亮。
    """
    keywords: List[str] = []
    seen: Set[str] = set()
    for hit in hits:
        for match in _KEYWORD_RE.finditer(hit.detail):
            kw = match.group(1)
            if kw and kw not in seen:
                seen.add(kw)
                keywords.append(kw)
    return keywords


def _build_preview_html(content: str, keywords: Sequence[str]) -> str:
    """构建内容预览 HTML，关键词以黄色背景高亮。

    先对内容做 html.escape 转义，再用单次正则替换插入高亮 span，
    避免多次 replace 破坏已插入的 HTML 标签。
    """
    escaped = html.escape(content)
    if keywords:
        # 按长度降序排列，优先匹配最长关键词
        escaped_kws = sorted({html.escape(k) for k in keywords if k}, key=len, reverse=True)
        if escaped_kws:
            pattern = "|".join(re.escape(k) for k in escaped_kws)
            regex = re.compile(pattern, re.IGNORECASE)
            escaped = regex.sub(
                lambda m: f'<span style="{_HIGHLIGHT_STYLE}">{m.group(0)}</span>',
                escaped,
            )
    # 保留换行
    escaped = escaped.replace("\n", "<br>")
    return f"<pre style='{_PREVIEW_STYLE}'>{escaped}</pre>"


class ScanState(enum.Enum):
    """扫描状态。"""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


class MainWindow(QMainWindow):
    """主窗口：扫描器 GUI 入口，GitHub Desktop 风格 5 区布局。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("uniscan 通用文件扫描器")

        self._config: Config = load_config()
        self._ruleset: Optional[RuleSet] = None
        self._rules_paths: List[Path] = []
        self._scan_root: Optional[Path] = None
        self._last_report: Optional[ScanReport] = None
        self._worker: Optional[ScanWorker] = None
        self._scan_state: ScanState = ScanState.IDLE
        self._use_builtin: bool = True
        # 扫描模式："full"（全盘）、"drive"（盘符）、"folder"（文件夹）
        self._scan_mode: str = "folder"
        # 详情区命中导航状态
        self._detail_hit_positions: List[Tuple[int, int]] = []
        self._detail_current_hit_index: int = -1
        self._detail_current_result: Optional[ScanResult] = None
        # 扫描历史记录
        self._scan_history: List[str] = []

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._apply_qss()
        self._apply_config()
        self._init_rules()

    # ----------------------------- UI 初始化 -----------------------------

    def _init_ui(self) -> None:
        """初始化中央 widget：主操作区 + 主体分割器（列表区 | 详情区）。"""
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._build_main_operation_area())
        layout.addWidget(self._build_body_splitter(), stretch=1)

    def _build_main_operation_area(self) -> QWidget:
        """构造 ② 主操作区：扫描模式 + 目标 + 规则 + 扫描按钮 + 进度 + 统计。"""
        container = QFrame()
        container.setObjectName("controlArea")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 扫描模式行：三张卡片按钮 + 盘符下拉
        layout.addLayout(self._build_scan_mode_row())

        # 目标路径行（仅 folder 模式可见）
        layout.addWidget(self._build_target_row())

        # 规则加载行
        layout.addLayout(self._build_rules_row())

        # 扫描控制按钮行：扫描按钮（开始/暂停/继续）+ 停止按钮
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.setObjectName("scanBtn")
        self._scan_btn.setCursor(Qt.PointingHandCursor)
        self._scan_btn.setMinimumHeight(40)
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setEnabled(False)
        btn_row.addWidget(self._scan_btn, stretch=3)

        self._stop_btn = QPushButton("停止")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setMinimumHeight(40)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setVisible(False)
        btn_row.addWidget(self._stop_btn, stretch=1)
        layout.addLayout(btn_row)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        self._progress.setMinimumHeight(20)
        layout.addWidget(self._progress)

        # 当前文件标签
        self._current_file_label = QLabel("")
        self._current_file_label.setObjectName("currentFileLabel")
        self._current_file_label.setVisible(False)
        layout.addWidget(self._current_file_label)

        # 统计标签
        self._stats_label = QLabel("就绪")
        self._stats_label.setObjectName("statsLabel")
        layout.addWidget(self._stats_label)

        return container

    def _build_scan_mode_row(self) -> QHBoxLayout:
        """构造扫描模式选择行：三张卡片按钮 + 盘符下拉。"""
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self._mode_btn_group = QButtonGroup(self)
        self._mode_btn_group.setExclusive(True)

        self._full_btn = QPushButton("全盘扫描\n扫描所有盘符")
        self._full_btn.setCheckable(True)
        self._full_btn.setObjectName("modeCard")
        self._full_btn.setCursor(Qt.PointingHandCursor)

        self._drive_btn = QPushButton("选择盘符\n扫描指定盘符")
        self._drive_btn.setCheckable(True)
        self._drive_btn.setObjectName("modeCard")
        self._drive_btn.setCursor(Qt.PointingHandCursor)

        self._folder_btn = QPushButton("选择文件夹\n扫描指定目录")
        self._folder_btn.setCheckable(True)
        self._folder_btn.setObjectName("modeCard")
        self._folder_btn.setCursor(Qt.PointingHandCursor)
        self._folder_btn.setChecked(True)

        self._mode_btn_group.addButton(self._full_btn, 0)
        self._mode_btn_group.addButton(self._drive_btn, 1)
        self._mode_btn_group.addButton(self._folder_btn, 2)
        self._mode_btn_group.buttonClicked.connect(self._on_scan_mode_changed)

        mode_row.addWidget(self._full_btn)
        mode_row.addWidget(self._drive_btn)
        mode_row.addWidget(self._folder_btn)
        mode_row.addStretch()

        self._drive_label = QLabel("盘符:")
        self._drive_combo = QComboBox()
        self._drive_combo.setToolTip("选择要扫描的盘符")
        self._drive_combo.setMinimumWidth(80)
        self._drive_combo.currentIndexChanged.connect(self._on_drive_selected)
        self._refresh_drive_combo()
        mode_row.addWidget(self._drive_label)
        mode_row.addWidget(self._drive_combo)

        return mode_row

    def _build_target_row(self) -> QWidget:
        """构造目标路径行（仅 folder 模式可见）。"""
        self._target_row = QWidget()
        target_layout = QHBoxLayout(self._target_row)
        target_layout.setContentsMargins(0, 0, 0, 0)
        self._path_label = QLabel("扫描路径:")
        self._path_combo = QComboBox()
        self._path_combo.setToolTip("扫描路径（可从历史记录中选择）")
        self._path_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._path_combo.currentIndexChanged.connect(self._on_path_selected)
        self._select_path_btn = QPushButton("选择路径...")
        self._select_path_btn.clicked.connect(self._on_select_path)
        target_layout.addWidget(self._path_label)
        target_layout.addWidget(self._path_combo, stretch=1)
        target_layout.addWidget(self._select_path_btn)
        return self._target_row

    def _build_rules_row(self) -> QHBoxLayout:
        """构造规则加载行。"""
        self._load_rules_btn = QPushButton("加载规则...")
        self._load_rules_btn.clicked.connect(self._on_load_rules)
        self._rules_label = QLabel("规则: 未加载")
        self._rules_label.setStyleSheet("padding: 4px;")
        self._use_builtin_checkbox = QCheckBox("使用通用规则")
        self._use_builtin_checkbox.setChecked(True)
        self._use_builtin_checkbox.setToolTip("勾选后加载软件内置通用规则，用户规则中同名规则会覆盖通用规则")
        self._use_builtin_checkbox.stateChanged.connect(self._on_toggle_builtin)

        rules_row = QHBoxLayout()
        rules_row.addWidget(self._load_rules_btn)
        rules_row.addWidget(self._rules_label, stretch=1)
        rules_row.addWidget(self._use_builtin_checkbox)
        return rules_row

    def _build_body_splitter(self) -> QSplitter:
        """构造主体分割器：左侧列表区 + 右侧详情区。"""
        self._splitter = QSplitter(Qt.Horizontal)
        list_area = self._build_list_area()
        detail_area = self._build_detail_area()
        # 水平 sizePolicy 设为 Ignored，让 QSplitter 按 stretchFactor/setSizes 分配，
        # 而非按子部件 sizeHint 比例（两者 sizeHint 接近会导致 1:1 平分）
        list_area.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        detail_area.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._splitter.addWidget(list_area)
        self._splitter.addWidget(detail_area)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)
        return self._splitter

    def _build_list_area(self) -> QWidget:
        """构造 ③ 列表区：QTabWidget + ⑤ 底部操作区。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("listTabs")
        self._tab_widget.addTab(self._build_results_tab(), "扫描结果")
        self._tab_widget.addTab(self._build_rules_tab(), "规则文件")
        self._tab_widget.addTab(self._build_history_tab(), "扫描历史")
        layout.addWidget(self._tab_widget, stretch=1)

        layout.addWidget(self._build_list_action_bar())
        return container

    def _build_results_tab(self) -> QWidget:
        """构造扫描结果 Tab：筛选栏 + 结果树。"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._build_result_filter_bar())

        self._result_tree = QTreeWidget()
        self._result_tree.setObjectName("resultTree")
        self._result_tree.setHeaderLabels(["路径", "规则", "严重等级", "命中数", "详情"])
        self._result_tree.setColumnWidth(0, 400)
        self._result_tree.setColumnWidth(1, 150)
        self._result_tree.setColumnWidth(2, 80)
        self._result_tree.setColumnWidth(3, 60)
        self._result_tree.setAlternatingRowColors(True)
        self._result_tree.setRootIsDecorated(True)
        self._result_tree.setSortingEnabled(True)
        self._result_tree.itemDoubleClicked.connect(self._on_result_double_clicked)
        self._result_tree.itemSelectionChanged.connect(self._on_result_selection_changed)
        layout.addWidget(self._result_tree, stretch=1)
        return tab

    def _build_result_filter_bar(self) -> QWidget:
        """构造结果筛选栏：路径筛选 + 规则筛选 + 分组模式。"""
        bar = QFrame()
        bar.setObjectName("filterBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        layout.addWidget(QLabel("筛选:"))

        self._path_filter_input = QLineEdit()
        self._path_filter_input.setPlaceholderText("按路径筛选...")
        self._path_filter_input.setClearButtonEnabled(True)
        self._path_filter_input.textChanged.connect(self._refresh_result_tree)
        layout.addWidget(self._path_filter_input, stretch=2)

        layout.addWidget(QLabel("规则:"))
        self._rule_filter_combo = QComboBox()
        self._rule_filter_combo.addItem("全部规则", "")
        self._rule_filter_combo.currentIndexChanged.connect(self._refresh_result_tree)
        layout.addWidget(self._rule_filter_combo, stretch=1)

        layout.addWidget(QLabel("分组:"))
        self._group_mode_combo = QComboBox()
        self._group_mode_combo.addItem("不分组", "flat")
        self._group_mode_combo.addItem("按规则", "rule")
        self._group_mode_combo.addItem("按严重等级", "severity")
        self._group_mode_combo.currentIndexChanged.connect(self._refresh_result_tree)
        layout.addWidget(self._group_mode_combo, stretch=1)

        return bar

    def _build_rules_tab(self) -> QWidget:
        """构造规则文件 Tab：规则文件列表 + 排序按钮 + 规则树。"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("规则文件（顺序从上到下，后者覆盖前者）"))

        self._rules_file_list = QListWidget()
        self._rules_file_list.setToolTip("已加载的规则文件，列表顺序代表优先级（从低到高）")
        layout.addWidget(self._rules_file_list)

        btn_layout = QHBoxLayout()
        self._move_up_btn = QPushButton("上移")
        self._move_up_btn.setToolTip("将选中的规则文件上移（优先级降低）")
        self._move_up_btn.clicked.connect(self._on_move_rule_up)
        self._move_down_btn = QPushButton("下移")
        self._move_down_btn.setToolTip("将选中的规则文件下移（优先级升高）")
        self._move_down_btn.clicked.connect(self._on_move_rule_down)
        self._remove_rule_btn = QPushButton("移除")
        self._remove_rule_btn.setToolTip("移除选中的规则文件")
        self._remove_rule_btn.clicked.connect(self._on_remove_rule)
        self._edit_rule_btn = QPushButton("编辑")
        self._edit_rule_btn.setToolTip("编辑选中的规则文件")
        self._edit_rule_btn.clicked.connect(self._on_edit_rules)
        btn_layout.addWidget(self._move_up_btn)
        btn_layout.addWidget(self._move_down_btn)
        btn_layout.addWidget(self._remove_rule_btn)
        btn_layout.addWidget(self._edit_rule_btn)
        layout.addLayout(btn_layout)

        self._rules_tree = QTreeWidget()
        self._rules_tree.setHeaderLabels(["规则名", "严重等级", "扩展名"])
        self._rules_tree.setRootIsDecorated(False)
        layout.addWidget(self._rules_tree, stretch=1)
        return tab

    def _build_history_tab(self) -> QWidget:
        """构造扫描历史 Tab：历史路径列表。"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("扫描历史（最近优先）"))
        self._history_list = QListWidget()
        self._history_list.setToolTip("最近扫描过的路径，双击可快速选择")
        self._history_list.itemDoubleClicked.connect(self._on_history_item_double_clicked)
        layout.addWidget(self._history_list, stretch=1)
        return tab

    def _build_list_action_bar(self) -> QWidget:
        """构造 ⑤ 底部操作区：备注输入框 + 按钮组。"""
        bar = QFrame()
        bar.setObjectName("listActionBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # 备注输入框
        self._note_edit = QPlainTextEdit()
        self._note_edit.setObjectName("noteEdit")
        self._note_edit.setPlaceholderText("备注/批注/导出说明...")
        self._note_edit.setMaximumHeight(80)
        layout.addWidget(self._note_edit)

        # 按钮组：辅助操作靠左，主操作靠右
        btn_row = QHBoxLayout()
        self._batch_btn = QPushButton("批量处理")
        self._batch_btn.setObjectName("batchBtn")
        self._batch_btn.setToolTip("对选中项批量处理（预留）")
        self._batch_btn.clicked.connect(self._on_batch_process)
        self._batch_btn.setEnabled(False)
        btn_row.addWidget(self._batch_btn)
        btn_row.addStretch()

        self._export_btn = QPushButton("导出结果")
        self._export_btn.setObjectName("exportBtn")
        self._export_btn.setToolTip("导出扫描结果到文件")
        self._export_btn.clicked.connect(self._on_export_menu)
        self._export_btn.setEnabled(False)
        btn_row.addWidget(self._export_btn)
        layout.addLayout(btn_row)
        return bar

    def _build_detail_area(self) -> QWidget:
        """构造 ④ 详情区：操作栏（QStackedWidget 两态）+ 主体（QStackedWidget 两态）。"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 操作栏：QStackedWidget 持久化空态/非空态两页面
        self._detail_action_stack = QStackedWidget()
        self._detail_action_stack.setObjectName("detailActionBar")
        self._detail_action_stack.addWidget(self._build_detail_empty_action())
        self._detail_action_stack.addWidget(self._build_detail_nonempty_action())
        layout.addWidget(self._detail_action_stack)

        # 主体：QStackedWidget 持久化空态/非空态两页面
        self._detail_main_stack = QStackedWidget()
        self._detail_main_stack.setObjectName("detailMain")
        self._detail_main_stack.addWidget(self._build_detail_empty_main())
        self._detail_main_stack.addWidget(self._build_detail_nonempty_main())
        layout.addWidget(self._detail_main_stack, stretch=1)
        return container

    def _build_detail_empty_action(self) -> QWidget:
        """详情区操作栏空态页：全局操作引导。"""
        bar = QFrame()
        bar.setObjectName("detailEmptyAction")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel("详情操作:"))
        hint = QLabel("未选中任何项")
        hint.setStyleSheet("color: #586069;")
        layout.addWidget(hint)
        layout.addStretch()

        self._detail_start_btn = QPushButton("开始扫描")
        self._detail_start_btn.setObjectName("detailStartBtn")
        self._detail_start_btn.setToolTip("开始扫描（需先选择目标与规则）")
        self._detail_start_btn.clicked.connect(self._on_scan)
        layout.addWidget(self._detail_start_btn)

        self._detail_load_rules_btn = QPushButton("加载规则")
        self._detail_load_rules_btn.setObjectName("detailLoadRulesBtn")
        self._detail_load_rules_btn.setToolTip("加载规则文件")
        self._detail_load_rules_btn.clicked.connect(self._on_load_rules)
        layout.addWidget(self._detail_load_rules_btn)

        self._detail_view_history_btn = QPushButton("查看历史")
        self._detail_view_history_btn.setObjectName("detailViewHistoryBtn")
        self._detail_view_history_btn.setToolTip("切换到扫描历史视图")
        self._detail_view_history_btn.clicked.connect(self._on_view_history)
        layout.addWidget(self._detail_view_history_btn)
        return bar

    def _build_detail_nonempty_action(self) -> QWidget:
        """详情区操作栏非空态页：针对具体详情的操作。"""
        bar = QFrame()
        bar.setObjectName("detailNonemptyAction")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._detail_locate_btn = QPushButton("定位命中")
        self._detail_locate_btn.setObjectName("detailLocateBtn")
        self._detail_locate_btn.setToolTip("滚动到当前命中位置")
        self._detail_locate_btn.clicked.connect(self._on_locate_hit)
        layout.addWidget(self._detail_locate_btn)

        self._detail_prev_btn = QPushButton("上一条")
        self._detail_prev_btn.setObjectName("detailPrevBtn")
        self._detail_prev_btn.setToolTip("跳转到上一个命中位置")
        self._detail_prev_btn.clicked.connect(self._on_prev_detail_hit)
        layout.addWidget(self._detail_prev_btn)

        self._detail_next_btn = QPushButton("下一条")
        self._detail_next_btn.setObjectName("detailNextBtn")
        self._detail_next_btn.setToolTip("跳转到下一个命中位置")
        self._detail_next_btn.clicked.connect(self._on_next_detail_hit)
        layout.addWidget(self._detail_next_btn)

        self._detail_nav_label = QLabel("0 / 0")
        self._detail_nav_label.setObjectName("detailNavLabel")
        layout.addWidget(self._detail_nav_label)

        layout.addStretch()

        self._detail_open_location_btn = QPushButton("打开文件位置")
        self._detail_open_location_btn.setObjectName("detailOpenLocationBtn")
        self._detail_open_location_btn.setToolTip("在文件管理器中打开所在目录")
        self._detail_open_location_btn.clicked.connect(self._on_open_file_location)
        layout.addWidget(self._detail_open_location_btn)

        self._detail_copy_path_btn = QPushButton("复制路径")
        self._detail_copy_path_btn.setObjectName("detailCopyPathBtn")
        self._detail_copy_path_btn.setToolTip("复制文件路径到剪贴板")
        self._detail_copy_path_btn.clicked.connect(self._on_copy_path)
        layout.addWidget(self._detail_copy_path_btn)

        self._detail_open_window_btn = QPushButton("在新窗口打开")
        self._detail_open_window_btn.setObjectName("detailOpenWindowBtn")
        self._detail_open_window_btn.setToolTip("弹出独立对话框查看完整详情")
        self._detail_open_window_btn.clicked.connect(self._on_open_in_window)
        layout.addWidget(self._detail_open_window_btn)
        return bar

    def _build_detail_empty_main(self) -> QWidget:
        """详情区主体空态页：引导文案。"""
        container = QFrame()
        container.setObjectName("detailEmptyMain")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)
        hint = QLabel("未选中任何项\n请先开始扫描或在左侧列表选择一项")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #586069; font-size: 13px;")
        layout.addWidget(hint)
        return container

    def _build_detail_nonempty_main(self) -> QWidget:
        """详情区主体非空态页：文件信息 + 命中表 + 内容预览 + 命中导航。"""
        container = QFrame()
        container.setObjectName("detailNonemptyMain")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 文件信息区
        self._detail_info_label = QLabel()
        self._detail_info_label.setTextFormat(Qt.RichText)
        self._detail_info_label.setWordWrap(True)
        self._detail_info_label.setStyleSheet(
            "padding: 8px; background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 4px;"
        )
        layout.addWidget(self._detail_info_label)

        # 命中规则表
        layout.addWidget(QLabel("命中规则:"))
        self._detail_hits_table = QTableWidget()
        self._detail_hits_table.setObjectName("detailHitsTable")
        self._detail_hits_table.setColumnCount(3)
        self._detail_hits_table.setHorizontalHeaderLabels(["规则名", "严重等级", "详情"])
        self._detail_hits_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._detail_hits_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._detail_hits_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._detail_hits_table, stretch=1)

        # 内容预览
        layout.addWidget(QLabel("内容预览 (关键词高亮):"))
        self._detail_preview = QTextEdit()
        self._detail_preview.setObjectName("detailPreview")
        self._detail_preview.setReadOnly(True)
        layout.addWidget(self._detail_preview, stretch=2)
        return container

    def _init_menu(self) -> None:
        """初始化菜单栏：文件/扫描/视图/帮助。"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu(self.tr("文件(&F)"))
        self._load_rules_action = QAction(self.tr("加载规则..."), self)
        self._load_rules_action.setShortcut("Ctrl+O")
        self._load_rules_action.triggered.connect(self._on_load_rules)
        file_menu.addAction(self._load_rules_action)

        self._edit_rules_action = QAction(self.tr("编辑规则..."), self)
        self._edit_rules_action.setShortcut("Ctrl+E")
        self._edit_rules_action.triggered.connect(self._on_edit_rules)
        file_menu.addAction(self._edit_rules_action)

        file_menu.addSeparator()

        self._export_csv_action = QAction(self.tr("导出 CSV..."), self)
        self._export_csv_action.setShortcut("Ctrl+S")
        self._export_csv_action.triggered.connect(lambda: self._on_export("csv"))
        file_menu.addAction(self._export_csv_action)

        self._export_json_action = QAction(self.tr("导出 JSON..."), self)
        self._export_json_action.setShortcut("Ctrl+Shift+S")
        self._export_json_action.triggered.connect(lambda: self._on_export("json"))
        file_menu.addAction(self._export_json_action)

        file_menu.addSeparator()

        quit_action = QAction(self.tr("退出(&Q)"), self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # 扫描菜单
        scan_menu = menubar.addMenu(self.tr("扫描(&S)"))
        select_path_action = QAction(self.tr("选择扫描路径..."), self)
        select_path_action.triggered.connect(self._on_select_path)
        scan_menu.addAction(select_path_action)

        self._scan_action = QAction(self.tr("开始扫描"), self)
        self._scan_action.setShortcut("F5")
        self._scan_action.triggered.connect(self._on_scan)
        scan_menu.addAction(self._scan_action)

        self._stop_action = QAction(self.tr("停止扫描"), self)
        self._stop_action.setShortcut("Esc")
        self._stop_action.triggered.connect(self._on_stop)
        scan_menu.addAction(self._stop_action)

        # 视图菜单
        view_menu = menubar.addMenu(self.tr("视图(&V)"))
        self._view_results_action = QAction(self.tr("切换到扫描结果"), self)
        self._view_results_action.setShortcut("Ctrl+1")
        self._view_results_action.triggered.connect(lambda: self._switch_tab(0))
        view_menu.addAction(self._view_results_action)

        self._view_rules_action = QAction(self.tr("切换到规则文件"), self)
        self._view_rules_action.setShortcut("Ctrl+2")
        self._view_rules_action.triggered.connect(lambda: self._switch_tab(1))
        view_menu.addAction(self._view_rules_action)

        self._view_history_action = QAction(self.tr("切换到扫描历史"), self)
        self._view_history_action.setShortcut("Ctrl+3")
        self._view_history_action.triggered.connect(lambda: self._switch_tab(2))
        view_menu.addAction(self._view_history_action)

        # 帮助菜单
        help_menu = menubar.addMenu(self.tr("帮助(&H)"))
        about_action = QAction(self.tr("关于"), self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbar(self) -> None:
        """工具栏与菜单复用 action。"""
        toolbar = self.addToolBar(self.tr("主工具栏"))
        toolbar.addAction(self._scan_action)
        toolbar.addAction(self._load_rules_action)
        toolbar.addAction(self._export_csv_action)

    def _switch_tab(self, index: int) -> None:
        """切换列表区 Tab 视图。"""
        if 0 <= index < self._tab_widget.count():
            self._tab_widget.setCurrentIndex(index)

    def _on_view_history(self) -> None:
        """切换到扫描历史视图。"""
        self._switch_tab(2)

    def _apply_qss(self) -> None:
        """应用 GitHub Desktop 风格样式表。

        配色：背景 #f6f8fa、主色 #0366d6、危险色 #d73a49、边框 #e1e4e8。
        字体层级：主操作按钮 14px > 列表项 13px > 详情正文 13px > 辅助说明 12px。
        """
        self.setStyleSheet(
            """
            QMainWindow, QWidget#central {
                background: #f6f8fa;
            }
            QFrame#controlArea {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
            }
            QFrame#listActionBar, QFrame#detailEmptyAction, QFrame#detailNonemptyAction {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
            }
            QFrame#detailEmptyMain, QFrame#detailNonemptyMain {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
            }
            QPushButton#modeCard {
                text-align: left;
                padding: 12px 16px;
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                background: #ffffff;
                font-size: 13px;
                min-width: 110px;
            }
            QPushButton#modeCard:hover {
                border-color: #0366d6;
                background: #f1f8ff;
            }
            QPushButton#modeCard:checked {
                border-color: #0366d6;
                background: #0366d6;
                color: white;
                font-weight: bold;
            }
            QPushButton#scanBtn {
                background: #0366d6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 24px;
            }
            QPushButton#scanBtn:hover {
                background: #0256c1;
            }
            QPushButton#scanBtn:pressed {
                background: #024a9c;
            }
            QPushButton#scanBtn:disabled {
                background: #e1e4e8;
                color: #ffffff;
            }
            QPushButton#stopBtn {
                background: #d73a49;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton#stopBtn:hover {
                background: #c12736;
            }
            QPushButton#stopBtn:pressed {
                background: #a51e2b;
            }
            QPushButton#stopBtn:disabled {
                background: #e1e4e8;
                color: #ffffff;
            }
            QPushButton#exportBtn {
                background: #0366d6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 16px;
            }
            QPushButton#exportBtn:hover {
                background: #0256c1;
            }
            QPushButton#exportBtn:disabled {
                background: #e1e4e8;
                color: #ffffff;
            }
            QPushButton#detailStartBtn, QPushButton#detailLoadRulesBtn, QPushButton#detailViewHistoryBtn {
                background: #ffffff;
                color: #0366d6;
                border: 1px solid #0366d6;
                border-radius: 4px;
                font-size: 13px;
                padding: 6px 12px;
            }
            QPushButton#detailStartBtn:hover, QPushButton#detailLoadRulesBtn:hover, QPushButton#detailViewHistoryBtn:hover {
                background: #f1f8ff;
            }
            QPushButton#detailPrevBtn, QPushButton#detailNextBtn,
            QPushButton#detailLocateBtn, QPushButton#detailOpenLocationBtn,
            QPushButton#detailCopyPathBtn, QPushButton#detailOpenWindowBtn,
            QPushButton#batchBtn {
                background: #ffffff;
                color: #24292e;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                font-size: 13px;
                padding: 6px 12px;
            }
            QPushButton#detailPrevBtn:hover, QPushButton#detailNextBtn:hover,
            QPushButton#detailLocateBtn:hover, QPushButton#detailOpenLocationBtn:hover,
            QPushButton#detailCopyPathBtn:hover, QPushButton#detailOpenWindowBtn:hover,
            QPushButton#batchBtn:hover {
                background: #f6f8fa;
                border-color: #0366d6;
            }
            QProgressBar {
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                text-align: center;
                background: #f6f8fa;
            }
            QProgressBar::chunk {
                background: #0366d6;
                border-radius: 3px;
            }
            QLabel#currentFileLabel {
                font-size: 12px;
                color: #586069;
                padding: 1px 4px;
            }
            QLabel#statsLabel {
                font-size: 13px;
                color: #24292e;
                padding: 2px 4px;
            }
            QTreeWidget#resultTree {
                font-size: 13px;
                alternate-background-color: #f6f8fa;
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
            }
            QTreeWidget#resultTree::item {
                min-height: 22px;
            }
            QTreeWidget {
                font-size: 13px;
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
            }
            QListWidget {
                font-size: 13px;
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #f6f8fa;
                color: #24292e;
                padding: 6px 12px;
                border: 1px solid #e1e4e8;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0366d6;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #e1e4e8;
            }
            QPlainTextEdit#noteEdit {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                font-size: 13px;
            }
            QTextEdit#detailPreview {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                font-size: 13px;
            }
            QTableWidget#detailHitsTable {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                font-size: 13px;
            }
            QLabel#detailNavLabel {
                font-size: 12px;
                color: #586069;
                padding: 0 8px;
            }
            QSplitter::handle {
                background: #e1e4e8;
            }
            QSplitter::handle:horizontal {
                width: 2px;
            }
            """
        )

    # ----------------------------- 配置持久化 -----------------------------

    def _apply_config(self) -> None:
        """应用配置：恢复窗口几何、分割器、扫描模式、规则路径、扫描历史。"""
        if self._config.window_geometry and len(self._config.window_geometry) == 4:
            x, y, w, h = self._config.window_geometry
            self.setGeometry(x, y, w, h)
        if self._config.window_state == "maximized":
            self.showMaximized()

        if self._config.splitter_sizes:
            self._splitter.setSizes(self._config.splitter_sizes)

        # 恢复扫描模式
        self._scan_mode = self._config.scan_mode if self._config.scan_mode in ("full", "drive", "folder") else "folder"
        mode_btn_map = {"full": self._full_btn, "drive": self._drive_btn, "folder": self._folder_btn}
        mode_btn_map[self._scan_mode].setChecked(True)
        self._update_target_visibility()

        # 恢复上次选择的盘符
        if self._config.last_drive:
            idx = self._drive_combo.findData(self._config.last_drive)
            if idx >= 0:
                self._drive_combo.blockSignals(True)
                self._drive_combo.setCurrentIndex(idx)
                self._drive_combo.blockSignals(False)

        self._use_builtin = self._config.use_builtin
        self._use_builtin_checkbox.blockSignals(True)
        self._use_builtin_checkbox.setChecked(self._config.use_builtin)
        self._use_builtin_checkbox.blockSignals(False)

        self._rules_paths = [Path(p) for p in self._config.rules_paths if Path(p).exists()]

        self._path_combo.blockSignals(True)
        for p in self._config.scan_paths:
            self._path_combo.addItem(p)
        self._path_combo.blockSignals(False)

        # 恢复扫描历史
        self._scan_history = list(self._config.scan_paths)
        self._refresh_history_list()

        # 恢复首个有效路径作为扫描目标，启用扫描按钮
        if self._scan_mode == "folder" and self._path_combo.count() > 0:
            first_path = Path(self._path_combo.itemText(0))
            self._scan_root = first_path if first_path.exists() else None
        self._update_scan_button()

    def _save_config(self) -> None:
        """保存当前状态到配置文件。"""
        geo = self.geometry()
        self._config.window_geometry = [geo.x(), geo.y(), geo.width(), geo.height()]
        self._config.window_state = "maximized" if self.isMaximized() else "normal"
        self._config.splitter_sizes = list(self._splitter.sizes())
        self._config.scan_mode = self._scan_mode
        self._config.last_drive = self._drive_combo.currentData() if self._drive_combo.count() > 0 else None
        self._config.rules_paths = [str(p) for p in self._rules_paths]
        self._config.use_builtin = self._use_builtin
        self._config.scan_paths = [self._path_combo.itemText(i) for i in range(self._path_combo.count())]
        save_config(self._config)

    def _add_scan_path_history(self, path_str: str) -> None:
        """将路径添加到扫描历史下拉与历史列表（去重、最近优先、限制数量）。"""
        self._path_combo.blockSignals(True)
        idx = self._path_combo.findText(path_str)
        if idx >= 0:
            self._path_combo.removeItem(idx)
        self._path_combo.insertItem(0, path_str)
        while self._path_combo.count() > MAX_HISTORY:
            self._path_combo.removeItem(self._path_combo.count() - 1)
        self._path_combo.setCurrentIndex(0)
        self._path_combo.blockSignals(False)

        # 同步扫描历史
        if path_str in self._scan_history:
            self._scan_history.remove(path_str)
        self._scan_history.insert(0, path_str)
        while len(self._scan_history) > MAX_HISTORY:
            self._scan_history.pop()
        self._refresh_history_list()

    def _refresh_history_list(self) -> None:
        """刷新扫描历史列表。"""
        self._history_list.clear()
        for path_str in self._scan_history:
            item = QListWidgetItem(path_str)
            item.setToolTip(path_str)
            self._history_list.addItem(item)

    def _on_history_item_double_clicked(self, item: QListWidgetItem) -> None:
        """双击历史列表项切换到 folder 模式并选择该路径。"""
        path_str = item.text()
        path = Path(path_str)
        if not path.exists():
            QMessageBox.information(self, "提示", f"路径不存在:\n{path_str}")
            return
        self._folder_btn.setChecked(True)
        self._on_scan_mode_changed(self._folder_btn)
        self._scan_root = path
        self._add_scan_path_history(path_str)
        self._update_scan_button()
        self._switch_tab(0)

    # ----------------------------- 规则加载 -----------------------------

    def _init_rules(self) -> None:
        """启动时加载规则：默认加载内置通用规则。"""
        try:
            self._reload_ruleset()
            self._refresh_rules_tree()
            self._refresh_rules_file_list()
            self._update_scan_button()
            if self._ruleset is not None:
                self._rules_label.setText("规则: 内置通用规则")
                self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条通用规则")
        except RuleError as exc:
            logger.warning("内置规则加载失败: %s", exc)
            self._rules_label.setText("规则文件: 内置规则加载失败")

    def _reload_ruleset(self) -> None:
        """根据当前通用规则开关与用户规则路径列表重新加载规则集。"""
        if self._use_builtin:
            self._ruleset = load_with_builtin(self._rules_paths)
        elif self._rules_paths:
            rulesets = [load_ruleset(p) for p in self._rules_paths]
            self._ruleset = merge_multiple_rulesets(*rulesets)
        else:
            self._ruleset = None

    def _on_toggle_builtin(self, state: int) -> None:
        """通用规则复选框状态变更。"""
        self._use_builtin = bool(state)
        try:
            self._reload_ruleset()
            self._refresh_rules_tree()
            self._refresh_rules_file_list()
            self._update_scan_button()
            if self._ruleset is not None:
                self._rules_label.setText(f"规则: {self._build_rules_label()}")
                self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
            else:
                self._rules_label.setText("规则: 未加载")
                self._stats_label.setText("未加载规则")
        except RuleError as exc:
            QMessageBox.warning(self, "规则错误", f"重新加载规则失败:\n{exc}")

    # ----------------------------- 扫描模式 -----------------------------

    def _on_scan_mode_changed(self, button) -> None:  # type: ignore[no-untyped-def]
        """扫描模式切换：更新目标选择器可见性与扫描按钮状态。"""
        btn_id = self._mode_btn_group.id(button)
        self._scan_mode = {0: "full", 1: "drive", 2: "folder"}.get(btn_id, "folder")
        self._update_target_visibility()
        self._update_scan_button()

    def _update_target_visibility(self) -> None:
        """根据扫描模式更新目标选择器可见性。"""
        is_drive = self._scan_mode == "drive"
        is_folder = self._scan_mode == "folder"
        self._drive_label.setVisible(is_drive)
        self._drive_combo.setVisible(is_drive)
        self._target_row.setVisible(is_folder)

    def _refresh_drive_combo(self) -> None:
        """刷新盘符下拉列表。"""
        self._drive_combo.blockSignals(True)
        self._drive_combo.clear()
        for drive in list_drives():
            self._drive_combo.addItem(str(drive), str(drive))
        self._drive_combo.blockSignals(False)

    def _on_drive_selected(self, _index: int) -> None:
        """盘符选择变更。"""
        self._update_scan_button()

    def _build_scan_roots(self) -> List[Path]:
        """根据扫描模式构造根路径列表。"""
        if self._scan_mode == "full":
            return list_drives()
        if self._scan_mode == "drive":
            data = self._drive_combo.currentData()
            return [Path(data)] if data else []
        # folder 模式
        return [self._scan_root] if self._scan_root else []

    # ----------------------------- 槽函数 -----------------------------

    def _on_load_rules(self) -> None:
        """加载规则文件，追加到已加载列表末尾。"""
        last_dir = str(self._rules_paths[-1].parent) if self._rules_paths else str(Path.home())
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "选择规则文件",
            last_dir,
            "YAML 文件 (*.yaml *.yml);;所有文件 (*.*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if path in self._rules_paths:
            QMessageBox.information(self, "提示", f"该规则文件已在列表中:\n{path.name}")
            return
        self._rules_paths.append(path)
        try:
            self._reload_ruleset()
            self._rules_label.setText(f"规则: {self._build_rules_label()}")
            self._refresh_rules_tree()
            self._refresh_rules_file_list()
            self._update_scan_button()
            if self._ruleset is not None:
                self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
        except RuleError as exc:
            self._rules_paths.remove(path)
            self._reload_ruleset()
            self._refresh_rules_tree()
            self._refresh_rules_file_list()
            self._update_scan_button()
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
        path = Path(path_str)
        self._scan_root = path
        self._add_scan_path_history(str(path))
        self._update_scan_button()

    def _on_path_selected(self, index: int) -> None:
        """从历史下拉选择扫描路径。"""
        if index < 0:
            self._scan_root = None
            self._update_scan_button()
            return
        path_str = self._path_combo.itemText(index)
        if not path_str:
            self._scan_root = None
        else:
            path = Path(path_str)
            self._scan_root = path if path.exists() else None
        self._update_scan_button()

    def _set_scan_controls_text(self, text: str) -> None:
        """同步设置扫描按钮与菜单/工具栏 action 的文本。"""
        self._scan_btn.setText(text)
        self._scan_action.setText(text)
        self._detail_start_btn.setText(text)

    def _on_scan(self) -> None:
        """扫描按钮：根据当前状态执行开始/暂停/继续。"""
        if self._scan_state == ScanState.RUNNING:
            self._pause_scan()
            return
        if self._scan_state == ScanState.PAUSED:
            self._resume_scan()
            return

        if self._ruleset is None:
            return

        roots = self._build_scan_roots()
        if not roots:
            QMessageBox.warning(self, "提示", "未选择有效的扫描目标")
            return

        self._result_tree.clear()
        self._detail_clear()
        self._scan_state = ScanState.RUNNING
        self._set_scan_controls_text("暂停扫描")
        self._stop_btn.setVisible(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._current_file_label.setVisible(True)
        self._current_file_label.setText("准备扫描...")
        self._stats_label.setText("扫描中...")

        self._worker = ScanWorker(
            ruleset=self._ruleset,
            roots=roots,
            scan_archives=True,
            max_workers=8,
        )
        self._worker.progress_info.connect(self._on_scan_progress)
        self._worker.finished_report.connect(self._on_scan_finished)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.cancelled.connect(self._on_scan_cancelled)
        self._worker.start()

    def _pause_scan(self) -> None:
        """暂停扫描。"""
        if self._worker is not None:
            self._worker.pause()
        self._scan_state = ScanState.PAUSED
        self._set_scan_controls_text("继续扫描")
        self._stats_label.setText("已暂停")

    def _resume_scan(self) -> None:
        """恢复扫描。"""
        if self._worker is not None:
            self._worker.resume()
        self._scan_state = ScanState.RUNNING
        self._set_scan_controls_text("暂停扫描")
        self._stats_label.setText("扫描中...")

    def _on_stop(self) -> None:
        """停止扫描。"""
        if self._worker is not None:
            self._worker.cancel()

    def _on_scan_cancelled(self, report: ScanReport) -> None:
        """扫描被取消后的回调。"""
        self._last_report = report
        self._reset_scan_ui()
        self._populate_results(report)
        stats = report.stats
        self._stats_label.setText(
            f"已取消: 总计 {stats.total_files} | 扫描 {stats.scanned_files} | "
            f"命中 {stats.matched_files} | 耗时 {stats.duration_seconds:.2f}s"
        )

    def _reset_scan_ui(self) -> None:
        """重置扫描 UI 到空闲状态。"""
        self._scan_state = ScanState.IDLE
        self._progress.setVisible(False)
        self._current_file_label.setVisible(False)
        self._stop_btn.setVisible(False)
        self._set_scan_controls_text("开始扫描")
        self._cleanup_worker()
        self._update_scan_button()

    def _cleanup_worker(self) -> None:
        """清理后台扫描线程：等待退出后释放引用。"""
        if self._worker is None:
            return
        self._worker.wait(2000)
        self._worker.deleteLater()
        self._worker = None

    def _on_scan_progress(self, info) -> None:  # type: ignore[no-untyped-def]
        """扫描实时进度回调。"""
        # 切换为确定进度模式
        if info.total > 0 and self._progress.maximum() != info.total:
            self._progress.setRange(0, info.total)
        self._progress.setValue(info.scanned)

        # 当前文件（截断显示）
        if info.current_file:
            path_text = info.current_file
            if len(path_text) > 100:
                path_text = "..." + path_text[-97:]
            self._current_file_label.setText(f"正在解析: {path_text}")

        # 详细统计
        self._stats_label.setText(
            f"已扫描 {info.scanned} | 跳过 {info.skipped} | "
            f"命中 {info.matched} | 错误 {info.errors} | "
            f"已用 {info.elapsed:.1f}s"
        )

    def _on_scan_finished(self, report: ScanReport) -> None:
        """扫描完成回调。"""
        self._last_report = report
        self._reset_scan_ui()

        self._populate_results(report)

        stats = report.stats
        self._stats_label.setText(
            f"完成: 总计 {stats.total_files} | 扫描 {stats.scanned_files} | "
            f"跳过 {stats.skipped_files} | 命中 {stats.matched_files} | "
            f"错误 {stats.errors} | 耗时 {stats.duration_seconds:.2f}s"
        )
        # 扫描完成后启用导出按钮
        self._export_btn.setEnabled(report.hits is not None and len(report.hits) > 0)

    def _on_scan_failed(self, error: str) -> None:
        """扫描失败回调。"""
        self._reset_scan_ui()
        self._stats_label.setText("扫描失败")
        QMessageBox.critical(self, "扫描失败", error)

    def _on_export_menu(self) -> None:
        """导出按钮：弹出格式选择对话框。"""
        if self._last_report is None:
            QMessageBox.information(self, "提示", "无可导出的扫描结果")
            return
        # 简单弹窗选择格式
        items = ["CSV 文件 (*.csv)", "JSON 文件 (*.json)"]
        item, ok = QInputDialog.getItem(self, "导出扫描结果", "选择导出格式:", items, 0, False)
        if not ok:
            return
        fmt = "csv" if "CSV" in item else "json"
        self._on_export(fmt)

    def _on_export(self, fmt: str) -> None:
        """导出扫描结果。"""
        if self._last_report is None:
            QMessageBox.information(self, "提示", "无可导出的扫描结果")
            return

        filter_str = "CSV 文件 (*.csv)" if fmt == "csv" else "JSON 文件 (*.json)"
        default_name = f"uniscan_report.{fmt}"
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
        from uniscan import __version__

        QMessageBox.about(
            self,
            "关于 uniscan",
            f"uniscan {__version__}\n\n通用文件扫描器\n支持多格式与压缩文件扫描\n\n技术栈: Python + PySide2",
        )

    def _on_batch_process(self) -> None:
        """批量处理按钮（预留）：提示功能未实现。"""
        QMessageBox.information(self, "提示", "批量处理功能尚未实现，敬请期待。")

    # ----------------------------- 详情区更新 -----------------------------

    def _on_result_selection_changed(self) -> None:
        """结果树选中变化：更新详情区主体。"""
        items = self._result_tree.selectedItems()
        if not items:
            self._detail_clear()
            return
        item = items[0]
        result = item.data(0, Qt.UserRole)
        if result is None and item.parent() is not None:
            result = item.parent().data(0, Qt.UserRole)
        if result is None:
            self._detail_clear()
            return
        self._detail_show_result(result)

    def _detail_clear(self) -> None:
        """清空详情区，切换到空态。"""
        self._detail_action_stack.setCurrentIndex(0)
        self._detail_main_stack.setCurrentIndex(0)
        self._detail_current_result = None
        self._detail_hit_positions = []
        self._detail_current_hit_index = -1
        self._detail_preview.clear()
        self._detail_hits_table.setRowCount(0)
        self._detail_info_label.setText("")

    def _detail_show_result(self, result: ScanResult) -> None:
        """在详情区展示选中项的详情，切换到非空态。"""
        self._detail_current_result = result
        self._detail_action_stack.setCurrentIndex(1)
        self._detail_main_stack.setCurrentIndex(1)
        self._populate_detail_file_info(result)
        self._populate_detail_hits_table(result)
        self._populate_detail_preview(result)

    def _populate_detail_file_info(self, result: ScanResult) -> None:
        """填充详情区文件元信息。"""
        path = result.path
        size = result.size
        try:
            mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            mtime_str = "无法获取"

        info_html = (
            f"<b>文件路径:</b> {html.escape(str(path))}<br>"
            f"<b>文件大小:</b> {_format_size(size)} ({size} 字节)<br>"
            f"<b>修改时间:</b> {html.escape(mtime_str)}<br>"
            f"<b>命中规则数:</b> {len(result.hits)}"
        )
        self._detail_info_label.setText(info_html)

    def _populate_detail_hits_table(self, result: ScanResult) -> None:
        """填充详情区命中规则表。"""
        hits = result.hits
        self._detail_hits_table.setRowCount(len(hits))
        for row, hit in enumerate(hits):
            self._detail_hits_table.setItem(row, 0, QTableWidgetItem(hit.rule_name))
            self._detail_hits_table.setItem(row, 1, QTableWidgetItem(hit.severity.value))
            self._detail_hits_table.setItem(row, 2, QTableWidgetItem(hit.detail))

    def _populate_detail_preview(self, result: ScanResult) -> None:
        """填充详情区内容预览，命中关键词高亮并定位到首个命中。"""
        path = result.path
        truncated = False

        # 优先使用提取器（支持 PDF/DOCX 等格式），失败回退到纯文本
        try:
            content = extract_content(path)
        except Exception:
            logger.debug("提取器提取失败，回退到纯文本: %s", path, exc_info=True)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                logger.warning("读取内容预览失败 %s", path, exc_info=True)
                self._detail_preview.setPlainText(f"无法读取文件内容: {exc}")
                self._update_detail_nav_label()
                return

        if not content:
            self._detail_preview.setPlainText("(文件内容为空或为二进制)")
            self._update_detail_nav_label()
            return

        # 截断过长内容
        if len(content) > _PREVIEW_MAX_CHARS:
            content = content[:_PREVIEW_MAX_CHARS]
            truncated = True

        keywords = _extract_keywords(result.hits)
        html_content = _build_preview_html(content, keywords)
        if truncated:
            html_content += "<p style='color: #888; font-size: 11px;'>(内容已截断，仅显示前 100KB)</p>"
        self._detail_preview.setHtml(html_content)

        # 查找所有关键词位置并定位到首个命中
        self._find_detail_hit_positions(keywords)
        if self._detail_hit_positions:
            self._detail_current_hit_index = 0
            self._highlight_current_detail_hit()
            self._scroll_to_current_detail_hit()
        self._update_detail_nav_label()

    def _find_detail_hit_positions(self, keywords: Sequence[str]) -> None:
        """在详情区预览文档中查找所有关键词出现位置，按位置排序后存储。"""
        self._detail_hit_positions = []
        if not keywords:
            return
        doc = self._detail_preview.document()
        seen: Set[Tuple[int, int]] = set()
        for kw in sorted(set(keywords), key=len, reverse=True):
            cursor = doc.find(kw)
            while not cursor.isNull():
                pos = (cursor.selectionStart(), cursor.selectionEnd())
                if pos not in seen:
                    seen.add(pos)
                    self._detail_hit_positions.append(pos)
                cursor = doc.find(kw, cursor)
        self._detail_hit_positions.sort()

    def _highlight_current_detail_hit(self) -> None:
        """用橙色背景高亮当前命中位置，区别于其他命中的黄色高亮。"""
        if self._detail_current_hit_index < 0 or self._detail_current_hit_index >= len(self._detail_hit_positions):
            self._detail_preview.setExtraSelections([])
            return
        start, end = self._detail_hit_positions[self._detail_current_hit_index]
        sel = QTextEdit.ExtraSelection()
        cursor = self._detail_preview.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        sel.cursor = cursor
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 165, 0))
        sel.format = fmt
        self._detail_preview.setExtraSelections([sel])

    def _scroll_to_current_detail_hit(self) -> None:
        """滚动详情区预览使当前命中位置可见。"""
        if self._detail_current_hit_index < 0 or self._detail_current_hit_index >= len(self._detail_hit_positions):
            return
        start, _ = self._detail_hit_positions[self._detail_current_hit_index]
        cursor = self._detail_preview.textCursor()
        cursor.setPosition(start)
        self._detail_preview.setTextCursor(cursor)
        self._detail_preview.ensureCursorVisible()

    def _on_prev_detail_hit(self) -> None:
        """跳转到上一个命中位置。"""
        if not self._detail_hit_positions:
            return
        self._detail_current_hit_index = (self._detail_current_hit_index - 1) % len(self._detail_hit_positions)
        self._highlight_current_detail_hit()
        self._scroll_to_current_detail_hit()
        self._update_detail_nav_label()

    def _on_next_detail_hit(self) -> None:
        """跳转到下一个命中位置。"""
        if not self._detail_hit_positions:
            return
        self._detail_current_hit_index = (self._detail_current_hit_index + 1) % len(self._detail_hit_positions)
        self._highlight_current_detail_hit()
        self._scroll_to_current_detail_hit()
        self._update_detail_nav_label()

    def _on_locate_hit(self) -> None:
        """定位命中：滚动到当前命中位置。"""
        self._scroll_to_current_detail_hit()

    def _update_detail_nav_label(self) -> None:
        """更新详情区导航标签与按钮状态。"""
        total = len(self._detail_hit_positions)
        if total == 0:
            self._detail_nav_label.setText("无命中")
            self._detail_prev_btn.setEnabled(False)
            self._detail_next_btn.setEnabled(False)
            self._detail_locate_btn.setEnabled(False)
        else:
            self._detail_nav_label.setText(f"{self._detail_current_hit_index + 1} / {total}")
            self._detail_prev_btn.setEnabled(True)
            self._detail_next_btn.setEnabled(True)
            self._detail_locate_btn.setEnabled(True)

    def _on_open_in_window(self) -> None:
        """在新窗口打开完整详情对话框。"""
        if self._detail_current_result is None:
            return
        dialog = HitDetailDialog(self._detail_current_result, self)
        dialog.exec_()

    def _on_copy_path(self) -> None:
        """复制文件路径到剪贴板。"""
        if self._detail_current_result is None:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(self._detail_current_result.path))
            self._stats_label.setText("已复制路径到剪贴板")

    def _on_open_file_location(self) -> None:
        """在文件管理器中打开所在目录。"""
        if self._detail_current_result is None:
            return
        path = self._detail_current_result.path
        try:
            import subprocess
            import sys

            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except Exception as exc:
            logger.warning("打开文件位置失败: %s", exc, exc_info=True)
            QMessageBox.warning(self, "提示", f"打开文件位置失败:\n{exc}")

    # ----------------------------- 辅助方法 -----------------------------

    def _refresh_rules_tree(self) -> None:
        """刷新规则列表展示。"""
        self._rules_tree.clear()
        if self._ruleset is None:
            return
        for rule in self._ruleset.rules:
            item = QTreeWidgetItem(
                [
                    rule.name,
                    rule.severity.value,
                    ", ".join(rule.file_extensions) if rule.file_extensions else "(全部)",
                ]
            )
            self._rules_tree.addTopLevelItem(item)

    def _refresh_rules_file_list(self) -> None:
        """刷新规则文件列表展示。"""
        self._rules_file_list.clear()
        for path in self._rules_paths:
            item = QListWidgetItem(str(path))
            item.setToolTip(str(path))
            self._rules_file_list.addItem(item)

    def _build_rules_label(self) -> str:
        """构造规则标签文本。"""
        names = [p.name for p in self._rules_paths]
        user_part = ", ".join(names)
        if self._use_builtin:
            return f"通用规则 + {user_part}" if user_part else "通用规则"
        return user_part if user_part else "未加载"

    def _on_move_rule_up(self) -> None:
        """将选中的规则文件上移一位。"""
        row = self._rules_file_list.currentRow()
        if row <= 0:
            return
        self._rules_paths[row - 1], self._rules_paths[row] = (
            self._rules_paths[row],
            self._rules_paths[row - 1],
        )
        self._refresh_rules_file_list()
        self._rules_file_list.setCurrentRow(row - 1)
        self._reload_and_refresh()

    def _on_move_rule_down(self) -> None:
        """将选中的规则文件下移一位。"""
        row = self._rules_file_list.currentRow()
        if row < 0 or row >= len(self._rules_paths) - 1:
            return
        self._rules_paths[row + 1], self._rules_paths[row] = (
            self._rules_paths[row],
            self._rules_paths[row + 1],
        )
        self._refresh_rules_file_list()
        self._rules_file_list.setCurrentRow(row + 1)
        self._reload_and_refresh()

    def _on_remove_rule(self) -> None:
        """移除选中的规则文件。"""
        row = self._rules_file_list.currentRow()
        if row < 0:
            return
        del self._rules_paths[row]
        self._refresh_rules_file_list()
        self._reload_and_refresh()

    def _on_edit_rules(self) -> None:
        """打开规则编辑器对话框。"""
        from uniscan.gui.rule_editor import RuleEditorDialog

        if not self._rules_paths:
            QMessageBox.information(self, "提示", "未加载任何规则文件，请先加载规则。")
            return
        dialog = RuleEditorDialog(self._rules_paths, self)
        dialog.rules_saved.connect(self._on_rules_saved)
        dialog.exec_()

    def _on_rules_saved(self, _path: str) -> None:
        """规则文件保存后重新加载规则集。"""
        self._reload_and_refresh()

    def _reload_and_refresh(self) -> None:
        """重新加载规则集并刷新相关 UI 组件。"""
        try:
            self._reload_ruleset()
            self._refresh_rules_tree()
            self._rules_label.setText(f"规则: {self._build_rules_label()}")
            self._update_scan_button()
            if self._ruleset is not None:
                self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
            else:
                self._stats_label.setText("未加载规则")
        except RuleError as exc:
            QMessageBox.warning(self, "规则错误", f"重新加载规则失败:\n{exc}")

    def _populate_results(self, report: ScanReport) -> None:
        """填充结果树：存储报告、更新规则筛选下拉、刷新结果树。"""
        self._last_report = report
        self._update_rule_filter_options(report)
        self._refresh_result_tree()
        # 有结果时启用导出按钮
        self._export_btn.setEnabled(len(report.hits) > 0)

    def _update_rule_filter_options(self, report: ScanReport) -> None:
        """根据扫描结果更新规则筛选下拉项。"""
        current_rule = self._rule_filter_combo.currentData()
        self._rule_filter_combo.blockSignals(True)
        self._rule_filter_combo.clear()
        self._rule_filter_combo.addItem("全部规则", "")
        rule_names: list[str] = []
        seen = set()
        for result in report.hits:
            for hit in result.hits:
                if hit.rule_name not in seen:
                    seen.add(hit.rule_name)
                    rule_names.append(hit.rule_name)
        for name in sorted(rule_names):
            self._rule_filter_combo.addItem(name, name)
        # 恢复之前选中的规则
        if current_rule:
            idx = self._rule_filter_combo.findData(current_rule)
            if idx >= 0:
                self._rule_filter_combo.setCurrentIndex(idx)
        self._rule_filter_combo.blockSignals(False)

    def _refresh_result_tree(self) -> None:
        """根据当前筛选条件与分组模式刷新结果树。"""
        self._result_tree.clear()
        if self._last_report is None:
            return

        path_filter = self._path_filter_input.text().strip().lower()
        rule_filter = self._rule_filter_combo.currentData() or ""
        group_mode = self._group_mode_combo.currentData() or "flat"

        # 筛选 + 收集命中
        filtered = self._filter_results(self._last_report, path_filter, rule_filter)

        if group_mode == "rule":
            self._populate_grouped_by_rule(filtered)
        elif group_mode == "severity":
            self._populate_grouped_by_severity(filtered)
        else:
            self._populate_flat(filtered)

    def _filter_results(
        self,
        report: ScanReport,
        path_filter: str,
        rule_filter: str,
    ) -> list[ScanResult]:
        """按路径与规则筛选结果，返回符合条件的 ScanResult 列表。

        路径筛选为大小写不敏感子串匹配；规则筛选时仅保留包含该规则命中的文件，
        且每个 ScanResult 的 hits 被过滤为仅匹配规则的命中。
        """
        result: list[ScanResult] = []
        for sr in report.hits:
            if path_filter and path_filter not in str(sr.path).lower():
                continue
            if rule_filter:
                matching_hits = tuple(h for h in sr.hits if h.rule_name == rule_filter)
                if not matching_hits:
                    continue
                result.append(ScanResult(path=sr.path, size=sr.size, hits=matching_hits, errors=sr.errors))
            else:
                result.append(sr)
        return result

    def _populate_flat(self, results: list[ScanResult]) -> None:
        """不分组：文件为顶层项，规则命中为子项。"""
        for sr in results:
            file_item = QTreeWidgetItem(
                [
                    str(sr.path),
                    "",
                    sr.max_severity.value,
                    str(len(sr.hits)),
                    f"{len(sr.hits)} 条命中",
                ]
            )
            file_item.setData(0, Qt.UserRole, sr)
            file_item.setTextAlignment(3, Qt.AlignCenter)
            for hit in sr.hits:
                child = QTreeWidgetItem(
                    [
                        "",
                        hit.rule_name,
                        hit.severity.value,
                        "",
                        hit.detail,
                    ]
                )
                file_item.addChild(child)
            self._result_tree.addTopLevelItem(file_item)

    def _populate_grouped_by_rule(self, results: list[ScanResult]) -> None:
        """按规则分组：规则名为顶层项，文件为子项。"""
        rule_map: dict[str, list[tuple[ScanResult, RuleHit]]] = {}
        for sr in results:
            for hit in sr.hits:
                rule_map.setdefault(hit.rule_name, []).append((sr, hit))

        for rule_name in sorted(rule_map.keys()):
            entries = rule_map[rule_name]
            hit_count = len(entries)
            top = QTreeWidgetItem(
                [
                    "",
                    rule_name,
                    "",
                    str(hit_count),
                    f"{hit_count} 个文件",
                ]
            )
            top.setTextAlignment(3, Qt.AlignCenter)
            for sr, hit in entries:
                child = QTreeWidgetItem(
                    [
                        str(sr.path),
                        "",
                        hit.severity.value,
                        "",
                        hit.detail,
                    ]
                )
                child.setData(0, Qt.UserRole, sr)
                top.addChild(child)
            self._result_tree.addTopLevelItem(top)

    def _populate_grouped_by_severity(self, results: list[ScanResult]) -> None:
        """按严重等级分组：等级为顶层项，文件为子项。"""
        severity_map: dict[str, list[ScanResult]] = {}
        for sr in results:
            sev = sr.max_severity.value
            severity_map.setdefault(sev, []).append(sr)

        for severity in sorted(severity_map.keys(), reverse=True):
            entries = severity_map[severity]
            file_count = len(entries)
            top = QTreeWidgetItem(
                [
                    "",
                    "",
                    severity,
                    str(file_count),
                    f"{file_count} 个文件",
                ]
            )
            top.setTextAlignment(3, Qt.AlignCenter)
            for sr in entries:
                child = QTreeWidgetItem(
                    [
                        str(sr.path),
                        "",
                        severity,
                        str(len(sr.hits)),
                        f"{len(sr.hits)} 条命中",
                    ]
                )
                child.setData(0, Qt.UserRole, sr)
                child.setTextAlignment(3, Qt.AlignCenter)
                top.addChild(child)
            self._result_tree.addTopLevelItem(top)

    def _on_result_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击结果项：在新窗口打开详情对话框。

        选中变化已通过 itemSelectionChanged 触发详情区更新，
        双击额外弹出独立对话框供放大查看。
        """
        result = item.data(0, Qt.UserRole)
        if result is None and item.parent() is not None:
            result = item.parent().data(0, Qt.UserRole)
        if result is None:
            return
        dialog = HitDetailDialog(result, self)
        dialog.exec_()

    def _update_scan_button(self) -> None:
        """根据规则、扫描模式与目标就绪状态更新扫描按钮。

        扫描进行中（RUNNING/PAUSED）时按钮始终可用，供暂停/继续使用，
        不受规则或目标就绪状态影响。
        """
        if self._scan_state in (ScanState.RUNNING, ScanState.PAUSED):
            self._scan_btn.setEnabled(True)
            self._scan_action.setEnabled(True)
            self._detail_start_btn.setEnabled(True)
            return
        if self._ruleset is None:
            ready = False
        elif self._scan_mode == "full":
            ready = True
        elif self._scan_mode == "drive":
            ready = self._drive_combo.count() > 0 and self._drive_combo.currentData() is not None
        else:  # folder
            ready = self._scan_root is not None
        self._scan_btn.setEnabled(ready)
        self._scan_action.setEnabled(ready)
        self._detail_start_btn.setEnabled(ready)

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
        """关闭时保存配置并终止后台线程。"""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self._save_config()
        super().closeEvent(event)
