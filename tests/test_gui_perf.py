"""性能测量基础设施测试。

验证 ``fuscan.gui.perf`` 的零开销开关、计时记录、事件记录与嵌套缩进。
"""

from __future__ import annotations

import logging
from typing import Iterator

import pytest

from fuscan.gui import perf as perf_mod


@pytest.fixture(autouse=True)
def _restore_perf_state() -> Iterator[None]:
    """每个测试后恢复 PERF_ENABLED 默认值（False），避免相互污染。"""
    original = perf_mod._PerfState.enabled
    yield
    perf_mod._PerfState.enabled = original
    perf_mod._PerfState.depth = 0


def _collect_debug_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """过滤 fuscan.gui.perf logger 的 DEBUG 记录。"""
    return [r for r in caplog.records if r.name == "fuscan.gui.perf" and r.levelno == logging.DEBUG]


def test_perf_disabled_by_default_no_logging(caplog: pytest.LogCaptureFixture) -> None:
    """默认 PERF_ENABLED=False 时 PerfTimer 不应记录任何日志。"""
    perf_mod.set_perf_enabled(False)
    with perf_mod.PerfTimer("noop"):
        pass
    assert _collect_debug_records(caplog) == []


def test_perf_enabled_records_begin_and_end(caplog: pytest.LogCaptureFixture) -> None:
    """启用后 PerfTimer 应记录 begin 与 end 两条 DEBUG 日志。"""
    caplog.set_level(logging.DEBUG, logger="fuscan.gui.perf")
    perf_mod.set_perf_enabled(True)
    with perf_mod.PerfTimer("stage_x"):
        pass
    records = _collect_debug_records(caplog)
    assert len(records) == 2
    assert "stage_x begin" in records[0].getMessage()
    assert "stage_x" in records[1].getMessage()
    assert "ms" in records[1].getMessage()


def test_perf_threshold_filters_short_durations(caplog: pytest.LogCaptureFixture) -> None:
    """threshold_ms 大于实际耗时时应跳过 end 日志（仍记录 begin）。"""
    caplog.set_level(logging.DEBUG, logger="fuscan.gui.perf")
    perf_mod.set_perf_enabled(True)
    with perf_mod.PerfTimer("fast_op", threshold_ms=10000.0):
        pass
    records = _collect_debug_records(caplog)
    # begin 始终记录，end 因耗时 < threshold_ms 被过滤
    assert len(records) == 1
    assert "fast_op begin" in records[0].getMessage()


def test_perf_nested_indent_levels(caplog: pytest.LogCaptureFixture) -> None:
    """嵌套 PerfTimer 应通过空格缩进表达层级关系。"""
    caplog.set_level(logging.DEBUG, logger="fuscan.gui.perf")
    perf_mod.set_perf_enabled(True)
    with perf_mod.PerfTimer("outer"), perf_mod.PerfTimer("inner"):
        pass
    records = _collect_debug_records(caplog)
    # outer begin / inner begin / inner end / outer end 共 4 条
    assert len(records) == 4
    messages = [r.getMessage() for r in records]
    outer_begin = next(m for m in messages if "outer begin" in m)
    inner_begin = next(m for m in messages if "inner begin" in m)
    # outer indent="" 消息为 "[perf] > outer begin"
    assert outer_begin == "[perf] > outer begin"
    # inner indent="  " 消息为 "[perf]   > inner begin"（两个空格前缀）
    assert inner_begin == "[perf]   > inner begin"


def test_perf_record_event_disabled(caplog: pytest.LogCaptureFixture) -> None:
    """未启用时 record_event 不应记录任何日志。"""
    perf_mod.set_perf_enabled(False)
    perf_mod.record_event("evt", count=1)
    assert _collect_debug_records(caplog) == []


def test_perf_record_event_enabled_with_fields(caplog: pytest.LogCaptureFixture) -> None:
    """启用后 record_event 应记录事件名称与字段键值对。"""
    caplog.set_level(logging.DEBUG, logger="fuscan.gui.perf")
    perf_mod.set_perf_enabled(True)
    perf_mod.record_event("scan_progress", files=100, matched=5)
    records = _collect_debug_records(caplog)
    assert len(records) == 1
    message = records[0].getMessage()
    assert "scan_progress" in message
    assert "files=100" in message
    assert "matched=5" in message


def test_perf_set_perf_enabled_toggles_state() -> None:
    """set_perf_enabled 应切换 _PerfState.enabled 运行时状态。"""
    perf_mod.set_perf_enabled(True)
    assert perf_mod._PerfState.enabled is True
    perf_mod.set_perf_enabled(False)
    assert perf_mod._PerfState.enabled is False
