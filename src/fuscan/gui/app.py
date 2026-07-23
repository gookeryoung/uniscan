"""GUI 应用入口：构造 QApplication 与主窗口。

提供 :func:`launch` 函数供 CLI ``gui`` 子命令调用，也可作为脚本直接运行。
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from string import Template
from typing import Sequence

try:
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    from PySide6.QtCore import Qt  # pyrefly: ignore [missing-import]
    from PySide6.QtWidgets import QApplication  # pyrefly: ignore [missing-import]

from fuscan import theme
from fuscan.gui.main_window import MainWindow

__all__ = ["launch", "load_stylesheet"]

logger = logging.getLogger(__name__)

_QSS_PATH = Path(__file__).parent / "styles.qss"


def load_stylesheet() -> str:
    """加载 QSS 并替换设计令牌占位符。

    :return: 替换令牌后的 QSS 字符串。QSS 缺失或令牌不匹配时返回空串并记录警告，
             不阻塞应用启动（界面将回退为 Qt 原生样式）。
    """
    if not _QSS_PATH.is_file():
        logger.warning("QSS 文件缺失：%s，使用 Qt 原生样式", _QSS_PATH)
        return ""
    try:
        raw = _QSS_PATH.read_text(encoding="utf-8")
        return Template(raw).substitute(theme.QSS_TOKENS)
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("QSS 加载或令牌替换失败，使用 Qt 原生样式：%s", exc)
        return ""


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
    # 抑制 cryptography 对 Python 3.8 的弃用警告（依赖链引入，非 fuscan 可控）
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="cryptography")
    _configure_high_dpi()
    args = list(argv) if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    app.setApplicationName("fuscan")
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()

    # PySide2 用 exec_，PySide6 推荐 exec
    run = app.exec if hasattr(app, "exec") else app.exec_
    return run()


if __name__ == "__main__":
    sys.exit(launch())
