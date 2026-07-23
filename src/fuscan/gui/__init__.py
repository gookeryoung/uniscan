"""PySide2 GUI 子包。

公共 API：

- :class:`MainWindow`：主窗口
- :func:`launch`：启动 GUI 应用
"""

from __future__ import annotations

import sys

# 注册 resources_rc 为顶层模块别名，供 pyside-uic 生成的 _ui.py 裸导入使用
# _ui.py 文件不可手动修改（重新生成会覆盖），其内部固定使用 `import resources_rc` 裸导入
import fuscan.gui.resources_rc as _resources_rc
sys.modules["resources_rc"] = _resources_rc

from fuscan.gui.main_window import MainWindow

__all__ = ["MainWindow", "launch"]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """惰性导入 launch，避免无 GUI 环境下 import 整个包失败。"""
    if name == "launch":
        from fuscan.gui.app import launch

        return launch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
