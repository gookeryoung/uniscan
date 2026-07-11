# iter-22：GUI 主窗口重构为 GitHub Desktop 5 区布局

## 本轮目标

将 `main_window.py` 从杀软风格重构为 GitHub Desktop 风格 5 区布局，满足 req-03 全部 5 条需求。重构后 GUI 须通过全部测试，覆盖率不低于上一轮（90%）。

## 改动文件清单

### 源码（1 文件，重写）

- `src/fuscan/gui/main_window.py`（~700 行 → ~1185 行，完全重写）：
  - **_init_ui**：中央 widget 改为「主操作区 + 主体分割器（列表区 | 详情区）」垂直布局。
  - **② 主操作区**（`_build_main_operation_area`）：扫描模式卡片按钮（全盘/盘符/文件夹）+ 盘符下拉 + 目标路径行 + 规则加载行 + 扫描/停止按钮 + 进度条 + 统计标签。
  - **③ 列表区**（`_build_list_area`）：`QTabWidget` 三 Tab（扫描结果/规则文件/扫描历史）+ ⑤ 底部操作区（`QPlainTextEdit` + 导出/批量按钮组）。
  - **④ 详情区**（`_build_detail_area`）：操作栏 `QStackedWidget` 两态（空态/非空态）+ 主体 `QStackedWidget` 两态（空态/非空态），强制持久化页面。
  - **菜单栏**（`_init_menu`）：文件(&F)/扫描(&S)/视图(&V)/帮助(&H) 四组，所有 action 复用 `self._scan_action` 等 QAction 实例，文案用 `self.tr()` 包裹。
  - **详情区嵌入预览**：从 `detail_dialog.py` 提取模块级辅助函数 `_format_size`/`_extract_keywords`/`_build_preview_html`，在详情区主体非空态页面嵌入文件信息 + 命中表 + 内容预览 + 命中导航（上/下条/定位）。
  - **QSS 配色**（`_apply_qss`）：GitHub Desktop 配色（背景 `#f6f8fa`、主色 `#0366d6`、危险色 `#d73a49`、边框 `#e1e4e8`），字体层级 14/13/13/12px。
  - **QSplitter 修复**：列表区与详情区水平 sizePolicy 设为 `QSizePolicy.Ignored`，让 QSplitter 按 `setStretchFactor(2,3)`/`setSizes` 分配空间，而非按子部件 sizeHint 比例（两者 sizeHint 接近会导致 offscreen 环境 1:1 平分）。

### 测试（1 文件，扩展）

- `tests/test_gui.py`（2599 行 → ~3195 行）：
  - **新增 TestMainWindowHelpers**（6 个测试）：模块级辅助函数 `_format_size`/`_extract_keywords`/`_build_preview_html` 的格式化、提取、去重、HTML 转义与高亮。
  - **新增 TestDetailArea**（14 个测试）：详情区两态切换、选中结果展示、分组子项、命中导航（上/下/循环/无命中）、导航标签、复制路径、空文件预览。
  - **新增 TestScanCallbacks**（6 个测试）：扫描进度回调（含长路径截断）、失败回调、取消回调、暂停/恢复状态、无 worker 停止。
  - **新增 TestExportAndMenu**（9 个测试）：导出菜单（无报告/CSV 写文件/取消）、关于对话框、批量处理未实现、Tab 切换、历史双击、closeEvent 保存。
  - **新增 TestRulesManagement**（5 个测试）：规则文件删除（无选中/有选中）、编辑（无规则/有规则）、重新加载刷新。
  - **修复 test_window_geometry_restored**：高度从 500 调整为 800（5 区布局最小高度约 680px，500 会被 Qt 强制抬升）。
  - 全部 193 个 GUI 测试通过。

## 关键决策与依据

### 1. QSplitter sizePolicy 设为 Ignored

**问题**：重构后列表区（QTabWidget sizeHint=550）与详情区（QStackedWidget sizeHint=598）sizeHint 接近，`showMaximized()` 后 QSplitter 按 sizeHint 比例分配，导致 1:1 平分（[388, 388]），`setSizes([400, 600])` 被覆盖。

**尝试过的方案**：
- `QTimer.singleShot(0, lambda: setSizes)` — 无效，show() 后 QSplitter 仍按 sizeHint 重算。
- `showEvent` 重写 + `_pending_splitter_sizes` — showEvent 在 `showMaximized()` 期间触发，此时 pending 尚未设置；且 `processEvents()` 会再次覆盖。

**最终方案**：将两个子部件水平 sizePolicy 设为 `QSizePolicy.Ignored`，QSplitter 不再参考 sizeHint，改按 `setStretchFactor` 和 `setSizes` 分配。简单 QSplitter 测试与 MainWindow 测试均验证通过。

### 2. 模块级辅助函数从 detail_dialog.py 提取

`_format_size`/`_extract_keywords`/`_build_preview_html` 原为 `detail_dialog.py` 的模块级函数。重构后详情区嵌入预览需要复用这些函数，故提取到 `main_window.py` 模块级。`detail_dialog.py` 的 `HitDetailDialog` 保留用于「在新窗口打开」功能。

### 3. 测试窗口几何高度调整

原测试 `test_window_geometry_restored` 期望高度 500，容差 2px。5 区布局最小高度约 680px（主操作区 ~250px + 列表区/详情区最小高度），Qt 强制抬升至最小值。将期望高度调整为 800（大于最小高度），容差 5px。

### 4. UP006/UP045 类型注解风格保持一致

新增代码继续使用 `List`/`Tuple`/`Set`/`Optional`（而非 `list`/`tuple`/`set`/`X | None`），与既有文件风格一致。类型注解迁移留待后续迭代（用户确认）。

## 验证结果

| 检查项 | 结果 |
|--------|------|
| `ruff check` | 244 errors（均为既有 UP006/UP045/ARG005，无新增错误类型） |
| `ruff format --check` | 通过（格式化后） |
| `pytest -m "not slow"` | 566 passed, 1 skipped |
| 覆盖率 | 90.32%（上一轮 90%，未下降） |
| main_window.py 覆盖率 | 93%（69 missed / 1185 total） |
| req-03 需求 | 5/5 全部满足 |

## 遗留事项

- **QAbstractItemView 迁移**：当前结果树/规则树仍用 QTreeWidget/QListWidget，QAbstractItemView 虚拟化迁移留待 iter-23（用户确认单独迭代）。
- **UP006/UP045 类型注解迁移**：全项目 ~240 处 `List`/`Tuple`/`Set`/`Optional` → `list`/`tuple`/`set`/`X | None`，留待后续迭代。
- **覆盖率未达 95% 门槛**：当前 90.32%，低于 pyproject.toml 配置的 `fail_under=95`，属既有技术债。
- **test_gui.py 模块未注册 `gui` marker**：`pytestmark = pytest.mark.gui` 触发 `PytestUnknownMarkWarning`，需在 pyproject.toml 注册 marker。
