"""OpenDocument 文档提取器：ODT 文字文档。

使用 odfpy 提取 ODT 文档的段落、标题、列表等文本内容。
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from typing_extensions import override

from fuscan.extractors.base import Extractor, ExtractorError

__all__ = ["OdtExtractor"]

logger = logging.getLogger(__name__)


class OdtExtractor(Extractor):
    """ODT 文字文档文本提取器。"""

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 ODT 提取器支持的扩展名。"""
        return ("odt",)

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "ODT 文档"

    @override
    def extract(self, path: Path) -> str:
        """提取 ODT 文档的段落与标题文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节提取 ODT 文档文本。"""
        try:
            from odf.opendocument import load
            from odf.text import H, P
        except ImportError as exc:
            raise ExtractorError("odfpy 未安装，无法提取 ODT") from exc

        try:
            doc = load(io.BytesIO(data))
        except Exception as exc:
            raise ExtractorError(f"ODT 解析失败: {exc}") from exc

        parts: list[str] = []
        # 提取段落 (P) 和标题 (H)
        for paragraph in doc.getElementsByType(P):
            text = str(paragraph).strip()
            if text:
                parts.append(text)
        for heading in doc.getElementsByType(H):
            text = str(heading).strip()
            if text:
                parts.append(text)

        return "\n".join(parts)
