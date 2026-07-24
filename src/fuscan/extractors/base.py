"""提取器抽象基类与注册表。

设计要点：

- :class:`Extractor` 抽象基类定义 ``extract(path)`` 与 ``extract_from_bytes(data)``
  两套接口：前者从磁盘路径提取，后者从内存字节提取（避免双重 I/O）
- :class:`ExtractorRegistry` 按扩展名分发，支持注册与查找
- 依赖第三方库的提取器在 ``extract`` 方法内部懒加载 import，避免模块导入时强依赖
- :func:`get_extractor` 提供默认注册表查询，未注册返回 ``None``（由调用方回退到纯文本）
- :class:`SpeedTier` 枚举（iter-90）划分 5 档解析速度，GUI 勾选树展示档次
  便于用户按需选择文件类型
"""

from __future__ import annotations

import enum
import logging
from abc import ABC, abstractmethod
from pathlib import Path

__all__ = [
    "Extractor",
    "ExtractorError",
    "ExtractorRegistry",
    "SpeedTier",
    "default_registry",
    "extract_content",
    "extract_content_from_bytes",
    "extract_content_with_fallback",
    "get_extractor",
]

logger = logging.getLogger(__name__)


class SpeedTier(enum.Enum):
    """提取器解析速度档次（iter-90，5 档）。

    档次依据实现复杂度划分，与典型文件大小（1MB）下的解析耗时对应：

    - ``VERY_FAST`` (T1 极速)：< 10ms/MB，纯字节解码，无第三方库
    - ``FAST`` (T2 快速)：10-50ms/MB，标准库解析
    - ``MEDIUM`` (T3 中速)：50-200ms/MB，单次 XML 解析 + 树遍历
    - ``SLOW`` (T4 慢速)：200-1000ms/MB，单元格遍历或字节级扫描
    - ``VERY_SLOW`` (T5 极慢)：> 1000ms/MB，复杂页面布局分析或解压+条目提取

    档次用于 GUI 勾选树展示，帮助用户预估勾选某类文件类型后的扫描耗时。
    实际耗时受文件大小、内容复杂度、磁盘缓存等影响，档次仅为数量级参考。
    """

    VERY_FAST = 1
    FAST = 2
    MEDIUM = 3
    SLOW = 4
    VERY_SLOW = 5

    @property
    def label(self) -> str:
        """返回档次短标签，如 ``T1 极速``（用于树形展示）。"""
        mapping = {
            SpeedTier.VERY_FAST: "T1 极速",
            SpeedTier.FAST: "T2 快速",
            SpeedTier.MEDIUM: "T3 中速",
            SpeedTier.SLOW: "T4 慢速",
            SpeedTier.VERY_SLOW: "T5 极慢",
        }
        return mapping[self]

    @property
    def description(self) -> str:
        """返回档次说明（用于 tooltip）。"""
        mapping = {
            SpeedTier.VERY_FAST: "纯字节解码，无第三方库（< 10ms/MB）",
            SpeedTier.FAST: "标准库解析（10-50ms/MB）",
            SpeedTier.MEDIUM: "单次 XML 解析 + 树遍历（50-200ms/MB）",
            SpeedTier.SLOW: "单元格遍历或字节级扫描（200-1000ms/MB）",
            SpeedTier.VERY_SLOW: "复杂布局分析或解压+条目提取（> 1000ms/MB）",
        }
        return mapping[self]

    @property
    def color(self) -> str:
        """返回档次对应的十六进制色值（从绿到红，用于 GUI 勾选树着色）。

        色值与 ``scan_stats_label`` 内联 HTML 风格一致，属于 rule-12 例外
        （程序化着色无法引用 QSS 令牌，在 docstring 注明）：

        - T1 极速：``#28A745`` 绿色
        - T2 快速：``#17A2B8`` 青色
        - T3 中速：``#FFC107`` 琥珀
        - T4 慢速：``#FD7E14`` 橙色
        - T5 极慢：``#DC3545`` 红色
        """
        mapping = {
            SpeedTier.VERY_FAST: "#28A745",
            SpeedTier.FAST: "#17A2B8",
            SpeedTier.MEDIUM: "#FFC107",
            SpeedTier.SLOW: "#FD7E14",
            SpeedTier.VERY_SLOW: "#DC3545",
        }
        return mapping[self]


class ExtractorError(Exception):
    """提取器相关错误。"""


class Extractor(ABC):
    """文件内容提取器抽象基类。

    子类须实现 :meth:`extract`（从路径提取）与 :meth:`extract_from_bytes`
    （从内存字节提取）。后者用于缓存模式：调用方一次 ``read_bytes`` 既算哈希
    又提取内容，避免双重磁盘 I/O。

    子类还须声明 :attr:`speed_tier` 标识解析速度档次（iter-90），
    供 GUI 勾选树展示。档次依据实现复杂度划分，详见 :class:`SpeedTier`。
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """该提取器支持的文件扩展名列表（不含点，小写）。"""

    @property
    @abstractmethod
    def speed_tier(self) -> SpeedTier:
        """该提取器的解析速度档次（iter-90）。

        子类须按实现复杂度返回对应 :class:`SpeedTier`：
        纯文本解码 → ``VERY_FAST``，标准库解析 → ``FAST``，
        XML 解析 → ``MEDIUM``，单元格遍历/字节扫描 → ``SLOW``，
        页面布局分析/解压+条目提取 → ``VERY_SLOW``。
        """

    @property
    def display_name(self) -> str:
        """提取器的中文显示名称，供 GUI 勾选区展示。默认返回类名，子类可覆盖。"""
        return type(self).__name__

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

    def list_extractors(self) -> list[tuple[str, str, tuple[str, ...], SpeedTier]]:
        """列出所有已注册的提取器信息，供 GUI 勾选区展示。

        :return: ``[(class_name, display_name, supported_extensions, speed_tier), ...]``
                 列表，按 display_name 排序。同一提取器实例支持多个扩展名时合并为一项。
                 ``speed_tier`` 为 :class:`SpeedTier` 枚举值（iter-90）。
        """
        seen: dict[int, tuple[str, str, tuple[str, ...], SpeedTier]] = {}
        for _ext, extractor in self._extractors.items():
            obj_id = id(extractor)
            if obj_id not in seen:
                exts = extractor.supported_extensions
                seen[obj_id] = (
                    type(extractor).__name__,
                    extractor.display_name,
                    tuple(sorted(e.lower().lstrip(".") for e in exts)),
                    extractor.speed_tier,
                )
        return sorted(seen.values(), key=lambda x: x[1])

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


def extract_content_with_fallback(path: Path) -> str:
    """提取文件内容，提取器失败时回退到纯文本读取。

    优先通过 :func:`extract_content` 提取（支持 PDF/DOCX 等格式），
    提取器抛出任何异常时回退到 UTF-8 纯文本读取（``errors="ignore"``）。
    纯文本读取失败时抛出 :class:`OSError`，由调用方处理。

    :param path: 文件路径
    :return: 提取的文本内容；提取器失败时返回纯文本内容
    :raises OSError: 纯文本回退读取失败
    """
    try:
        return extract_content(path)
    except Exception:
        logger.debug("提取器提取失败，回退到纯文本: %s", path, exc_info=True)
        return path.read_text(encoding="utf-8", errors="ignore")
