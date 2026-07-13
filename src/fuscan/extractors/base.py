"""提取器抽象基类与注册表。

设计要点：

- :class:`Extractor` 抽象基类定义 ``extract(path)`` 与 ``extract_from_bytes(data)``
  两套接口：前者从磁盘路径提取，后者从内存字节提取（避免双重 I/O）
- :class:`ExtractorRegistry` 按扩展名分发，支持注册与查找
- 依赖第三方库的提取器在 ``extract`` 方法内部懒加载 import，避免模块导入时强依赖
- :func:`get_extractor` 提供默认注册表查询，未注册返回 ``None``（由调用方回退到纯文本）
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

__all__ = [
    "Extractor",
    "ExtractorError",
    "ExtractorRegistry",
    "default_registry",
    "extract_content",
    "extract_content_from_bytes",
    "get_extractor",
]

logger = logging.getLogger(__name__)


class ExtractorError(Exception):
    """提取器相关错误。"""


class Extractor(ABC):
    """文件内容提取器抽象基类。

    子类须实现 :meth:`extract`（从路径提取）与 :meth:`extract_from_bytes`
    （从内存字节提取）。后者用于缓存模式：调用方一次 ``read_bytes`` 既算哈希
    又提取内容，避免双重磁盘 I/O。
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """该提取器支持的文件扩展名列表（不含点，小写）。"""

    @abstractmethod
    def extract(self, path: Path) -> str:
        """提取文件文本内容。

        :param path: 文件路径
        :return: 提取的文本内容
        :raises ExtractorError: 提取失败（依赖缺失、文件损坏、加密等）
        """

    @abstractmethod
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节提取文本内容，避免重复读磁盘。

        :param data: 文件完整字节内容
        :return: 提取的文本内容
        :raises ExtractorError: 提取失败
        """


class ExtractorRegistry:
    """提取器注册表：按扩展名分发到对应提取器实例。"""

    def __init__(self) -> None:
        self._extractors: dict[str, Extractor] = {}

    def register(self, extractor: Extractor) -> None:
        """注册提取器，按其 supported_extensions 建立映射。"""
        for ext in extractor.supported_extensions:
            normalized = ext.lower().lstrip(".")
            if normalized in self._extractors:
                logger.debug(
                    "扩展名 %s 提取器被覆盖: %s -> %s",
                    normalized,
                    type(self._extractors[normalized]).__name__,
                    type(extractor).__name__,
                )
            self._extractors[normalized] = extractor

    def get(self, extension: str) -> Extractor | None:
        """按扩展名查找提取器，未注册返回 None。"""
        normalized = extension.lower().lstrip(".")
        return self._extractors.get(normalized)

    @property
    def registered_extensions(self) -> tuple[str, ...]:
        """已注册的所有扩展名。"""
        return tuple(sorted(self._extractors.keys()))

    def extract(self, path: Path, extension: str | None = None) -> str:
        """按扩展名提取文件内容。

        :param path: 文件路径
        :param extension: 显式指定扩展名（默认从路径推断）
        :return: 提取的文本；无提取器时返回空字符串
        :raises ExtractorError: 提取失败
        """
        ext = extension if extension is not None else path.suffix.lower().lstrip(".")
        extractor = self.get(ext)
        if extractor is None:
            logger.debug("扩展名 %s 无注册提取器，返回空内容", ext)
            return ""
        return extractor.extract(path)

    def extract_from_bytes(self, data: bytes, extension: str) -> str:
        """按扩展名从内存字节提取文件内容。

        :param data: 文件完整字节内容
        :param extension: 扩展名（不含点，小写）
        :return: 提取的文本；无提取器时返回空字符串
        :raises ExtractorError: 提取失败
        """
        normalized = extension.lower().lstrip(".")
        extractor = self.get(normalized)
        if extractor is None:
            logger.debug("扩展名 %s 无注册提取器，返回空内容", normalized)
            return ""
        return extractor.extract_from_bytes(data)


default_registry = ExtractorRegistry()


def get_extractor(extension: str) -> Extractor | None:
    """从默认注册表查找提取器。"""
    return default_registry.get(extension)


def extract_content(path: Path, extension: str | None = None) -> str:
    """使用默认注册表从磁盘路径提取文件内容。"""
    return default_registry.extract(path, extension=extension)


def extract_content_from_bytes(data: bytes, extension: str) -> str:
    """使用默认注册表从内存字节提取文件内容。

    用于缓存模式：调用方一次 ``read_bytes`` 后既算哈希又提取内容，
    避免提取器内部重复读磁盘。

    :param data: 文件完整字节内容
    :param extension: 扩展名（不含点，小写）
    :return: 提取的文本；无提取器时返回空字符串
    """
    return default_registry.extract_from_bytes(data, extension)
