"""设置对话框。

使用 QTabWidget 实现多页面切换，避免设置项过于臃肿：

1. 通用设置：是否包含网络映射盘、是否启用内置规则、缓存设置
2. 扫描设置：最大工作线程数、最大扫描深度、是否扫描压缩包
3. 忽略项：忽略目录、忽略扩展名（左右双栏大尺寸编辑器，便于查看长列表）

UI 装配委托给 ``Ui_SettingsDialog``（对应 ``settings_dialog.ui``），
本模块仅负责信号槽连接、配置加载与保存等业务逻辑。
"""

from __future__ import annotations

try:
    from PySide2.QtWidgets import QDialog, QWidget
except ImportError:  # pragma: no cover
    from PySide6.QtWidgets import QDialog, QWidget  # pyrefly: ignore [missing-import]

from fuscan.config import Config
from fuscan.gui.settings_dialog_ui import Ui_SettingsDialog

__all__ = ["SettingsDialog"]


class SettingsDialog(QDialog, Ui_SettingsDialog):  # pyrefly: ignore [invalid-inheritance]
    """设置对话框，多页面 Tab 形式展示。"""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setupUi(self)

        self._configure_ui()
        self._load_config()

    def _configure_ui(self) -> None:
        """配置 .ui 无法静态表达的信号槽连接。"""
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)
        # 忽略目录列表通常远长于扩展名列表，给左侧目录栏更大拉伸比例（2:1），
        # 使两个编辑器在「忽略项」Tab 中按宽度 2:1 分配可用空间。
        self.ignore_page_layout.setStretch(0, 2)
        self.ignore_page_layout.setStretch(1, 1)

    def _load_config(self) -> None:
        """加载当前配置到控件。"""
        self.max_workers_spin.setValue(self.config.max_workers)
        self.max_depth_spin.setValue(self.config.max_depth or 0)
        # 字节转 MB（0 表示不限制，SpinBox 最小值 0 + specialValueText "不限制"）
        self.max_file_size_spin.setValue(self.config.max_file_size // (1024 * 1024))
        self.scan_archives_check.setChecked(self.config.scan_archives)
        self.include_network_check.setChecked(self.config.include_network_drives)
        self.use_builtin_check.setChecked(self.config.use_builtin)
        self.ignore_dirs_edit.setPlainText("\n".join(self.config.ignore_dirs))
        self.ignore_extensions_edit.setPlainText("\n".join(self.config.ignore_extensions))
        self.cache_enabled_check.setChecked(self.config.cache_enabled)
        self.cache_path_edit.setText(self.config.cache_path or "")

    def _save_config(self) -> None:
        """将控件值保存到配置。"""
        self.config.max_workers = self.max_workers_spin.value()

        depth = self.max_depth_spin.value()
        self.config.max_depth = depth if depth > 0 else None
        # MB 转 bytes（0 表示不限制，与 Scanner._normalize_max_file_size 语义一致）
        self.config.max_file_size = self.max_file_size_spin.value() * 1024 * 1024
        self.config.scan_archives = self.scan_archives_check.isChecked()
        self.config.include_network_drives = self.include_network_check.isChecked()
        self.config.use_builtin = self.use_builtin_check.isChecked()
        self.config.ignore_dirs = [
            line.strip() for line in self.ignore_dirs_edit.toPlainText().splitlines() if line.strip()
        ]
        self.config.ignore_extensions = [
            line.strip() for line in self.ignore_extensions_edit.toPlainText().splitlines() if line.strip()
        ]
        self.config.cache_enabled = self.cache_enabled_check.isChecked()
        path_text = self.cache_path_edit.text().strip()
        self.config.cache_path = path_text or None

    def on_accept(self) -> None:
        """确定按钮：保存配置并关闭对话框。"""
        self._save_config()
        self.accept()
