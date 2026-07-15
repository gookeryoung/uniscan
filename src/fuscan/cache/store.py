"""SQLite 持久化扫描结果缓存。

公共 API：

- :class:`CacheStore`：线程安全的 SQLite 缓存，封装规则登记、结果查询、清理等操作
- :class:`CacheStats`：缓存统计快照（不可变）

设计要点：

- 单连接 + ``threading.RLock``：所有读写经锁序列化，``check_same_thread=False`` 允许跨线程使用
- WAL 模式：读不阻塞写，提升并发扫描吞吐
- 缓存键为 ``(file_hash, rule_hash)``：路径无关，规则变更感知
- ``scanned_files`` 表以内容哈希为主键，``file_paths`` 表登记多个路径引用
- **进程内 LRU 命中缓存**：``get_cached_hits`` 结果在内存中再缓存一份，
  热点文件（如 node_modules 中重复依赖）查询次数大幅降低；``put_result``
  / ``register_file`` 等写入操作自动 invalidate 对应 ``file_hash`` 条目
- **路径预筛**：``lookup_file_hash`` 按 ``(path, mtime, size)`` 查询
  ``file_paths`` 索引，未修改文件可跳过 ``read_bytes`` 与哈希计算
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Collection, Mapping

from fuscan.cache.hashes import compute_rule_hash, hash_bytes, serialize_rule
from fuscan.cache.schema import CURRENT_VERSION, migrate
from fuscan.rules.model import Rule, RuleSet, Severity
from fuscan.scanner.result import RuleHit

__all__ = ["CacheStats", "CacheStore", "default_cache_path"]

logger = logging.getLogger(__name__)

# 进程内 LRU 命中缓存容量上限（条目数）。
# 每条平均 ~1KB（含 rule_hash 元组与 RuleHit），4096 条约占 4MB 内存。
_HIT_CACHE_MAX: int = 4096


def default_cache_path() -> Path:
    """返回默认缓存路径：``~/.fuscan/cache.db``。"""
    return Path.home() / ".fuscan" / "cache.db"


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串（含时区后缀 ``Z``）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class CacheStats:
    """缓存统计快照（不可变）。"""

    rule_files: int = 0
    rules: int = 0
    scanned_files: int = 0
    file_paths: int = 0
    scan_results: int = 0
    db_bytes: int = 0
    schema_version: int = 0


class CacheStore:
    """线程安全的 SQLite 扫描结果缓存。

    使用方式：

    1. 构造时打开/创建数据库，自动迁移 schema
    2. ``register_ruleset()`` 登记当前规则集与来源文件
    3. 扫描每个文件时：
       - 算 ``file_hash``
       - ``get_cached_hits()`` 批量查询
       - 命中的规则直接复用 ``RuleHit``
       - 未命中的规则扫描后调 ``put_result()`` 写入
       - ``register_file()`` / ``register_path()`` 更新元数据
    4. 可选 ``prune_orphan_rules()`` / ``prune_stale_files()`` 清理
    5. ``close()`` 释放连接

    所有公共方法线程安全（``RLock`` 串行化）。
    """

    def __init__(self, db_path: Path) -> None:
        """打开或创建缓存数据库。

        :param db_path: SQLite 文件路径；父目录自动创建
        """
        self._db_path: Path = db_path
        self._lock: threading.RLock = threading.RLock()
        # 进程内 LRU 命中缓存：file_hash -> (rule_hashes_tuple, result_dict)
        # 用 OrderedDict 实现 LRU 语义：访问时 move_to_end，超容量时 popitem(last=False)
        self._hit_cache: OrderedDict[str, tuple[tuple[str, ...], dict[str, RuleHit | None]]] = OrderedDict()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False 允许跨线程使用连接，所有访问经 RLock 序列化
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            isolation_level=None,  # 自动提交模式，事务显式管理
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库：启用 WAL、外键，迁移 schema。"""
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            version = migrate(self._conn)
            logger.debug("缓存数据库已就绪: %s, schema_version=%d", self._db_path, version)

    @property
    def db_path(self) -> Path:
        """缓存数据库文件路径。"""
        return self._db_path

    @property
    def schema_version(self) -> int:
        """当前 schema 版本号。"""
        with self._lock:
            row = self._conn.execute("PRAGMA user_version").fetchone()
            return int(row[0]) if row else 0

    # ------------------------------------------------------------------ 内存 LRU

    def _hit_cache_get(
        self,
        file_hash: str,
        rule_hashes: Collection[str],
    ) -> dict[str, RuleHit | None] | None:
        """查询进程内 LRU 命中缓存（已持锁）。

        命中条件：``file_hash`` 与 ``rule_hashes`` 集合完全一致（顺序无关）。
        命中时移动到队尾（LRU），返回缓存的字典；未命中返回 None。
        """
        key = (file_hash, tuple(sorted(rule_hashes)))
        cached = self._hit_cache.get(file_hash)
        if cached is None:
            return None
        cached_rule_keys, cached_dict = cached
        if cached_rule_keys != key[1]:
            # rule_hashes 集合变化：视为未命中（如新增了规则）
            return None
        # LRU：移到队尾
        self._hit_cache.move_to_end(file_hash)
        return dict(cached_dict)  # 返回副本，避免外部修改污染缓存

    def _hit_cache_put(
        self,
        file_hash: str,
        rule_hashes: Collection[str],
        result: dict[str, RuleHit | None],
    ) -> None:
        """写入进程内 LRU 命中缓存（已持锁）。

        超容量时弹出最旧条目。
        """
        self._hit_cache[file_hash] = (tuple(sorted(rule_hashes)), dict(result))
        self._hit_cache.move_to_end(file_hash)
        while len(self._hit_cache) > _HIT_CACHE_MAX:
            self._hit_cache.popitem(last=False)

    def _hit_cache_invalidate(self, file_hash: str) -> None:
        """失效指定 ``file_hash`` 的内存缓存条目（已持锁）。

        ``put_result`` / ``register_file`` / ``register_path`` 写入后调用，
        确保下次查询走 SQLite 取最新数据。
        """
        self._hit_cache.pop(file_hash, None)

    def hit_cache_size(self) -> int:
        """返回进程内 LRU 命中缓存当前条目数（诊断用）。"""
        with self._lock:
            return len(self._hit_cache)

    # ------------------------------------------------------------------ 规则登记

    def register_ruleset(
        self,
        ruleset: RuleSet,
        source_files: Mapping[Path, str] | None = None,
    ) -> dict[str, str]:
        """登记规则集到缓存：算规则哈希，写入 ``rules``/``rule_files``/``rule_file_members``。

        相同规则的哈希跨文件去重，``rule_file_members`` 维护多对多关系。
        旧的 ``rule_file_members`` 关系在重新登记时被该文件的当前规则集替换。

        :param ruleset: 规则集
        :param source_files: 规则文件路径 → 文件 SHA-256 映射；
            为空时按"匿名来源"登记（``__inline__`` 虚拟文件）
        :return: ``rule_name -> rule_hash`` 映射，供 Scanner 复用
        """
        with self._lock:
            now = _now_iso()
            sources: dict[Path, str] = dict(source_files) if source_files else {}
            # 默认虚拟来源，避免无 source_files 时规则无处归属
            if not sources:
                sources = {Path("__inline__"): hash_bytes(b"")}

            # 收集 (rule_name -> rule_hash)，重名规则以最后一条为准
            rule_hashes: dict[str, str] = {}
            for rule in ruleset.rules:
                rhash = compute_rule_hash(rule)
                rule_hashes[rule.name] = rhash
                self._upsert_rule(rule, rhash)

            # 登记规则文件与成员关系
            for file_path, file_hash in sources.items():
                path_str = str(file_path)
                try:
                    mtime = file_path.stat().st_mtime if file_path.exists() else 0.0
                except OSError:
                    mtime = 0.0
                self._conn.execute(
                    "INSERT INTO rule_files (file_path, file_hash, mtime, loaded_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(file_path) DO UPDATE SET "
                    "  file_hash = excluded.file_hash, "
                    "  mtime = excluded.mtime, "
                    "  loaded_at = excluded.loaded_at",
                    (path_str, file_hash, mtime, now),
                )
                # 替换该文件下的成员关系（先删后插）
                self._conn.execute(
                    "DELETE FROM rule_file_members WHERE file_path = ?",
                    (path_str,),
                )
                for rule in ruleset.rules:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO rule_file_members (file_path, rule_hash) VALUES (?, ?)",
                        (path_str, rule_hashes[rule.name]),
                    )
            return rule_hashes

    def _upsert_rule(self, rule: Rule, rule_hash: str) -> None:
        """写入或更新单条规则（按 rule_hash 去重）。"""
        serialized = serialize_rule(rule)
        self._conn.execute(
            "INSERT INTO rules (rule_hash, rule_name, severity, description, serialized) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(rule_hash) DO UPDATE SET "
            "  rule_name = excluded.rule_name, "
            "  severity = excluded.severity, "
            "  description = excluded.description, "
            "  serialized = excluded.serialized",
            (rule_hash, rule.name, rule.severity.value, rule.description, serialized),
        )

    def get_rule_hashes(self) -> dict[str, str]:
        """查询当前已登记的 ``rule_name -> rule_hash`` 映射。

        重名规则以最后登记的为准（与 ``register_ruleset`` 行为一致）。
        """
        with self._lock:
            rows = self._conn.execute("SELECT rule_name, rule_hash FROM rules").fetchall()
            return {row["rule_name"]: row["rule_hash"] for row in rows}

    # ------------------------------------------------------------------ 结果缓存

    def get_cached_hits(
        self,
        file_hash: str,
        rule_hashes: Collection[str],
    ) -> dict[str, RuleHit | None]:
        """批量查询缓存结果。

        优先命中进程内 LRU 缓存；未命中走 SQLite 查询，结果写回 LRU。

        :param file_hash: 被扫描文件内容哈希
        :param rule_hashes: 待查询的规则哈希集合
        :return: ``rule_hash -> RuleHit | None`` 映射；
            值为 ``RuleHit`` 表示该规则命中且已缓存；
            值为 ``None`` 表示该规则未命中且已缓存（避免重复扫描未命中）；
            不在返回字典中的 ``rule_hash`` 表示未缓存，需扫描。
        """
        if not rule_hashes:
            return {}
        with self._lock:
            # 先查进程内 LRU
            cached = self._hit_cache_get(file_hash, rule_hashes)
            if cached is not None:
                return cached

            placeholders = ",".join("?" for _ in rule_hashes)
            params: tuple[Any, ...] = (file_hash, *rule_hashes)
            rows = self._conn.execute(
                f"SELECT rule_hash, matched, severity, detail, match_text, "
                f"       match_count, target FROM scan_results "
                f"WHERE file_hash = ? AND rule_hash IN ({placeholders})",
                params,
            ).fetchall()
            result: dict[str, RuleHit | None] = {}
            for row in rows:
                if row["matched"]:
                    severity = Severity(row["severity"]) if row["severity"] else Severity.INFO
                    result[row["rule_hash"]] = RuleHit(
                        rule_name="",  # 调用方按 rule_hash 反查 name，避免冗余存储
                        severity=severity,
                        detail=row["detail"] or "",
                        match_text=row["match_text"] or "",
                        match_count=row["match_count"],
                        target=row["target"] or "",
                    )
                else:
                    result[row["rule_hash"]] = None
            # 写回 LRU
            self._hit_cache_put(file_hash, rule_hashes, result)
            return result

    def put_result(
        self,
        file_hash: str,
        rule_hash: str,
        hit: RuleHit | None,
    ) -> None:
        """写入单条缓存结果。

        仅写入 ``scan_results``；文件元数据（``scanned_files``/``file_paths``）请由调用方
        通过 :meth:`register_file` 与 :meth:`register_path` 单独登记，避免单次调用承担过多职责。

        写入后失效对应 ``file_hash`` 的进程内 LRU 条目，下次查询走 SQLite 取最新数据。

        :param file_hash: 文件内容哈希
        :param rule_hash: 规则哈希
        :param hit: ``RuleHit`` 表示命中；``None`` 表示该规则对该文件未命中（也缓存，避免重复扫描）
        """
        now = _now_iso()
        with self._lock:
            # 确保 scanned_files 中存在该 file_hash，避免外键约束失败；
            # size 未知时用 0 占位，调用方可通过 register_file() 更新真实 size。
            self._conn.execute(
                "INSERT OR IGNORE INTO scanned_files "
                "(file_hash, size, first_seen_at, last_scanned_at) VALUES (?, 0, ?, ?)",
                (file_hash, now, now),
            )
            if hit is None:
                self._conn.execute(
                    "INSERT INTO scan_results "
                    "(file_hash, rule_hash, matched, severity, detail, match_text, "
                    " match_count, target, cached_at) "
                    "VALUES (?, ?, 0, NULL, NULL, NULL, 0, '', ?) "
                    "ON CONFLICT(file_hash, rule_hash) DO UPDATE SET "
                    "  matched = 0, severity = NULL, detail = NULL, match_text = NULL, "
                    "  match_count = 0, target = '', cached_at = excluded.cached_at",
                    (file_hash, rule_hash, now),
                )
            else:
                self._conn.execute(
                    "INSERT INTO scan_results "
                    "(file_hash, rule_hash, matched, severity, detail, match_text, "
                    " match_count, target, cached_at) "
                    "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(file_hash, rule_hash) DO UPDATE SET "
                    "  matched = 1, severity = excluded.severity, detail = excluded.detail, "
                    "  match_text = excluded.match_text, match_count = excluded.match_count, "
                    "  target = excluded.target, cached_at = excluded.cached_at",
                    (
                        file_hash,
                        rule_hash,
                        hit.severity.value,
                        hit.detail,
                        hit.match_text,
                        hit.match_count,
                        hit.target,
                        now,
                    ),
                )
            # 失效 LRU 条目：调用方下次查询时会从 SQLite 取最新数据并回填 LRU
            self._hit_cache_invalidate(file_hash)

    def _register_file_locked(self, file_hash: str, size: int, now: str) -> None:
        """登记文件哈希到 ``scanned_files``（已持锁）。

        ``put_result`` 会用 ``size=0`` 占位插入以满足外键约束；
        本方法用真实 size 覆盖占位值（仅在 size > 0 时更新，避免覆盖已登记的真实值）。
        """
        self._conn.execute(
            "INSERT INTO scanned_files (file_hash, size, first_seen_at, last_scanned_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(file_hash) DO UPDATE SET "
            "  size = CASE WHEN excluded.size > 0 THEN excluded.size ELSE scanned_files.size END, "
            "  last_scanned_at = excluded.last_scanned_at",
            (file_hash, size, now, now),
        )

    def _register_path_locked(self, file_hash: str, path: Path, mtime: float, now: str) -> None:
        """登记文件路径到 ``file_paths``（已持锁）。"""
        self._conn.execute(
            "INSERT INTO file_paths (file_hash, path, mtime, last_seen_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(file_hash, path) DO UPDATE SET "
            "  mtime = excluded.mtime, last_seen_at = excluded.last_seen_at",
            (file_hash, str(path), mtime, now),
        )

    def register_file(self, file_hash: str, size: int) -> None:
        """登记/更新 ``scanned_files`` 的 ``last_scanned_at``。

        写入后失效对应 ``file_hash`` 的进程内 LRU 条目。
        """
        with self._lock:
            now = _now_iso()
            self._register_file_locked(file_hash, size, now)
            self._hit_cache_invalidate(file_hash)

    def register_path(self, file_hash: str, path: Path, mtime: float) -> None:
        """登记/更新 ``file_paths``。

        写入后失效对应 ``file_hash`` 的进程内 LRU 条目。
        """
        with self._lock:
            now = _now_iso()
            self._register_path_locked(file_hash, path, mtime, now)
            self._hit_cache_invalidate(file_hash)

    def lookup_file_hash(
        self,
        path: Path,
        mtime: float,
        size: int,
    ) -> str | None:
        """按 ``(path, mtime, size)`` 查询已登记的 ``file_hash``。

        用于缓存模式预筛：文件 mtime 与 size 未变时，
        可直接复用已登记的 ``file_hash``，跳过 ``read_bytes`` 与哈希计算。

        安全性说明：mtime 可被人为修改，本方法仅作为性能优化；
        对安全性敏感场景，调用方可关闭此预筛（始终走哈希校验）。

        :param path: 文件路径
        :param mtime: 当前文件 mtime（秒，浮点）
        :param size: 当前文件大小（字节）
        :return: 命中时返回 ``file_hash``（64 字符 hex）；未命中返回 None
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT file_hash FROM file_paths "
                "WHERE path = ? AND mtime = ? AND file_hash IN ("
                "  SELECT file_hash FROM scanned_files WHERE size = ?"
                ")",
                (str(path), mtime, size),
            ).fetchone()
            return row["file_hash"] if row else None

    # ------------------------------------------------------------------ 清理与统计

    def prune_orphan_rules(self, active_rule_hashes: Collection[str]) -> int:
        """清理不在当前规则集中的旧规则及其缓存。

        清理后失效全部进程内 LRU 条目（规则哈希集合已变）。

        :param active_rule_hashes: 当前活跃的规则哈希集合
        :return: 删除的规则数（``rules`` 表行数）
        """
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM rules").fetchone()
            before = cur[0] if cur else 0
            if active_rule_hashes:
                placeholders = ",".join("?" for _ in active_rule_hashes)
                self._conn.execute(
                    f"DELETE FROM rules WHERE rule_hash NOT IN ({placeholders})",
                    tuple(active_rule_hashes),
                )
            else:
                self._conn.execute("DELETE FROM rules")
            cur = self._conn.execute("SELECT COUNT(*) FROM rules").fetchone()
            after = cur[0] if cur else 0
            deleted = before - after
            if deleted > 0:
                logger.info("清理孤立规则: %d 条", deleted)
                # 规则集合变化：全部 LRU 条目可能引用了已删除规则，整体失效
                self._hit_cache.clear()
            return deleted

    def prune_stale_files(self, max_age_days: int = 30) -> int:
        """清理 ``last_scanned_at`` 早于 ``max_age_days`` 天的文件缓存。

        清理后失效全部进程内 LRU 条目。

        :param max_age_days: 最大保留天数
        :return: 删除的文件数（``scanned_files`` 表行数）
        """
        if max_age_days < 0:
            raise ValueError("max_age_days 不能为负数")
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM scanned_files").fetchone()
            before = cur[0] if cur else 0
            self._conn.execute(
                "DELETE FROM scanned_files WHERE last_scanned_at < ?",
                (_iso_days_ago(max_age_days),),
            )
            cur = self._conn.execute("SELECT COUNT(*) FROM scanned_files").fetchone()
            after = cur[0] if cur else 0
            deleted = before - after
            if deleted > 0:
                logger.info("清理过期文件缓存: %d 条（>=%d 天）", deleted, max_age_days)
                self._hit_cache.clear()
            return deleted

    def stats(self) -> CacheStats:
        """返回缓存统计快照。"""
        with self._lock:
            rule_files = self._count("rule_files")
            rules = self._count("rules")
            scanned_files = self._count("scanned_files")
            file_paths = self._count("file_paths")
            scan_results = self._count("scan_results")
            db_bytes = self._db_path.stat().st_size if self._db_path.exists() else 0
            return CacheStats(
                rule_files=rule_files,
                rules=rules,
                scanned_files=scanned_files,
                file_paths=file_paths,
                scan_results=scan_results,
                db_bytes=db_bytes,
                schema_version=CURRENT_VERSION,
            )

    def _count(self, table: str) -> int:
        """统计表行数（已持锁）。"""
        # table 名来自代码常量，非用户输入，无 SQL 注入风险
        cur = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return cur[0] if cur else 0

    # ------------------------------------------------------------------ 资源管理

    def close(self) -> None:
        """关闭数据库连接。"""
        with self._lock:
            self._hit_cache.clear()
            self._conn.close()

    def __enter__(self) -> CacheStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def _iso_days_ago(days: int) -> str:
    """返回 ``days`` 天前的 UTC ISO 时间字符串。"""
    from datetime import timedelta

    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
