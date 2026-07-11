"""提取器默认注册表。

将所有内置提取器注册到 default_registry。
提取器实例化是轻量的（不 import 第三方库），可安全地在模块导入时执行。
"""

from __future__ import annotations

from fuscan.extractors.base import default_registry
from fuscan.extractors.odf import OdtExtractor
from fuscan.extractors.office import DocxExtractor, PptxExtractor
from fuscan.extractors.pdf import PdfExtractor
from fuscan.extractors.spreadsheet import OdsExtractor, XlsxExtractor
from fuscan.extractors.text import TextExtractor
from fuscan.extractors.wps import WpsExtractor

__all__ = ["default_registry", "register_all"]


def register_all() -> None:
    """注册所有内置提取器到 default_registry。

    幂等：重复调用安全，已注册的扩展名会被相同实例覆盖。
    """
    default_registry.register(TextExtractor())
    default_registry.register(PdfExtractor())
    default_registry.register(DocxExtractor())
    default_registry.register(PptxExtractor())
    default_registry.register(XlsxExtractor())
    default_registry.register(OdsExtractor())
    default_registry.register(OdtExtractor())
    default_registry.register(WpsExtractor())


# 模块导入时自动注册
register_all()
