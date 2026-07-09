# iter-04 PySide2 GUI 界面

迭代日期：2026-07-09
阶段：P3（GUI 界面）

## 本轮目标

实现 PySide2 图形界面，支持规则加载、路径选择、后台扫描、结果展示与
导出，使非技术用户也能使用扫描器。

## 验收标准（P3 范围）

- [x] MainWindow 主窗口（菜单栏、工具栏、规则面板、结果树、状态栏）
- [x] ScanWorker 后台扫描线程（QThread，不阻塞 UI）
- [x] 结果树形展示（按文件分组，展开显示规则命中）
- [x] CSV/JSON 导出
- [x] CLI gui 子命令接入
- [x] GUI 烟雾测试（17 个用例，使用 offscreen 平台）
- [x] 覆盖率 ≥ 80%（实际 80.94%）
- [x] ruff lint 全部通过

## 改动文件清单

### GUI 子包（src/pyfilescan/gui/）
- `main_window.py`：MainWindow 类，含菜单栏（文件/扫描/帮助）、
  工具栏、规则树、结果树、状态栏与进度条；文件对话框加载规则与
  选择路径；CSV/JSON 导出
- `worker.py`：ScanWorker（QThread），后台执行 Scanner.scan，
  通过 progress/finished_report/failed 信号通知 UI
- `app.py`：launch() 入口函数，构造 QApplication 与 MainWindow
- `__init__.py`：公共 API 导出，launch 惰性导入避免无 GUI 环境报错

### CLI 集成（src/pyfilescan/cli.py）
- `_cmd_gui`：从占位改为调用 `pyfilescan.gui.launch()`，PySide2
  未安装时返回错误码 3

### 测试（tests/）
- `test_gui.py`：17 个 GUI 测试用例，使用 gui marker，
  QT_QPA_PLATFORM=offscreen 在无显示器环境运行
- `test_cli.py`：更新 GUI 子命令测试，mock launch 验证调用

## 关键决策与依据

### 1. Python 环境切换
PySide2 仅支持 Python 3.8-3.10，当前开发机默认 Python 3.13 无法安装。
创建 conda 环境 `pyfilescan`（Python 3.10.20）专门用于 P3/P4 阶段。
P0-P2 的测试在该环境下同样通过（214 passed），向后兼容性验证 OK。

### 2. 后台扫描线程
Scanner.scan 是同步阻塞调用，直接在 UI 线程运行会冻结界面。
ScanWorker 继承 QThread，在 run() 中执行扫描，通过 Qt 信号
通知 UI。当前 Scanner 无进度回调，progress 信号为粗粒度
（扫描完成后一次性 emit）。

### 3. 信号跨线程传递
测试中发现 QThread.finished 信号需通过 QEventLoop 处理才能
被主线程接收。测试中使用 QEventLoop + QTimer 超时保护等待
worker 完成，避免直接 wait() 导致信号丢失。

### 4. launch 函数测试策略
app.launch() 调用 `app.exec_()` 进入 Qt 事件循环，直接测试会
阻塞。通过 monkeypatch 替换 QApplication 与 MainWindow 为
Fake 类，FakeApp.exec_() 直接返回 0 不进入循环。
test_launch_reuses_existing_app 不使用 qapp fixture（真实
QApplication），避免 exec_() 阻塞。

### 5. GUI 测试平台
使用 `QT_QPA_PLATFORM=offscreen` 环境变量，让 Qt 在无显示器
环境（CI、远程开发）运行。所有 GUI 测试标记 `gui` marker，
CI 可通过 `-m "not gui"` 跳过。

### 6. 文件对话框 mock
QFileDialog.getOpenFileName/getExistingDirectory 是模态对话框，
测试中通过 monkeypatch 替换为返回固定路径的 lambda，避免弹出
对话框阻塞测试。QMessageBox.warning 同理。

### 7. launch 惰性导入
gui/__init__.py 中 launch 函数通过 `__getattr__` 惰性导入，
这样在无 PySide2 环境（如 Python 3.13 base env）import
pyfilescan.gui 不会立即失败，只有调用 launch 才报错。
MainWindow 与 ScanWorker 是顶层导入（PySide2 是硬依赖）。

## 验证结果

```
测试：232 passed, 1 skipped in 2.10s
  - P0 规则引擎与 CLI：137（含更新的 gui 测试）
  - P1 多格式提取器：36
  - P2 压缩扫描：43
  - P3 GUI：17
覆盖率：80.94%（branch coverage，阈值 80%）
ruff check：All checks passed!
```

GUI 模块覆盖率：
- gui/__init__.py: 45%（launch 惰性导入分支未完全覆盖）
- gui/app.py: 100%（launch 测试覆盖创建与复用两条路径）
- gui/main_window.py: 76%（部分事件处理如 _on_scan 实际启动
  worker 的路径未测试，避免复杂 mock）
- gui/worker.py: 73%（run 方法异常分支未覆盖）

手动验证：
- `pyfilescan gui` 启动主窗口，窗口标题、菜单栏、工具栏正常
- 加载 rules/example.yaml，规则树展示 5 条规则
- 选择扫描路径，扫描按钮变为可用
- 点击扫描，进度条显示，完成后结果树展示命中项
- 导出 CSV/JSON 文件内容正确

## 遗留事项

1. **GUI 事件处理覆盖不全**：_on_scan 实际启动 worker 的完整
   流程、_on_export 的文件保存对话框、_on_about 对话框未测试。
   需要更复杂的 mock 或集成测试环境。
2. **扫描进度细粒度**：当前 progress 信号仅扫描完成时 emit 一次。
   P5 阶段可为 Scanner 增加进度回调，实现实时进度更新。
3. **规则可视化编辑**：当前仅展示规则，不支持 GUI 编辑规则。
   如需支持，可增加规则编辑对话框。
4. **结果过滤与排序**：结果树不支持按严重等级过滤、按路径排序。
   P5 可增加右键菜单与过滤栏。
5. **GUI 线程安全**：ScanWorker 通过信号更新 UI 是线程安全的
   （Qt 自动跨线程排队连接），但 _last_report 在 worker 完成
   与用户导出之间可能有竞态（当前单 worker 无影响）。

## 下一阶段（P4）重点

- 系统托盘驻守（QSystemTrayIcon）
- watchdog 文件监控（监控新增文件）
- 配置忽略目录（预设 Windows 系统目录等）
- 增量扫描（仅扫描新增/修改文件）
- 托盘菜单与通知
