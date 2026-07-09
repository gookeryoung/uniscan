# iter-05 托盘驻守与文件监控

迭代日期：2026-07-09
阶段：P4（托盘驻守 + 文件监控 + 增量扫描）

## 本轮目标

实现长期驻守系统托盘的动态扫描：基于 watchdog 监控目录新增文件，
通过增量扫描器仅扫描变化文件，配合系统托盘图标提供后台运行能力。

## 验收标准（P4 范围）

- [x] FileMonitor 基于 watchdog 的目录监控（启动/停止/新增路径/事件去重）
- [x] IncrementalScanner 增量扫描器（mtime 跟踪/状态持久化/跳过未变化）
- [x] default_ignore_dirs 平台默认忽略目录（Windows 系统目录 + VCS + 缓存）
- [x] TrayApp 系统托盘应用（QSystemTrayIcon + 右键菜单 + 批量扫描 + 通知）
- [x] CLI tray 子命令接入
- [x] 测试覆盖：watcher 24 例 + tray 26 例 = 50 例新增
- [x] 覆盖率 ≥ 80%（实际 82.20%）
- [x] ruff lint 全部通过

## 改动文件清单

### watcher 子包（src/pyfilescan/watcher/）
- `monitor.py`：FileMonitor + _EventHandler，基于 watchdog Observer
  监控目录；支持忽略目录/扩展名过滤、事件去重（dedup_interval）、
  递归监控；FileEvent/FileEventType 数据结构
- `incremental.py`：IncrementalScanner，维护 path→mtime 映射，
  scan() 增量扫描目录、scan_paths() 扫描指定路径列表（由监控触发）、
  save_state()/load_state() JSON 持久化
- `ignore_dirs.py`：common_ignore_dirs + windows_system_dirs +
  default_ignore_dirs() 平台感知函数
- `tray.py`：TrayApp(QObject)，集成 QSystemTrayIcon + FileMonitor +
  IncrementalScanner；右键菜单（显示窗口/启停监控/全量扫描/退出）；
  QTimer 2 秒去抖批量处理文件事件；命中时托盘通知 + 信号发射
- `__init__.py`：导出公共 API，TrayApp 经 __getattr__ 惰性导入
  避免无 PySide2 环境 import 失败

### CLI 集成（src/pyfilescan/cli.py）
- `tray` 子命令：`-r/--rules`、`-w/--watch`、`--state` 参数，
  创建 TrayApp 并启动事件循环

### 测试（tests/）
- `test_watcher.py`：24 个用例
  - TestIgnoreDirs（2）：默认忽略目录、Windows 平台检测
  - TestWatcherLazyImport（2）：TrayApp 惰性导入、未知属性报错
  - TestFileMonitor（8）：启停、忽略目录/扩展名、重复启动、
    无路径不启动、新增监控、上下文管理器、删除事件
  - TestIncrementalScanner（12）：首次扫描、跳过未变化、
    修改重扫、新增文件、scan_paths、mark_scanned、remove_path、
    状态持久化、损坏文件、扩展名过滤
- `test_tray.py`：26 个用例（gui marker）
  - TestTrayAppConstruction（3）：构造、watch_paths、状态加载
  - TestTrayAppMonitoring（4）：启停、重复启动、未启动停止、切换
  - TestTrayAppFileEvent（5）：创建/修改/删除/目录/去重
  - TestTrayAppScanHandling（4）：批量扫描、信号发射、无命中、状态持久化
  - TestTrayAppFullScan（2）：无路径通知、有路径启动 worker
  - TestTrayAppQuit（2）：停止监控、状态持久化
  - TestTrayAppShowWindow（2）：显示窗口、无窗口不报错
  - TestTrayAppInit（3）：托盘图标、窗口隐藏/显示
- `test_cli.py`：新增 TestMainModuleImport（1），__main__ 模块导入测试

## 关键决策与依据

### 1. 事件去重策略
watchdog 对同一文件短时间内可能触发多次事件（created→modified）。
_EventHandler 用 Dict[Path, float] 记录最后事件时间，
dedup_interval（默认 1 秒）内同路径事件被丢弃。
测试中 dedup_interval=0 验证删除事件能被捕获。

### 2. 增量扫描的 mtime 比较
用 abs(entry.mtime - stored_mtime) < 0.001 而非 == 比较，
避免文件系统 mtime 精度差异导致误判为"已变化"。
状态以 path_str → mtime 的 Dict 持久化为 JSON。

### 3. TrayApp 批量扫描去抖
文件监控可能短时间内产生大量事件（如解压几百个文件）。
QTimer singleShot + 2 秒间隔，将 pending_paths 列表批量扫描，
避免逐文件扫描的开销。

### 4. _full_scan 的 worker 生命周期
ScanWorker(QThread) 原为局部变量，存在被 GC 回收风险。
改为存储到 self._scan_worker 实例属性，确保引用保持。

### 5. _handle_scan_result 状态持久化
原实现仅在 report.hits 非空时持久化状态，导致无命中时
已扫描文件状态丢失。修复为无论是否有命中都持久化。

### 6. TrayApp 惰性导入
watcher/__init__.py 用 __getattr__ 惰性导入 TrayApp，
使无 PySide2 环境下 import pyfilescan.watcher 不报错。
TrayApp 仅在实际访问时触发 PySide2 导入。

### 7. QThread 测试策略
TrayApp._full_scan 创建真实 ScanWorker(QThread) 在测试中
会导致 Windows STATUS_STACK_BUFFER_OVERRASH 崩溃。
用 monkeypatch 替换 ScanWorker 为 FakeWorker（带 finished_report
信号的 connect 方法），避免真实线程创建。

## 验证结果

- pytest：283 passed, 1 skipped（RAR 需 unrar）
- coverage：82.20%（≥80% 门槛）
- ruff：All checks passed
- watcher 子包覆盖率：__init__ 100% / monitor 91% / incremental 89% / tray 88% / ignore_dirs 90%

## 遗留事项

- pyrefly 类型检查未安装在此环境，P5 阶段补齐
- rar_reader.py 覆盖率 34%（需 unrar 工具，CI 环境跳过）
- extractors 覆盖率偏低（pdf 45% / odf 49% / wps 57%），P5 补测试
- TrayApp.start() 进入 app.exec_() 事件循环，未直接测试（需集成测试）
