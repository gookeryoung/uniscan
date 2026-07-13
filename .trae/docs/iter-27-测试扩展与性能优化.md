# 迭代 27：测试扩展与性能优化

## 迭代目标

扩展测试覆盖（多格式文件 + 多规则场景），建立扫描性能 benchmark 基准，
分析并实现提升扫描吞吐量的优化方法（流水线扫描、缓存 I/O 跳过、进度减负）。

## 改动文件清单

### 新建文件

- `tests/test_multiformat_scan.py`：多格式多规则扫描测试（40 个测试）
- `benchmarks/__init__.py`：benchmark 包标记
- `benchmarks/bench_scan.py`：独立性能基准脚本（5 场景 + table/JSON 输出）
- `tests/test_benchmark.py`：slow 标记的吞吐量与缓存命中率回归测试

### 修改文件

- `src/fuscan/scanner/scanner.py`：
  - 新增 `_scan_pipelined` 方法（流水线扫描：walk 与 scan 并行，每 500 future 非阻塞 drain）
  - 新增 `_drain_futures` 方法（非阻塞收集已完成 future）
  - 删除 `_scan_concurrent` 方法（被流水线版本取代）
  - 4 处 `if self._on_progress is not None:` 守卫 matched_files 收集（_scan_sequential/_scan_pipelined/_drain_futures/_scan_archive_phase）
  - `_scan_entry_cached` 入口分流：无 CONTENT 规则时跳过文件 I/O
- `tests/test_scanner.py`：
  - `test_pipelined_large_fileset_triggers_drain`：600 文件触发 drain，验证结果一致性
  - `test_matched_files_not_collected_without_callback`：无回调时 matched_files 为空
  - `test_pipelined_drain_error_handling`：drain 阶段异常处理
  - `test_pipelined_drain_collects_matched_files_with_callback`：drain + on_progress 收集
  - `test_archive_phase_collects_matched_files_with_callback`：archive + on_progress 收集
  - `test_pipelined_cancel_during_walk`：walk 阶段取消中断

## 关键决策与依据

1. **流水线扫描替代两阶段**：原 scan() 先 walk 收集全部 entries 再 pool.submit，walk I/O 与 scan I/O 串行。
   流水线版本边遍历边提交，重叠 walk 与 scan 的 I/O，每 500 future 非阻塞 drain 控制内存。
2. **drain 阈值 500**：平衡 drain 频率与内存。max_workers=4 时 500 在途 future 内存约 150KB，可忽略。
3. **删除 _scan_concurrent**：无外部引用（仅 scan() 调用），流水线版本语义等价但更优，不留死代码。
4. **保守 benchmark 阈值**：CI 环境性能波动大，吞吐量阈值设为典型性能的 1/5-1/10（50/200 files/s），
   仅验证数量级与回归，不作为绝对性能门禁。
5. **benchmark workdir 用临时目录**：避免 .py 测试数据文件污染项目根目录导致 pyrefly 误报。
6. **进度减负仅守卫 append**：_emit_progress 已有 None 早退；matched_files 收集在上游，
   无回调时跳过可避免大扫描量时无谓列表增长与截断（每 500 条截断）。

## 验证结果

- ruff check：All checks passed
- ruff format --check：71 files already formatted
- pyrefly check：0 errors (108 suppressed, 17 warnings)
- pytest -m "not slow" --cov：961 passed, coverage 96.05%
- pytest -m slow tests/test_benchmark.py：4 passed
- benchmark 脚本：200 文件正常输出 table，缓存命中率 100%

## 遗留事项

- scanner.py 仍有少量未覆盖分支（default_extract_content_with_hash 的 OSError/Exception 回退、
  _spec_needs_content 最终 return False、walker.py 边界条件），整体覆盖率已达 96% 门槛
- benchmark 显示小文件场景单线程略快于多线程（线程池开销 > I/O 重叠收益），
  大文件或网络存储场景多线程优势更明显，可后续补充大文件 benchmark
