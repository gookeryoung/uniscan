"""扫描目标面板。

加载 ``scan_target.ui`` 生成 ``target_group`` 的全部子控件（scan_mode_combo /
target_stack / path_combo / select_path_btn 等），并封装 ``path_combo`` 切换
与 ``select_path_btn`` 点击的信号交互（iter-94）。

主窗口将本面板实例放入 ``scan_target_container`` 容器，通过公共属性访问子控件
（``scan_mode_combo`` / ``target_stack`` / ``drive_buttons_layout`` /
``path_combo`` / ``select_path_btn``）传给 :class:`ScanModePanel` 与
:class:`ScanPathHistory`，再调 :meth:`bind` 连接信号。主窗口通过
``select_path_requested`` 信号感知用户点击「选择...」按钮。

``ScanModePanel`` 仍独立管理模式 combo / 盘符按钮组 / folder 路径状态，
本面板仅接管 path_combo / select_path_btn 的信号连接。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from PySide2.QtCore import Signal
    from PySide2.QtWidgets import QWidget
except ImportError:  # pragma: no cover
    from PySide6.QtCore import Signal  # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import QWidget  # pyrefly: ignore [missing-import]

from fuscan.gui.scan_target_ui import Ui_scan_target

if TYPE_CHECKING:
    from fuscan.gui.scan_mode_panel import ScanModePanel

__all__ = ["ScanTargetPanel"]

logger = logging.getLogger(__name__)


class ScanTargetPanel(QWidget, Ui_scan_target):  # pyrefly: ignore [invalid-inheritance]
    """扫描目标面板：加载 ``scan_target.ui`` 并封装 path_combo / select_path_btn 信号交互。

    使用方式：

    1. 主窗口创建本面板实例（构造时调 ``setupUi`` 生成全部子控件）
    2. 通过公共属性 ``scan_mode_combo`` / ``target_stack`` /
       ``drive_buttons_layout`` / ``path_combo`` / ``select_path_btn``
       将控件引用传给 :class:`ScanModePanel` 与 :class:`ScanPathHistory`
    3. 调 :meth:`bind` 绑定 :class:`ScanModePanel` 并连接信号
    4. 连接 ``select_path_requested`` 信号到主窗口槽

    :param parent: 父 QWidget
    """

    # 用户点击「选择...」按钮（主窗口弹出 QFileDialog 选择目录）
    select_path_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self._scan_mode_panel: ScanModePanel | None = None
        # target_group_layout 只有一项（scan_mode_layout），不伸展
        # 布局设置内聚到面板中，主窗口不再操作 target_group_layout
        self.target_group_layout.setStretch(0, 0)

    def bind(self, scan_mode_panel: ScanModePanel) -> None:
        """绑定 :class:`ScanModePanel` 并连接 path_combo / select_path_btn 信号。

        必须在 :class:`ScanModePanel` 创建后调用——path_combo 切换时需要调用
        ``scan_mode_panel.set_folder_root`` 更新 folder 路径状态。

        :param scan_mode_panel: 扫描模式面板控制器
        """
        self._scan_mode_panel = scan_mode_panel
        # path_combo 切换：内部处理 path → set_folder_root
        # set_folder_root 内部 emit mode_changed，触发主窗口 _update_scan_button
        self.path_combo.currentIndexChanged.connect(self._on_path_selected)
        # select_path_btn 点击：发信号给主窗口（QFileDialog 交互由主窗口处理）
        self.select_path_btn.clicked.connect(self.select_path_requested)

    def _on_path_selected(self, index: int) -> None:
        """path_combo 切换：更新 folder 路径状态。

        从 path_combo 获取路径文本，存在且有效时调用
        :meth:`ScanModePanel.set_folder_root` 更新 folder 路径状态
        （内部 emit ``mode_changed`` 通知主窗口更新扫描按钮）。
        ``index < 0`` 或路径文本为空时清除 folder 路径。

        :param index: path_combo 当前项索引（-1 表示无选中项）
        """
        assert self._scan_mode_panel is not None
        if index < 0:
            self._scan_mode_panel.set_folder_root(None)
            return
        path_str = self.path_combo.itemText(index)
        if not path_str:
            self._scan_mode_panel.set_folder_root(None)
            return
        path = Path(path_str)
        self._scan_mode_panel.set_folder_root(path if path.exists() else None)
