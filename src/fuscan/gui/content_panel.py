"""配置页内容 TAB 面板控制器。

封装文件类型树与忽略目录两个 TAB 的全部交互逻辑：
``ExtractorTreeModel`` 勾选管理、忽略目录编辑器的加载与节流保存、
勾选计数标签同步。主窗口通过公共 API 驱动，不直接操作底层控件，
提高功能内聚（iter-79 起；iter-87 移除「忽略扩展名」TAB 改为白名单制）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

try:
    from PySide2.QtCore import QObject, QTimer
except ImportError:  # pragma: no cover
    from PySide6.QtCore import QObject, QTimer  # pyrefly: ignore [missing-import]

from fuscan.config import Config, save_config
from fuscan.extractors.base import default_registry
from fuscan.gui.extractor_model import ExtractorTreeModel

try:
    from PySide2.QtWidgets import QPushButton
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QPushButton  # pyrefly: ignore [missing-import]

if TYPE_CHECKING:
    from PySide2.QtWidgets import QLabel, QPlainTextEdit, QTreeView

__all__ = ["ContentTabPanel"]

logger = logging.getLogger(__name__)

# 忽略项节流保存间隔（毫秒）：用户停止输入后等待此时间再写入配置文件，
# 避免每次按键触发文件 I/O
_IGNORE_SAVE_INTERVAL_MS: int = 500


class ContentTabPanel(QObject):  # pyrefly: ignore [invalid-inheritance]
    """配置页内容 TAB 面板控制器：封装文件类型树与忽略目录编辑器。

    职责内聚：

    - 构造 :class:`ExtractorTreeModel` 并绑定到 ``file_types_view`` QTreeView
    - 勾选状态变化时即时保存到 :class:`Config` 并更新计数标签
    - 忽略目录编辑器 ``textChanged`` 后节流保存（500ms）
    - :meth:`apply_config` 从配置恢复勾选状态与忽略目录内容
      （``blockSignals`` 包裹避免触发保存循环）
    - :meth:`flush_pending_save` 立即保存待写入的忽略目录（扫描启动前调用）

    主窗口通过 :meth:`enabled_extensions` / :meth:`archives_enabled` /
    :meth:`disabled_extractors` 读取勾选状态，传给 :class:`ScanWorker`。

    .. note::
       iter-87 起统一为白名单制：扩展名过滤由勾选区（``ExtractorTreeModel``）
       生成的白名单驱动，不再保留「忽略扩展名」黑名单 TAB。
    """

    def __init__(
        self,
        view: QTreeView,
        count_label: QLabel,
        dirs_edit: QPlainTextEdit,
        config: Config,
        select_all_btn: QPushButton,
        unselect_all_btn: QPushButton,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._view = view
        self._count_label = count_label
        self._dirs_edit = dirs_edit

        # 文件类型树模型：从提取器注册表加载元数据，按父类别分组
        self._extractor_model = ExtractorTreeModel(default_registry, parent=self)
        self._view.setModel(self._extractor_model)
        # 展开所有父类别节点，让子项直接可见（headerHidden 与
        # expandsOnDoubleClick 已在 .ui 中静态配置）
        self._view.expandAll()

        # 忽略目录节流保存 timer：textChanged 后 500ms 写入配置文件
        self._ignore_save_timer = QTimer(self)
        self._ignore_save_timer.setSingleShot(True)
        self._ignore_save_timer.setInterval(_IGNORE_SAVE_INTERVAL_MS)
        self._ignore_save_timer.timeout.connect(self._save_ignore_to_config)

        # 信号槽连接：勾选变化 → 即时保存 + 更新计数；忽略目录变化 → 节流保存
        self._extractor_model.extractors_changed.connect(self._on_extractor_toggled)  # pyrefly: ignore [missing-attribute]
        self._dirs_edit.textChanged.connect(self._on_ignore_changed)
        # 全选/全不选按钮：委托模型批量勾选，extractors_changed 信号触发保存与计数同步
        select_all_btn.clicked.connect(self._extractor_model.check_all)
        unselect_all_btn.clicked.connect(self._extractor_model.uncheck_all)

        self._update_count()

    # ----------------------------- 内部槽 -----------------------------

    def _on_extractor_toggled(self) -> None:
        """提取器勾选状态变化：从模型读取并即时保存配置，同步计数标签。

        压缩包分类的勾选状态同步到 ``Config.scan_archives``（iter-79），
        取代独立的 ``scan_archives`` 配置项——压缩包是否扫描由文件类型树统一管理。
        """
        self._config.disabled_extractors = self._extractor_model.disabled_extractors()
        self._config.scan_archives = self._extractor_model.archives_enabled()
        save_config(self._config)
        self._update_count()

    def _on_ignore_changed(self) -> None:
        """忽略目录编辑器文本变化：启动节流 timer，500ms 后保存到 Config。

        避免每次按键触发文件 I/O；用户停止输入 500ms 后才真正写入配置文件。
        """
        self._ignore_save_timer.start()  # pyrefly: ignore [missing-argument]

    def _save_ignore_to_config(self) -> None:
        """从忽略目录编辑器读取文本并保存到 Config（节流 timer 触发）。

        按行解析，strip 首尾空白，过滤空行。保存后立即写入配置文件，
        确保用户编辑不丢失（即使不立即扫描）。
        """
        self._config.ignore_dirs = [line.strip() for line in self._dirs_edit.toPlainText().splitlines() if line.strip()]
        save_config(self._config)

    def _update_count(self) -> None:
        """同步文件类型勾选计数标签（``已勾选 N/M 项``）。

        N 为当前勾选的提取器数量，M 为提取器总数。批量勾选父类别时 N 即时
        反映子项勾选总数，让用户直观感知批量操作的覆盖范围。
        """
        checked = self._extractor_model.checked_count()
        total = self._extractor_model.total_count()
        self._count_label.setText(f"已勾选 {checked}/{total} 项")

    # ----------------------------- 公共 API -----------------------------

    def apply_config(self, config: Config) -> None:
        """从配置恢复勾选状态与忽略目录内容。

        ``blockSignals`` 包裹避免 ``set_disabled_extractors`` / ``setPlainText``
        触发保存循环（``extractors_changed`` / ``textChanged``）。

        向后兼容（iter-79）：旧配置 ``scan_archives=False`` 但
        ``disabled_extractors`` 中无 ``"ArchiveFiles"`` 时，补充禁用压缩包分类。
        """
        disabled = list(config.disabled_extractors)
        if not config.scan_archives and "ArchiveFiles" not in disabled:
            disabled.append("ArchiveFiles")
        self._extractor_model.blockSignals(True)
        self._extractor_model.set_disabled_extractors(disabled)
        self._extractor_model.blockSignals(False)
        # 恢复后同步计数标签（blockSignals 期间 _on_extractor_toggled 不会触发）
        self._update_count()

        # 恢复忽略目录编辑器内容（blockSignals 避免 textChanged 触发节流保存循环）
        self._dirs_edit.blockSignals(True)
        self._dirs_edit.setPlainText("\n".join(config.ignore_dirs))
        self._dirs_edit.blockSignals(False)

    def enabled_extensions(self) -> tuple[str, ...] | None:
        """返回启用的文件扩展名白名单（全选时 None，Scanner 走原快速路径）。

        iter-87：返回值含压缩包扩展名（zip/rar/7z），与其他扩展名统一过滤。
        部分勾选时返回非空 tuple，用户全部取消勾选时返回空 tuple（Scanner 不扫任何文件）。
        """
        return self._extractor_model.enabled_extensions()

    def archives_enabled(self) -> bool:
        """返回压缩包分类勾选状态。"""
        return self._extractor_model.archives_enabled()

    def disabled_extractors(self) -> list[str]:
        """返回已禁用的提取器类名列表。"""
        return self._extractor_model.disabled_extractors()

    def flush_pending_save(self) -> None:
        """立即保存待写入的忽略目录（扫描启动前调用）。

        用户编辑后可能未满 500ms 就点扫描，此处立即保存确保扫描使用最新忽略配置。
        """
        if self._ignore_save_timer.isActive():
            self._ignore_save_timer.stop()
            self._save_ignore_to_config()
