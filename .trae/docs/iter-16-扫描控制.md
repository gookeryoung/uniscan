# iter-16：扫描过程控制（开始/暂停/继续/停止）

## 本轮目标

实现需求02-1：扫描过程支持开始/暂停/继续（同一按钮切换状态）、停止功能。要求暂停时扫描线程阻塞且不消耗 CPU，停止时快速退出并返回已扫描的部分结果。

## 改动文件清单

### 源代码（4 文件）

- `src/fuscan/scanner/result.py`：`ScanReport` 新增 `cancelled: bool = False` 字段，标识扫描是否被取消
- `src/fuscan/scanner/scanner.py`：
  - 新增 `threading.Event` 控制机制（`_pause_event` / `_cancel_event`）
  - 新增 `pause()` / `resume()` / `cancel()` / `is_paused` / `is_cancelled` / `_check_control()` 方法
  - 重构 `scan()`：提取 `_scan_archive_phase()` 消除 PLR0912（分支过多）；进度上下文移至实例属性
  - 简化 `_emit_progress()` / `_scan_sequential()` / `_scan_concurrent()` 签名（移除 `start`/`total`/`skipped` 参数，改用实例属性），同时消除 PLR0913
- `src/fuscan/gui/worker.py`：
  - 新增 `cancelled = Signal(object)` 信号
  - 新增 `_cancel_requested` 标志，解决 Scanner 尚未创建时 cancel 丢失的竞态
  - `cancel()` 设置标志并委托 Scanner；`run()` 创建 Scanner 后检查标志
  - `run()` 在 roots 循环中检查取消标志；取消时 emit `cancelled` 而非 `finished_report`
- `src/fuscan/gui/main_window.py`：
  - 新增 `ScanState` 枚举（IDLE / RUNNING / PAUSED）驱动三态按钮
  - 扫描按钮 + 停止按钮 HBox 布局（停止按钮初始隐藏，扫描时显示）
  - `_set_scan_controls_text()` 同步按钮与菜单文本
  - `_on_scan` 三态分发：IDLE→启动、RUNNING→暂停、PAUSED→恢复
  - 新增 `_pause_scan` / `_resume_scan` / `_on_stop` / `_on_scan_cancelled` / `_reset_scan_ui` / `_cleanup_worker`
  - `_update_scan_button` 在 RUNNING/PAUSED 时保持按钮启用
  - `closeEvent` 改用 `cancel()` 替代 `quit()`（ScanWorker 重写 `run()`，非事件循环模式）

### 测试（2 文件）

- `tests/test_scanner.py`：新增 `TestScannerControl`（9 项测试）
  - 初始状态、暂停/恢复/取消标志、cancel 解除暂停阻塞
  - 扫描前取消返回 cancelled 报告
  - 扫描中取消返回部分结果（进度回调触发取消，无时序依赖）
  - 并发扫描取消
  - 暂停/恢复后扫描正常完成
- `tests/test_gui.py`：新增 3 个测试类共 17 项测试
  - `TestScanControlUI`（11 项）：状态转换、按钮文本同步、停止按钮可见性、`_update_scan_button` 在 RUNNING/PAUSED 的行为、暂停/恢复/重置
  - `TestScanControlIntegration`（4 项）：MainWindow 全流程扫描完成、取消回调、worker 清理、无路径告警
  - `TestScanWorkerControl`（2 项）：Worker cancel emit cancelled 信号（进度回调触发）、pause/resume 委托 Scanner

### 需求文档（2 文件）

- `.trae/req/需求01.md`：格式化为 `- [x]` 复选框格式
- `.trae/req/需求02.md`：格式化为 `- [x]` 复选框格式；需求02-1 标记为 `[x]`

## 关键决策与依据

1. **threading.Event 实现暂停/取消**：`_pause_event.wait()` 阻塞扫描线程且不占 CPU；`_cancel_event` 在遍历、扫描、并发收集、压缩包扫描各阶段检查，确保快速退出。
2. **取消竞态修复**：`ScanWorker.cancel()` 可能在 `run()` 创建 Scanner 之前调用（如快速点击停止）。新增 `_cancel_requested` 标志，`run()` 创建 Scanner 后立即检查并转发取消。
3. **进度回调触发取消（测试策略）**：扫描 50 文件仅需 0.6ms，`threading.Event` + `sleep` 的时序测试不可靠。改用 `on_progress` 回调在首次进度事件时调用 `scanner.cancel()`，无时序依赖。
4. **三态按钮 vs 双按钮**：需求明确"开始/暂停/继续（同一按钮）"，故扫描按钮三态切换；停止功能用独立红色按钮，避免三态以上复杂度。
5. **PLR0912 重构**：`scan()` 分支数 14 > 12。提取 `_scan_archive_phase()` 并将进度上下文移至实例属性，同时简化多个方法签名，消除 PLR0912 和 PLR0913。

## 验证结果

- ruff check：213 errors（全部为既有 UP006/UP045/ARG005/PLR0913，本轮新增 3 个 UP006 与既有风格一致，消除 1 个 PLR0913）
- pytest：483 passed, 1 failed（`test_window_geometry_restored` 为既有 PySide2 offscreen 环境问题）, 1 skipped
- coverage：89.36%（较基线 88.26% 提升 1.1%）
- pyrefly：322 errors（全部为既有 PySide2 类型存根问题）

## 遗留事项

- `test_window_geometry_restored`：PySide2 offscreen 平台 `propagateSizeHints()` 不支持，窗口高度 548 vs 预期 500（偏差 48 > 2）。既有问题，非本轮引入。
- coverage 89.36% 低于 95% 门槛：既有技术债，主要缺口在 extractors/office.py（76%）、gui/worker.py（80%）、watcher/ignore_dirs.py（65%）。
- UP006/UP045 全量迁移（`List`→`list`、`Optional[X]`→`X | None`）：213 个错误，需单独迭代处理。
