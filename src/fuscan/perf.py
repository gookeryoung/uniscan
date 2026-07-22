"""性能测量基础设施（GUI 与扫描器共用）。

提供两类工具：

- :class:`PerfTimer`：单阶段上下文计时器，用于 GUI 卡滞定位
- :class:`PerfStats`：线程安全的聚合统计，用于扫描器分阶段瓶颈分析

启用方式：
- :class:`PerfStats` **始终启用**（iter-66 起）：仅做聚合统计（无日志输出），
  开销约 1-2μs/次，对扫描性能影响 < 0.3%。扫描结果通过 :meth:`PerfStats.to_dict`
  导出，填入 :attr:`ScanStats.perf_summary` 供 GUI/CLI 展示与持久化。
- :class:`PerfTimer` / :func:`record_event` 需 ``FUSCAN_PERF=1`` 或 CLI ``--perf``
  启用：输出详细 DEBUG 日志，适合定向卡滞定位，不适合日常使用。

设计要点：
- :class:`PerfStats` 始终记录：``measure`` 仅 ``perf_counter`` + Lock，无 enabled 检查
- :class:`PerfTimer` 默认零开销：未启用时仅一次 bool 检查 + yield
- 上下文管理器：``with PerfTimer("stage"): ...`` 自动记录进入/退出时间
- 嵌套支持：``PerfTimer`` 通过 ``logger.debug`` 输出层级缩进，便于阅读
- 聚合统计：``PerfStats`` 累计各阶段总耗时/调用次数/最大值，扫描结束时
  :meth:`PerfStats.report` 输出汇总，便于一眼定位瓶颈
- 持久化：:meth:`PerfStats.save_to_json` 将统计写入 JSON 文件供后续分析

公共 API：
- :data:`PERF_ENABLED`：PerfTimer 详细日志开关（模块加载时快照，运行时切换用 :func:`set_perf_enabled`）
- :class:`PerfTimer`：上下文管理器计时器（单阶段，需启用）
- :class:`PerfStats`：聚合统计计时器（多阶段累计，始终启用）
- :func:`record_event`：记录离散事件（需启用）
- :func:`set_perf_enabled`：运行时切换 PerfTimer 开关
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

__all__ = ["PERF_ENABLED", "PerfStats", "PerfTimer", "record_event", "set_perf_enabled"]

logger = logging.getLogger(__name__)


class _PerfState:
    """PerfTimer 详细日志运行时可变状态。

    用类属性封装可变状态，避免 ``global`` 声明（PLW0603）。
    仅供模块内部使用，外部通过 :data:`PERF_ENABLED` 与 :func:`set_perf_enabled` 间接访问。

    注意：iter-66 起 ``enabled`` 仅控制 :class:`PerfTimer` / :func:`record_event`
    的详细日志输出。:class:`PerfStats` 始终启用，不受此开关影响。
    """

    enabled: bool = os.environ.get("FUSCAN_PERF", "") == "1"
    # 嵌套层级跟踪（线程局部可避免并发干扰，但 GUI 主线程单线程足够）
    depth: int = 0


# 性能测量总开关：模块加载时快照（只读视图），运行时切换请用 set_perf_enabled
PERF_ENABLED: bool = _PerfState.enabled


def set_perf_enabled(enabled: bool) -> None:
    """运行时切换性能测量开关（测试用）。

    :param enabled: True 开启计时记录，False 关闭
    """
    _PerfState.enabled = enabled


@contextmanager
def PerfTimer(name: str, *, threshold_ms: float = 0.0) -> Iterator[None]:
    """计时上下文管理器：记录代码块耗时。

    未启用时（``_PerfState.enabled=False``）直接 yield 不做任何记录，保证零开销。
    启用后通过 ``logger.debug`` 输出形如 ``[perf] > stage_name 12.3ms`` 的日志，
    嵌套层级通过缩进前缀表达。

    :param name: 代码块名称（如 ``MainWindow.__init__``）
    :param threshold_ms: 仅当耗时超过该阈值（毫秒）时记录，默认 0 总是记录
    """
    if not _PerfState.enabled:
        yield
        return
    start = time.perf_counter()
    _PerfState.depth += 1
    indent = "  " * (_PerfState.depth - 1)
    logger.debug("[perf] %s> %s begin", indent, name)
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000.0
        _PerfState.depth -= 1
        if elapsed >= threshold_ms:
            logger.debug("[perf] %s< %s %.1fms", indent, name, elapsed)


def record_event(name: str, **fields: object) -> None:
    """记录离散事件及其关联字段（如计数、状态）。

    与 :class:`PerfTimer` 不同，本函数记录瞬时事件而非代码块耗时，
    适用于"扫描进度回调触发 N 次"等计数场景。

    :param name: 事件名称
    :param fields: 附加字段，以 ``key=value`` 形式记录到日志
    """
    if not _PerfState.enabled:
        return
    pairs = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.debug("[perf] event %s %s", name, pairs)


class _StageStats:
    """单阶段聚合统计（内部使用，``__slots__`` 降低内存开销）。"""

    __slots__ = ("count", "max_val", "total")

    def __init__(self) -> None:
        self.total: float = 0.0
        self.count: int = 0
        self.max_val: float = 0.0


class PerfStats:
    """线程安全的性能聚合统计。

    累计各阶段总耗时、调用次数与最大单次耗时，扫描结束时通过
    :meth:`report` 输出汇总，便于一眼定位瓶颈阶段。

    iter-66 起始终启用（仅聚合统计，无日志输出），开销约 1-2μs/次
    （``perf_counter`` + Lock），对 171 files/s 的扫描影响 < 0.3%。
    :class:`PerfTimer` 的详细日志仍需 ``FUSCAN_PERF=1`` 启用。

    用法：

    >>> stats = PerfStats()
    >>> with stats.measure("read_bytes"):
    ...     data = path.read_bytes()
    >>> stats.report(logger)
    >>> stats.save_to_json(Path("perf.json"))

    线程安全：所有写入操作经 ``threading.Lock`` 保护，可在多 worker
    线程下并发调用 :meth:`measure` / :meth:`record`。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stages: dict[str, _StageStats] = {}

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        """计时上下文：累计阶段耗时。始终记录（iter-66 起）。

        :param name: 阶段名称（如 ``read_bytes`` / ``hash`` / ``match``）
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._record_locked(name, elapsed)

    def record(self, name: str, elapsed: float) -> None:
        """直接记录一段耗时（非上下文模式）。始终记录（iter-66 起）。

        适用于无法用 ``with`` 包裹的阶段（如回调内手动计时）。

        :param name: 阶段名称
        :param elapsed: 已测得的耗时（秒）
        """
        self._record_locked(name, elapsed)

    def _record_locked(self, name: str, elapsed: float) -> None:
        """在锁保护下累计阶段统计。"""
        with self._lock:
            stage = self._stages.get(name)
            if stage is None:
                stage = _StageStats()
                self._stages[name] = stage
            stage.total += elapsed
            stage.count += 1
            stage.max_val = max(stage.max_val, elapsed)

    def report(self, log: logging.Logger) -> None:
        """输出汇总日志到 DEBUG 级别。无数据时不输出。

        按总耗时降序排列，便于一眼定位热点阶段。

        :param log: 接收汇总日志的 logger（通常为 ``logging.getLogger(__name__)``）
        """
        if not self._stages:
            return
        with self._lock:
            items = sorted(self._stages.items(), key=lambda x: -x[1].total)
        log.debug("[perf] === 性能汇总 ===")
        for name, stage in items:
            avg_ms = (stage.total / stage.count * 1000.0) if stage.count else 0.0
            log.debug(
                "[perf] %-24s 总计 %8.1fms  调用 %6d 次  平均 %7.2fms  最大 %8.1fms",
                name,
                stage.total * 1000.0,
                stage.count,
                avg_ms,
                stage.max_val * 1000.0,
            )

    def reset(self) -> None:
        """清空所有阶段统计（用于 Scanner 复用时重置上下文）。"""
        with self._lock:
            self._stages.clear()

    def to_dict(self) -> dict[str, dict[str, float]]:
        """导出各阶段统计为可序列化字典。

        格式：``{stage_name: {"total_ms": float, "count": int, "max_ms": float}}``

        :return: 各阶段统计字典（总耗时降序），可直接 json.dumps
        """
        with self._lock:
            items = sorted(self._stages.items(), key=lambda x: -x[1].total)
        return {
            name: {
                "total_ms": round(stage.total * 1000.0, 3),
                "count": stage.count,
                "max_ms": round(stage.max_val * 1000.0, 3),
            }
            for name, stage in items
        }

    def merge_dict(self, data: dict[str, dict[str, float]]) -> None:
        """合并外部字典数据到当前实例（用于多根路径扫描累计）。

        接受 :meth:`to_dict` 输出格式的字典，累加 total/count，取 max。
        线程安全。

        :param data: :meth:`to_dict` 输出格式的字典
        """
        with self._lock:
            for name, info in data.items():
                stage = self._stages.get(name)
                if stage is None:
                    stage = _StageStats()
                    self._stages[name] = stage
                stage.total += info.get("total_ms", 0.0) / 1000.0
                stage.count += int(info.get("count", 0))
                stage.max_val = max(stage.max_val, info.get("max_ms", 0.0) / 1000.0)

    def summary_text(self, top: int = 3) -> str:
        """返回简要文本摘要（供 GUI 状态栏展示）。

        格式：``read 69% | extract 43% | match 18%``（按总耗时占比降序，取前 N 个）

        :param top: 返回前 N 个热点阶段，默认 3
        :return: 简要文本；无数据时返回空字符串
        """
        with self._lock:
            if not self._stages:
                return ""
            items = sorted(self._stages.items(), key=lambda x: -x[1].total)
        grand_total = sum(s.total for _, s in items) or 1.0
        parts = [f"{name} {s.total / grand_total * 100:.0f}%" for name, s in items[:top]]
        return " | ".join(parts)

    def save_to_json(self, path: Path, *, meta: dict[str, object] | None = None) -> None:
        """持久化统计到 JSON 文件。

        写入格式包含时间戳、可选元信息与各阶段统计，供后续分析对比。

        :param path: 目标 JSON 文件路径（父目录自动创建）
        :param meta: 附加元信息（如文件数、耗时），写入 ``meta`` 字段
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "stages": self.to_dict(),
            "meta": meta or {},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
