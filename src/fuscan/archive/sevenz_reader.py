"""7Z 压缩文件读取器。

基于第三方库 py7zr 实现，纯 Python 无需系统工具，支持加密条目（需提供密码）。

实现要点（py7zr API 限制）：

- ``py7zr.SevenZipFile.read(targets)`` 多次调用同一 ``SevenZipFile`` 实例时，
  第二次起的 ``decompress`` 会因内部流状态污染而**死锁**（py7zr 0.22 复现）。
  因此本读取器在 ``__init__`` 中一次性 ``readall()`` 预读全部非目录条目的字节，
  缓存到 ``_bytes_cache``，后续 ``read_entry`` 直接返回缓存字节，避免重复调用 ``read``。
- 加密条目在 ``readall()`` 时若未提供密码会抛 ``PasswordRequired``，
  在 ``_preload_bytes`` 中捕获并标记为加密，``read_entry`` 时再按密码策略抛出。
- ``read_entry`` 对未在 ``_bytes_cache`` 中的条目（如目录条目）返回 ``b""``，
  保留 ``_info_map`` 用于 ``list_entries`` 的元数据查询。
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from typing_extensions import override

from fuscan.archive.base import ArchiveEntry, ArchiveError, ArchiveReader

if TYPE_CHECKING:
    import py7zr

__all__ = ["SevenZReader"]

logger = logging.getLogger(__name__)


class SevenZReader(ArchiveReader):
    """7Z 压缩包读取器。

    使用 py7zr 库读取 7z 格式（纯 Python 实现，无需系统工具）。
    加密条目需要密码；未提供密码或密码错误时跳过并记录。
    """

    def __init__(self, path: Path, password: str | None = None) -> None:
        try:
            import py7zr  # 惰性导入，避免未安装时的导入失败
        except ImportError as exc:
            raise ArchiveError("py7zr 库未安装，无法读取 7Z 文件") from exc

        self._path = path
        self._password = password
        try:
            self._sevenz: py7zr.SevenZipFile = py7zr.SevenZipFile(str(path), mode="r", password=password)
        except py7zr.Bad7zFile as exc:
            raise ArchiveError(f"损坏的 7Z 文件: {path}") from exc
        except py7zr.PasswordRequired as exc:
            raise ArchiveError(f"7Z 文件需要密码: {path}: {exc}") from exc
        except py7zr.UnsupportedCompressionMethodError as exc:
            raise ArchiveError(f"不支持的 7Z 压缩方法: {path}: {exc}") from exc
        except OSError as exc:
            raise ArchiveError(f"无法打开 7Z 文件: {path}: {exc}") from exc
        except Exception as exc:
            raise ArchiveError(f"打开 7Z 文件失败: {path}: {exc}") from exc
        # 预构建 entry_name -> FileInfo 映射
        # py7zr.SevenZipFile 无 getinfo 方法，list() 返回 List[FileInfo]
        self._info_map: dict[str, Any] = {info.filename: info for info in self._sevenz.list()}
        # 预读全部非目录条目字节并缓存，避免多次调用 read() 触发死锁
        # 加密条目未提供密码时标记到 _encrypted_entries，read_entry 时按策略抛出
        self._bytes_cache: dict[str, bytes] = {}
        self._encrypted_entries: set[str] = set()
        self._preload_bytes()

    def _preload_bytes(self) -> None:
        """预读全部非目录、非加密条目字节到 ``_bytes_cache``。

        加密条目在无密码时跳过预读，记录到 ``_encrypted_entries``；
        有密码时尝试预读，密码错误则该条目标记为加密。
        目录条目无内容，无需预读。
        """
        non_dir_entries = [
            name for name, info in self._info_map.items() if not bool(getattr(info, "is_directory", False))
        ]
        if not non_dir_entries:
            return
        try:
            import py7zr
        except ImportError as exc:  # pragma: no cover - 构造时已校验
            raise ArchiveError("py7zr 库未安装") from exc

        # 一次性 readall()，避免多次调用 read() 触发 py7zr 死锁
        try:
            data = self._sevenz.readall()
        except py7zr.PasswordRequired:
            # 整体加密的压缩包未提供密码时，全部条目标记为加密
            self._encrypted_entries.update(non_dir_entries)
            return
        except py7zr.Bad7zFile as exc:
            raise ArchiveError(f"7Z 文件损坏: {self._path}: {exc}") from exc
        except Exception as exc:
            # 其他异常（密码错误、解压失败等）降级为全部加密标记，避免阻塞扫描
            logger.warning("7Z readall 失败，全部条目降级为加密: %s: %s", self._path, exc)
            self._encrypted_entries.update(non_dir_entries)
            return

        assert data is not None  # readall 成功返回时 data 必非 None（类型收窄）
        for name, bio in data.items():
            if bio is None:
                continue
            try:
                self._bytes_cache[name] = bio.read()
            except Exception as exc:
                logger.warning("7Z 条目读取失败: %s!%s: %s", self._path, name, exc)
                self._encrypted_entries.add(name)
            finally:
                close = getattr(bio, "close", None)
                if close is not None:
                    try:
                        close()
                    except Exception:  # pragma: no cover - 关闭异常无需上报
                        logger.debug("关闭 7Z 条目流失败: %s", name, exc_info=True)

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """支持的压缩文件扩展名。"""
        return ("7z",)

    @override
    def list_entries(self) -> list[ArchiveEntry]:
        """列出压缩包内所有条目。"""
        entries: list[ArchiveEntry] = []
        for info in self._info_map.values():
            entries.append(
                ArchiveEntry(
                    archive_path=self._path,
                    entry_name=info.filename,
                    size=int(getattr(info, "uncompressed", 0) or 0),
                    compressed_size=int(getattr(info, "compressed", 0) or 0),
                    is_dir=bool(getattr(info, "is_directory", False)),
                )
            )
        return entries

    @override
    def read_entry(self, entry_name: str) -> bytes:
        """读取条目内容。

        :raises ArchiveError: 读取失败（加密、损坏、找不到条目等）
        """
        info = self._info_map.get(entry_name)
        if info is None:
            raise ArchiveError(f"7Z 条目不存在: {entry_name}")
        if bool(getattr(info, "is_directory", False)):
            return b""
        # 加密条目未提供密码时抛 ArchiveError
        if entry_name in self._encrypted_entries and self._password is None:
            logger.info("7Z 条目加密且未提供密码，跳过: %s!%s", self._path, entry_name)
            raise ArchiveError(f"加密条目未提供密码: {entry_name}")
        # 命中预读缓存直接返回
        cached = self._bytes_cache.get(entry_name)
        if cached is not None:
            return cached
        # 缓存缺失：预读阶段被跳过（加密、损坏等），按加密处理
        if entry_name in self._encrypted_entries:
            raise ArchiveError(f"加密条目读取失败（密码错误或解压失败）: {entry_name}")
        return b""

    def close(self) -> None:
        """关闭 7Z 文件句柄。"""
        try:
            self._sevenz.close()
        except Exception:  # pragma: no cover - 关闭异常无需上报
            logger.debug("关闭 7Z 文件句柄失败: %s", self._path, exc_info=True)
        # 释放字节缓存，避免长期持有大块内存
        self._bytes_cache.clear()

    def __enter__(self) -> SevenZReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
