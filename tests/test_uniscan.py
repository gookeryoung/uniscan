"""uniscan 基础冒烟测试."""

from __future__ import annotations

import uniscan


def test_version_is_string() -> None:
    """__version__ 应为非空字符串."""
    assert isinstance(uniscan.__version__, str)
    assert uniscan.__version__


def test_package_importable() -> None:
    """包应可正常导入."""
    assert hasattr(uniscan, "__all__")
    assert "__version__" in uniscan.__all__
