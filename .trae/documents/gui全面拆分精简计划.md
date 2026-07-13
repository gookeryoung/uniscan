# GUI 全面拆分与精简计划

## 执行进度（截至本会话）

### 已完成

- **Phase 1（对话框多继承）**：已完成并提交 `a11d51d`。`detail_dialog.py`、`rule_editor.py` 均改为多继承，`_bind_widgets` 移除，99 处测试引用已更新。
- **Phase 2 源码重构（部分）**：`main_window.py` 已改为 `class MainWindow(QMainWindow, Ui_MainWindow)`，`_bind_widgets` 已移除，大部分 UI 部件名已去下划线。`test_gui.py` 中 `window._ui.` 已全部移除（0 处）。

### 待完成（本会话剩余工作）

#### Phase 2 收尾：源码遗漏修复 + 测试批量更新

**源码遗漏（必须先修）**——main_window.py 中以下 UI 部件名未改完：

| 当前（错误） | 应改为 | 出现行 |
|--------------|--------|--------|
| `self._detail_hits_table` | `self.detail_hits_table` | 423, 424, 425, 426, 1355, 1393, 1399, 1402, 1405, 1413, 1417 |
| `self._load_rules_btn` | `self.load_rules_btn` | 511, 567 |
| `self._load_rules_action` | `self.load_rules_action` | 512, 586, 745 |
| `self._edit_rule_btn` | `self.edit_rule_btn` | 515, 573 |
| `self._edit_rules_action` | `self.edit_rules_action` | 516, 587, 746 |
| `self._rules_tree` | `self.rules_tree` | 1626, 1636 |
| `self.__detail_open_location_btn`（双下划线 bug） | `self.detail_open_location_btn` | 578 |
| `self.__skipped_dirs_list`（双下划线 bug） | `self.skipped_dirs_list` | 1059, 1201, 1205, 1208, 1209, 1211, 1212 |

修复方式：对每个部件名用 `Edit replace_all` 批量替换。双下划线需先替换 `self.__xxx` → `self.xxx`。

**测试批量更新**——test_gui.py 中约 319 处需改：

- 38 个 UI 部件 `window._xxx` → `window.xxx`（如 `window._result_tree` 58 处、`window._scan_btn` 26 处等，详见下方完整清单）
- 1 个特殊改名 `window._splitter` → `window.results_splitter`（1 处）
- 6 处 `window._ui` → `window`（`hasattr(window._ui, "xxx")` 断言，第 1411, 1475, 1476, 1486, 1487, 1488 行）

**不改的引用**（业务方法/状态属性，保持下划线）：
- 业务方法：`window._on_xxx`、`window._populate_results`、`window._switch_stage`、`window._set_use_builtin`、`window._refresh_xxx`、`window._update_xxx`、`window._reload_xxx`、`window._build_xxx`、`window._pause_scan`、`window._resume_scan`、`window._cleanup_worker`、`window._detail_show_result`、`window._detail_clear`、`window._reset_scan_ui`、`window._format_report`（类方法）、`window._shortcut_prev/next/remove_rule`、`window._add_scan_path_history`、`window._build_scan_roots`、`window._reload_and_refresh`、`window._scroll_to_current_detail_hit`、`window._highlight_current_detail_hit`、`window._update_detail_nav_label`
- 业务状态属性：`window._config`、`window._ruleset`、`window._rules_paths`、`window._scan_state`、`window._worker`、`window._cache`、`window._scan_root`、`window._last_report`、`window._scan_mode`、`window._drive_buttons`、`window._workflow_stage`、`window._detail_hit_positions`、`window._detail_current_hit_index`、`window._detail_current_result`、`window._use_builtin`、`window._selected_drive`、`window._header_button_group`

**测试改动完整清单**（按出现次数降序，共 319 处）：

| 旧引用 | 新引用 | 处数 |
|--------|--------|------|
| `window._result_tree` | `window.result_tree` | 58 |
| `window._scan_btn` | `window.scan_btn` | 26 |
| `window._rules_file_list` | `window.rules_file_list` | 15 |
| `window._main_stack` | `window.main_stack` | 14 |
| `window._group_mode_combo` | `window.group_mode_combo` | 14 |
| `window._rules_tree` | `window.rules_tree` | 14 |
| `window._skipped_dirs_list` | `window.skipped_dirs_list` | 12 |
| `window._detail_hits_table` | `window.detail_hits_table` | 12 |
| `window._pause_resume_btn` | `window.pause_resume_btn` | 11 |
| `window._scan_mode_combo` | `window.scan_mode_combo` | 10 |
| `window._progress` | `window.progress` | 10 |
| `window._rule_filter_combo` | `window.rule_filter_combo` | 10 |
| `window._path_combo` | `window.path_combo` | 9 |
| `window._detail_action_stack` | `window.detail_action_stack` | 7 |
| `window._stats_label` | `window.stats_label` | 7 |
| `window._path_filter_input` | `window.path_filter_input` | 7 |
| `window._detail_nav_label` | `window.detail_nav_label` | 7 |
| `window._view_results_btn` | `window.view_results_btn` | 7 |
| `window._matched_files_list` | `window.matched_files_list` | 6 |
| `window._sidebar` | `window.sidebar` | 6 |
| `window._detail_main_stack` | `window.detail_main_stack` | 6 |
| `window._ui` | `window` | 6 |
| `window._current_file_label` | `window.current_file_label` | 5 |
| `window._scan_action` | `window.scan_action` | 4 |
| `window._export_json_action` | `window.export_json_action` | 3 |
| `window._export_csv_action` | `window.export_csv_action` | 3 |
| `window._rescan_btn` | `window.rescan_btn` | 3 |
| `window._settings_action` | `window.settings_action` | 3 |
| `window._edit_rule_btn` | `window.edit_rule_btn` | 3 |
| `window._tab_stack` | `window.tab_stack` | 3 |
| `window._target_stack` | `window.target_stack` | 3 |
| `window._detail_preview` | `window.detail_preview` | 3 |
| `window._detail_prev_btn` | `window.detail_prev_btn` | 2 |
| `window._detail_next_btn` | `window.detail_next_btn` | 2 |
| `window._edit_rules_action` | `window.edit_rules_action` | 2 |
| `window._detail_info_label` | `window.detail_info_label` | 2 |
| `window._splitter` | `window.results_splitter` | 1 |
| `window._cancel_btn` | `window.cancel_btn` | 1 |
| `window._load_rules_action` | `window.load_rules_action` | 1 |
| `window._export_btn` | `window.export_btn` | 1 |

**注意**：`window._load_rules_btn` 在测试中是否出现需确认（源码中有但测试统计未列出，可能 0 处）。

#### Phase 2 验证与提交

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95
```

通过后提交：`refactor: main_window 改为多继承模式，移除 _bind_widgets`

---

## 背景与目标

main_window.py 2032 行、main_window_ui.py 780 行过于臃肿。3 个 GUI 模块（main_window / detail_dialog / rule_editor）均采用组合模式（`self._ui = Ui_X()`）+ `_bind_widgets` 冗余绑定（main_window 77 行、detail_dialog 6 行、rule_editor 2 行）。settings_dialog.py 已改为多继承模式（`class X(QDialog, Ui_X)`）作为参考样板。

**用户要求**：参照 settings_dialog 简化思路，全面拆分含 .ui 文件，312+99 处测试同步改动。

**文件清单**（当前规模）：

| 文件 | 行数 | 角色 |
|------|------|------|
| settings_dialog.py | 75 | 参考样板（已多继承） |
| settings_dialog.ui | 353 | 参考样板 |
| main_window.py | 2032 | 主窗口业务逻辑（待精简） |
| main_window_ui.py | 780 | 主窗口 UI 装配（待拆分） |
| main_window.ui | 1341 | 主窗口 XML（待拆分） |
| detail_dialog.py | 438 | 详情对话框（待多继承） |
| detail_dialog.ui | 182 | 详情对话框 XML |
| rule_editor.py | 153 | 规则编辑器（待多继承） |
| rule_editor.ui | 116 | 规则编辑器 XML |
| test_gui.py | 5620 | 测试（960 处引用待改） |

## 测试引用统计

- `window._xxx`：856 处（含 UI 部件属性 + 业务方法调用，仅 UI 部件属性需改）
- `dialog._xxx`：99 处（detail_dialog + rule_editor，全部需改）
- `window._ui.xxx`：5 处（setup_action_bar, setup_btn_row, file_menu, help_menu, about_action，全部需改）
- 合计需改动约 405 处（312 UI 部件 + 99 对话框 + 5 _ui 显式访问，其余 `window._xxx` 是业务方法/状态属性不改）

## 阶段 1：对话框统一多继承（低风险）

### detail_dialog.py

- 改为 `class HitDetailDialog(QDialog, Ui_HitDetailDialog)` 多继承
- 移除 `self._ui = Ui_HitDetailDialog()` 与 `_bind_widgets` 方法
- 部件属性名归一化（与 ui 中实际名称对齐）：

| 旧属性 | 新属性（=ui 名） |
|--------|------------------|
| `self._info_label` | `self.hit_info_label` |
| `self._hits_table` | `self.hits_table` |
| `self._preview` | `self.preview` |
| `self._prev_btn` | `self.prev_btn` |
| `self._next_btn` | `self.next_btn` |
| `self._nav_label` | `self.nav_label` |

- 业务状态属性保持不变：`self._result`, `self._hit_positions`, `self._current_hit_index`
- `_configure_ui` 内 `self._ui.main_layout.setStretch(...)` → `self.main_layout.setStretch(...)`

### rule_editor.py

- 改为 `class RuleEditorDialog(QDialog, Ui_RuleEditorDialog)` 多继承
- 移除 `self._ui` 与 `_bind_widgets`
- `self._file_combo` → `self.file_combo`，`self._editor` → `self.editor`
- 业务状态属性保持不变：`self._rules_paths`
- `_configure_ui` 内 `ui.reload_btn.clicked.connect` → `self.reload_btn.clicked.connect`，`ui.save_btn` → `self.save_btn`，`ui.empty_label` → `self.empty_label`，`ui.main_layout` → `self.main_layout`

### 测试更新（99 处）

- `dialog._info_label` → `dialog.hit_info_label`
- `dialog._hits_table` → `dialog.hits_table`
- `dialog._preview` → `dialog.preview`
- `dialog._prev_btn` → `dialog.prev_btn`
- `dialog._next_btn` → `dialog.next_btn`
- `dialog._nav_label` → `dialog.nav_label`
- `dialog._file_combo` → `dialog.file_combo`
- `dialog._editor` → `dialog.editor`

### 验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95
```

通过后提交：`refactor: detail_dialog/rule_editor 改为多继承模式，移除 _bind_widgets`

## 阶段 2：main_window 改多继承（中风险）

### main_window.py

- 改为 `class MainWindow(QMainWindow, Ui_MainWindow)` 多继承
- 移除 `self._ui = Ui_MainWindow()` 与 `_bind_widgets` 方法（77 行）
- UI 部件属性名归一化（去掉下划线前缀，与 ui 名对齐）：

| 旧属性 | 新属性 |
|--------|--------|
| `self._tab_stack` | `self.tab_stack` |
| `self._sidebar` | `self.sidebar` |
| `self._tab_scan_btn` | `self.tab_scan_btn` |
| `self._tab_rules_btn` | `self.tab_rules_btn` |
| `self._tab_history_btn` | `self.tab_history_btn` |
| `self._settings_btn` | `self.settings_btn` |
| `self._about_btn` | `self.about_btn` |
| `self._sidebar_splitter` | `self.sidebar_splitter` |
| `self._main_stack` | `self.main_stack` |
| `self._scan_btn` | `self.scan_btn` |
| `self._view_results_btn` | `self.view_results_btn` |
| `self._pause_resume_btn` | `self.pause_resume_btn` |
| `self._cancel_btn` | `self.cancel_btn` |
| `self._rescan_btn` | `self.rescan_btn` |
| `self._scan_mode_combo` | `self.scan_mode_combo` |
| `self._target_stack` | `self.target_stack` |
| `self._drive_buttons_layout` | `self.drive_buttons_layout` |
| `self._path_combo` | `self.path_combo` |
| `self._select_path_btn` | `self.select_path_btn` |
| `self._history_list` | `self.history_list` |
| `self._load_rules_btn` | `self.load_rules_btn` |
| `self._rules_file_list` | `self.rules_file_list` |
| `self._edit_rule_btn` | `self.edit_rule_btn` |
| `self._rules_tree` | `self.rules_tree` |
| `self._skipped_dirs_list` | `self.skipped_dirs_list` |
| `self._matched_files_list` | `self.matched_files_list` |
| `self._splitter` | `self.results_splitter`（注意：ui 名是 results_splitter，旧绑定名不一致） |
| `self._result_tree` | `self.result_tree` |
| `self._path_filter_input` | `self.path_filter_input` |
| `self._rule_filter_combo` | `self.rule_filter_combo` |
| `self._group_mode_combo` | `self.group_mode_combo` |
| `self._note_edit` | `self.note_edit` |
| `self._export_btn` | `self.export_btn` |
| `self._detail_action_stack` | `self.detail_action_stack` |
| `self._detail_main_stack` | `self.detail_main_stack` |
| `self._detail_prev_btn` | `self.detail_prev_btn` |
| `self._detail_next_btn` | `self.detail_next_btn` |
| `self._detail_nav_label` | `self.detail_nav_label` |
| `self._detail_open_location_btn` | `self.detail_open_location_btn` |
| `self._detail_info_label` | `self.detail_info_label` |
| `self._detail_hits_table` | `self.detail_hits_table` |
| `self._detail_preview` | `self.detail_preview` |
| `self._scan_action` | `self.scan_action` |
| `self._load_rules_action` | `self.load_rules_action` |
| `self._edit_rules_action` | `self.edit_rules_action` |
| `self._export_csv_action` | `self.export_csv_action` |
| `self._export_json_action` | `self.export_json_action` |
| `self._settings_action` | `self.settings_action` |

- **状态栏部件**（在 `_configure_ui` 中创建，非 ui 文件来源）属性名也去掉下划线：
  - `self._stats_label` → `self.stats_label`
  - `self._current_file_label` → `self.current_file_label`
  - `self._progress` → `self.progress`

- **业务状态属性保持下划线**（非 UI 部件）：
  - `self._config`, `self._scan_state`, `self._worker`, `self._stage`, `self._results`, `self._current_result`, `self._ruleset`, `self._rules_paths`, `self._detail_hit_positions`, `self._detail_current_hit_index`, `self._detail_current_result`, `self._scan_history`, `self._drive_button_group`, `self._drive_buttons`, `self._selected_drive`, `self._cache`, `self._last_skipped_dirs`, `self._last_matched_files`, `self._last_list_update_time`

### 测试更新（317 处）

- 312 处 `window._xxx`（UI 部件）→ `window.xxx`
- 5 处 `window._ui.xxx` → `window.xxx`
- 业务方法调用如 `window._on_scan_start()` 等保持不变（方法名仍带下划线）

### 验证

全套门禁通过后提交：`refactor: main_window 改为多继承模式，移除 _bind_widgets`

## 阶段 3：拆分 main_window_ui.py 为多个页面 UI 文件（高风险）

### 拆分策略：手工实例化（不用 promoted widget）

不使用 Qt Designer 的 promoted widget 机制（增加复杂度且 pyside-uic 工具链易出问题）。改为：
- 每个 page.ui 文件独立设计页面内部结构
- 父 main_window.ui 中只保留空容器（QWidget 占位）
- MainWindow.__init__ 中实例化各 Page 类并 `addWidget` 到对应容器

### 文件结构

```
src/fuscan/gui/
├── main_window.py              # 主窗口业务逻辑（精简后）
├── main_window_ui.py           # 仅保留：actions, header_bar, tab_stack, sidebar, sidebar_splitter, main_stack 容器, menubar
├── main_window.ui              # 对应 XML，移除页面内部结构
├── pages/
│   ├── __init__.py
│   ├── scan_setup_page.py      # ScanSetupPage(QWidget, Ui_ScanSetupPage)
│   ├── scan_setup_page_ui.py   # Ui_ScanSetupPage
│   ├── scan_setup_page.ui      # XML
│   ├── scanning_page.py        # ScanningPage(QWidget, Ui_ScanningPage)
│   ├── scanning_page_ui.py     # Ui_ScanningPage
│   ├── scanning_page.ui
│   ├── results_page.py         # ResultsPage(QWidget, Ui_ResultsPage)
│   ├── results_page_ui.py      # Ui_ResultsPage
│   ├── results_page.ui
│   ├── rules_tab.py            # RulesTab(QWidget, Ui_RulesTab)
│   ├── rules_tab_ui.py         # Ui_RulesTab
│   ├── rules_tab.ui
│   ├── history_tab.py          # HistoryTab(QWidget, Ui_HistoryTab)
│   ├── history_tab_ui.py       # Ui_HistoryTab
│   └── history_tab.ui
```

### 各页面部件归属

| 页面类 | ui 文件根部件 | 包含部件 |
|--------|--------------|----------|
| ScanSetupPage | QWidget | target_group, scan_mode_combo, target_stack, full_scan_page/label, drive_select_page/drive_buttons_layout, folder_select_page/path_combo/select_path_btn, setup_action_bar, view_results_btn, scan_btn |
| ScanningPage | QWidget | lists_splitter, skipped_dirs_group/list, matched_files_group/list, scanning_btn_row, pause_resume_btn, cancel_btn |
| ResultsPage | QWidget | results_top_bar, rescan_btn, export_btn, results_splitter, results_list_area, filter_bar, path_filter_input, rule_filter_combo, group_mode_combo, result_tree, detail_area, detail_action_stack, detail_main_stack, detail_*（全部详情子部件）, note_edit |
| RulesTab | QWidget | rules_group, load_rules_btn, edit_rule_btn, rules_file_label, rules_file_list, rules_tree |
| HistoryTab | QWidget | history_label, history_list |

### main_window_ui.py 保留内容

- 9 个 QAction
- header_bar（tab_scan_btn, tab_rules_btn, tab_history_btn, settings_btn, about_btn）
- tab_stack 容器（3 个空 QWidget：scan_tab/rules_tab/history_tab 作为占位）
- scan_tab 内：sidebar_splitter, sidebar, main_stack（空容器，等待页面 addWidget）
- menubar
- retranslateUi（仅主窗口级文本，页面文本由各 Page.retranslateUi 负责）

### MainWindow 初始化页面

```python
def __init__(self, ...):
    super().__init__(parent)
    self.setupUi(self)  # 装配主窗口骨架
    # 实例化各页面并加入 main_stack / tab_stack
    self.setup_page = ScanSetupPage()
    self.main_stack.addWidget(self.setup_page)
    self.scanning_page = ScanningPage()
    self.main_stack.addWidget(self.scanning_page)
    self.results_page = ResultsPage()
    self.main_stack.addWidget(self.results_page)
    self.rules_tab_page = RulesTab()
    self.tab_stack.addWidget(self.rules_tab_page)
    self.history_tab_page = HistoryTab()
    self.tab_stack.addWidget(self.history_tab_page)
    self._configure_ui()
    self._apply_config()
    self._init_rules()
```

### 部件访问路径变化

主窗口业务方法访问页面内部件需通过页面实例：
- `self.scan_btn` → `self.setup_page.scan_btn`
- `self.view_results_btn` → `self.setup_page.view_results_btn`
- `self.scan_mode_combo` → `self.setup_page.scan_mode_combo`
- `self.target_stack` → `self.setup_page.target_stack`
- `self.drive_buttons_layout` → `self.setup_page.drive_buttons_layout`
- `self.path_combo` → `self.setup_page.path_combo`
- `self.select_path_btn` → `self.setup_page.select_path_btn`
- `self.skipped_dirs_list` → `self.scanning_page.skipped_dirs_list`
- `self.matched_files_list` → `self.scanning_page.matched_files_list`
- `self.pause_resume_btn` → `self.scanning_page.pause_resume_btn`
- `self.cancel_btn` → `self.scanning_page.cancel_btn`
- `self.rescan_btn` → `self.results_page.rescan_btn`
- `self.export_btn` → `self.results_page.export_btn`
- `self.path_filter_input` → `self.results_page.path_filter_input`
- `self.rule_filter_combo` → `self.results_page.rule_filter_combo`
- `self.group_mode_combo` → `self.results_page.group_mode_combo`
- `self.result_tree` → `self.results_page.result_tree`
- `self.results_splitter` → `self.results_page.results_splitter`
- `self.detail_action_stack` → `self.results_page.detail_action_stack`
- `self.detail_main_stack` → `self.results_page.detail_main_stack`
- `self.detail_prev_btn` → `self.results_page.detail_prev_btn`
- `self.detail_next_btn` → `self.results_page.detail_next_btn`
- `self.detail_nav_label` → `self.results_page.detail_nav_label`
- `self.detail_open_location_btn` → `self.results_page.detail_open_location_btn`
- `self.detail_info_label` → `self.results_page.detail_info_label`
- `self.detail_hits_table` → `self.results_page.detail_hits_table`
- `self.detail_preview` → `self.results_page.detail_preview`
- `self.note_edit` → `self.results_page.note_edit`
- `self.load_rules_btn` → `self.rules_tab_page.load_rules_btn`
- `self.rules_file_list` → `self.rules_tab_page.rules_file_list`
- `self.edit_rule_btn` → `self.rules_tab_page.edit_rule_btn`
- `self.rules_tree` → `self.rules_tab_page.rules_tree`
- `self.history_list` → `self.history_tab_page.history_list`

**保留在 MainWindow 的部件**（不迁移）：
- tab_stack, sidebar, sidebar_splitter, main_stack
- tab_scan_btn, tab_rules_btn, tab_history_btn, settings_btn, about_btn
- 9 个 QAction
- 状态栏部件（stats_label, current_file_label, progress）

### 测试更新（317 处再次调整）

阶段 2 已将 `window._xxx` 改为 `window.xxx`，阶段 3 需进一步改为 `window.<page>.xxx`。建议用脚本批量替换。

### 验证

全套门禁通过后提交：`refactor: 拆分 main_window_ui 为 5 个独立页面 UI 文件`

## 阶段 4：main_window.py 业务逻辑拆分（可选）

如果阶段 3 后 main_window.py 仍 >800 行，按功能拆分为 mixin：

| Mixin 文件 | 职责 |
|------------|------|
| main_window_scan.py | ScanMixin：扫描流程（_start_scan, _on_scan_progress, _pause_resume_scan, _cancel_scan 等） |
| main_window_results.py | ResultsMixin：结果展示（_populate_results, _refresh_result_tree, _apply_filters 等） |
| main_window_detail.py | DetailMixin：详情区（_show_detail, _populate_detail_*, _on_detail_nav 等） |
| main_window_rules.py | RulesMixin：规则管理（_load_rules, _edit_rules, _refresh_rules_tree 等） |

```python
class MainWindow(QMainWindow, Ui_MainWindow, ScanMixin, ResultsMixin, DetailMixin, RulesMixin):
    ...
```

**决策标准**：阶段 3 完成后测量 main_window.py 行数，>800 行才执行阶段 4。

## 关键约束

1. **.ui 文件同步**：每个新页面 .ui 文件须与 _ui.py 手工同步（项目无自动 uic 工具链）
2. **PySide2/6 双兼容**：所有新文件须 try/except 导入，按 settings_dialog_ui.py 现有模式
3. **覆盖率**：不得低于 95%（当前 96.12%），新增页面类须有基础测试
4. **测试属性映射**：阶段 2 与阶段 3 各需批量替换测试引用，建议用 PowerShell 脚本一次性完成
5. **不修改业务逻辑**：本迭代仅做结构重构，不改变功能行为
6. **每阶段独立提交**：便于回滚，提交信息遵循 rule-09 中文风格

## 实施顺序与回滚点

1. 阶段 1（对话框多继承）→ 门禁 → 提交 → **回滚点 1**
2. 阶段 2（main_window 多继承）→ 门禁 → 提交 → **回滚点 2**
3. 阶段 3（UI 文件拆分）→ 门禁 → 提交 → **回滚点 3**
4. 阶段 4（业务逻辑 mixin，条件触发）→ 门禁 → 提交

## 风险评估

| 阶段 | 风险 | 主因 | 缓解 |
|------|------|------|------|
| 1 | 低 | 改动小、模式已有参考 | 直接照搬 settings_dialog 模式 |
| 2 | 中 | 312 处测试引用批量改 | 用脚本替换 + 全套门禁验证 |
| 3 | 高 | UI 文件拆分易遗漏部件、页面间信号槽连接 | 先列全部件清单，逐页迁移后跑全套测试 |
| 4 | 中 | mixin 破坏类内聚 | 仅在必要时执行，保持 mixin 内方法自洽 |
