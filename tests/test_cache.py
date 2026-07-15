"""缓存模块单元测试。

覆盖：

- :mod:`fuscan.cache.hashes`：规则/匹配的稳定序列化与哈希计算
- :mod:`fuscan.cache.store`：SQLite CRUD、清理、统计、并发
- 路径无关性、规则变更触发重扫等核心需求
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from fuscan.cache import (
    CacheStats,
    CacheStore,
    compute_file_hash,
    compute_rule_hash,
    default_cache_path,
    hash_bytes,
    serialize_match,
    serialize_rule,
)
from fuscan.cache.schema import CURRENT_VERSION, migrate
from fuscan.rules.model import (
    AndMatch,
    LeafMatch,
    MatchMode,
    MatchTarget,
    NotMatch,
    OrMatch,
    Rule,
    RuleSet,
    Severity,
)
from fuscan.scanner.result import RuleHit

# ---------------------------------------------------------------- 哈希与序列化


def _filename_rule(name: str = "r1", pattern: str = "secret") -> Rule:
    return Rule(
        name=name,
        match=LeafMatch(
            target=MatchTarget.FILENAME,
            mode=MatchMode.CONTAINS,
            pattern=pattern,
        ),
    )


def _content_rule(name: str = "r2", pattern: str = "password") -> Rule:
    return Rule(
        name=name,
        severity=Severity.CRITICAL,
        match=LeafMatch(
            target=MatchTarget.CONTENT,
            mode=MatchMode.REGEX,
            pattern=pattern,
            case_sensitive=True,
        ),
    )


def _and_rule(name: str = "r3") -> Rule:
    return Rule(
        name=name,
        match=AndMatch(
            children=(
                LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="conf"),
                LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="db"),
            )
        ),
    )


def _or_rule(name: str = "r4") -> Rule:
    return Rule(
        name=name,
        match=OrMatch(
            children=(
                LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="a"),
                LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="b"),
            )
        ),
    )


def _not_rule(name: str = "r5") -> Rule:
    return Rule(
        name=name,
        match=NotMatch(child=LeafMatch(target=MatchTarget.PATH, mode=MatchMode.CONTAINS, pattern="backup")),
    )


class TestSerializeMatch:
    def test_serialize_leaf(self) -> None:
        m = LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="x")
        data = serialize_match(m)
        assert data["type"] == "leaf"
        assert data["target"] == "filename"
        assert data["mode"] == "contains"
        assert data["pattern"] == "x"
        assert data["case_sensitive"] is False

    def test_serialize_and(self) -> None:
        m = _and_rule().match
        data = serialize_match(m)
        assert data["type"] == "and"
        assert len(data["children"]) == 2
        assert all(isinstance(c, dict) for c in data["children"])

    def test_serialize_or(self) -> None:
        data = serialize_match(_or_rule().match)
        assert data["type"] == "or"
        assert len(data["children"]) == 2

    def test_serialize_not(self) -> None:
        data = serialize_match(_not_rule().match)
        assert data["type"] == "not"
        assert "child" in data
        assert data["child"]["target"] == "path"

    def test_serialize_unknown_match_raises(self) -> None:
        """未知匹配类型触发防御性 TypeError。"""
        with pytest.raises(TypeError, match="未知匹配类型"):
            serialize_match("not-a-match")  # type: ignore[arg-type]

    def test_serialize_with_extensions(self) -> None:
        rule = Rule(
            name="ext",
            match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.EQUALS, pattern="x"),
            file_extensions=("txt", "md"),
        )
        data = json.loads(serialize_rule(rule))
        # file_extensions 排序后序列化，保证顺序无关
        assert data["file_extensions"] == ["md", "txt"]
        # 整体键排序
        assert list(data.keys()) == sorted(data.keys())

    def test_serialize_extensions_order_independent(self) -> None:
        """扩展名顺序不同但内容相同 → 哈希相同。"""
        r1 = Rule(
            name="r",
            match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.EQUALS, pattern="x"),
            file_extensions=("txt", "md"),
        )
        r2 = Rule(
            name="r",
            match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.EQUALS, pattern="x"),
            file_extensions=("md", "txt"),
        )
        assert compute_rule_hash(r1) == compute_rule_hash(r2)


class TestRuleHashCompute:
    def test_same_rule_same_hash(self) -> None:
        r1 = _filename_rule()
        r2 = _filename_rule()
        assert compute_rule_hash(r1) == compute_rule_hash(r2)
        assert len(compute_rule_hash(r1)) == 64

    def test_different_rule_different_hash(self) -> None:
        r1 = _filename_rule(pattern="secret")
        r2 = _filename_rule(pattern="password")
        assert compute_rule_hash(r1) != compute_rule_hash(r2)

    def test_case_sensitive_affects_hash(self) -> None:
        r1 = Rule(
            name="r",
            match=LeafMatch(
                target=MatchTarget.CONTENT,
                mode=MatchMode.CONTAINS,
                pattern="x",
                case_sensitive=False,
            ),
        )
        r2 = Rule(
            name="r",
            match=LeafMatch(
                target=MatchTarget.CONTENT,
                mode=MatchMode.CONTAINS,
                pattern="x",
                case_sensitive=True,
            ),
        )
        assert compute_rule_hash(r1) != compute_rule_hash(r2)

    def test_severity_affects_hash(self) -> None:
        r1 = Rule(
            name="r",
            severity=Severity.INFO,
            match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="x"),
        )
        r2 = Rule(
            name="r",
            severity=Severity.CRITICAL,
            match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="x"),
        )
        assert compute_rule_hash(r1) != compute_rule_hash(r2)

    def test_composite_match_hash_stable(self) -> None:
        r1 = _and_rule()
        r2 = _and_rule()
        assert compute_rule_hash(r1) == compute_rule_hash(r2)

    def test_rule_hash_is_sha256_hex(self) -> None:
        h = compute_rule_hash(_filename_rule())
        # BLAKE2b digest_size=32 输出 64 字符 hex（与 SHA-256 长度一致）
        assert len(h) == 64
        # 全部为十六进制字符
        int(h, 16)

    def test_serialize_rule_is_valid_json(self) -> None:
        s = serialize_rule(_filename_rule())
        data = json.loads(s)
        assert data["name"] == "r1"
        assert "match" in data

    def test_hash_bytes_empty(self) -> None:
        # 空字节返回固定摘要（BLAKE2b digest_size=32）
        assert hash_bytes(b"") == hashlib.blake2b(b"", digest_size=32).hexdigest()

    def test_compute_file_hash(self, tmp_path: Path) -> None:
        p = tmp_path / "a.txt"
        p.write_bytes(b"hello")
        assert compute_file_hash(p) == hashlib.blake2b(b"hello", digest_size=32).hexdigest()

    def test_compute_file_hash_missing(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            compute_file_hash(tmp_path / "missing.txt")


# ---------------------------------------------------------------- CacheStore 初始化


class TestCacheStoreInit:
    def test_init_creates_schema(self, tmp_path: Path) -> None:
        db = tmp_path / "cache.db"
        store = CacheStore(db)
        assert db.exists()
        assert store.schema_version == CURRENT_VERSION
        store.close()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        db = tmp_path / "cache.db"
        store1 = CacheStore(db)
        store1.register_ruleset(RuleSet(version="1.0", rules=(_filename_rule(),)))
        store1.close()
        # 二次打开不应报错，schema 与数据保留
        store2 = CacheStore(db)
        assert store2.schema_version == CURRENT_VERSION
        hashes = store2.get_rule_hashes()
        assert "r1" in hashes
        store2.close()

    def test_migration_creates_tables(self, tmp_path: Path) -> None:
        db = tmp_path / "cache.db"
        store = CacheStore(db)
        # 通过 stats 验证表已创建（COUNT 查询不抛异常即说明表存在）
        stats = store.stats()
        assert stats.rule_files == 0
        assert stats.rules == 0
        store.close()

    def test_default_cache_path_under_home(self) -> None:
        p = default_cache_path()
        assert p.parent == Path.home() / ".fuscan"
        assert p.name == "cache.db"

    def test_context_manager(self, tmp_path: Path) -> None:
        """with 语句自动关闭连接。"""
        db = tmp_path / "cache.db"
        with CacheStore(db) as store:
            store.register_ruleset(RuleSet(version="1.0", rules=(_filename_rule(),)))
            assert store.stats().rules == 1
        # 退出后连接已关闭，后续操作应抛异常
        with pytest.raises(sqlite3.ProgrammingError):
            store.stats()

    def test_db_path_property(self, tmp_path: Path) -> None:
        db = tmp_path / "cache.db"
        store = CacheStore(db)
        assert store.db_path == db
        store.close()


# ---------------------------------------------------------------- 规则登记


class TestCacheStoreRuleset:
    def test_register_ruleset_returns_hashes(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        assert set(hashes.keys()) == {"r1", "r2"}
        assert len(hashes["r1"]) == 64
        store.close()

    def test_register_ruleset_with_source_files(self, tmp_path: Path) -> None:
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("dummy", encoding="utf-8")
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        file_hash = hash_bytes(b"dummy")
        store.register_ruleset(rs, source_files={rules_file: file_hash})
        stats = store.stats()
        assert stats.rule_files == 1
        assert stats.rules == 1
        store.close()

    def test_register_ruleset_stat_oserror_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """source_files 中的路径 stat() 抛 OSError 时回退到 mtime=0。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))

        def raise_oserror(self: Path) -> float:
            raise OSError("simulated")

        # 仅对真实存在的路径触发；__inline__ 路径走 exists() False 分支
        rules_file = tmp_path / "rules.yaml"
        rules_file.write_text("x", encoding="utf-8")
        monkeypatch.setattr(Path, "stat", raise_oserror)
        store.register_ruleset(rs, source_files={rules_file: hash_bytes(b"x")})
        # 登记成功，mtime=0（OSError 回退）
        store.close()

    def test_register_ruleset_inline_when_no_sources(self, tmp_path: Path) -> None:
        """无 source_files 时使用 __inline__ 虚拟来源。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        store.register_ruleset(rs)
        # 默认虚拟来源登记，rules 表有规则
        stats = store.stats()
        assert stats.rules == 1
        store.close()

    def test_register_ruleset_dedup_rules(self, tmp_path: Path) -> None:
        """同一规则被两个文件载入时，rules 表只存一份。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        store.register_ruleset(
            rs,
            source_files={
                Path("a.yaml"): hash_bytes(b"a"),
                Path("b.yaml"): hash_bytes(b"b"),
            },
        )
        stats = store.stats()
        assert stats.rule_files == 2
        assert stats.rules == 1  # 同一规则去重
        store.close()

    def test_register_ruleset_update_file_hash(self, tmp_path: Path) -> None:
        """规则文件哈希变化后再次登记，rule_files 表更新而非新增。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        fpath = Path("rules.yaml")
        store.register_ruleset(rs, source_files={fpath: hash_bytes(b"v1")})
        store.register_ruleset(rs, source_files={fpath: hash_bytes(b"v2")})
        stats = store.stats()
        assert stats.rule_files == 1  # 同一文件不重复
        store.close()

    def test_get_rule_hashes_after_register(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        store.register_ruleset(rs)
        hashes = store.get_rule_hashes()
        assert hashes["r1"] == compute_rule_hash(_filename_rule())
        assert hashes["r2"] == compute_rule_hash(_content_rule())
        store.close()


# ---------------------------------------------------------------- 结果缓存


class TestCacheStoreResults:
    def test_put_and_get_hit(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        file_hash = hash_bytes(b"file-content")
        hit = RuleHit(
            rule_name="r1",
            severity=Severity.WARNING,
            detail="命中 secret",
            match_text="secret",
            match_count=2,
            target="filename",
        )
        store.put_result(file_hash, rule_hash, hit)
        cached = store.get_cached_hits(file_hash, [rule_hash])
        assert rule_hash in cached
        result = cached[rule_hash]
        assert result is not None
        assert result.detail == "命中 secret"
        assert result.match_count == 2
        assert result.match_text == "secret"
        assert result.target == "filename"
        store.close()

    def test_put_and_get_miss(self, tmp_path: Path) -> None:
        """规则未命中也缓存（值为 None），避免重复扫描未命中。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        file_hash = hash_bytes(b"no-hit-content")
        store.put_result(file_hash, rule_hash, None)
        cached = store.get_cached_hits(file_hash, [rule_hash])
        assert cached[rule_hash] is None
        store.close()

    def test_get_cached_hits_empty_query(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        result = store.get_cached_hits("abc", [])
        assert result == {}
        store.close()

    def test_get_cached_hits_partial_miss(self, tmp_path: Path) -> None:
        """部分规则已缓存，部分未缓存：未缓存的不在返回字典中。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        file_hash = hash_bytes(b"content")
        # 仅写 r1 的结果
        store.put_result(
            file_hash,
            hashes["r1"],
            RuleHit(rule_name="r1", severity=Severity.WARNING, detail="d"),
        )
        cached = store.get_cached_hits(file_hash, [hashes["r1"], hashes["r2"]])
        assert hashes["r1"] in cached
        assert hashes["r2"] not in cached  # 未缓存
        store.close()

    def test_path_change_still_hits(self, tmp_path: Path) -> None:
        """核心需求：路径变化后缓存仍命中（按 file_hash 查询，与路径无关）。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        # 同一内容，两个不同路径
        file_hash = hash_bytes(b"same-content")
        path1 = Path("/old/location/file.txt")
        path2 = Path("/new/location/file_moved.txt")
        hit = RuleHit(rule_name="r1", severity=Severity.WARNING, detail="d")
        store.put_result(file_hash, rule_hash, hit)
        store.register_file(file_hash, 100)
        store.register_path(file_hash, path1, 1000.0)
        store.register_path(file_hash, path2, 2000.0)
        # 路径变化后查询，仍命中
        cached = store.get_cached_hits(file_hash, [rule_hash])
        assert cached[rule_hash] is not None
        store.close()

    def test_rule_change_triggers_rescan(self, tmp_path: Path) -> None:
        """规则变更：旧 rule_hash 的缓存不会被新 rule_hash 命中。"""
        store = CacheStore(tmp_path / "cache.db")
        old_rule = _filename_rule(pattern="old")
        rs_old = RuleSet(version="1.0", rules=(old_rule,))
        hashes_old = store.register_ruleset(rs_old)
        file_hash = hash_bytes(b"content")
        store.put_result(
            file_hash,
            hashes_old["r1"],
            RuleHit(rule_name="r1", severity=Severity.WARNING, detail="old"),
        )
        # 新规则（pattern 不同 → hash 不同）
        new_rule = _filename_rule(pattern="new")
        rs_new = RuleSet(version="1.0", rules=(new_rule,))
        hashes_new = store.register_ruleset(rs_new)
        assert hashes_old["r1"] != hashes_new["r1"]
        # 新规则查询应未命中（不在缓存中）
        cached = store.get_cached_hits(file_hash, [hashes_new["r1"]])
        assert hashes_new["r1"] not in cached
        store.close()

    def test_put_result_overwrites(self, tmp_path: Path) -> None:
        """同一 (file_hash, rule_hash) 二次写入应覆盖。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        file_hash = hash_bytes(b"c")
        store.put_result(
            file_hash,
            rule_hash,
            RuleHit(rule_name="r1", severity=Severity.INFO, detail="first"),
        )
        store.put_result(
            file_hash,
            rule_hash,
            RuleHit(rule_name="r1", severity=Severity.CRITICAL, detail="second"),
        )
        cached = store.get_cached_hits(file_hash, [rule_hash])
        assert cached[rule_hash].detail == "second"
        assert cached[rule_hash].severity == Severity.CRITICAL
        store.close()


# ---------------------------------------------------------------- 文件登记


class TestCacheStoreFileRegistration:
    def test_register_file_updates_timestamp(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 100)
        stats = store.stats()
        assert stats.scanned_files == 1
        store.close()

    def test_register_file_idempotent(self, tmp_path: Path) -> None:
        """同一 file_hash 二次登记不新增行。"""
        store = CacheStore(tmp_path / "cache.db")
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 100)
        store.register_file(file_hash, 200)  # size 不同也不新增
        stats = store.stats()
        assert stats.scanned_files == 1
        store.close()

    def test_register_path_multiple_paths(self, tmp_path: Path) -> None:
        """同一 file_hash 可对应多个路径。"""
        store = CacheStore(tmp_path / "cache.db")
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 100)
        store.register_path(file_hash, Path("/a.txt"), 1.0)
        store.register_path(file_hash, Path("/b.txt"), 2.0)
        stats = store.stats()
        assert stats.file_paths == 2
        assert stats.scanned_files == 1
        store.close()

    def test_register_path_without_file_fails_fk(self, tmp_path: Path) -> None:
        """未登记 scanned_files 直接登记路径，外键约束应阻止。"""
        store = CacheStore(tmp_path / "cache.db")
        file_hash = hash_bytes(b"missing")
        with pytest.raises(sqlite3.IntegrityError):
            store.register_path(file_hash, Path("/x.txt"), 1.0)
        store.close()


# ---------------------------------------------------------------- 清理


class TestCacheStorePrune:
    def test_prune_orphan_rules(self, tmp_path: Path) -> None:
        """清理不在活跃集合中的旧规则。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        # 旧规则全部不再活跃
        deleted = store.prune_orphan_rules({hashes["r1"]})
        assert deleted == 1
        stats = store.stats()
        assert stats.rules == 1
        store.close()

    def test_prune_orphan_rules_keeps_active(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        deleted = store.prune_orphan_rules(set(hashes.values()))
        assert deleted == 0
        store.close()

    def test_prune_orphan_rules_empty_active(self, tmp_path: Path) -> None:
        """空活跃集合 → 全部规则被清理。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        store.register_ruleset(rs)
        deleted = store.prune_orphan_rules(set())
        assert deleted == 2
        assert store.stats().rules == 0
        store.close()

    def test_prune_orphan_rules_cascade_results(self, tmp_path: Path) -> None:
        """清理规则时，关联的 scan_results 也被级联删除。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 1)
        store.put_result(
            file_hash,
            hashes["r1"],
            RuleHit(rule_name="r1", severity=Severity.WARNING, detail="d"),
        )
        store.put_result(
            file_hash,
            hashes["r2"],
            RuleHit(rule_name="r2", severity=Severity.CRITICAL, detail="d"),
        )
        # 删除 r2
        store.prune_orphan_rules({hashes["r1"]})
        cached = store.get_cached_hits(file_hash, [hashes["r1"], hashes["r2"]])
        assert hashes["r1"] in cached
        assert hashes["r2"] not in cached
        store.close()

    def test_prune_stale_files(self, tmp_path: Path) -> None:
        """清理过期文件缓存（last_scanned_at 早于阈值）。"""
        store = CacheStore(tmp_path / "cache.db")
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 100)
        # 模拟一年前扫描

        conn = store._conn  # 测试访问私有属性以模拟过期场景
        old = "2020-01-01T00:00:00Z"
        conn.execute(
            "UPDATE scanned_files SET last_scanned_at = ? WHERE file_hash = ?",
            (old, file_hash),
        )
        deleted = store.prune_stale_files(max_age_days=30)
        assert deleted == 1
        stats = store.stats()
        assert stats.scanned_files == 0
        store.close()

    def test_prune_stale_files_keeps_recent(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        store.register_file(hash_bytes(b"c"), 100)
        deleted = store.prune_stale_files(max_age_days=30)
        assert deleted == 0
        store.close()

    def test_prune_stale_files_invalid_arg(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        with pytest.raises(ValueError):
            store.prune_stale_files(max_age_days=-1)
        store.close()


# ---------------------------------------------------------------- 统计


class TestCacheStoreStats:
    def test_stats_empty(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        stats = store.stats()
        assert isinstance(stats, CacheStats)
        assert stats.rule_files == 0
        assert stats.rules == 0
        assert stats.scanned_files == 0
        assert stats.scan_results == 0
        assert stats.schema_version == CURRENT_VERSION
        assert stats.db_bytes > 0  # 空库也有字节
        store.close()

    def test_stats_counts(self, tmp_path: Path) -> None:
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(), _content_rule()))
        hashes = store.register_ruleset(rs)
        file_hash = hash_bytes(b"c")
        store.register_file(file_hash, 100)
        store.register_path(file_hash, Path("/x.txt"), 1.0)
        store.put_result(
            file_hash,
            hashes["r1"],
            RuleHit(rule_name="r1", severity=Severity.WARNING, detail="d"),
        )
        stats = store.stats()
        assert stats.rules == 2
        assert stats.scanned_files == 1
        assert stats.file_paths == 1
        assert stats.scan_results == 1
        store.close()

    def test_stats_db_missing_returns_zero_bytes(self, tmp_path: Path) -> None:
        """db_path 不存在时 db_bytes 为 0。"""
        store = CacheStore(tmp_path / "cache.db")
        store._db_path = tmp_path / "nonexistent.db"  # 测试访问私有属性模拟路径丢失
        stats = store.stats()
        assert stats.db_bytes == 0
        store.close()


# ---------------------------------------------------------------- 并发


class TestCacheStoreConcurrency:
    def test_concurrent_writes(self, tmp_path: Path) -> None:
        """多线程并发写入不同 file_hash 不冲突。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        errors: list[Exception] = []

        def writer(idx: int) -> None:
            try:
                fh = hash_bytes(f"content-{idx}".encode())
                store.register_file(fh, idx)
                store.put_result(
                    fh,
                    rule_hash,
                    RuleHit(rule_name="r1", severity=Severity.WARNING, detail=f"d-{idx}"),
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        stats = store.stats()
        assert stats.scanned_files == 20
        assert stats.scan_results == 20
        store.close()

    def test_concurrent_read_write(self, tmp_path: Path) -> None:
        """读+写并发：读不阻塞写，且读到的是一致状态。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        stop = threading.Event()
        errors: list[Exception] = []

        def reader() -> None:
            try:
                while not stop.is_set():
                    store.stats()
            except Exception as exc:
                errors.append(exc)

        def writer() -> None:
            try:
                for i in range(50):
                    fh = hash_bytes(f"c-{i}".encode())
                    store.register_file(fh, i)
                    store.put_result(
                        fh,
                        rule_hash,
                        RuleHit(rule_name="r1", severity=Severity.WARNING, detail=f"d-{i}"),
                    )
            except Exception as exc:
                errors.append(exc)
            stop.set()

        # 给 CacheStore 加一个批量查询辅助方法用于测试
        reader_t = threading.Thread(target=reader)
        writer_t = threading.Thread(target=writer)
        writer_t.start()
        reader_t.start()
        writer_t.join()
        reader_t.join(timeout=2)
        assert not errors
        store.close()

    def test_concurrent_same_file_hash(self, tmp_path: Path) -> None:
        """多线程同时写同一 (file_hash, rule_hash)：最后一个胜出，不抛异常。"""
        store = CacheStore(tmp_path / "cache.db")
        rs = RuleSet(version="1.0", rules=(_filename_rule(),))
        hashes = store.register_ruleset(rs)
        rule_hash = hashes["r1"]
        fh = hash_bytes(b"shared")
        store.register_file(fh, 0)
        errors: list[Exception] = []

        def writer(idx: int) -> None:
            try:
                store.put_result(
                    fh,
                    rule_hash,
                    RuleHit(rule_name="r1", severity=Severity.WARNING, detail=f"d-{idx}"),
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        cached = store.get_cached_hits(fh, [rule_hash])
        assert cached[rule_hash] is not None
        store.close()


# ---------------------------------------------------------------- migrate


class TestMigrate:
    def test_migrate_fresh_db(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(str(tmp_path / "fresh.db"))
        conn.row_factory = sqlite3.Row
        version = migrate(conn)
        assert version == CURRENT_VERSION
        # 二次调用幂等
        assert migrate(conn) == CURRENT_VERSION
        conn.close()

    def test_migrate_already_up_to_date(self, tmp_path: Path) -> None:
        conn = sqlite3.connect(str(tmp_path / "u.db"))
        conn.row_factory = sqlite3.Row
        migrate(conn)
        # 第二次迁移应直接返回当前版本
        version = migrate(conn)
        assert version == CURRENT_VERSION
        conn.close()


class TestCacheCompatVersion:
    """缓存数据兼容版本号管理（iter-38）。"""

    def test_fresh_db_writes_compat_version(self, tmp_path: Path) -> None:
        """新建数据库应写入当前 CACHE_COMPAT_VERSION 到 meta 表。"""
        from fuscan.cache.schema import CACHE_COMPAT_VERSION

        conn = sqlite3.connect(str(tmp_path / "fresh.db"))
        conn.row_factory = sqlite3.Row
        migrate(conn)
        row = conn.execute("SELECT value FROM meta WHERE key = 'cache_compat_version'").fetchone()
        assert row is not None
        assert int(row["value"]) == CACHE_COMPAT_VERSION
        conn.close()

    def test_old_compat_version_triggers_purge(self, tmp_path: Path) -> None:
        """兼容版本号低于当前值时清空旧业务表数据。"""
        db = tmp_path / "old.db"
        # 先用旧 schema + 旧 compat 版本号建库
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('cache_compat_version', '1')")
        conn.execute("CREATE TABLE scanned_files (file_hash TEXT PRIMARY KEY, size INTEGER)")
        conn.execute("INSERT INTO scanned_files VALUES ('oldhash', 100)")
        conn.commit()

        # 触发迁移：应清空 scanned_files
        from fuscan.cache.schema import CACHE_COMPAT_VERSION

        assert CACHE_COMPAT_VERSION >= 2  # 当前为 2，旧库 v1 应被清空
        migrate(conn)
        # 旧数据应被清空
        rows = conn.execute("SELECT * FROM scanned_files").fetchall()
        assert len(rows) == 0
        # meta 中 compat 版本应已升级
        row = conn.execute("SELECT value FROM meta WHERE key = 'cache_compat_version'").fetchone()
        assert int(row["value"]) == CACHE_COMPAT_VERSION
        conn.close()

    def test_future_compat_version_triggers_purge(self, tmp_path: Path) -> None:
        """兼容版本号高于当前代码时，保守清空未来版本数据。"""
        db = tmp_path / "future.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        # 写入未来版本号（远超当前值）
        conn.execute("INSERT INTO meta (key, value) VALUES ('cache_compat_version', '999')")
        conn.execute("CREATE TABLE scanned_files (file_hash TEXT PRIMARY KEY, size INTEGER)")
        conn.execute("INSERT INTO scanned_files VALUES ('futurehash', 200)")
        conn.commit()

        migrate(conn)
        # 未来数据应被清空
        rows = conn.execute("SELECT * FROM scanned_files").fetchall()
        assert len(rows) == 0
        conn.close()

    def test_corrupted_compat_version_triggers_purge(self, tmp_path: Path) -> None:
        """meta 中 compat 版本号损坏（非数字）时清空缓存。"""
        db = tmp_path / "corrupt.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO meta (key, value) VALUES ('cache_compat_version', 'not-a-number')")
        conn.execute("CREATE TABLE scanned_files (file_hash TEXT PRIMARY KEY, size INTEGER)")
        conn.execute("INSERT INTO scanned_files VALUES ('x', 1)")
        conn.commit()

        migrate(conn)
        rows = conn.execute("SELECT * FROM scanned_files").fetchall()
        assert len(rows) == 0
        conn.close()

    def test_same_compat_version_preserves_data(self, tmp_path: Path) -> None:
        """兼容版本号一致时不触发清空。"""

        db = tmp_path / "same.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        # 模拟一个已迁移到当前版本的库，含真实数据
        migrate(conn)
        file_hash = hash_bytes(b"keep-me")
        conn.execute(
            "INSERT INTO scanned_files (file_hash, size, first_seen_at, last_scanned_at) "
            "VALUES (?, 42, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (file_hash,),
        )
        conn.commit()

        # 再次 migrate（模拟下次启动）
        migrate(conn)
        # 数据应保留
        row = conn.execute("SELECT size FROM scanned_files WHERE file_hash = ?", (file_hash,)).fetchone()
        assert row is not None
        assert row["size"] == 42
        conn.close()


class TestHitCache:
    """进程内 LRU 命中缓存（iter-38）。"""

    @staticmethod
    def _setup_store_with_rule(tmp_path: Path, rule_name: str = "r1") -> tuple[CacheStore, str]:
        """构造已登记单条规则的 CacheStore，返回 (store, rule_hash)。"""
        from fuscan.rules.model import LeafMatch, MatchMode, MatchTarget, Rule, RuleSet, Severity

        rule = Rule(
            name=rule_name,
            description="d",
            severity=Severity.WARNING,
            match=LeafMatch(
                target=MatchTarget.CONTENT,
                mode=MatchMode.CONTAINS,
                pattern="x",
                case_sensitive=False,
            ),
            file_extensions=(),
        )
        rs = RuleSet(version="1.0", rules=(rule,))
        store = CacheStore(tmp_path / "c.db")
        hashes = store.register_ruleset(rs)
        return store, hashes[rule_name]

    def test_get_cached_hits_writes_to_lru(self, tmp_path: Path) -> None:
        """首次查询走 SQLite 后写入 LRU，第二次同参数命中 LRU。"""
        store, rule_hash = self._setup_store_with_rule(tmp_path)
        try:
            file_hash = hash_bytes(b"content")
            store.put_result(file_hash, rule_hash, None)
            assert store.hit_cache_size() == 0  # put 后 invalidate

            # 首次查询：走 SQLite
            r1 = store.get_cached_hits(file_hash, [rule_hash])
            assert rule_hash in r1
            assert store.hit_cache_size() == 1
            # 第二次查询：命中 LRU
            r2 = store.get_cached_hits(file_hash, [rule_hash])
            assert r2 == r1
        finally:
            store.close()

    def test_put_result_invalidates_lru(self, tmp_path: Path) -> None:
        """put_result 后下次查询走 SQLite 取最新数据。"""
        store, rule_hash = self._setup_store_with_rule(tmp_path)
        try:
            file_hash = hash_bytes(b"c")
            # 首次未命中也缓存
            store.put_result(file_hash, rule_hash, None)
            store.get_cached_hits(file_hash, [rule_hash])  # 填充 LRU
            assert store.hit_cache_size() == 1

            # 写入命中结果
            from fuscan.rules.model import Severity
            from fuscan.scanner.result import RuleHit

            hit = RuleHit(
                rule_name="r",
                severity=Severity.WARNING,
                detail="d",
                match_text="t",
                match_count=1,
                target="content",
            )
            store.put_result(file_hash, rule_hash, hit)
            assert store.hit_cache_size() == 0  # 已 invalidate

            # 下次查询应取到 hit，而非缓存的 None
            r = store.get_cached_hits(file_hash, [rule_hash])
            assert r[rule_hash] is not None
            assert r[rule_hash].severity == Severity.WARNING
        finally:
            store.close()

    def test_lru_evicts_oldest_when_full(self, tmp_path: Path) -> None:
        """LRU 容量超限时弹出最旧条目。"""
        from fuscan.cache import store as store_mod

        store, rule_hash = self._setup_store_with_rule(tmp_path)
        try:
            # 临时缩小容量以便测试
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(store_mod, "_HIT_CACHE_MAX", 3)
                for i in range(5):
                    fh = hash_bytes(f"content-{i}".encode())
                    store.put_result(fh, rule_hash, None)
                    store.get_cached_hits(fh, [rule_hash])  # 填充 LRU
                # 应只剩最近 3 个
                assert store.hit_cache_size() == 3
        finally:
            store.close()

    def test_rule_hashes_set_change_treats_as_miss(self, tmp_path: Path) -> None:
        """rule_hashes 集合变化时 LRU 视为未命中，走 SQLite。"""
        # 登记 2 条规则，得到 rh1 / rh2
        from fuscan.rules.model import LeafMatch, MatchMode, MatchTarget, Rule, RuleSet, Severity

        rules = [
            Rule(
                name=f"r{i}",
                description="d",
                severity=Severity.WARNING,
                match=LeafMatch(
                    target=MatchTarget.CONTENT,
                    mode=MatchMode.CONTAINS,
                    pattern="x",
                    case_sensitive=False,
                ),
                file_extensions=(),
            )
            for i in (1, 2)
        ]
        rs = RuleSet(version="1.0", rules=tuple(rules))
        store = CacheStore(tmp_path / "c.db")
        try:
            hashes = store.register_ruleset(rs)
            rh1, rh2 = hashes["r1"], hashes["r2"]

            file_hash = hash_bytes(b"c")
            store.put_result(file_hash, rh1, None)
            store.get_cached_hits(file_hash, [rh1])  # LRU 用 (rh1) 填充

            # 加入 rh2 后 LRU 仍记录 (rh1) 集合，应判定未命中
            store.put_result(file_hash, rh2, None)
            r = store.get_cached_hits(file_hash, [rh1, rh2])
            # 应同时返回 rh1 和 rh2 的结果（来自 SQLite 重查）
            assert rh1 in r
            assert rh2 in r
        finally:
            store.close()

    def test_prune_clears_lru(self, tmp_path: Path) -> None:
        """清理孤立规则后 LRU 整体失效（规则集合已变）。"""
        store, rule_hash = self._setup_store_with_rule(tmp_path)
        try:
            file_hash = hash_bytes(b"c")
            store.put_result(file_hash, rule_hash, None)
            store.get_cached_hits(file_hash, [rule_hash])
            assert store.hit_cache_size() == 1

            # 传入空集合：触发"删除所有规则"分支，deleted > 0，LRU 应被清空
            store.prune_orphan_rules(set())
            assert store.hit_cache_size() == 0
        finally:
            store.close()


class TestLookupFileHash:
    """mtime 预筛：lookup_file_hash（iter-38）。"""

    def test_lookup_returns_hash_when_path_mtime_size_match(self, tmp_path: Path) -> None:
        """(path, mtime, size) 三元组完全匹配时返回已登记的 file_hash。"""
        with CacheStore(tmp_path / "c.db") as store:
            file_hash = hash_bytes(b"content")
            path = tmp_path / "file.txt"
            path.write_bytes(b"content")
            st = path.stat()
            store.register_file(file_hash, st.st_size)
            store.register_path(file_hash, path, st.st_mtime)

            found = store.lookup_file_hash(path, st.st_mtime, st.st_size)
            assert found == file_hash

    def test_lookup_returns_none_when_mtime_differs(self, tmp_path: Path) -> None:
        """mtime 不匹配时返回 None（文件已修改，需重算哈希）。"""
        with CacheStore(tmp_path / "c.db") as store:
            file_hash = hash_bytes(b"content")
            path = tmp_path / "file.txt"
            path.write_bytes(b"content")
            st = path.stat()
            store.register_file(file_hash, st.st_size)
            store.register_path(file_hash, path, st.st_mtime)

            # 模拟文件被修改：mtime + 100s
            assert store.lookup_file_hash(path, st.st_mtime + 100, st.st_size) is None

    def test_lookup_returns_none_when_size_differs(self, tmp_path: Path) -> None:
        """size 不匹配时返回 None。"""
        with CacheStore(tmp_path / "c.db") as store:
            file_hash = hash_bytes(b"content")
            path = tmp_path / "file.txt"
            path.write_bytes(b"content")
            st = path.stat()
            store.register_file(file_hash, st.st_size)
            store.register_path(file_hash, path, st.st_mtime)

            assert store.lookup_file_hash(path, st.st_mtime, st.st_size + 1) is None

    def test_lookup_returns_none_when_path_unknown(self, tmp_path: Path) -> None:
        """未登记的路径返回 None。"""
        with CacheStore(tmp_path / "c.db") as store:
            assert store.lookup_file_hash(tmp_path / "unknown", 0.0, 0) is None

    def test_lookup_handles_multiple_paths_same_hash(self, tmp_path: Path) -> None:
        """同一 file_hash 关联多个路径时，每个路径都能查到。"""
        with CacheStore(tmp_path / "c.db") as store:
            file_hash = hash_bytes(b"shared-content")
            p1 = tmp_path / "a.txt"
            p2 = tmp_path / "b.txt"
            p1.write_bytes(b"shared-content")
            p2.write_bytes(b"shared-content")
            st1 = p1.stat()
            st2 = p2.stat()
            store.register_file(file_hash, st1.st_size)
            store.register_path(file_hash, p1, st1.st_mtime)
            store.register_path(file_hash, p2, st2.st_mtime)

            assert store.lookup_file_hash(p1, st1.st_mtime, st1.st_size) == file_hash
            assert store.lookup_file_hash(p2, st2.st_mtime, st2.st_size) == file_hash
