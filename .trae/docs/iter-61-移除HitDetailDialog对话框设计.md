# iter-61：移除 HitDetailDialog 对话框设计

## 需求清单

1. 反复打开 HitDetailDialog 对话框依然卡顿，iter-60 LRU 缓存方案未根本解决
2. 右侧栏 DetailPanel 已提供完整的详情功能（文件信息、命中表、内容预览、关键词高亮、命中导航）
3. 完全移除对话框设计并优化整合代码

## 迭代目标

- 删除 HitDetailDialog 相关的 3 个文件（.py 实现、_ui.py、.ui）
- 移除源码中仅为对话框服务的冗余设计：`result_activated` 信号、`open_in_window_requested` 信号、双击处理、"在新窗口打开"右键菜单项
- 同步清理测试：删除对话框测试、重命名辅助测试、迁移位置高亮测试改用 DetailPanel
- 全门禁通过（ruff/pyrefly/pytest/coverage）

## 改动文件清单

### 删除文件

| 文件 | 说明 |
|------|------|
| `src/fuscan/gui/detail_dialog.py` | HitDetailDialog（QDialog 子类）实现 |
| `src/fuscan/gui/detail_dialog_ui.py` | uic 生成的 `Ui_HitDetailDialog` |
| `src/fuscan/gui/detail_dialog.ui` | Qt Designer XML 源 |

### 修改文件

| 文件 | 说明 |
|------|------|
| `src/fuscan/gui/main_window.py` | 移除 HitDetailDialog 导入；移除 `_on_result_activated`、`_on_open_in_window_requested` 方法；移除 `result_activated` 与 `open_in_window_requested` 信号连接；`_on_result_tree_context_menu` 移除"在新窗口打开"菜单项；docstring 三个信号 → 两个信号 |
| `src/fuscan/gui/detail_panel.py` | 移除 `open_in_window_requested = Signal(object)` 与 `open_in_window` 方法；docstring 三个信号 → 两个信号；保留 `extract_content_cached` 导入（DetailPanel 仍使用缓存） |
| `src/fuscan/gui/result_tree.py` | 移除 `result_activated = Signal(object)` 信号、`doubleClicked` 连接与 `_handle_double_clicked` 方法；移除 `QModelIndex` 导入；docstring 选中/双击/右键 → 选中/右键 |
| `src/fuscan/gui/styles.qss` | 移除 HitDetailDialog 样式块（`#hit_info_label` / `#hit_preview` / `#hit_hits_table`，约 24 行） |
| `src/fuscan/gui/preview_utils.py` | 模块文档注释 `detail_dialog.py` → `detail_panel.py` |
| `.trae/skills/fuscan-development/SKILL.md` | GUI 模块清单 `detail_dialog.py` → `detail_panel.py` |
| `tests/test_gui.py` | 移除 HitDetailDialog 导入；移除 `TestHitDetailDialog` / `TestHitDetailDialogNavigation` 测试类与若干对话框测试；重命名 `TestHitDetailDialogHelpers` → `TestPreviewHelpers`；迁移 `TestMatchTextHighlighting` 中 4 个位置高亮测试改用 DetailPanel；适配 `test_result_tree_context_menu_actions` 断言 3→2 |

### 新建文件

| 文件 | 说明 |
|------|------|
| `.trae/req/req-12-iter61需求.md` | 需求清单 |

## 关键决策与依据

### 决策1：直接移除对话框而非继续优化

iter-60 通过 `extract_content_cached` LRU 缓存试图缓解对话框反复打开卡顿，但卡顿根因是 `QDialog` + `WA_DeleteOnClose` + `QTextBrowser` 渲染开销叠加。右侧栏 DetailPanel 已提供等价功能且无对话框生命周期开销，移除对话框是更彻底的解决方案。

### 决策2：保留 `extract_content_cached` 缓存

虽然对话框移除，DetailPanel 仍使用 `extract_content_cached` 在主窗口内提供缓存，避免切换不同结果时重复读取文件。该缓存由 DetailPanel 接管使用，不随对话框删除。

### 决策3：迁移位置高亮测试改用 DetailPanel

`TestMatchTextHighlighting` 中 4 个 `test_dialog_positions_*` 测试用例验证的是关键词位置定位逻辑，与对话框无关。迁移为 `test_panel_positions_*`，通过 `window = MainWindow(); window._detail_panel.show_result(result)` 走公共接口，更贴近实际使用路径。

### 决策4：保留 TestPreviewHelpers

`TestHitDetailDialogHelpers` 测试的是 `preview_utils.py` 的公共辅助函数（`format_size` / `extract_keywords` / `build_preview_html`），DetailPanel 仍在使用。重命名为 `TestPreviewHelpers` 以反映其真实职责。

### 决策5：保留右键菜单两项动作

移除"在新窗口打开"后，右键菜单保留"复制路径"与"打开文件位置"两项，与 DetailPanel 控制器提供的公共能力一致，无功能损失。

## 代码实现情况

### 源码改动

- `main_window.py`：删除 2 个方法（`_on_result_activated` / `_on_open_in_window_requested`）与 2 处信号连接；右键菜单从 3 项缩减为 2 项
- `detail_panel.py`：删除 1 个信号（`open_in_window_requested`）与 1 个方法（`open_in_window`）
- `result_tree.py`：删除 1 个信号（`result_activated`）、1 个连接（`doubleClicked`）与 1 个方法（`_handle_double_clicked`）
- `styles.qss`：删除 3 个样式选择器块

### 测试改动

- 删除测试类 2 个：`TestHitDetailDialog`（约 168 行）、`TestHitDetailDialogNavigation`（约 254 行）
- 删除单测方法 3 个：`test_double_click_grouped_child_opens_dialog`、`test_detail_open_in_window_no_result`、`test_detail_open_in_window_with_result`
- 删除 `TestSeverityDisplay.test_detail_dialog_shows_severity_colors`
- 重命名 1 个测试类：`TestHitDetailDialogHelpers` → `TestPreviewHelpers`
- 迁移 4 个测试方法：`test_dialog_positions_*` → `test_panel_positions_*`，改用 `MainWindow + DetailPanel.show_result`
- 调整 1 处断言：`test_result_tree_context_menu_actions` 由 3 个 action 改为 2 个

## 整合优化情况

- 信号链路精简：`ResultTreeView.doubleClicked → result_activated → MainWindow._on_result_activated → HitDetailDialog` 整条链路移除
- `DetailPanel.open_in_window_requested → MainWindow._on_open_in_window_requested → HitDetailDialog` 整条链路移除
- `main_window.py` 减少约 35 行；`detail_panel.py` 减少约 10 行；`result_tree.py` 减少约 15 行；`styles.qss` 减少约 24 行
- 测试文件净减少约 400 行

## 测试验证结果

| 门禁 | 结果 |
|------|------|
| `uv run ruff check src tests` | All checks passed |
| `uv run ruff format --check src tests` | 91 files already formatted |
| `uv run pyrefly check` | 0 errors（459 suppressed，58 warnings not shown） |
| `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95` | 1353 passed / 0 failed / 16 deselected，coverage 96.24% |

## 遗留事项

无。DetailPanel 已完整承接对话框的所有详情功能。

## 下一轮计划

无。本轮迭代目标完整达成，等待用户下一轮需求。
