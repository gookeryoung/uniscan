"""GUI 应用入口：构造 QApplication 与主窗口。

提供 :func:`launch` 函数供 CLI ``gui`` 子命令调用，也可作为脚本直接运行。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

try:
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

from fuscan.gui.main_window import MainWindow

__all__ = ["launch"]

logger = logging.getLogger(__name__)

# QSS 样式表路径（与本模块同目录）
_QSS_PATH = Path(__file__).parent / "styles.qss"


def _configure_high_dpi() -> None:
    """配置高 DPI 缩放属性，必须在 QApplication 创建前调用。

    - ``AA_EnableHighDpiScaling``：在高分辨率屏幕上自动缩放界面
    - ``AA_UseHighDpiPixmaps``：使用高 DPI 位图资源（SVG 矢量图天然支持）
    """
    # 仅在尚未创建 QApplication 时设置（属性在实例化后不生效）
    if QApplication.instance() is not None:
        return
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def launch(argv: Sequence[str] | None = None) -> int:
    """启动 GUI 应用。

    :param argv: 命令行参数（默认从 sys.argv 读取）
    :return: 退出码
    """
    _configure_high_dpi()
    args = list(argv) if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    app.setApplicationName("fuscan")

    # 加载 GitHub Desktop 风格样式表
    try:
        app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("加载样式表失败: %s", _QSS_PATH, exc_info=True)

    window = MainWindow()
    window.show()

    # PySide2 用 exec_，PySide6 推荐 exec
    run = app.exec if hasattr(app, "exec") else app.exec_
    return run()


if __name__ == "__main__":
    sys.exit(launch())
