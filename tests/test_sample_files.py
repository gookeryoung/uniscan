"""典型文件示例功能测试。

验证 benchmarks/sample_files.py 生成的各格式文件能被正确提取，
且 ``password`` 关键词能被扫描器命中。

覆盖纯文本（txt/json/yaml/xml/csv/md/html）与二进制（rtf/docx/xlsx/pptx/eml）格式。
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from benchmarks.sample_files import BINARY_GENERATORS, GENERATORS, TEXT_GENERATORS, generate_file
from fuscan.extractors import extract_content
from fuscan.rules.model import LeafMatch, MatchMode, MatchTarget, Rule, RuleSet, Severity
from fuscan.scanner import Scanner

# 所有可生成的格式
_ALL_FORMATS = sorted(GENERATORS.keys())
_TEXT_FORMATS = sorted(TEXT_GENERATORS.keys())
_BINARY_FORMATS = sorted(BINARY_GENERATORS.keys())


def _make_ruleset() -> RuleSet:
    """构建扫描 password 关键词的规则集。"""
    return RuleSet(
        version="1.0",
        rules=(
            Rule(
                name="明文密码",
                severity=Severity.WARNING,
                match=LeafMatch(target=MatchTarget.CONTENT, mode=MatchMode.CONTAINS, pattern="password"),
            ),
        ),
    )


@pytest.fixture()
def rng() -> random.Random:
    return random.Random(42)


class TestSampleFileExtraction:
    """验证每种格式的示例文件能被提取且包含 password。"""

    @pytest.mark.parametrize("ext", _ALL_FORMATS)
    def test_extract_contains_password(self, tmp_path: Path, ext: str, rng: random.Random) -> None:
        """每种格式的示例文件提取后应包含 password 关键词。"""
        path = tmp_path / f"sample.{ext}"
        generate_file(path, ext, size_hint=4096, rng=rng)
        content = extract_content(path)
        assert "password" in content, f"格式 {ext} 提取结果未包含 password: {content[:200]}"

    @pytest.mark.parametrize("ext", _TEXT_FORMATS)
    def test_text_format_extract_contains_filler(self, tmp_path: Path, ext: str, rng: random.Random) -> None:
        """纯文本格式应保留填充文本。"""
        path = tmp_path / f"sample.{ext}"
        generate_file(path, ext, size_hint=4096, rng=rng)
        content = extract_content(path)
        assert "quick brown fox" in content

    @pytest.mark.parametrize("ext", _BINARY_FORMATS)
    def test_binary_format_extract_not_empty(self, tmp_path: Path, ext: str, rng: random.Random) -> None:
        """二进制格式提取结果不应为空。"""
        path = tmp_path / f"sample.{ext}"
        generate_file(path, ext, size_hint=4096, rng=rng)
        content = extract_content(path)
        assert len(content) > 0, f"格式 {ext} 提取结果为空"


class TestSampleFileScan:
    """验证扫描器能命中示例文件中的 password。"""

    @pytest.mark.parametrize("ext", _ALL_FORMATS)
    def test_scan_finds_password(self, tmp_path: Path, ext: str, rng: random.Random) -> None:
        """扫描器应命中每种格式示例文件中的 password。"""
        path = tmp_path / f"sample.{ext}"
        generate_file(path, ext, size_hint=4096, rng=rng)
        scanner = Scanner(_make_ruleset(), max_workers=1)
        result = scanner.scan_file(path)
        assert result.has_hit, f"格式 {ext} 未被扫描命中 password"
        assert any(hit.rule_name == "明文密码" for hit in result.hits)

    @pytest.mark.slow
    def test_scan_mixed_format_directory(self, tmp_path: Path, rng: random.Random) -> None:
        """扫描混合格式目录应命中所有含 password 的文件。"""
        from benchmarks.sample_files import generate_files

        root = tmp_path / "mixed"
        generate_files(root, count=30, seed=42)
        scanner = Scanner(_make_ruleset(), max_workers=4)
        report = scanner.scan(root)
        assert report.stats.scanned_files == 30
        assert report.stats.matched_files > 0


class TestSampleFileGeneration:
    """验证示例文件生成器本身的行为。"""

    def test_generate_file_unsupported_format(self, tmp_path: Path) -> None:
        """不支持的格式应抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持的格式"):
            generate_file(tmp_path / "bad.xyz", "xyz")

    def test_generate_files_creates_all(self, tmp_path: Path) -> None:
        """generate_files 应创建指定数量的文件。"""
        from benchmarks.sample_files import generate_files

        root = tmp_path / "batch"
        paths = generate_files(root, count=10, seed=123)
        assert len(paths) == 10
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0

    @pytest.mark.slow
    def test_generate_files_reproducible(self, tmp_path: Path) -> None:
        """相同种子应生成相同文件名序列。"""
        from benchmarks.sample_files import generate_files

        root1 = tmp_path / "r1"
        root2 = tmp_path / "r2"
        paths1 = generate_files(root1, count=10, seed=42)
        paths2 = generate_files(root2, count=10, seed=42)
        assert [p.name for p in paths1] == [p.name for p in paths2]

    def test_binary_formats_are_binary(self, tmp_path: Path, rng: random.Random) -> None:
        """ZIP 类二进制格式（docx/xlsx/pptx）生成的文件应包含非 ASCII 字节。

        RTF 和 EML 虽归入"二进制生成器"类别（需库生成），但内容本身是纯文本。
        """
        zip_exts = ("docx", "xlsx", "pptx")
        for ext in zip_exts:
            path = tmp_path / f"sample.{ext}"
            generate_file(path, ext, size_hint=2048, rng=rng)
            data = path.read_bytes()
            assert any(b > 127 for b in data), f"格式 {ext} 文件应包含二进制内容"
