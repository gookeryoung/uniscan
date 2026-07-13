# 精简 main_window.py UI 设计

## 执行进度

| # | 任务 | 状态 |
|---|------|------|
| 1 | `main_window.ui` 迁移静态属性（editTriggers/selectionBehavior/垂直 spacers） | 已完成 |
| 2 | `main_window_ui.py` 重新生成（含迁移属性） | 已完成 |
| 3 | `main_window.py` `_configure_ui` 拆分为 12 个子方法 + 删除 4 行已迁移代码 | 已完成 |
| 4 | `Makefile` `ui` 目标追加 `settings_dialog.ui` 编译命令 | 待执行 |
| 5 | 全套门禁验证（ruff + pyrefly + pytest + coverage ≥ 96%） | 待执行 |
| 6 | git commit + push origin/main | 待执行 |

**当前未提交变更**（`git status --short`）：
- ` M src/fuscan/gui/main_window.py`
- ` M src/fuscan/gui/main_window.ui`
- ` M src/fuscan/gui/main_window_ui.py`
- `?? .trae/documents/精简 main_window.py UI 设计.md`

**已验证事实**：
- `main_window_ui.py:507-508` 已包含 `setEditTriggers(NoEditTriggers)` 与 `setSelectionBehavior(QTableWidget.SelectRows)`
- `main_window_ui.py:453-467` 已包含 `detail_empty_top_spacer` 与 `detail_empty_bottom_spacer`
- `main_window.py:393-408` `_configure_ui` 已重构为 13 行调用序列
- `tests/test_gui.py` 不依赖 `setEditTriggers`/`setSelectionBehavior`/`insertStretch`/`_configure_ui`（Grep 无匹配），拆分不破坏测试
- `settings_dialog.ui` 与 `settings_dialog_ui.py` 均已存在，仅 Makefile 未纳入编译流程

## 剩余执行步骤

### 步骤 1：更新 Makefile（Task #4）

在 `Makefile` 第 18 行后追加一行：
```makefile
	pyside2-uic src/fuscan/gui/settings_dialog.ui -o src/fuscan/gui/settings_dialog_ui.py
```

完整 `ui` 目标应为：
```makefile
ui: ## 编译 .ui 文件到 _ui.py (pyside2-uic)
	pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py
	pyside2-uic src/fuscan/gui/detail_dialog.ui -o src/fuscan/gui/detail_dialog_ui.py
	pyside2-uic src/fuscan/gui/rule_editor.ui -o src/fuscan/gui/rule_editor_ui.py
	pyside2-uic src/fuscan/gui/settings_dialog.ui -o src/fuscan/gui/settings_dialog_ui.py
```

### 步骤 2：全套门禁验证（Task #5）

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
uv run pytest tests/test_gui.py -m gui -v
```

**重点验证项**：
- 窗口创建无异常（`test_window_creation`）
- 初始状态栏 progress/current_file_label 不可见（`test_initial_stage_actions`）
- 进度条与状态栏更新正常（`test_scan_progress_updates_status_bar`）
- 详情区空态提示标签垂直居中（spacer 生效）
- 详情表 `SelectRows` + `NoEditTriggers` 生效

### 步骤 3：提交并推送（Task #6）

```bash
git add Makefile src/fuscan/gui/main_window.py src/fuscan/gui/main_window.ui src/fuscan/gui/main_window_ui.py ".trae/documents/精简 main_window.py UI 设计.md"
git commit -m "refactor(gui): 精简 main_window.py UI 设计，迁移静态属性到 .ui 并拆分 _configure_ui"
git push origin main
```

遵循 `rule-09-git提交规则.md`：中文 + 变更类型 + 简洁一段落。push 自动执行（分支已跟踪远程）。

---

## 背景

`main_window.py`（1970 行）中 `_configure_ui` 方法占据 394-601 行（约 207 行），混合了静态属性设置与动态逻辑。参考 `settings_dialog.py`（75 行）的极简风格——`.ui` 表达所有静态 UI，`.py` 只做信号槽与业务——本次迭代将可稳妥迁移的静态属性移到 `main_window.ui`，并将 `_configure_ui` 拆分为职责单一的子方法以改善可读性。

**约束**：`pyside2-uic 5.15.2` 对部分属性（QStatusBar stretch、QSplitter stretchFactor、QVBoxLayout stretch、QTreeWidget 每列独立宽度、QTableWidget 全列 Stretch）支持有限，这些保留在 `.py` 中。

## 改动清单

### 1. `src/fuscan/gui/main_window.ui` — 迁移静态属性

**A. `detail_hits_table` 添加属性**（对应 .py 423-425 行）
```xml
<widget class="QTableWidget" name="detail_hits_table">
  <property name="editTriggers"><set>NoEditTriggers</set></property>
  <property name="selectionBehavior"><enum>SelectRows</enum></property>
  <attribute name="horizontalHeaderStretchLastSection"><bool>true</bool></attribute>
  ...
</widget>
```
- `setSectionResizeMode(QHeaderView.Stretch)` 保留在 .py（.ui 仅支持 StretchLastSection，不等价）
- `cellClicked.connect(...)` 保留在 .py（信号槽）

**B. `detail_empty_main_layout` 垂直居中**（对应 .py 477-478 行）
在 `detail_empty_hint` 上下各添加一个垂直 `<spacer>`，替代 .py 中的 `insertStretch(0)` + `addStretch()`：
```xml
<item>
  <spacer name="detail_empty_top_spacer">
    <property name="orientation"><enum>Qt::Vertical</enum></property>
    <property name="sizeHint" stdset="0"><size><width>20</width><height>40</height></size></property>
  </spacer>
</item>
<item>
  <widget class="QLabel" name="detail_empty_hint">...</widget>
</item>
<item>
  <spacer name="detail_empty_bottom_spacer">
    <property name="orientation"><enum>Qt::Vertical</enum></property>
    <property name="sizeHint" stdset="0"><size><width>20</width><height>40</height></size></property>
  </spacer>
</item>
```

### 2. `src/fuscan/gui/main_window_ui.py` — 重新生成

执行 `pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py` 重新编译。验证生成的代码包含新增的 `editTriggers`、`selectionBehavior` 属性设置与 spacer 调用。

### 3. `src/fuscan/gui/main_window.py` — 重构 _configure_ui

**删除已迁移到 .ui 的代码**：
- 423-425 行：`detail_hits_table.horizontalHeader().setSectionResizeMode(...)` 保留，删除 `setEditTriggers`、`setSelectionBehavior` 两行
- 477-478 行：`detail_empty_main_layout.insertStretch(0)` + `addStretch()` 两行删除

**将 `_configure_ui` 拆分为 12 个子方法**（按调用顺序）：

| 子方法 | 职责 | 原 .py 行号 |
|--------|------|------------|
| `_setup_status_bar` | 创建 stats_label/current_file_label/progress 并加入 statusBar | 397-413 |
| `_setup_results_tree` | 结果树列宽 | 416-420 |
| `_setup_detail_table` | 详情表 sectionResizeMode + cellClicked 信号 | 423-426 |
| `_setup_comboboxes` | rule_filter_combo / group_mode_combo 初始项（带 userData） | 429-432 |
| `_setup_splitters` | results_splitter / sidebar_splitter stretchFactor + 初始 sizes | 435-436, 457-458, 550 |
| `_setup_layouts` | 各 layout setStretch | 440-474 |
| `_setup_icons` | 主题图标加载与设置（按钮、菜单、侧边栏） | 480-531 |
| `_setup_button_groups` | 头部 Tab 按钮组 + 盘符按钮组 | 534-538, 553-556 |
| `_setup_sidebar` | 侧边栏阶段项填充（依赖主题图标） | 541-547 |
| `_connect_signals` | 所有信号槽连接（按钮、actions、worker 等） | 559-594 |
| `_setup_context_menus` | 结果树与规则文件列表右键菜单策略 | 605-608 |
| `_setup_shortcuts` | F3 / Shift+F3 / Delete 快捷键 | 643-650 |

重构后的 `_configure_ui` 仅保留调用顺序与初始阶段切换：
```python
def _configure_ui(self) -> None:
    """配置 .ui 无法静态表达的动态属性、layout stretch 与信号槽连接。"""
    self._setup_status_bar()
    self._setup_results_tree()
    self._setup_detail_table()
    self._setup_comboboxes()
    self._setup_splitters()
    self._setup_layouts()
    self._setup_icons()
    self._setup_button_groups()
    self._setup_sidebar()
    self._connect_signals()
    self._setup_context_menus()
    self._setup_shortcuts()
    self._switch_stage(WorkflowStage.SETUP)
```

### 4. `Makefile` — 补全 `ui` 目标

在 `ui` 目标末尾追加 settings_dialog.ui 的编译命令：
```makefile
ui: ## 编译 .ui 文件到 _ui.py (pyside2-uic)
	pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py
	pyside2-uic src/fuscan/gui/detail_dialog.ui -o src/fuscan/gui/detail_dialog_ui.py
	pyside2-uic src/fuscan/gui/rule_editor.ui -o src/fuscan/gui/rule_editor_ui.py
	pyside2-uic src/fuscan/gui/settings_dialog.ui -o src/fuscan/gui/settings_dialog_ui.py
```

## 验证

```bash
# 1. 重新生成 _ui.py 并检查 diff
pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py
git diff src/fuscan/gui/main_window_ui.py

# 2. 全套门禁
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96

# 3. GUI 烟雾测试（确认 detail_hits_table 行为与详情面板居中显示无回归）
uv run pytest tests/test_gui.py -m gui -v

# 4. 关键测试用例（确认状态栏、详情表、空白详情面板行为正确）
uv run pytest tests/test_gui.py -m gui -v -k "detail or status_bar or stage_actions or initial"
```

**重点验证项**：
- `test_window_creation`：窗口创建无异常
- `test_initial_stage_actions`：初始状态栏 progress/current_file_label 不可见
- `test_scan_progress_updates_status_bar`：进度条与状态栏更新正常
- 详情区空态选中切换测试：空白详情面板的提示标签仍垂直居中
- 详情表行选择行为：`SelectRows` 生效（点击单元格选中整行）
- 详情表编辑行为：`NoEditTriggers` 生效（双击不进入编辑模式）

## 预期收益

- `_configure_ui` 从 207 行单方法变为 13 行调用序列 + 12 个职责单一的子方法（每个 10-50 行）
- 消除 `.ui` 已声明 widget 与 `.py` 重复设置属性的 4 行
- Makefile 工具链完整覆盖所有 .ui 文件
- 代码量净减少约 4 行，但可读性与可维护性显著提升
