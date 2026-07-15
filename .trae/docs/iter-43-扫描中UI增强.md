# iter-43 扫描中 UI 增强

## 需求清单

- [x] 增加在扫描中也可以查看匹配情况和定位文件的功能，方便用户边查边处理
- [x] 扫描中界面下，命中的文件下方增加已处理文件列表，更新已处理文件清单
- [x] 使用不同的颜色和标识区分命中的文件和已处理文件信息，如 ``绿色`` 表示已通过，``红色`` 表示未通过，`黄色` 表示跳过，`红色` 表示错误

## 迭代目标

为扫描中页面（SCANNING 阶段）补充两项交互能力：

1. **需求6/7 分类统计面板**：在 `lists_splitter` 与 `scanning_btn_row` 之间插入
   QLabel，用 HTML 富文本显示四类计数与颜色标识（绿/红/黄/红），随扫描进度
   实时刷新，让用户在不切到结果页的情况下掌握扫描整体进展。
2. **需求5 命中文件双击定位**：为 `matched_files_list` 接入 `itemDoubleClicked`
   信号，双击命中项弹出 `QMessageBox.question` 简化详情对话框，提供"打开"/"关闭"
   两个标准按钮，选中"打开"时跨平台定位到文件管理器并选中该文件。

## 改动文件清单

### `src/fuscan/gui/main_window.py`（修改）

#### 新增方法

- `_setup_scan_stats_panel()`：创建 `scan_stats_label`（QLabel），设置居中对齐
  与 RichText 格式，`scanning_layout.insertWidget(1, ...)` 插入到 `lists_splitter`
  与 `scanning_btn_row` 之间，初始化为全零计数。
- `_update_scan_stats(passed, matched, skipped, errors)`：用 HTML 富文本刷新
  QLabel，四类计数用 `<span style="color: ...">` 内联样式着色：
  - 绿色 `#28A745`：已通过（已扫描且未命中且未错误）
  - 红色 `#DC3545`：命中
  - 黄色 `#FFC107`：跳过
  - 红色 `#DC3545`：错误

  颜色标识用内联样式避免引入 QSS 样式表，与项目既有 HTML 富文本风格一致。
- `_open_path_in_explorer(path)`：从 `_on_open_file_location` 提取的公共方法，
  跨平台调用文件管理器定位文件（Windows `explorer /select,`、macOS `open -R`、
  Linux `xdg-open`），失败时弹 `QMessageBox.warning` 不抛异常。
- `_on_matched_file_double_clicked(item)`：扫描中页命中文件列表双击槽。
  解析 `"路径 → 规则名"` 格式（`rsplit(" → ", 1)` 从右侧分割一次，容忍路径中
  含 `" → "` 的极端情况），用 `QMessageBox.question` 静态方法弹简化详情对话框，
  提供"打开"/"关闭"两个标准按钮，选中"打开"时委托 `_open_path_in_explorer` 定位。

#### 修改方法

- `_configure_ui`：在 `_setup_layouts` 之后新增 `self._setup_scan_stats_panel()` 调用。
- `_connect_signals`：新增 `matched_files_list.itemDoubleClicked.connect(
  self._on_matched_file_double_clicked)` 连接。
- `_on_scan`：在 `_switch_stage(WorkflowStage.SCANNING)` 之前新增
  `self._update_scan_stats(0, 0, 0, 0)` 重置统计面板，避免上次扫描残留。
- `_on_scan_progress`：在列表更新节流分支后同步刷新统计面板，
  `passed = max(scanned - matched - errors, 0)` 对负数兜底。
- `_on_open_file_location`：重构为委托 `self._open_path_in_explorer(
  self._detail_current_result.path)`，消除与 `_on_matched_file_double_clicked`
  的 explorer 调用重复。

### `tests/test_gui.py`（修改）

- 顶部 import 块新增 `QListWidgetItem` 与 `QMessageBox` 导入（PySide2/PySide6
  try/except 兼容），新增 `import sys` 供 `monkeypatch.setattr(sys, "platform", ...)`。
- 新增 12 个测试用例（TestScanCallbacks 类内）：
  - `test_setup_scan_stats_panel_initial_zeros`：初始化后面板显示全零计数
  - `test_update_scan_stats_html_content`：HTML 包含四类计数与颜色 hex 值
  - `test_on_scan_progress_updates_scan_stats_panel`：进度回调同步刷新面板，
    passed = scanned - matched - errors
  - `test_on_scan_progress_scan_stats_passed_floor_zero`：scanned < matched + errors
    时 passed 兜底为 0
  - `test_on_scan_resets_scan_stats_panel`：`_on_scan` 启动扫描时重置面板
    （用 _FakeWorker 拦截 ScanWorker 避免启动真实线程）
  - `test_on_matched_file_double_clicked_open_location`：选"打开"调 _open_path_in_explorer
  - `test_on_matched_file_double_clicked_close_no_call`：选"关闭"不调定位
  - `test_on_matched_file_double_clicked_no_arrow_returns_early`：无 `" → "` 直接返回
  - `test_on_matched_file_double_clicked_rsplit_path_with_arrow`：路径含 `" → "`
    时从右侧分割一次
  - `test_open_path_in_explorer_win32`：Windows 调 `explorer /select,` 命令
  - `test_open_path_in_explorer_failure_warns`：Popen 失败时弹 warning 不抛异常
  - `test_on_open_file_location_delegates_to_open_path`：_on_open_file_location
    委托给 _open_path_in_explorer

### `.trae/req/req-09-功能更新.md`（修改）

需求5/6/7 从 `[]` 改为 `[x]`。

## 关键决策与依据

### 需求6/7 实现方案：QLabel + HTML 富文本

用户通过 AskUserQuestion 确认"已处理文件列表"= 已扫描文件分类统计面板（非逐文件
列表）。用 QLabel + HTML 富文本实现而非 QFrame + QHBoxLayout 多 QLabel 方案：

- 避免引入 QFrame/QHBoxLayout 新导入与多个 QLabel 实例
- HTML `<span style="color: ...">` 内联样式与项目既有 RichText 风格一致
- 单个 QLabel 占用空间小，不挤压 `lists_splitter` 的列表区域

### 需求5 交互方案：双击弹出简化详情 + 定位按钮

用户通过 AskUserQuestion 确认交互方式为"双击弹出简化详情+定位按钮"。用
`QMessageBox.question` 静态方法而非自定义 QDialog 实例：

- 静态方法便于测试 mock（`monkeypatch.setattr` 字符串路径）
- 标准 `QMessageBox.Open`/`QMessageBox.Close` 按钮无需自定义文本
- 与项目其他 `QMessageBox.warning`/`QMessageBox.information` 风格一致

### 路径解析：rsplit 而非 split

`matched_files_list` 项格式为 `"路径 → 规则名"`，用 `rsplit(" → ", 1)` 从右侧
分割一次，容忍路径本身含 `" → "` 字符的极端情况（Windows 路径理论上不含 →，
但跨平台场景需稳健）。

### 统计面板节流策略

`_update_scan_stats` 与 `_update_skipped_dirs_list`/`_update_matched_files_list`
共用 0.5 秒节流（`_last_list_update_time`），避免每帧重绘 QLabel HTML。
扫描完成时 `_on_scan_finished` 切到 RESULTS 页，统计面板不可见，最终值是否
更新不影响用户。

### _on_open_file_location 重构

提取 `_open_path_in_explorer(path)` 公共方法，`_on_open_file_location` 与
`_on_matched_file_double_clicked` 共用，消除 explorer 调用重复。现有测试
`test_on_open_file_location_win32` 仍通过（间接覆盖 _open_path_in_explorer）。

## 代码实现情况

### 统计面板创建与更新

```python
def _setup_scan_stats_panel(self) -> None:
    self.scan_stats_label = QLabel()
    self.scan_stats_label.setObjectName("scan_stats_label")
    self.scan_stats_label.setAlignment(Qt.AlignCenter)
    self.scan_stats_label.setTextFormat(Qt.RichText)
    # 插入到 scanning_layout 的 index 1（lists_splitter=0, scanning_btn_row=1→2）
    self.scanning_layout.insertWidget(1, self.scan_stats_label)
    self._update_scan_stats(0, 0, 0, 0)

def _update_scan_stats(self, passed: int, matched: int, skipped: int, errors: int) -> None:
    self.scan_stats_label.setText(
        f'<span style="color: #28A745; font-weight: bold;">已通过 {passed}</span>'
        f" &nbsp;|&nbsp; "
        f'<span style="color: #DC3545; font-weight: bold;">命中 {matched}</span>'
        f" &nbsp;|&nbsp; "
        f'<span style="color: #FFC107; font-weight: bold;">跳过 {skipped}</span>'
        f" &nbsp;|&nbsp; "
        f'<span style="color: #DC3545; font-weight: bold;">错误 {errors}</span>'
    )
```

### 双击槽实现

```python
def _on_matched_file_double_clicked(self, item: QListWidgetItem) -> None:
    text = item.text()
    if " → " not in text:
        return
    file_path_str, rule_name = text.rsplit(" → ", 1)
    reply = QMessageBox.question(
        self,
        "命中详情",
        f"文件路径:\n{file_path_str}\n\n命中规则: {rule_name}",
        QMessageBox.Open | QMessageBox.Close,
        QMessageBox.Close,
    )
    if reply == QMessageBox.Open:
        self._open_path_in_explorer(Path(file_path_str))
```

### 进度回调集成

```python
# _on_scan_progress 中，列表节流后同步刷新统计面板
self._update_skipped_dirs_list(info.skipped_dirs)
self._update_matched_files_list(info.matched_files)
# 同步刷新分类统计面板（需求6/7）：已通过 = 已扫描 - 命中 - 错误
passed = max(info.scanned - info.matched - info.errors, 0)
self._update_scan_stats(passed, info.matched, info.skipped, info.errors)
```

## 测试验证结果

### 门禁检查

- **ruff check**：605 errors（与基线完全一致，无新增违规）
- **ruff format**：79 files already formatted
- **pyrefly**：804 errors（基线 801 + 3 个 `setCurrentItem` overload 错误，
  与基线 `test_on_open_file_location_win32` 行 4546 同模式，PySide2 类型 stub 已知问题）
- **pytest**：1303 passed, 16 deselected, 覆盖率 96.10% ≥ 95%

### 新增测试覆盖

12 个新测试全部通过，覆盖：
- 统计面板初始化、HTML 内容、进度回调集成、负数兜底、扫描启动重置
- 双击槽的 4 种分支（打开/关闭/无箭头/路径含箭头）
- `_open_path_in_explorer` 的 Windows 调用与失败容错
- `_on_open_file_location` 委托验证

## 遗留事项

- 需求8（Splitter 颜色美化）与需求9（结果列表性能优化）留待 iter-44。
- 统计面板在扫描完成时最终值可能因节流未刷新，但因 `_on_scan_finished` 切到
  RESULTS 页面板不可见，不影响用户体验。

## 下一轮计划

iter-44：性能优化与 Splitter 美化（需求8/9）。
