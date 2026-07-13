"""RTF 富文本提取器。

使用 striprtf 库将 RTF 转换为纯文本，保留可见文字内容。
"""

from __future__ import annotations

import logging
from pathlib import Path

from typing_extensions import override

from fuscan.extractors.base import Extractor, ExtractorError

__all__ = ["RtfExtractor"]

logger = logging.getLogger(__name__)


class RtfExtractor(Extractor):
    """RTF 富文本文件文本提取器。"""

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 RTF 提取器支持的扩展名。"""
        return ("rtf",)

    @override
    def extract(self, path: Path) -> str:
        """提取 RTF 文件纯文本内容。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节提取 RTF 纯文本。"""
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError as exc:
            raise ExtractorError("striprtf 未安装，无法提取 RTF") from exc

        try:
            text = data.decode("utf-8", errors="ignore")
            return rtf_to_text(text)
        except Exception as exc:
            raise ExtractorError(f"RTF 解析失败: {exc}") from exc
