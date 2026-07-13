"""纯文本提取器。

使用 charset-normalizer 自动检测编码，支持 BOM 处理与最大读取限制。
覆盖常见纯文本与代码文件格式。
"""

from __future__ import annotations

import logging
from pathlib import Path

from typing_extensions import override

from fuscan.extractors.base import Extractor, ExtractorError

__all__ = ["TEXT_EXTENSIONS", "TextExtractor"]

logger = logging.getLogger(__name__)

# 支持的纯文本扩展名（不含点，小写）
TEXT_EXTENSIONS: tuple[str, ...] = (
    "txt",
    "log",
    "md",
    "rst",
    "conf",
    "ini",
    "cfg",
    "properties",
    "yaml",
    "yml",
    "json",
    "xml",
    "csv",
    "tsv",
    "html",
    "htm",
    "sql",
    "py",
    "js",
    "ts",
    "jsx",
    "tsx",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "go",
    "rs",
    "rb",
    "php",
    "sh",
    "bash",
    "bat",
    "cmd",
    "ps1",
    "tex",
    "bib",
    "toml",
    "env",
    "gitignore",
    "dockerignore",
    "gradle",
    "kt",
    "swift",
    "scala",
    "lua",
    "pl",
    "r",
    "dart",
    "vue",
    "svelte",
    "scss",
    "sass",
    "less",
    "css",
)

_DEFAULT_MAX_SIZE = 50 * 1024 * 1024  # 50MB


class TextExtractor(Extractor):
    """纯文本提取器：自动检测编码，支持 BOM 与大小限制。"""

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._max_size = max_size

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回纯文本提取器支持的扩展名。"""
        return TEXT_EXTENSIONS

    @override
    def extract(self, path: Path) -> str:
        """提取纯文本内容，自动检测编码并应用大小限制。"""
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ExtractorError(f"无法读取文件大小: {path}: {exc}") from exc

        if size > self._max_size:
            logger.debug("文件过大，跳过提取: %s (%d bytes)", path, size)
            return ""

        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc

        if not data:
            return ""

        return self._decode(data)

    def _decode(self, data: bytes) -> str:
        """检测编码并解码字节流。

        统一行尾为 ``\\n``：Windows 上 ``write_text`` 会将 ``\\n`` 写为 ``\\r\\n``，
        若不规范化会导致 CONTENT EQUALS 等严格比较在跨平台时失败。
        """
        try:
            from charset_normalizer import from_bytes

            result = from_bytes(data).best()
            if result is not None:
                return _normalize_newlines(str(result))
        except ImportError:
            logger.warning("charset-normalizer 未安装，回退到 UTF-8 解码")
        except Exception:
            logger.warning("编码检测失败，回退到 UTF-8 解码", exc_info=True)

        # 回退：尝试 UTF-8 和 GBK，最终用 latin-1（能解码任意字节序列，永不失败）
        for encoding in ("utf-8", "gbk"):
            try:
                return _normalize_newlines(data.decode(encoding))
            except UnicodeDecodeError:
                continue
        return _normalize_newlines(data.decode("latin-1"))


def _normalize_newlines(text: str) -> str:
    """将 CRLF/CR 统一为 LF，保证跨平台内容比较一致。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")
