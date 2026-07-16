# iter-47：代码质量审查修复

## 需求清单

- [x] 1. 修复 python-code-reviewer 审查发现的 Critical 级问题（C1、C2）
- [x] 2. 修复审查发现的 Important 级问题（I2、I3、I4、I5、I6、I9）
- [x] 3. 修复审查发现的 Suggested 级问题（S7）
- [x] 4. 修复 C1 配套的 worker.py was_cancelled 判断逻辑
- [x] 5. 为所有修复补充回归测试，覆盖率不低于基线 96.05%

## 迭代目标

基于 python-code-reviewer 对核心模块（scanner、cache、walker、worker）的自动审查报告，
修复全部 Critical 与 Important 级缺陷，补充 Suggested 级修复，并为每项修复添加回归测试，
确保全门禁（ruff/pyrefly/pytest/coverage）通过且覆盖率不下降。

## 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/fuscan/scanner/scanner.py` | C1+I4+I6 | scan() 控制状态管理重设计、try/finally 异常路径 flush、deque 无界增长防护 |
| `src/fuscan/cache/hashes.py` | C2 | serialize_match 为所有 MatchSpec 类型补充 description 字段 |
| `src/fuscan/cache/schema.py` | C2 配套 | CACHE_COMPAT_VERSION 从 4 递增到 5 |
| `src/fuscan/scanner/walker.py` | I2+I3 | OSError 捕获补 logger.debug、符号链接环路检测 |
| `src/fuscan/cache/store.py` | I5+I9+S7 | ROLLBACK 失败保护、__init__ 连接泄漏防护、close() 幂等 |
| `src/fuscan/gui/worker.py` | C1 配套 | was_cancelled 改用 report.cancelled 而非 self._scanner.is_cancelled |
| `tests/test_scanner.py` | 测试 | C1 回归测试（取消后可复用）+ I6 适配（deque 比较） |
| `tests/test_walker.py` | 测试 | I3 符号链接环路检测测试（5 个用例） |
| `tests/test_cache.py` | 测试 | C2 serialize_match description 测试（6 个）+ I5 ROLLBACK 失败测试 + I9 连接泄漏测试 + S7 close 幂等测试（2 个） |

## 关键决策与依据

### C1：Scanner 取消后不可复用

- **问题**：scan() 在 finally 中不清除 _cancel_event，导致取消后下次 scan() 的 is_cancelled 仍为 True，静默跳过全部扫描逻辑
- **方案演进**：
  - 方案 1（失败）：scan() 开头 `self._cancel_event.clear()` → 破坏"scan() 前取消"语义，3 个测试失败
  - 方案 2（采用）：scan() 开头记录 `cancelled = self.is_cancelled`，finally 中 `cancelled = self.is_cancelled; self._cancel_event.clear()` → 保留"scan() 前取消"语义，取消后 Scanner 可复用
- **依据**：取消标志的语义应在 scan() 返回时通过 report.cancelled 传达，而非持久保留在 Scanner 状态中

### C2：缓存描述过期

- **问题**：serialize_match 遗漏 description 字段，仅修改 MatchSpec.description 后 rule_hash 不变，缓存命中旧结果，描述变更无法生效
- **修复**：为 LeafMatch/AndMatch/OrMatch/NotMatch 四类 MatchSpec 的 serialize_match 输出补充 description 字段
- **CACHE_COMPAT_VERSION 递增**：从 4 到 5，触发旧缓存自动 purge（serialize_match 输出结构变更）

### I3：符号链接环路检测

- **问题**：follow_symlinks=True 时无环路检测，遇到 a/link -> a 会无限递归
- **修复**：新增 `_seen_realpaths` 集合 + `_is_symlink_loop` 辅助方法，跟踪已访问目录的真实路径（resolve()），重复访问判定为环路
- **PLR0912 处理**：环路检测增加分支导致 _walk_dir 分支数 13 > 12，提取 `_is_symlink_loop` 辅助方法将环路检测逻辑移出 _walk_dir

### I5：ROLLBACK 失败掩盖异常

- **问题**：batch_put_results 的 except 块中 `self._conn.execute("ROLLBACK")` 若失败会掩盖原始异常
- **修复**：ROLLBACK 用 try/except 包裹，失败时 `logger.warning` 不 raise，保留原始异常的 raise

### I6：列表无界增长

- **问题**：_skipped_dirs 与 _matched_files 为 list，大规模扫描（如全盘跳过 node_modules）时无界增长导致内存膨胀
- **修复**：改为 `deque(maxlen=_PROGRESS_LIST_MAX)`（200），自动截断旧条目
- **_emit_progress 适配**：`tuple(self._skipped_dirs[-200:])` 简化为 `tuple(self._skipped_dirs)`（deque maxlen 已截断）
- **测试适配**：`deque([]) == []` 为 False，`test_matched_files_not_collected_without_callback` 改用 `not scanner._matched_files`

### I9 + S7：连接泄漏与 close 幂等

- **I9**：`__init__` 用 try/except 包裹 `_init_db()`，失败时 `self._conn.close()` 防泄漏
- **S7**：新增 `self._closed: bool = False`，close() 加幂等保护，重复调用安全

### worker.py was_cancelled 判断（C1 配套）

- **问题**：C1 修复后 scan() 在 finally 中 clear _cancel_event，scan() 返回后 `self._scanner.is_cancelled` 恒为 False，worker 误判取消为正常完成
- **修复**：was_cancelled 改为基于 `report.cancelled` 累积判断，循环中检测到取消即 break

## 代码实现情况

### scanner.py scan() 控制状态管理（C1 核心）

```python
def scan(self, root: Path) -> ScanReport:
    self._progress_start = time.perf_counter()
    self._pause_event.set()
    self._skipped_dirs.clear()
    self._matched_files.clear()
    # ... 初始化局部变量
    cancelled = self.is_cancelled  # 记录 scan() 前取消状态

    try:
        if not cancelled:
            # ... 扫描逻辑
        # archive phase
        if self._scan_archives and ... and not self.is_cancelled:
            self._flush_batch()
            # ... archive 逻辑
    finally:
        # 异常路径也 flush 已累积批次
        self._flush_batch()
        # 记录取消状态后清除标志，使 Scanner 可复用（C1 修复）
        cancelled = self.is_cancelled
        self._cancel_event.clear()

    # ... 构建 stats
    return ScanReport(root=root, results=tuple(results), stats=stats, cancelled=cancelled)
```

### walker.py 符号链接环路检测（I3 核心）

```python
def _is_symlink_loop(self, dir_path: Path) -> bool:
    if not self._follow_symlinks:
        return False
    real = str(dir_path.resolve())
    if real in self._seen_realpaths:
        logger.debug("检测到符号链接环路，跳过: %s", dir_path)
        return True
    self._seen_realpaths.add(real)
    return False
```

### worker.py was_cancelled 判断（C1 配套）

```python
was_cancelled = False
for root in self._roots:
    if was_cancelled:
        break
    report: ScanReport = self._scanner.scan(root)
    # ... 累加统计
    if report.cancelled:
        was_cancelled = True
```

## 整合优化情况

- C1 修复与 I4 修复共用 try/finally 结构，一次性解决控制状态管理与异常路径 flush
- I3 环路检测提取为辅助方法，既解决 PLR0912 分支数超限，又提升可读性
- I6 deque 改造与 _emit_progress 适配联动，简化取最近条目逻辑
- 所有修复均配套回归测试，覆盖正反路径

## 测试验证结果

| 门禁 | 结果 |
|------|------|
| `uv run ruff check src tests benchmarks` | All checks passed |
| `uv run ruff format --check src tests benchmarks` | 79 files already formatted |
| `uv run pyrefly check` | 0 errors (435 suppressed) |
| `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95` | 1323 passed, 16 deselected, 覆盖率 96.06% |

覆盖率从基线 96.05% 提升至 96.06%（+0.01%），满足"不低于上一次的值"约束。

### 新增测试清单

| 测试文件 | 测试用例 | 覆盖修复 |
|---------|---------|---------|
| `tests/test_scanner.py` | `test_scanner_reusable_after_cancel` | C1 |
| `tests/test_walker.py` | `TestSymlinkLoopDetection`（5 个） | I3 |
| `tests/test_cache.py` | `test_serialize_leaf_includes_description` 等 6 个 | C2 |
| `tests/test_cache.py` | `test_init_failure_closes_connection` | I9 |
| `tests/test_cache.py` | `test_close_is_idempotent` + `test_context_manager_close_idempotent` | S7 |
| `tests/test_cache.py` | `test_batch_put_results_rollback_failure_preserves_original_error` | I5 |

### 覆盖率提升明细

| 模块 | 基线 | 当前 | 变化 |
|------|------|------|------|
| `scanner/walker.py` | 88% | 93% | +5% |
| `cache/store.py` | 97% | 98% | +1% |
| `scanner/scanner.py` | 95% | 95% | 持平 |
| `gui/worker.py` | 97% | 97% | 持平 |

## 遗留事项

- `scanner/scanner.py` 仍有 23 行未覆盖（95%），主要为 pipelined 模式的异常分支与 archive phase 边界场景，属既有技术债
- `walker.py` 行 32（Unix 平台分支）、69/74-75（ctypes 异常分支）在 Windows 测试环境无法覆盖，属平台限制
- python-code-reviewer 审查报告中的 Suggested 级建议（除 S7 外）未全部处理，后续可视情况推进

## 下一轮计划

无明确下一轮计划。本轮代码质量审查修复完成，全门禁通过，待 CI 验证后收尾。
