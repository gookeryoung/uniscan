"""结果树筛选面板控制器。

封装结果页筛选控件（路径输入、规则筛选、分组模式）与结果树的刷新逻辑：
combo 初始化、节流 timer、按筛选条件刷新 ResultTreeView、根据扫描报告更新
规则筛选下拉项。主窗口通过公共 API 驱动，不直接操作底层控件，提高功能内聚
（iter-79 续解耦）。

设计要点：panel 不持有扫描报告状态，通过 ``report_getter`` 回调从主窗口
读取 ``_last_report``，避免主窗口与 panel 双状态同步问题。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

try:
    from PySide2.QtCore import QObject, QTimer
    from PySide2.QtWidgets import QComboBox, QLineEdit
except ImportError:  # pragma: no cover
    from PySide6.QtCore import QObject, QTimer  # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import (  # pyrefly: ignore [missing-import]
        QComboBox,
        QLineEdit,
    )

from fuscan.gui.result_tree import ResultTreeView
from fuscan.scanner import ScanReport

if TYPE_CHECKING:
    from PySide2.QtWidgets import QWidget

__all__ = ["ResultFilterPanel"]

logger = logging.getLogger(__name__)

# 节流间隔（毫秒）：path_filter_input 每次按键仅重置 timer，避免连续输入时
# 全量重建结果树导致 UI 卡滞（需求9）
_FILTER_THROTTLE_MS = 300


class ResultFilterPanel(QObject):  # pyrefly: ignore [invalid-inheritance]
    """结果树筛选面板控制器：封装筛选控件 + 节流 timer + 结果树刷新。

    职责内聚：

    - 管理 ``path_filter_input`` 路径筛选输入（节流 300ms 触发刷新）
    - 管理 ``rule_filter_combo`` 规则筛选下拉（切换立即刷新）
    - 管理 ``group_mode_combo`` 分组模式下拉（flat/rule/severity，切换立即刷新）
    - 管理 ``result_tree`` ResultTreeView 的 populate/refresh/clear
    - 通过 ``report_getter`` 回调读取当前扫描报告（避免双状态同步）
    - :meth:`populate` 一站式填充新报告（停止节流 + populate + 更新规则下拉 + 刷新）
    - :meth:`refresh` 按当前筛选条件重新渲染结果树
    - :meth:`clear` 清空结果树（启动新扫描前调用）

    ``result_tree`` 的 ``result_selected`` / ``context_menu_requested`` 信号
    由主窗口直接连接（响应逻辑在主窗口），本面板不介入。
    """

    def __init__(
        self,
        path_filter_input: QLineEdit,
        rule_filter_combo: QComboBox,
        group_mode_combo: QComboBox,
        result_tree: ResultTreeView,
        report_getter: Callable[[], ScanReport | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path_filter_input = path_filter_input
        self._rule_filter_combo = rule_filter_combo
        self._group_mode_combo = group_mode_combo
        self._result_tree = result_tree
        self._report_getter = report_getter

        # 节流 timer：path_filter_input.textChanged 每次按键仅重置 timer，
        # 避免连续输入时全量重建结果树导致 UI 卡滞；combo 切换立即刷新
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(_FILTER_THROTTLE_MS)
        self._filter_timer.timeout.connect(self.refresh)

        # 初始化 combo 选项（.ui 不便表达带 userData 的下拉项）
        self._setup_combo_items()

        # 筛选信号连接（combo 切换立即响应，路径输入节流）。
        # currentIndexChanged(int) 会传入 combo index，用 lambda *_ 吸收避免
        # index 被误解为 refresh 的参数（refresh 无参，传 int 会 TypeError）
        self._path_filter_input.textChanged.connect(self._schedule_refresh)
        self._rule_filter_combo.currentIndexChanged.connect(lambda *_: self.refresh())
        self._group_mode_combo.currentIndexChanged.connect(lambda *_: self.refresh())

    # ----------------------------- 内部槽 -----------------------------

    def _setup_combo_items(self) -> None:
        """填充筛选 combo 初始项（带 userData，.ui 不便表达）。"""
        self._rule_filter_combo.addItem("全部规则", "")
        self._group_mode_combo.addItem("不分组", "flat")
        self._group_mode_combo.addItem("按规则", "rule")
        self._group_mode_combo.addItem("按严重等级", "severity")

    def _schedule_refresh(self) -> None:
        """节流触发结果树刷新。

        ``path_filter_input.textChanged`` 每次按键仅重置 timer，避免连续输入
        时全量重建结果树导致 UI 卡滞。
        """
        self._filter_timer.start()  # pyrefly: ignore [missing-argument]

    def _update_rule_filter_options(self, report: ScanReport) -> None:
        """根据扫描结果更新规则筛选下拉项。

        保留之前选中的规则（若仍存在于新报告中），``blockSignals`` 包裹避免
        ``clear`` / ``addItem`` 触发 ``currentIndexChanged`` 引发重复刷新。
        """
        current_rule = self._rule_filter_combo.currentData()
        self._rule_filter_combo.blockSignals(True)
        self._rule_filter_combo.clear()
        self._rule_filter_combo.addItem("全部规则", "")
        for name in sorted(report.rule_names):
            self._rule_filter_combo.addItem(name, name)
        # 恢复之前选中的规则
        if current_rule:
            idx = self._rule_filter_combo.findData(current_rule)
            if idx >= 0:
                self._rule_filter_combo.setCurrentIndex(idx)
        self._rule_filter_combo.blockSignals(False)

    # ----------------------------- 公共 API -----------------------------

    def populate(self, report: ScanReport) -> None:
        """一站式填充新报告：停止节流 + populate 结果树 + 更新规则下拉 + 刷新。

        :param report: 新的扫描报告（主窗口应已赋值给 ``_last_report``）
        """
        # 取消挂起的节流刷新，避免与下方立即刷新重复触发（需求9）
        self._filter_timer.stop()
        self._result_tree.populate(report)
        self._update_rule_filter_options(report)
        self.refresh()

    def refresh(self) -> None:
        """按当前筛选条件刷新结果树。

        通过 ``report_getter`` 回调从主窗口读取 ``_last_report``，避免
        panel 与主窗口双状态同步问题。
        """
        report = self._report_getter()
        if report is None:
            self._result_tree.clear_results()
            return

        path_filter = self._path_filter_input.text().strip()
        rule_filter = self._rule_filter_combo.currentData() or ""
        group_mode = self._group_mode_combo.currentData() or "flat"

        self._result_tree.refresh(
            report,
            path_query=path_filter,
            rule_name=rule_filter,
            group_mode=group_mode,
        )

    def clear(self) -> None:
        """清空结果树（启动新扫描前调用）。

        不需要清 ``_last_report``（主窗口持有，由主窗口管理生命周期）。
        """
        self._filter_timer.stop()
        self._result_tree.clear_results()
