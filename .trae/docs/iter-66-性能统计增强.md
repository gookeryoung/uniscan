# iter-66：扫描性能统计增强（req-15）

## 需求清单

来源：用户"能否在不影响性能的情况，增加扫描过程性能统计，便于后续进行性能优化"
经 AskUserQuestion 澄清，选定三个增强方向（多选）：

- [x] R1：默认轻量启用 + 持久化（PerfStats 始终启用，扫描结束可写 JSON）
- [x] R2：GUI 展示性能摘要（状态栏显示速度与热点占比）
- [x] R3：CLI/GUI 便捷开关（新增 `--perf`/`--perf-save` 与菜单项，免去环境变量）

## 迭代目标

iter-65 已建设 `PerfStats` 聚合统计基础设施（需 `FUSCAN_PERF=1` 启用），
但日常使用中用户不会主动设置环境变量，导致性能数据无法被收集。

本迭代在保证零开销前提下，让 `PerfStats` 始终启用并贯通 GUI/CLI 展示链路，
让用户无需任何额外配置即可在每次扫描后看到性能摘要，并能一键保存为 JSON
供后续定向优化分析。

## 关键决策与依据

### 决策1：PerfStats 始终启用，PerfTimer 仍需启用

`PerfStats.measure` 仅做 `perf_counter` + `Lock`，无日志输出，
单次开销约 1-2μs。每文件 5-10 个 measure 点，按 171 files/s 计总开销 < 0.3%，
对生产扫描性能无可感知影响。

`PerfTimer` 输出 DEBUG 日志（含字符串格式化），开销显著，仍需 `FUSCAN_PERF=1`
或 `--perf` 显式启用，仅用于定向卡滞定位。

`_PerfState.enabled` 开关语义收窄：iter-66 起仅控制 `PerfTimer`/`record_event`，
不再控制 `PerfStats`。`PerfStats.measure`/`record` 移除 `enabled` 检查。

### 决策2：perf_summary 通过 ScanStats 携带，不新增独立信号

`ScanStats.perf_summary: dict[str, dict[str, float]] | None` 字段携带各阶段
统计字典（格式同 `PerfStats.to_dict()` 输出），随 `ScanReport` 一路传递到
GUI/CLI 展示层。无需新增信号槽，复用既有 `finished_report` 信号路径。

多根路径扫描时，`ScanWorker` 持有 `PerfStats` 实例累计每次 `scan()` 的
`perf_summary`（通过 `merge_dict`），最终合并结果填入 `ScanReport`。

### 决策3：CLI 双选项分离"详细日志"与"持久化"

- `--perf`：启用 `PerfTimer` 详细 DEBUG 日志（需配合 `-vv`），适合实时定位
- `--perf-save FILE`：将 `PerfStats` 聚合统计写入 JSON 文件，适合事后分析

两者独立可单独使用，也可组合使用。`PerfStats` 始终启用，故不带 `--perf`
时 `--perf-save` 仍可工作。

### 决策4：GUI 菜单项嵌入既有"扫描"菜单，不新建顶层菜单

`扫描` 菜单末尾追加分隔符 + 两项：
- `性能统计...`（`perf_stats_action`）：弹出 HTML 表格对话框，含"保存为 JSON"按钮
- `启用性能日志`（`perf_log_action`，checkable）：切换 `PerfTimer` 详细日志开关

遵循 rule-12 关联设计原则，性能相关功能聚合到扫描上下文中，不增加顶层菜单复杂度。

### 决策5：ScanStats 新增 speed 属性而非字段

`speed` 作为 `@property` 由 `scanned_files / duration_seconds` 计算，
避免冗余字段与同步开销。`duration_seconds == 0` 时返回 0.0 避免除零。

## 改动文件清单

### 修改文件

| 文件 | 说明 |
|------|------|
| `src/fuscan/perf.py` | 模块 docstring 更新；`_PerfState` docstring 更新；`PerfStats.measure`/`record`/`report` 移除 `enabled` 检查；新增 `to_dict`/`merge_dict`/`summary_text`/`save_to_json` 4 个方法 |
| `src/fuscan/scanner/result.py` | `ScanStats` 新增 `perf_summary: dict[str, dict[str, float]] \| None = None` 字段与 `speed` 属性 |
| `src/fuscan/scanner/scanner.py` | `scan()` 末尾填充 `perf_summary=self._perf.to_dict()`；注释更新说明 PerfStats 始终启用 |
| `src/fuscan/gui/worker.py` | 新增 `from fuscan.perf import PerfStats`；`ScanWorker` 持有 `self._perf` 累计多根路径；合并后填入 `ScanReport.perf_summary` |
| `src/fuscan/gui/main_window.py` | 导入 `QTextEdit`/`QVBoxLayout`/`set_perf_enabled`；`_on_scan_finished` 状态栏追加速度与热点摘要；新增 `_on_show_perf_stats`/`_on_toggle_perf_log` 方法；连接 `perf_stats_action`/`perf_log_action` 信号 |
| `src/fuscan/gui/main_window.ui` | `scan_menu` 追加分隔符 + `perf_stats_action` + `perf_log_action`；新增两个 `<action>` 定义 |
| `src/fuscan/gui/main_window_ui.py` | 由 .ui 自动重新生成 |
| `src/fuscan/cli.py` | `build_parser` 新增 `--perf` 与 `--perf-save` 参数；`_cmd_scan` 启用 `PerfTimer` 与持久化逻辑；`_print_summary` 输出各阶段性能统计 |
| `tests/test_gui_perf.py` | `test_perf_stats_disabled_zero_overhead` 改为 `test_perf_stats_always_records_regardless_of_enabled`；新增 4 个测试（to_dict/merge_dict/summary_text/save_to_json） |
| `tests/test_scanner.py` | `TestScanStats` 新增 3 个测试（speed/perf_summary 默认值/perf_summary 持有字典） |
| `tests/test_cli.py` | `TestScanCommand` 新增 2 个测试（--perf-save 写 JSON / --perf 启用详细日志） |
| `tests/test_gui.py` | `TestWorkflowStage` 新增 4 个测试（状态栏摘要/无数据提示/对话框展示/切换开关） |

### 新增文件

| 文件 | 说明 |
|------|------|
| `.trae/req/req-15-性能统计增强.md` | 需求清单 |

## 代码实现情况

### perf.py 核心改动

```python
# PerfStats.measure 移除 enabled 检查
@contextmanager
def measure(self, name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        self._record_locked(name, elapsed)

# 新增 4 个方法
def to_dict(self) -> dict[str, dict[str, float]]: ...  # 导出可序列化字典
def merge_dict(self, data: dict[str, dict[str, float]]) -> None: ...  # 合并外部字典
def summary_text(self, top: int = 3) -> str: ...  # 简要热点文本
def save_to_json(self, path: Path, *, meta: dict[str, object] | None = None) -> None: ...  # 持久化
```

### ScanStats 新增字段

```python
perf_summary: dict[str, dict[str, float]] | None = None

@property
def speed(self) -> float:
    """扫描吞吐量（文件/秒），duration 为 0 时返回 0.0。"""
    return self.scanned_files / self.duration_seconds if self.duration_seconds > 0 else 0.0
```

### ScanWorker 多根路径累计

```python
self._perf: PerfStats = PerfStats()  # 累计多根路径
# 每次 scan() 后
if report.stats.perf_summary:
    self._perf.merge_dict(report.stats.perf_summary)
# 最终 ScanReport 填充合并结果
perf_summary=self._perf.to_dict()
```

### GUI 状态栏摘要

```python
summary = report.summary()
speed = report.stats.speed
if speed > 0:
    summary += f" | 速度 {speed:.0f} 文件/s"
perf = report.stats.perf_summary
if perf:
    total_ms = sum(s.get("total_ms", 0.0) for s in perf.values()) or 1.0
    ranked = sorted(perf.items(), key=lambda x: -x[1].get("total_ms", 0.0))[:3]
    hotspots = " | ".join(f"{name} {info.get('total_ms', 0.0) / total_ms * 100:.0f}%" for name, info in ranked)
    summary += f" | 热点: {hotspots}"
```

### CLI 选项

```python
scan_parser.add_argument("--perf", action="store_true", help="启用性能详细日志...")
scan_parser.add_argument("--perf-save", type=Path, default=None, metavar="FILE", help="将性能统计保存为 JSON 文件...")
```

## 整合优化情况

- `PerfStats` 从条件启用改为始终启用，消除"用户忘记设置环境变量导致无数据"问题
- `perf_summary` 通过既有 `ScanReport` → `finished_report` 信号链路传递，无需新增信号
- 多根路径扫描通过 `ScanWorker._perf` 累计，避免分次扫描数据丢失
- GUI 菜单项嵌入既有"扫描"菜单，遵循关联设计原则，不增加顶层菜单复杂度
- CLI 双选项分离"详细日志"与"持久化"，语义清晰可单独使用

## 测试验证结果

- ruff check：全部通过（修复 1 处 F401 未使用导入 `ScanStats`）
- ruff format --check：93 files already formatted
- pyrefly check：0 errors（463 suppressed, 60 warnings not shown）
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1436 passed**, 16 deselected, 覆盖率 **96.02%**
- perf.py 覆盖率：100%
- 新增 13 个测试全部通过：
  - test_gui_perf.py：4 个（to_dict/merge_dict/summary_text/save_to_json + 改写 always_records）
  - test_scanner.py：3 个（speed/perf_summary 默认值/持有字典）
  - test_cli.py：2 个（--perf-save/--perf）
  - test_gui.py：4 个（状态栏摘要/无数据提示/对话框展示/切换开关）

## 遗留事项

- 用户在实际扫描中收集 perf_summary 数据，根据热点占比决定下一迭代定向优化方向：
  - 若 `read_bytes` 占比高 → mmap 或异步 I/O
  - 若 `match` 占比高 → ProcessPoolExecutor
  - 若 `extract` 占比高 → 提取器优化（lxml / 流式）
  - 若 `cache_*` 占比高 → SQLite 读写分离
- `PerfStats` 始终启用后，未来可考虑增加更细粒度阶段（如单规则匹配耗时）

## 下一轮计划

- 等待用户提供真实扫描 perf_summary 数据，按瓶颈定向实施优化方案
- 若数据不足，可扩展 PerfStats 测量更细粒度阶段
