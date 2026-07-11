# GUI 精简整合优化方案

## Context

主窗口当前有约 23 个交互控件，存在功能重复（加载规则/导出/选择路径在按钮和菜单中重复）、死功能（batch_btn 占位符）、操作不便（详情区 6 个按钮拥挤、无右键菜单、无快捷键）等问题。用户要求精简整合、减少按钮、操作更便捷，保持 5 区布局不变，不加工具栏。

## 优化清单

### 1. 删除 10 个冗余/死功能 widget

| widget | 区域 | 原因 |
|--------|------|------|
| `use_builtin_checkbox` | 控制卡 | 已存在于 SettingsDialog |
| `rules_label` | 控制卡 | 状态栏已有 "已加载 X 条规则" |
| `filter_label` | 筛选栏 | 用 placeholder 替代 |
| `rule_filter_label` | 筛选栏 | 去掉文本标签 |
| `group_mode_label` | 筛选栏 | 去掉文本标签 |
| `move_up_btn` / `move_down_btn` / `remove_rule_btn` | 规则 Tab | 移到右键菜单 |
| `detail_locate_btn` | 详情操作栏 | 自动滚动已覆盖 |
| `detail_copy_path_btn` | 详情操作栏 | 移到右键菜单 |
| `detail_open_window_btn` | 详情操作栏 | 移到右键菜单（与双击重复） |
| `batch_btn` | 详情主体 | 死功能 |

### 2. 新增右键菜单

- **result_tree 右键菜单**：复制路径 / 在新窗口打开 / 打开文件位置（复用现有 `_on_copy_path`、`_on_open_in_window`、`_on_open_file_location`）
- **rules_file_list 右键菜单**：上移 / 下移 / 移除（复用现有 `_on_move_rule_up`、`_on_move_rule_down`、`_on_remove_rule`）

### 3. 新增快捷键

- `F3` → 下一条命中
- `Shift+F3` → 上一条命中
- `Delete`（rules_file_list 聚焦时）→ 移除规则文件

### 4. 新增 `_set_use_builtin(enabled)` 方法

替代原 checkbox 的 `stateChanged` 散落逻辑，`_on_settings` 和测试统一调用。

## 实施步骤

### 步骤 1：修改 `main_window.ui`

- 删除上述 10 个 widget 及其所在 layout item
- 给 `rule_filter_combo` 添加 tooltip "按规则筛选"，`group_mode_combo` 添加 tooltip "分组模式"
- `rules_btn_row` layout 仅保留 `edit_rule_btn`
- `detail_nonempty_action_layout` 仅保留 prev/next/nav_label/spacer/open_location
- `detail_export_row` 仅保留 spacer + export_btn
- `filter_layout` 仅保留 path_filter_input + rule_filter_combo + group_mode_combo

### 步骤 2：重新编译 _ui.py

```bash
pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py
```

### 步骤 3：修改 `main_window.py`

**导入新增**：`QMenu`(QtWidgets)、`QShortcut`(QtWidgets)、`QKeySequence`(QtGui)

**`_bind_widgets` 删除 9 行**：rules_label、use_builtin_checkbox、move_up_btn、move_down_btn、remove_rule_btn、batch_btn、detail_locate_btn、detail_copy_path_btn、detail_open_window_btn

**`_configure_ui` 删除 8 行信号连接**：use_builtin_checkbox.stateChanged、move_up/down/remove.clicked、batch_btn.clicked、detail_locate_btn.clicked、detail_copy_path_btn.clicked、detail_open_window_btn.clicked

**`_configure_ui` 调整 filter_layout stretch**（6 项 → 3 项）：
```python
ui.filter_layout.setStretch(0, 2)  # path_filter_input
ui.filter_layout.setStretch(1, 1)  # rule_filter_combo
ui.filter_layout.setStretch(2, 1)  # group_mode_combo
```

**新增方法**：
- `_setup_context_menus()`：为 result_tree 和 rules_file_list 设置 CustomContextMenu 策略
- `_on_result_tree_context_menu(pos)`：创建含 3 个 action 的 QMenu
- `_on_rules_file_list_context_menu(pos)`：创建含 3 个 action 的 QMenu
- `_setup_shortcuts()`：创建 F3/Shift+F3/Delete 三个 QShortcut
- `_set_use_builtin(enabled)`：统一设置 use_builtin 并刷新规则

**删除方法**：`_on_toggle_builtin`、`_on_batch_process`、`_on_locate_hit`、`_build_rules_label`

**修改方法**：
- `_apply_config`：删除 checkbox 同步，仅设 `self._use_builtin = self._config.use_builtin`
- `_on_settings`：用 `_set_use_builtin` 替代 checkbox 同步，删除 rules_label 更新
- `_init_rules`：删除 `_rules_label.setText` 调用
- `_on_load_rules`：删除 `_rules_label.setText` 调用
- `_reload_and_refresh`：删除 `_rules_label.setText` 调用
- `_update_detail_nav_label`：删除 `_detail_locate_btn.setEnabled` 调用

### 步骤 4：修改 `styles.qss`

第 226-242 行：移除 `detail_locate_btn`、`detail_copy_path_btn`、`detail_open_window_btn`、`batch_btn` 的选择器，仅保留 `detail_prev_btn`、`detail_next_btn`、`detail_open_location_btn`。

### 步骤 5：修改 `test_gui.py`

- 替换约 30 处 `_use_builtin_checkbox.setChecked(X)` → `_set_use_builtin(X)`
- 替换约 7 处 `_rules_label.text()` 断言 → 检查 `_use_builtin` 或 `_rules_file_list.count()`
- 删除 2 处 `_detail_locate_btn` 断言
- 删除 3 个废弃测试（batch_process、locate_hit、build_rules_label）
- 新增 6 个测试：context menu action 列表、shortcut 触发、_set_use_builtin

### 步骤 6：验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

## 关键文件

- `src/fuscan/gui/main_window.ui` — 删除 10 个 widget，调整 layout
- `src/fuscan/gui/main_window_ui.py` — pyside2-uic 重新编译
- `src/fuscan/gui/main_window.py` — 核心修改：删除绑定/连接/方法，新增 context menu/shortcut/_set_use_builtin
- `src/fuscan/gui/styles.qss` — 移除已删除按钮的 QSS 选择器
- `tests/test_gui.py` — 替换约 40 处引用，删除 3 个测试，新增 6 个测试

## 风险

1. **filter_layout 索引偏移**：删除 3 个 label 后 stretch 索引必须同步调整
2. **Delete 键全局冲突**：QShortcut 以 rules_file_list 为 parent，仅聚焦时生效
3. **覆盖率下降**：新增的 context menu/shortcut 方法需有对应测试覆盖
