"""旧版 Microsoft Office 提取器：XLS、DOC、PPT。

XLS 通过 calamine（Rust + PyO3）读取 Excel 97-2003 工作簿，与 XLSX/ODS
共用同一 Rust 后端。DOC/PPT 仍使用 olefile 读取 OLE 复合文档，从文本流中
提取 UTF-16LE 编码内容。

注意：DOC/PPT 为二进制格式，本提取器仅做简单文本提取，不支持复杂格式
（如修订、嵌入对象等）。如需完整提取，建议先转换为 DOCX/PPTX。
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from typing_extensions import override

from fuscan.extractors.base import Extractor, ExtractorError, SpeedTier

__all__ = ["DocExtractor", "PptExtractor", "XlsExtractor"]

logger = logging.getLogger(__name__)

# 连续非可打印字符作为分隔
_NON_PRINTABLE_RE = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]+")


def _extract_utf16le_text(data: bytes) -> str:
    """从二进制数据中提取 UTF-16LE 编码的文本片段。

    扫描字节流，识别 UTF-16LE 编码的可打印字符序列（ASCII + CJK 汉字），
    跳过不可打印的控制字符。适用于 DOC/PPT 二进制格式中的文本存储。

    :param data: 二进制流内容
    :return: 提取的纯文本，片段以换行分隔
    """
    if len(data) < 2:
        return ""

    parts: list[str] = []
    current: list[str] = []

    for i in range(0, len(data) - 1, 2):
        lo = data[i]
        hi = data[i + 1]
        # ASCII 可打印字符（高字节为 0）
        if hi == 0 and 0x20 <= lo <= 0x7E:
            current.append(chr(lo))
        # CJK 统一汉字（U+4E00-U+9FFF）或全角标点（U+3000-U+30FF）
        elif 0x4E <= hi <= 0x9F or hi == 0x30:
            code = lo | (hi << 8)
            current.append(chr(code))
        elif current:
            text = "".join(current).strip()
            if len(text) >= 2:
                parts.append(text)
            current = []

    if current:
        text = "".join(current).strip()
        if len(text) >= 2:
            parts.append(text)

    return "\n".join(parts)


class XlsExtractor(Extractor):
    """XLS (Excel 97-2003) 工作簿文本提取器。

    iter-92 起切换到 calamine (Rust + PyO3) 后端，从 T4 慢速降至 T2 快速，
    与 XLSX/ODS 共用同一 Rust 后端。
    """

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 XLS 提取器支持的扩展名。"""
        return ("xls",)

    @property
    @override
    def speed_tier(self) -> SpeedTier:
        """calamine (Rust + PyO3) 释放 GIL，T2 快速。"""
        return SpeedTier.FAST

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "Excel（XLS）"

    @override
    def extract(self, path: Path) -> str:
        """提取 XLS 工作表单元格文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节解析 XLS 工作簿。"""
        from fuscan.extractors.spreadsheet import _extract_calamine_workbook

        return _extract_calamine_workbook(data, error_label="XLS")


class DocExtractor(Extractor):
    """DOC (Word 97-2003) 文档文本提取器。

    通过 olefile 读取 OLE 复合文档中的 WordDocument 流，提取 UTF-16LE
    编码的文本。仅做简单文本提取，不解析复杂格式。
    """

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 DOC 提取器支持的扩展名。"""
        return ("doc",)

    @property
    @override
    def speed_tier(self) -> SpeedTier:
        """DOC OLE 复合文档 + UTF-16LE 逐字节扫描为 T4 慢速。"""
        return SpeedTier.SLOW

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "Word（DOC）"

    @override
    def extract(self, path: Path) -> str:
        """提取 DOC 文档文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节解析 DOC 文档。"""
        try:
            import olefile
        except ImportError as exc:
            raise ExtractorError("olefile 未安装，无法提取 DOC") from exc

        try:
            ole = olefile.OleFileIO(io.BytesIO(data))
        except Exception as exc:
            raise ExtractorError(f"DOC 解析失败: {exc}") from exc

        try:
            if ole.exists("WordDocument"):
                stream = ole.openstream("WordDocument")
                return _extract_utf16le_text(stream.read())
            logger.debug("DOC 文件无 WordDocument 流")
            return ""
        finally:
            ole.close()


class PptExtractor(Extractor):
    """PPT (PowerPoint 97-2003) 演示文稿文本提取器。

    通过 olefile 读取 OLE 复合文档中的 PowerPoint Document 流，提取
    UTF-16LE 编码的文本。仅做简单文本提取，不解析幻灯片结构。
    """

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 PPT 提取器支持的扩展名。"""
        return ("ppt",)

    @property
    @override
    def speed_tier(self) -> SpeedTier:
        """PPT OLE 复合文档 + UTF-16LE 逐字节扫描为 T4 慢速。"""
        return SpeedTier.SLOW

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "PowerPoint（PPT）"

    @override
    def extract(self, path: Path) -> str:
        """提取 PPT 演示文稿文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节解析 PPT 演示文稿。"""
        try:
            import olefile
        except ImportError as exc:
            raise ExtractorError("olefile 未安装，无法提取 PPT") from exc

        try:
            ole = olefile.OleFileIO(io.BytesIO(data))
        except Exception as exc:
            raise ExtractorError(f"PPT 解析失败: {exc}") from exc

        try:
            if ole.exists("PowerPoint Document"):
                stream = ole.openstream("PowerPoint Document")
                return _extract_utf16le_text(stream.read())
            logger.debug("PPT 文件无 PowerPoint Document 流")
            return ""
        finally:
            ole.close()
