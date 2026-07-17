# iter-49 功能内聚重构 P2（详情面板拆分）

## 需求清单

- [x] P2 详情面板拆分：将 main_window.py 的 15 个 `_detail_*` 方法群拆到独立 `gui/detail_panel.py`，使主窗口仅负责信号路由

## 迭代目标

将详情区的状态管理、内容填充、命中导航与文件操作从 `main_window.py` 拆分到独立的
`DetailPanel(QObject)` 控制器类，实现功能内聚。主窗口仅负责创建控件、连接信号与
响应用户操作，详情区逻辑内聚到 `DetailPanel`。此为 P1/P2/P3 三阶段重构的最后阶段
（P1 导出拆分 + P3 结果树拆分已在 iter-48 完成）。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/detail_panel.py` | 新增 | P2 核心模块：`DetailControls` + `DetailPanel(QObject)` |
| `src/fuscan/gui/main_window.py` | 修改 | 删除 15 个 `_detail_*` 方法、新增 3 个槽、改用 `_detail_panel` API |
| `tests/test_gui.py` | 修改 | 迁移约 100 处 `_detail_*` 引用到 `_detail_panel.X`，新增 1 个测试 |

## 关键决策与依据

### DetailPanel(QObject) 控制器模式（非 QWidget 子类）

- **方案选型**：DetailPanel 继承 `QObject` 而非 `QWidget`，UI 控件由主窗口 `setupUi`
  创建后通过 `DetailControls` dataclass 传入。理由：
  - `QObject` 子类可用 `Signal` 向外通信（纯逻辑控制器无法用 Signal）
  - 不拆分 `.ui` 文件，UI 控件所有权留在主窗口，降低风险
  - DetailPanel 不依赖 MainWindow 类，仅通过信号解耦通信
- **DetailControls frozen dataclass**：封装 10 个详情区 UI 控件引用
  （action_stack/main_stack/prev_btn/next_btn/nav_label/open_location_btn/
  info_label/hits_table/preview/note_edit），构造时传入 DetailPanel

### 信号路由解耦

DetailPanel 通过 3 个信号向外通信，主窗口用 3 个槽响应：
- `path_copy_requested(str)` → `_on_path_copy_requested`：更新状态栏提示
- `open_location_requested(object)` → `_on_open_location_requested`：调 `_open_path_in_explorer`
- `open_in_window_requested(object)` → `_on_open_in_window_requested`：创建 `HitDetailDialog`

### _detail_panel 非 None 类型保证

- **问题**：`_detail_panel: DetailPanel | None = None` 导致 pyrefly 报 79 个
  `NoneType has no attribute` 错误（main_window.py 5 处 + test_gui.py 74 处）
- **方案**：在 `__init__` 中 `setupUi(self)` 后立即调 `_create_detail_panel()`
  构造 DetailPanel，类型为 `DetailPanel`（非 `| None`）。`_create_detail_panel`
  是纯工厂方法，在 `_configure_ui` 之前调用，确保后续 `_connect_signals`/
  `_setup_shortcuts` 可安全引用
- **依据**：`setupUi` 在 `__init__` 第一行调用，所有 UI 控件已就绪；DetailPanel
  不依赖 `_configure_ui` 中的其他配置（如 layout stretch、icons）

### 公共 API 设计

DetailPanel 公共 API：
- `show_result(result)` / `clear()`：驱动详情区
- `current_result`（property）：读取当前选中结果
- `prev_hit()` / `next_hit()`：命中导航
- `copy_path()` / `open_in_window()` / `open_location()`：文件操作（发信号）

私有 API（测试可访问）：`_hit_positions` / `_current_hit_index` / `_current_result` /
`_highlight_current_hit` / `_scroll_to_current_hit` / `_on_hits_row_clicked` /
`_update_nav_label`

## 代码实现情况

### detail_panel.py（新增 418 行）

- `DetailControls` frozen dataclass：10 个 UI 控件引用
- `DetailPanel(QObject)`：3 个 Signal + 8 个公共方法 + 8 个私有方法
- 模块级辅助函数：`_severity_text` / `_apply_severity_to_table_item`
- 从 `main_window.py` 迁入的完整逻辑：命中表填充、内容预览、关键词高亮定位、
  命中导航（循环）、行点击跳转、文件操作信号发射

### main_window.py（净减约 250 行）

- **删除**：15 个 `_detail_*` 方法 + `_on_copy_path` / `_on_open_in_window` /
  `_on_open_file_location` + 模块级 `_apply_severity_to_table_item`（迁到 detail_panel）
- **删除导入**：`QColor`/`QTextCharFormat`/`QTextCursor`/`QHeaderView`/
  `QTableWidgetItem`/`QTextEdit` + `extract_content_with_fallback`/
  `PREVIEW_MAX_CHARS`/`build_keyword_to_rule_map`/`build_preview_html`/
  `compile_keyword_pattern`/`extract_keywords` + `RuleHit` + `Sequence`
- **新增导入**：`from fuscan.gui.detail_panel import DetailControls, DetailPanel`
- **新增方法**：`_create_detail_panel`（工厂）+ 3 个槽
  （`_on_path_copy_requested`/`_on_open_location_requested`/`_on_open_in_window_requested`）
- **修改调用点**：`_connect_signals`（信号路由）、`_setup_shortcuts`（F3/Shift+F3）、
  `_start_scan`（clear）、`_on_result_selected`（show_result/clear）、
  `_on_result_tree_context_menu`（current_result + copy_path/open_in_window/open_location）
- **保留**：`_open_path_in_explorer`（被 `_on_open_location_requested` 与
  `_on_matched_file_double_clicked` 共用）、`_severity_text` 和
  `_apply_severity_to_tree_item`（用于规则树）

### test_gui.py（迁移 + 新增）

- **批量迁移**（约 100 处）：`window._detail_*` → `window._detail_panel.*`
  - 方法调用：`_detail_show_result` → `show_result`、`_detail_clear` → `clear`、
    `_on_next/prev_detail_hit` → `next_hit/prev_hit`、`_on_copy_path` → `copy_path`、
    `_on_open_in_window` → `open_in_window`、`_on_open_file_location` → `open_location`、
    `_on_detail_hits_row_clicked` → `_on_hits_row_clicked`、`_update_detail_nav_label` →
    `_update_nav_label`
  - 属性访问：`_detail_current_result` → `_current_result`、
    `_detail_hit_positions` → `_hit_positions`、
    `_detail_current_hit_index` → `_current_hit_index`
- **新增测试**：`test_detail_open_in_window_with_result`（覆盖 `open_in_window`
  带结果路径 + `_on_open_in_window_requested` 槽，mock `HitDetailDialog`）

## 整合优化情况

- **消除 main_window.py 过重功能**：15 个详情方法群（约 250 行）内聚到 detail_panel.py，
  主窗口仅保留信号路由槽（3 个短方法）
- **DetailPanel 与 MainWindow 解耦**：DetailPanel 不导入 MainWindow，仅通过
  DetailControls（数据）+ 3 个 Signal（行为）与主窗口交互，可独立测试与复用
- **未拆分 .ui 文件**：降低风险，UI 控件所有权留在主窗口，DetailPanel 仅持有引用。
  未来若需进一步解耦可考虑提升控件 + 拆分 .ui

## 测试验证结果

| 门禁 | 结果 | 基线（iter-48） | 变化 |
|------|------|----------------|------|
| ruff check | 0 errors | 0 errors | — |
| ruff format --check | 80 files passed | 80 files passed | — |
| pyrefly check | 0 errors (452 suppressed) | 0 errors (442 suppressed) | +10 suppressed |
| pytest | 1324 passed / 0 failed | 1323 passed / 0 failed | +1 test |
| coverage | 96.04% | 95.97% | +0.07% |

pyrefly suppressed +10 原因：detail_panel.py 新增 Signal `connect`/`emit`（8 处）+
main_window.py 信号路由连接（3 处中的 2 处，1 处为 NoneType 已消除），
均为 PySide2 stub 已知限制。

## 遗留事项

- 无

## 下一轮计划

- P1/P2/P3 三阶段功能内聚重构已全部完成，无后续计划
- 若未来需要进一步解耦，可考虑：将 DetailPanel 提升为 QWidget 子类并拆分 .ui
  （当前不拆分 .ui 的决策已足够，仅在需要独立复用详情面板时才考虑）
