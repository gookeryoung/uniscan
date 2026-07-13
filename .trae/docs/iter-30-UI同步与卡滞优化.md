# iter-30 UI 同步与扫描卡滞优化

## 迭代目标

1. 同步代码到 UI 文件，便于通过 Qt Designer 调整设计。
2. 清理无效的文件，简化代码。
3. 优化扫描过程中点击设置卡滞问题。

## 需求确认

- UI 同步范围：全部 3 个 UI 文件（main_window.ui + detail_dialog.ui + rule_editor.ui）
- 旧文档处理：直接删除 iter-01~24，保留最近 iter-25~29

## 改动文件清单

### 删除

- `src/fuscan/assets/icons/back.svg`：无任何代码引用的无效图标资源（grep `_ICON_BACK`/`back.svg` 无匹配）。
- `.trae/docs/iter-01~iter-24`（15 个文件）：rule-01 要求每 5 次迭代清理归档；经验已沉淀在 `project_memory.md` 和 skills 文件。

### 修改

- `src/fuscan/gui/main_window.py`：实现 `_on_scan_progress` 增量更新 + 独立节流，消除扫描中点击设置卡滞。
  - imports 新增 `import time`。
  - `__init__` 新增增量更新状态变量：
    - `_last_skipped_dirs: tuple[str, ...] = ()`
    - `_last_matched_files: tuple[tuple[str, str], ...] = ()`
    - `_last_list_update_time: float = -1.0`（初始 -1.0 确保首次回调不被节流）
  - `_on_scan` 中重置增量状态。
  - 重写 `_on_scan_progress`：进度条/当前文件/状态栏高频更新，列表更新独立节流 0.5s。
  - 新增 `_update_skipped_dirs_list` 方法：前缀对比增量 append，否则全量重建用 `addItems` 批量。
  - 新增 `_update_matched_files_list` 方法：同上逻辑，格式 `"路径 → 规则名"`。
- `src/fuscan/gui/detail_dialog.ui`：同步匹配 `detail_dialog_ui.py`：
  - `info_label` 改名为 `hit_info_label`。
  - 移除内联 styleSheet（由 QSS 托管）。
- `src/fuscan/gui/main_window.ui`：完整重写（1363 行 XML）匹配 `main_window_ui.py` 新结构：
  - 新增 `header_bar`（QFrame）含 `tab_scan_btn`/`tab_rules_btn`/`tab_history_btn`（checkable）+ `header_spacer` + `settings_btn` + `about_btn`。
  - 新增 `tab_stack`（QStackedWidget）含 3 个 Tab：`scan_tab`/`rules_tab`/`history_tab`。
  - `scan_tab` 含 `sidebar_splitter`（QSplitter）→ `sidebar`（QListWidget, min160/max280）+ `main_stack`。
  - `main_stack` 含 `setup_page`/`scanning_page`/`results_page`。
  - `setup_page`：`target_group` + `setup_action_bar`（`setup_btn_leading_spacer` + `view_results_btn` + `scan_btn`）。
  - `scanning_page`：移除 `progress`/`current_file_label`/`stats_group`，仅保留 `scanning_title_label` + `lists_splitter` + `scanning_btn_row`。
  - `rules_tab`：`rules_group`（从 setup_page 移入）。
  - `history_tab`：`history_label` + `history_list`。
  - `results_page` 及 menubar/actions 从原 .ui 保留。
- `tests/test_gui.py`：在 `TestScanCallbacks` 类中新增 4 个测试：
  - `test_on_scan_progress_throttles_list_update`：连续两次 0.1s 内回调，第二次列表不更新。
  - `test_on_scan_progress_incremental_append_skipped_dirs`：前缀匹配时增量 append，不 clear。
  - `test_on_scan_progress_full_rebuild_on_truncation`：滚动截断时全量重建。
  - `test_on_scan_progress_incremental_append_matched_files`：命中文件列表增量 append。
  - 测试用 `monkeypatch.setattr(time_mod, "perf_counter", lambda: t[0])` 控制时间。

### 检查（无需改动）

- `src/fuscan/gui/rule_editor.ui`：已与 `rule_editor_ui.py` 同步，无需改动。
- `src/fuscan/gui/settings_dialog.py`：`__init__` 仅构建 UI + 加载配置（内存操作），非卡滞根因。

## 关键决策与依据

### 卡滞根因定位

`_on_scan_progress` 每次进度回调（间隔 0.15s）全量 `clear()` + 逐条 `addItem()` 重添列表，列表项可能多达 500 条，O(N) 操作阻塞主线程。扫描运行中点击设置按钮，事件循环被列表更新阻塞，导致明显卡滞。

### 优化方案

- **进度条/当前文件/状态栏**：保留高频更新（每 0.15s），这些是轻量文本设置。
- **列表更新**：独立节流（0.5s 间隔），并改用增量 append：
  - 若新列表是旧列表的扩展（旧列表是新列表前缀），只 append 新增尾部条目。
  - 否则（滚动截断或内容变化）全量重建用 `addItems` 批量添加。
- **初始值陷阱**：`time.perf_counter()` 在新进程可能返回 `0.017` 等小值，若 `_last_list_update_time` 初始为 `0.0`，首次回调会被节流跳过。改用 `-1.0` 初始值确保首次不被节流。

### UI 文件同步策略

`main_window.ui` 严重落后于 `main_window_ui.py`（旧结构含 progress/stats_group，新结构已迁移至 tab_stack + sidebar），需完整重写以支持 Qt Designer 后续编辑。`detail_dialog.ui` 仅需局部同步（重命名 + 移除内联样式）。`rule_editor.ui` 已同步无需改动。

### 旧文档清理

按 rule-01 要求每 5 次迭代清理归档，删除 iter-01~24（共 15 个文件，iter-25~29 保留）。经验已沉淀在 `project_memory.md` 和 skills 文件，删除不影响知识传承。

## 验证结果

- `uv run ruff check src tests`：All checks passed
- `uv run ruff format --check src tests`：70 files already formatted
- `uv run pyrefly check`：0 errors
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：981 passed, coverage 96.25%

## 遗留事项

无。所有需求闭环完成，门禁全部通过。
