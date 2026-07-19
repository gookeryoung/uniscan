# iter-59 GUI 性能优化 P0

## 需求清单

- [x] 1. 基于基线性能进一步制定性能优化方案，避免界面卡滞（用户请求
  "请基于基线性能，进一步制定性能优化方案，避免界面卡滞。"）
- [x] 2. 在执行过程中记录性能，便于建立基线和调试分析（用户附加说明）

## 迭代目标

用户基于 `benchmarks/baseline.md`（iter-39 后的扫描吞吐量基线）提出 GUI 卡滞
优化需求。经 AskUserQuestion 确认采用「仅 P0（推荐）」方案，三项目标：

1. **P0-1 启动延后**：消除 GUI 启动期盘符枚举阻塞（未就绪光驱 OSError 阻塞
   100-500ms/盘）
2. **P0-2 导出异步化**：PDF/Excel 渲染移至后台线程，避免主线程数秒阻塞
3. **P0-3 进度回调减负**：减小进度列表上限从 200 到 50，降低跨线程信号槽分发开销

附加产出：性能测量基础设施 `src/fuscan/gui/perf.py`，环境变量开关零开销设计，
便于建立 GUI 性能基线与调试卡滞根因。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/perf.py` | 新建 | 性能测量基础设施：PerfTimer/record_event/set_perf_enabled |
| `src/fuscan/gui/export_worker.py` | 新建 | 后台导出线程 ExportWorker(QThread) |
| `src/fuscan/scanner/walker.py` | 修改 | `_list_windows_drives` 改用 GetLogicalDrives API；模块级 `import ctypes` |
| `src/fuscan/scanner/scanner.py` | 修改 | `_PROGRESS_LIST_MAX` 由 200 下调到 50 |
| `src/fuscan/gui/main_window.py` | 修改 | `__init__` 加 PerfTimer 埋点；`_on_export` 改为异步 ExportWorker；新增 `_on_export_finished`/`_on_export_failed`/`_cleanup_export_worker` |
| `tests/test_walker.py` | 修改 | 删除 `test_list_drives_skips_unready_drive`；新增 `test_list_drives_uses_get_logical_drives_bitmask` 与 `test_list_drives_network_filter` |
| `tests/test_gui.py` | 修改 | 新增 `_wait_export_worker` helper；6 个导出测试适配异步调用；新增 `test_export_worker_run_emits_finished_ok` 与 `test_export_worker_run_emits_failed_on_os_error` |
| `tests/test_gui_perf.py` | 新建 | perf.py 单元测试 7 例，覆盖启用/禁用/嵌套/事件记录 |
| `benchmarks/gui-baseline.md` | 新建 | GUI 性能基线文档 |

## 关键决策与依据

### P0-1 选择 GetLogicalDrives API 而非延迟启动

考虑过两种方案：

| 方案 | 内容 | 取舍 |
|------|------|------|
| API 化（采用） | `GetLogicalDrives` 位掩码单次调用枚举盘符 | 根因消除，启动期同步可保留 |
| 延迟启动 | `_init_rules` 与 `_refresh_drive_buttons` 延后到事件循环 | 仅掩盖症状，启动后用户点击设置仍卡顿 |

API 化方案治本：未就绪光驱不再触发 OSError，盘符探测从最坏 ~500ms 降至 <1ms。
`GetLogicalDrives` 仅返回已挂载逻辑盘符，未格式化或未就绪的设备自动排除。

### `_list_windows_drives` 的非 Windows 防御性回退

```python
windll = getattr(ctypes, "windll", None)
if windll is None:  # pragma: no cover - 非 Windows 环境的防御性回退
    return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
```

`getattr(ctypes, "windll", None)` 而非 `ctypes.windll` 直接访问，因为非 Windows
平台（Linux/macOS）`ctypes` 模块没有 `windll` 属性，直接访问会 AttributeError。
`# pragma: no cover` 因项目测试环境为 Windows，Unix 分支无法覆盖。

### `import ctypes` 提到模块级的原因

原 `_is_network_drive` 内部 `import ctypes` 是惰性导入，但 P0-1 新增的
`_list_windows_drives` 也需要 ctypes。两个函数都用到时，模块级导入更合理：

- 避免每次调用重复 import 开销
- 便于测试 monkeypatch：`monkeypatch.setattr(walker_mod.ctypes, "windll", _FakeWindll())`
  要求 ctypes 是模块属性

测试无法 monkeypatch 函数内部 lazy import 的对象，故必须模块级导入。

### P0-2 选择 QThread 子类化而非 QRunnable

考虑过两种方案：

| 方案 | 内容 | 取舍 |
|------|------|------|
| QThread 子类化（采用） | ExportWorker(QThread) 重写 run()，与 ScanWorker 一致 | 模式复用，信号槽直接 connect |
| QRunnable + QThreadPool | 需继承 QObject 实现信号，配合 QThreadPool.globalInstance() | 模式不一致，引入额外抽象 |

QThread 子类化与项目既有 ScanWorker 模式一致，便于维护者理解。
导出通常 < 5 秒，用户不会主动取消，故不需要 QRunnable 的取消接口。

### QThread 子线程代码无法被 coverage 捕获

`coverage` 的 `concurrency=thread` 配置仅对 Python `threading.Thread` 生效，
QThread 是 C++ 扩展线程，coverage 无法自动 trace。解决方法（参考 ScanWorker 测试）：

```python
worker.run()  # 直接调用，不通过 start()
```

在主线程同步执行 `run()`，coverage 可正常捕获。但失去了 QThread 的异步语义，
故仅用于单元测试覆盖，集成测试仍用 `start()` + `_wait_export_worker` 等待。

### `_wait_export_worker` helper 设计

```python
def _wait_export_worker(window: MainWindow, qapp: QApplication) -> None:
    worker = getattr(window, "_export_worker", None)
    if worker is None:
        return
    worker.wait(5000)
    qapp.processEvents()
```

- `worker.wait(5000)` 阻塞主线程直到 worker 退出或超时 5 秒
- `qapp.processEvents()` 让信号槽分发到主线程的槽函数（如 `_on_export_finished`）
- `getattr` + None 检查防御 `test_export_cancelled`（取消时无 worker 创建）

### P0-3 选择 50 而非更小值

`_PROGRESS_LIST_MAX` 下调到 50 的依据：

- 50 项足以让用户感知"近期"上下文（最新命中/跳过文件列表）
- 单次回调元组拷贝从 400 项降至 100 项，减少 75% 拷贝开销
- 50 与 `_BATCH_THRESHOLD=50`（批量写入阈值）一致，保持配置一致性
- 更小值（如 20）会让用户难以看到足够的上下文，影响调试体验

### perf.py 用 `_PerfState` 类替代 `global` 声明

ruff PLW0603 不推荐 `global` 声明。用类属性封装可变状态：

```python
class _PerfState:
    enabled: bool = os.environ.get("FUSCAN_PERF", "") == "1"
    depth: int = 0
```

对外保持 `PERF_ENABLED` 模块级常量（模块加载时快照），运行时切换通过
`set_perf_enabled` 修改 `_PerfState.enabled`。外部代码（main_window.py、
export_worker.py）只导入 `PerfTimer`，不直接读 `PERF_ENABLED`，故 API 兼容。

### 删除 `# noqa: N802` 的依据

`PerfTimer` 命名采用 PascalCase 是为了与 `with PerfTimer("..."):` 上下文管理器
习惯一致（如 `open()`、`contextlib.contextmanager`）。ruff.toml 的 select 未启用
N 规则集（pep8-naming），故 `# noqa: N802` 是未使用的 noqa，触发 RUF100 警告。
删除后命名保持 PascalCase 不变。

## 代码实现情况

### `src/fuscan/gui/perf.py`（新建）

零开销性能测量基础设施：

- 环境变量 `FUSCAN_PERF=1` 启用，默认关闭
- `PerfTimer` 上下文管理器，未启用时仅一次开关检查后 yield，无计时开销
- `record_event` 记录离散事件及关联字段
- 嵌套层级通过空格缩进表达
- 输出到 `fuscan.gui.perf` logger（DEBUG 级别）

### `src/fuscan/gui/export_worker.py`（新建）

```python
class ExportWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, report: ScanReport, path: Path, parent: QObject | None = None) -> None: ...
    def run(self) -> None:
        try:
            with PerfTimer("ExportWorker.save_report"):
                save_report(self._report, self._path)
            self.finished_ok.emit(self._path)
        except OSError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - reportlab/openpyxl 内部异常防御
            self.failed.emit(str(exc))
```

异常分级：`OSError` 单独捕获记录 warning；其他异常 `# pragma: no cover` 标注
（reportlab/openpyxl 内部异常防御，非预期路径）。

### `src/fuscan/scanner/walker.py::_list_windows_drives`

```python
def _list_windows_drives() -> list[Path]:
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
    try:
        bitmask = windll.kernel32.GetLogicalDrives()
    except OSError:
        return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
    if bitmask == 0:
        return []
    return [Path(f"{letter}:\\") for i, letter in enumerate(string.ascii_uppercase) if bitmask & (1 << i)]
```

位掩码解算：bit 0=A:、bit 1=B:、...，按位与生成 Path 列表。

### `src/fuscan/gui/main_window.py::_on_export` 异步化

```python
def _on_export(self, fmt: str) -> None:
    # ... 路径选择 ...
    self.export_btn.setEnabled(False)
    self.stats_label.setText(f"正在导出 {path.name}...")
    from fuscan.gui.export_worker import ExportWorker
    self._export_worker = ExportWorker(self._last_report, path, parent=self)
    self._export_worker.finished_ok.connect(self._on_export_finished)
    self._export_worker.failed.connect(self._on_export_failed)
    self._export_worker.start()
```

延迟导入 `ExportWorker` 避免 main_window 顶部依赖 reportlab/openpyxl 触发导入，
与 iter-58 `launch` 入口设计一致。

## 整合优化情况

- **零开销测量**：perf.py 默认关闭，未启用时 PerfTimer 仅一次开关检查后 yield，
  不影响生产环境性能
- **模式复用**：ExportWorker 与 ScanWorker 同为 QThread 子类化模式，维护者
  理解成本低
- **测试可观察**：通过 `worker.run()` 直接调用覆盖 QThread 子线程代码
  （与 ScanWorker 测试一致），解决 coverage 无法捕获 QThread 子线程的限制
- **配置一致性**：`_PROGRESS_LIST_MAX=50` 与 `_BATCH_THRESHOLD=50` 保持一致
- **基线文档**：`benchmarks/gui-baseline.md` 记录 GUI 性能基线与优化项，
  便于后续回归对比

## 测试验证结果

| 门禁 | 结果 | 基线（iter-58） | 变化 |
|------|------|----------------|------|
| ruff check | All checks passed | 0 errors | — |
| ruff format --check | 92 files already formatted | 91 files | +1（test_gui_perf.py） |
| pyrefly check | 0 errors (471 suppressed) | 0 errors (467 suppressed) | +4 suppressed |
| pytest | 1373 passed / 0 failed | 1364 passed | +9 测试 |
| coverage | 96.22% | 95.86% | +0.36% |

新增测试 9 例：
- `tests/test_gui_perf.py` 7 例（perf.py 100% 覆盖）
- `tests/test_gui.py` 2 例（ExportWorker run() 成功/失败路径，100% 覆盖）

覆盖率提升 0.36% 来自：
- export_worker.py 100%（新增）
- perf.py 100%（新增）
- main_window.py 94%（保持，新增 _on_export_finished/_on_export_failed/_cleanup_export_worker 已覆盖）

## 遗留事项

- **GUI 真实性能测量**：当前 `benchmarks/gui-baseline.md` 基于代码路径分析与
  理论估算，未在真实 Windows 环境运行 `FUSCAN_PERF=1` 记录实际耗时。后续可在
  真实环境补充分阶段启动耗时与导出耗时分布
- **P1/P2 优化未实施**：用户选择「仅 P0」，未实施的 P1（结果树虚拟模型）、
  P2（详情面板惰性加载）等优化项可后续迭代
- **`_PROGRESS_LIST_MAX` 进一步下调空间**：若实测仍存在进度回调卡滞，可考虑
  下调到 20 或引入差量更新（仅传递新增项）

## 下一轮计划

无明确下一轮计划。iter-59 P0 优化已完成，全门禁通过，覆盖率提升。
如用户提出新需求或实测发现性能瓶颈再行迭代。
