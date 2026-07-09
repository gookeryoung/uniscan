# iter-09: 多线程扫描与详情对话框

## 本轮目标

1. 使用更高性能的库/方式提升扫描速度
2. 扫描结果双击列表项后，显示更详细的内容

## 改动文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/pyfilescan/scanner/scanner.py` | 修改 | 新增 `max_workers` 参数，重构 `scan()` 为三阶段（遍历→扫描→压缩包），新增 `_scan_sequential` / `_scan_concurrent` 方法 |
| `src/pyfilescan/gui/worker.py` | 修改 | `ScanWorker.__init__` 新增 `max_workers` 参数并透传给 `Scanner` |
| `src/pyfilescan/gui/main_window.py` | 修改 | `_on_scan` 中设置 `max_workers=8`；`_populate_results` 将 `ScanResult` 存入 `Qt.UserRole`；新增 `_on_result_double_clicked` 方法连接 `itemDoubleClicked` 信号 |
| `src/pyfilescan/gui/detail_dialog.py` | 新增 | `HitDetailDialog` 类：展示文件元信息、命中规则表、内容预览（关键词高亮） |
| `tests/test_scanner.py` | 修改 | 新增 `TestScannerConcurrency` 测试类（6 个测试） |
| `tests/test_gui.py` | 修改 | 新增 `TestHitDetailDialogHelpers`（12 个）和 `TestHitDetailDialog`（8 个）测试类 |

## 关键决策与依据

### 1. 多线程扫描用 ThreadPoolExecutor（标准库）

- **决策**：使用 `concurrent.futures.ThreadPoolExecutor`，不引入第三方依赖
- **依据**：文件扫描为 I/O 密集型任务，线程池可有效并发读取文件；`_scan_entry` 每个文件创建独立 `MatchContext`，无共享可变状态，线程安全
- **压缩包扫描保持顺序**：`ArchiveScanner` 可能持有内部状态，不保证线程安全，压缩包内条目扫描始终单线程

### 2. GUI 默认 max_workers=8

- **决策**：GUI 扫描时默认 `max_workers=8`
- **依据**：大多数现代机器 8 线程可平衡性能与资源占用；CLI 保持默认单线程（兼容性优先）

### 3. 详情对话框用 QDialog 弹出

- **决策**：双击结果项弹出模态 `QDialog`，而非内嵌面板
- **依据**：模态对话框不干扰主窗口布局，用户可自由调整大小查看长内容

### 4. 关键词高亮用单次正则替换

- **决策**：`_build_preview_html` 先 `html.escape` 转义内容，再用单次 `re.sub` 插入高亮 span
- **依据**：多次 `str.replace` 会破坏已插入的 HTML 标签；按关键词长度降序排列避免短词匹配到长词内部
- **大小写不敏感**：使用 `re.IGNORECASE` 高亮所有大小写变体，符合"显示所有匹配"的用户预期

### 5. 内容预览优先用提取器

- **决策**：预览内容先用 `extract_content(path)` 提取（支持 PDF/DOCX 等），失败回退到纯文本
- **依据**：与扫描器 `default_extract_content` 逻辑一致，保证预览内容与匹配内容同源
- **截断限制**：预览限制前 100KB，避免大文件阻塞 UI

## 验证结果

- ruff: 全部通过
- pytest: 329 passed, 1 skipped
- 覆盖率: 87.92%（门槛 80%）
  - `detail_dialog.py`: 96%
  - `scanner.py`: 90%
  - `main_window.py`: 78%（双击路径已覆盖，加载/导出路径未覆盖）

## 遗留事项

- 无
