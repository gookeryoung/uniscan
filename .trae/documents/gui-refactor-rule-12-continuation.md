# GUI 重构续作计划：rule-12 剩余步骤（3-10）

## 背景

原计划见 [gui-refactor-rule-12.md](file:///home/zhou/fuscan/.trae/documents/gui-refactor-rule-12.md)，已由用户批准并开始执行。前次会话因上下文丢失中断，已完成步骤 1-2，本计划承接剩余步骤 3-10。

## 已完成（步骤 1-2）

- **步骤 1** [theme.py](file:///home/zhou/fuscan/src/fuscan/theme.py)：37 个设计令牌 + `QSS_TOKENS` 字典，色值沿用 GitHub 配色（`COLOR_PRIMARY=#0366d6`）
- **步骤 2** [styles.qss](file:///home/zhou/fuscan/src/fuscan/gui/styles.qss)：全部硬编码替换为 `${TOKEN}` 占位符，新增 HeaderBar/Sidebar/TabStack 样式段

## 待执行（步骤 3-10）

### 步骤 3：更新 [app.py](file:///home/zhou/fuscan/src/fuscan/gui/app.py)

**现状**：L56 `app.setStyleSheet(_QSS_PATH.read_text(encoding="utf-8"))` 直接读 raw QSS，未做令牌替换。

**改动**：
- 新增 `load_stylesheet() -> str` 函数：`from string import Template` + `from fuscan import theme`，`Template(qss_text).substitute(theme.QSS_TOKENS)`
- L55-58 `app.setStyleSheet(...)` 改为 `app.setStyleSheet(load_stylesheet())`
- 异常捕获扩展为 `except (OSError, KeyError) as exc:`（OSError 文件读取 + KeyError 令牌缺失）
- 保留 `_QSS_PATH` 常量（测试依赖）
- `__all__` 增加 `load_stylesheet`

### 步骤 4：更新 [test_gui.py](file:///home/zhou/fuscan/tests/test_gui.py)（2 处最小修改）

**现状**：L1375、L1384 用 `_QSS_PATH.read_text()` 读 raw QSS 检查 `#0366d6`，但模板化后 raw 文件含 `${COLOR_PRIMARY}` 而非 `#0366d6`。

**改动**：
- L1373 `from fuscan.gui.app import _QSS_PATH` → `from fuscan.gui.app import load_stylesheet`
- L1375 `qss = _QSS_PATH.read_text(encoding="utf-8")` → `qss = load_stylesheet()`
- L1382-1384 同上修改
- 断言不变（substituted QSS 仍含 `#0366d6`，因 `COLOR_PRIMARY=#0366d6`）

### 步骤 5：检查点 — 运行 QSS 相关测试

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/test_gui.py -x -m "not slow" -k "qss or launch or severity" 2>&1 | tail -30
```

验证令牌替换无 KeyError、色值断言通过。

### 步骤 6：重写 [main_window_ui.py](file:///home/zhou/fuscan/src/fuscan/gui/main_window_ui.py)

**现状**：746 行，结构为 `menubar + central_layout(main_stack[3页])`，无 header_bar/sidebar/tab_stack。

**目标结构**（保留 menubar + 全部现有 `_ui` 属性名）：

```
MainWindow (1280x800, minSize 800x600)
├── menubar (QMenuBar) — 保留不变（file_menu/scan_menu/help_menu）
├── central (QWidget)
│   └── central_layout (QVBoxLayout, margins 0)
│       ├── header_bar (QFrame#header_bar, fixed height 40)
│       │   └── header_layout (QHBoxLayout)
│       │       ├── tab_scan_btn / tab_rules_btn / tab_history_btn (checkable)
│       │       ├── spacer
│       │       └── settings_btn / about_btn
│       └── tab_stack (QStackedWidget#tab_stack)
│           ├── scan_tab [0] — sidebar_splitter(Sidebar + main_stack)
│           │   ├── sidebar (QListWidget#sidebar, width 220)
│           │   └── main_stack (QStackedWidget) ← 保留，3 页页序不变
│           │       ├── setup_page [0] — 移除 rules_group，保留 target_group(移除 history) + setup_action_bar
│           │       ├── scanning_page [1] — 不变
│           │       └── results_page [2] — 不变
│           ├── rules_tab [1] — 从 setup_page 移入 rules_group
│           └── history_tab [2] — 从 target_group 移入 history_label + history_list
└── statusbar (QStatusBar) — 保留（如已有）
```

**关键保留点**：
- `main_stack` 仍是 QStackedWidget，addWidget 顺序 setup→scanning→results 不变（38 处测试检查 `currentIndex` 0/1/2）
- 所有 `_ui` 属性名不变：`setup_action_bar`/`file_menu`/`help_menu`/`about_action`/`rules_group`/`rules_file_list`/`rules_tree`/`history_list`/`history_label`/`target_group` 等
- `rules_group`/`history_label`/`history_list` 移到新 Tab，但 `_ui` 属性名不变
- 窗口默认 1280×800，最小 800×600

### 步骤 7：更新 [main_window.py](file:///home/zhou/fuscan/src/fuscan/gui/main_window.py)

**现状**：1839 行，`_bind_widgets()`(L345) 绑定 `_main_stack`，`_configure_ui()`(L405) 配置布局，`_switch_stage()`(L620) 切页。

**改动**：

1. **L130-134 `_SEVERITY_COLORS`**：改用 `from fuscan import theme` 常量
   - `QColor("#d73a49")` → `QColor(theme.COLOR_DANGER)`
   - `QColor("#f0883e")` → `QColor(theme.COLOR_WARNING)`
   - `QColor("#0366d6")` → `QColor(theme.COLOR_INFO)`

2. **`_bind_widgets()` 末尾新增**：
   - `self._tab_stack = ui.tab_stack`
   - `self._sidebar = ui.sidebar`
   - `self._tab_scan_btn = ui.tab_scan_btn` / `_tab_rules_btn` / `_tab_history_btn`
   - `self._settings_btn = ui.settings_btn` / `_about_btn = ui.about_btn`
   - `self._sidebar_splitter = ui.sidebar_splitter`

3. **`_configure_ui()` 新增**：
   - 创建 `_header_button_group = QButtonGroup(self)`，`setExclusive(True)`，addButton 三个 tab 按钮（id 0/1/2）
   - sidebar 填充 3 项：「配置」/「扫描中」/「结果」（带图标）
   - 信号槽：`_sidebar.currentRowChanged` → `_on_sidebar_stage_changed`；`_header_button_group.idClicked` → `_on_header_tab_changed`；`_settings_btn.clicked` → `_on_settings`；`_about_btn.clicked` → `_on_about`
   - `_sidebar_splitter.setSizes([220, 1060])` 初始比例
   - `_tab_scan_btn.setChecked(True)` 初始选中扫描 Tab
   - `_sidebar.setCurrentRow(0)` 初始选中配置项

4. **`_configure_ui()` 修改**：
   - `setup_layout.setStretch` 调整（移除 rules_group 后仅 target_group + setup_action_bar）
   - `target_group_layout.setStretch` 调整（移除 history 后仅 scan_mode_layout）
   - 新增 `rules_tab_layout.setStretch(0, 1)` 和 `history_tab_layout.setStretch(1, 1)`

5. **新增方法**：
   - `_on_header_tab_changed(tab_id: int)`：`_tab_stack.setCurrentIndex(tab_id)`；`_sidebar.setVisible(tab_id == 0)`；若是扫描 Tab，根据当前 `_workflow_stage` 同步 sidebar 选中项
   - `_on_sidebar_stage_changed(row: int)`：映射 row→WorkflowStage（0→SETUP/1→SCANNING/2→RESULTS），调用 `_switch_stage(stage)`

6. **`_switch_stage()` 末尾新增**（L631 后）：
   ```python
   self._sidebar.blockSignals(True)
   self._sidebar.setCurrentRow(page_index)
   self._sidebar.blockSignals(False)
   ```
   同步 sidebar 选中项，避免循环触发。

7. **`_on_about()` 文本**：「Python + PySide2」→「Python + PySide」（双兼容表述）

### 步骤 8：更新 [detail_dialog.py](file:///home/zhou/fuscan/src/fuscan/gui/detail_dialog.py)

**现状**：L54-58 `_SEVERITY_COLORS` 硬编码 `#d73a49`/`#f0883e`/`#0366d6`。

**改动**：
- 顶部 `from fuscan import theme`
- L55-57 改用 `theme.COLOR_DANGER`/`theme.COLOR_WARNING`/`theme.COLOR_INFO`
- L371 `QColor(255, 165, 0)` 保持不变（高亮橙色，无对应令牌）
- L203 `self._info_label = ui.info_label` → `self._info_label = ui.hit_info_label`（配合步骤 9 objectName 改名）

### 步骤 9：更新 [detail_dialog_ui.py](file:///home/zhou/fuscan/src/fuscan/gui/detail_dialog_ui.py)

**现状**：L29 `info_label.setObjectName(u"info_label")`，L30 内联样式 `setStyleSheet("padding: 8px; background: #f5f5f5; border: 1px solid #ddd;")`。

**改动**：
- L29 objectName 改为 `u"hit_info_label"`（匹配 styles.qss L770 `QLabel#hit_info_label`）
- 属性名同步改为 `self.hit_info_label`（pyside-uic 生成代码属性名=objectName）
- L30 移除 `setStyleSheet(...)` 内联样式（QSS 已托管）

### 步骤 10：全套门禁验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
QT_QPA_PLATFORM=offscreen uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

全部通过后：
- 创建 `.trae/req/req-08-gui重构rule12.md`（需求记录）
- 创建 `.trae/docs/iter-28-gui重构rule12.md`（迭代记录）
- `git add`（按文件名）+ `git commit` + `git push`

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| main_window_ui.py 重写遗漏 `_ui` 属性 | 对照原文件 746 行逐一核对属性名；优先跑 `TestMainWindow`/`TestWorkflowStage` |
| `_main_stack` 页序偏移 | addWidget 顺序 setup→scanning→results 不变；跑 `TestWorkflowStage` |
| QSS 令牌缺失导致 KeyError | 步骤 5 检查点验证；`grep -oP '\$\{(\w+)\}' styles.qss \| sort -u` 与 `QSS_TOKENS.keys()` 比对 |
| `_sidebar` 信号循环触发 | `_switch_stage` 中 blockSignals 包裹 setCurrentRow |
| `hit_info_label` 改名破坏 detail_dialog 测试 | 测试用 `dialog._info_label`（Python 属性），非 `ui.info_label`；步骤 8 同步更新 `self._info_label = ui.hit_info_label` |
| QMenuBar 与 HeaderBar 视觉冲突 | QMenuBar 保留原生样式；HeaderBar 用 COLOR_PRIMARY 背景；测试不依赖 menubar 可见性 |

## 验证方式

1. 步骤 5 检查点：QSS 模板化相关测试通过
2. 步骤 10 全套门禁：ruff + pyrefly + pytest(覆盖率≥96%) 全通过
3. 手动启动 `python -m fuscan gui`：HeaderBar/Sidebar 视觉效果、Tab 切换、Sidebar 切换、扫描流程、规则管理、历史查看全部正常
