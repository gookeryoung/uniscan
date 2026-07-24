"""扫描目标面板控制器。

封装 ``target_group`` 中 ``path_combo`` 与 ``select_path_btn`` 的信号交互，
将 path_combo 切换逻辑内聚到面板内部，``select_path_btn`` 点击通过信号
通知主窗口弹出 ``QFileDialog``（iter-93）。

``ScanModePanel`` 仍独立管理模式 combo / 盘符按钮组 / folder 路径状态，
本面板仅接管 path_combo / select_path_btn 的信号连接，避免主窗口散落地
直接操作 ``target_group`` 内的底层控件。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from PySide2.QtCore import QObject, Signal
    from PySide2.QtWidgets import QComboBox, QPushButton
except ImportError:  # pragma: no cover
    from PySide6.QtCore import QObject, Signal  # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import QComboBox, QPushButton  # pyrefly: ignore [missing-import]

if TYPE_CHECKING:
    from fuscan.gui.scan_mode_panel import ScanModePanel

__all__ = ["ScanTargetPanel"]

logger = logging.getLogger(__name__)


class ScanTargetPanel(QObject):  # pyrefly: ignore [invalid-inheritance]
    """扫描目标面板控制器：封装 path_combo / select_path_btn 的信号交互。

    职责内聚：

    - 连接 ``path_combo.currentIndexChanged`` → 内部处理 path → ``ScanModePanel.set_folder_root``
    - 连接 ``select_path_btn.clicked`` → 发 ``select_path_requested`` 信号给主窗口

    主窗口通过 ``select_path_requested`` 信号感知用户点击「选择...」按钮，
    弹出 ``QFileDialog`` 选择目录后回写 ``ScanModePanel.set_folder_root`` 与
    ``ScanPathHistory.add``。path_combo 切换由本面板内部处理，主窗口不再
    直接连接 ``path_combo.currentIndexChanged``。

    :param scan_mode_panel: 扫描模式面板控制器（提供 ``set_folder_root`` 等 API）
    :param path_combo: 扫描路径下拉选择控件
    :param select_path_btn: 「选择...」按钮
    :param parent: 父 QObject
    """

    # 用户点击「选择...」按钮（主窗口弹出 QFileDialog 选择目录）
    select_path_requested = Signal()

    def __init__(
        self,
        scan_mode_panel: ScanModePanel,
        path_combo: QComboBox,
        select_path_btn: QPushButton,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._scan_mode_panel = scan_mode_panel
        self._path_combo = path_combo

        # path_combo 切换：内部处理 path → set_folder_root
        # set_folder_root 内部 emit mode_changed，触发主窗口 _update_scan_button
        path_combo.currentIndexChanged.connect(self._on_path_selected)
        # select_path_btn 点击：发信号给主窗口（QFileDialog 交互由主窗口处理）
        select_path_btn.clicked.connect(self.select_path_requested)

    def _on_path_selected(self, index: int) -> None:
        """path_combo 切换：更新 folder 路径状态。

        从 path_combo 获取路径文本，存在且有效时调用
        :meth:`ScanModePanel.set_folder_root` 更新 folder 路径状态
        （内部 emit ``mode_changed`` 通知主窗口更新扫描按钮）。
        ``index < 0`` 或路径文本为空时清除 folder 路径。

        :param index: path_combo 当前项索引（-1 表示无选中项）
        """
        if index < 0:
            self._scan_mode_panel.set_folder_root(None)
            return
        path_str = self._path_combo.itemText(index)
        if not path_str:
            self._scan_mode_panel.set_folder_root(None)
            return
        path = Path(path_str)
        self._scan_mode_panel.set_folder_root(path if path.exists() else None)
