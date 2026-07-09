"""扫描后台线程：避免阻塞 UI。

ScanWorker 在独立 QThread 中运行 Scanner.scan，通过信号通知 UI
进度、完成与错误。由于 Scanner 当前为同步实现，进度信号按文件数
粗粒度emit。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide2.QtCore import QThread, Signal

from pyfilescan.rules.model import RuleSet
from pyfilescan.scanner import ScanReport
from pyfilescan.scanner.scanner import Scanner

__all__ = ["ScanWorker"]

logger = logging.getLogger(__name__)


class ScanWorker(QThread):
    """后台扫描线程。

    信号：

    - ``progress``：当前已扫描文件数（粗粒度，每文件 emit）
    - ``finished_report``：扫描完成，携带 ScanReport
    - ``failed``：扫描异常，携带错误信息
    """

    progress = Signal(int)
    finished_report = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        ruleset: RuleSet,
        root: Path,
        max_depth: Optional[int] = None,
        scan_archives: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ruleset = ruleset
        self._root = root
        self._max_depth = max_depth
        self._scan_archives = scan_archives
        self._scanner: Optional[Scanner] = None

    def run(self) -> None:
        """线程入口：执行扫描。"""
        try:
            self._scanner = Scanner(
                ruleset=self._ruleset,
                max_depth=self._max_depth,
                scan_archives=self._scan_archives,
            )
            # 包装 emit 进度（当前 Scanner 无回调，完成后一次性 emit）
            report: ScanReport = self._scanner.scan(self._root)
            self.progress.emit(report.stats.scanned_files)
            self.finished_report.emit(report)
        except Exception as exc:
            logger.exception("后台扫描失败")
            self.failed.emit(str(exc))
