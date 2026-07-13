"""扫描性能基准回归测试（slow）。

验证扫描吞吐量与缓存收益的数量级正确性，阈值保守以适应 CI 性能波动。

运行方式::

    uv run pytest -m slow tests/test_benchmark.py -q
"""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest

from fuscan.cache import CacheStore
from fuscan.rules.model import LeafMatch, MatchMode, MatchTarget, Rule, RuleSet, Severity
from fuscan.scanner import Scanner

# 测试文件数（保守，兼顾 CI 速度与统计意义）
_FILE_COUNT = 500

# 敏感数据样本
_SECRETS = ("AKIAIOSFODNN7EXAMPLE", "password=secret123", "api_key=AKIAEXAMPLE1234")
_FILLER = "the quick brown fox jumps over the lazy dog\n"


def _generate_bench_files(root: Path, count: int, seed: int = 42) -> None:
    """生成混合格式测试文件，约 30% 含敏感数据。

    格式：.txt/.json/.yaml/.py/.xml/.csv/.md/.html，大小 1KB-30KB。
    """
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    formats = (".txt", ".json", ".yaml", ".py", ".xml", ".csv", ".md", ".html")
    for i in range(count):
        ext = rng.choice(formats)
        path = root / f"file_{i:05d}{ext}"
        size = rng.randint(1024, 30 * 1024)
        has_secret = rng.random() < 0.3
        lines: list[str] = []
        written = 0
        if has_secret:
            secret = rng.choice(_SECRETS)
            lines.append(f"# {secret}\n")
            written += len(secret) + 3
        while written < size:
            lines.append(_FILLER)
            written += len(_FILLER)
        path.write_text("".join(lines)[:size], encoding="utf-8")


def _content_ruleset() -> RuleSet:
    """内容规则集（触发文件读取 + 哈希计算）。"""
    return RuleSet(
        version="1.0",
        rules=(
            Rule(
                name="AWS密钥",
                severity=Severity.CRITICAL,
                match=LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="AKIA"),
            ),
            Rule(
                name="明文密码",
                severity=Severity.WARNING,
                match=LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="password"),
            ),
        ),
    )


def _filename_ruleset() -> RuleSet:
    """文件名规则集（不含 CONTENT 目标，缓存模式可跳过文件 I/O）。"""
    return RuleSet(
        version="1.0",
        rules=(
            Rule(
                name="敏感文件名",
                severity=Severity.INFO,
                match=LeafMatch(target=MatchTarget.FILENAME, mode=MatchMode.CONTAINS, pattern="file_"),
            ),
        ),
    )


@pytest.fixture()
def bench_dir(tmp_path: Path) -> Path:
    """生成 500 个混合格式测试文件。"""
    root = tmp_path / "bench"
    _generate_bench_files(root, _FILE_COUNT)
    return root


@pytest.mark.slow
class TestScanBenchmark:
    """扫描性能基准回归测试。"""

    def test_sequential_throughput(self, bench_dir: Path) -> None:
        """单线程扫描 500 文件应 ≥ 50 files/s。"""
        rs = _content_ruleset()
        scanner = Scanner(rs, max_workers=1)
        start = time.perf_counter()
        report = scanner.scan(bench_dir)
        duration = time.perf_counter() - start
        files_per_sec = report.stats.scanned_files / duration
        assert files_per_sec >= 50, f"单线程吞吐量 {files_per_sec:.1f} files/s 低于阈值 50"

    def test_concurrent_throughput(self, bench_dir: Path) -> None:
        """4 线程扫描 500 文件应 ≥ 50 files/s。"""
        rs = _content_ruleset()
        scanner = Scanner(rs, max_workers=4)
        start = time.perf_counter()
        report = scanner.scan(bench_dir)
        duration = time.perf_counter() - start
        files_per_sec = report.stats.scanned_files / duration
        assert files_per_sec >= 50, f"并发吞吐量 {files_per_sec:.1f} files/s 低于阈值 50"

    def test_cache_throughput(self, tmp_path: Path) -> None:
        """缓存命中后扫描 500 文件应 ≥ 200 files/s（filename 规则跳过文件 I/O）。"""
        root = tmp_path / "bench"
        _generate_bench_files(root, _FILE_COUNT)
        rs = _filename_ruleset()
        cache = CacheStore(tmp_path / "cache.db")
        try:
            # 首次扫描（填充缓存）
            Scanner(rs, max_workers=4, cache=cache).scan(root)
            # 二次扫描（热缓存，filename 规则跳过 I/O）
            scanner = Scanner(rs, max_workers=4, cache=cache)
            start = time.perf_counter()
            report = scanner.scan(root)
            duration = time.perf_counter() - start
            files_per_sec = report.stats.scanned_files / duration
            assert files_per_sec >= 200, f"缓存吞吐量 {files_per_sec:.1f} files/s 低于阈值 200"
        finally:
            cache.close()

    def test_cache_hit_ratio(self, tmp_path: Path) -> None:
        """二次扫描缓存命中率应 ≥ 95%。"""
        root = tmp_path / "bench"
        _generate_bench_files(root, _FILE_COUNT)
        rs = _content_ruleset()
        cache = CacheStore(tmp_path / "cache.db")
        try:
            # 首次扫描（填充缓存）
            Scanner(rs, max_workers=4, cache=cache).scan(root)
            entries_after_first = cache.stats().scan_results
            assert entries_after_first > 0, "首次扫描应写入缓存条目"
            # 二次扫描（热缓存）
            Scanner(rs, max_workers=4, cache=cache).scan(root)
            entries_after_second = cache.stats().scan_results
            # 命中率 = 1 - 新增条数 / 首次条数（新增条数 = 未命中数）
            misses = entries_after_second - entries_after_first
            hit_ratio = 1.0 - misses / entries_after_first
            assert hit_ratio >= 0.95, f"缓存命中率 {hit_ratio:.1%} 低于阈值 95%"
        finally:
            cache.close()
