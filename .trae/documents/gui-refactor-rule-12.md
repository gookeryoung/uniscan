# GUI 重构计划：遵循 rule-12-gui-pyside-standards.md

## Context

当前 fuscan GUI 采用 GitHub Desktop 风格（QMenuBar + QStackedWidget 三页整页切换），配色硬编码散落于 [styles.qss](file:///home/zhou/fuscan/src/fuscan/gui/styles.qss) 和 [main_window.py](file:///home/zhou/fuscan/src/fuscan/gui/main_window.py)，无设计令牌系统，无 HeaderBar/Sidebar 结构。

rule-12 要求：设计令牌集中到 `theme.py`、主窗口改为「头部 + 侧边栏 + 内容区 + 状态栏」四区结构、QSS 用 `${TOKEN}` 占位符模板化。

本次重构在**严格保留全部功能**（tests/test_gui.py 5266 行全通过）前提下，落地 rule-12 的核心结构要求。

## 用户确认的关键决策

1. **Tab 结构**：Header 3 个 Tab — 扫描（内部用 Sidebar 切换 配置/扫描中/结果 三阶段，保留 `_main_stack`）/ 规则管理 / 扫描历史
2. **范围**：仅核心 — 布局重构 + 设计令牌 + QSS 模板化（不含 self.tr()、QSettings、响应式折叠）
3. **回归**：严格保留全部功能，tests/test_gui.py 全通过
4. **颜色**：保留 `#0366d6` 作为 COLOR_PRIMARY（偏离 rule-12 表格的 `#0887A0`）
5. **验收**：ruff/pyrefly/pytest 全套门禁 + GUI 测试通过 + 覆盖率 ≥ 96.05%

## 关键约束（来自测试分析）

- `_main_stack.currentIndex()` 38 处测试检查（0=SETUP/1=SCANNING/2=RESULTS），必须保留 QStackedWidget 与页序
- `_switch_stage(WorkflowStage)` 19 处测试调用，方法签名不变
- `_ui.file_menu`/`_ui.help_menu` 必须是 QMenu（含 actions），`_ui.setup_action_bar`/`_ui.about_action` 必须存在
- 私有属性 `_scan_btn`/`_rules_tree`/`_result_tree`/`_ruleset`/`_rules_paths` 等全部保留
- 2 个色值测试读 raw styles.qss 检查 `#0366d6`，QSS 模板化后需改为读 `load_stylesheet()`（ substituted QSS 仍含 `#0366d6`）

## 实施步骤

### 步骤 1：创建 src/fuscan/theme.py（新建）

集中定义所有设计令牌，使用现有 GitHub 配色（非 rule-12 的 `#0887A0`）：

- 色彩令牌：`COLOR_PRIMARY=#0366d6`、`COLOR_PRIMARY_DARK=#0256c1`、`COLOR_PRIMARY_DARKER=#024aa0`、`COLOR_DANGER=#d73a49`、`COLOR_WARNING=#f0883e`、`COLOR_INFO=#0366d6`、`COLOR_TEXT_PRIMARY=#24292e`、`COLOR_TEXT_SECONDARY=#586069`、`COLOR_TEXT_MUTED=#959da5`、`COLOR_TEXT_ON_PRIMARY=#ffffff`、`COLOR_BG_APP=#f6f8fa`、`COLOR_BG_CARD=#ffffff`、`COLOR_BG_HOVER=#f6f8fa`、`COLOR_BG_SELECTED=#f1f8ff`、`COLOR_BORDER=#e1e4e8`、`COLOR_BORDER_MUTED=#d0d7de`、`COLOR_ACCENT=#58a6ff`
- 排版：`FONT_FAMILY`、`FONT_SIZE_CAPTION=11px`、`FONT_SIZE_SMALL=12px`、`FONT_SIZE_BODY=13px`、`FONT_SIZE_HEADING=15px`、`FONT_SIZE_TITLE=18px`
- 间距：`SPACING_XS=4px`、`SPACING_SM=8px`、`SPACING_MD=16px`、`SPACING_LG=24px`、`SPACING_XL=32px`
- 圆角与尺寸：`RADIUS_SM=4px`、`RADIUS_MD=6px`、`RADIUS_LG=8px`、`HEADER_HEIGHT=40px`、`SIDEBAR_WIDTH=220px`、`STATUSBAR_HEIGHT=28px`、`CONTROL_HEIGHT=32px`、`CONTROL_HEIGHT_LG=44px`
- `QSS_TOKENS: dict[str, str]` 汇总所有令牌供 `string.Template.substitute()` 使用
- 定义 `__all__` 显式导出

### 步骤 2：转换 src/fuscan/gui/styles.qss

- 将所有硬编码色值替换为 `${TOKEN}` 占位符（约 28 处 `#0366d6`→`${COLOR_PRIMARY}`、25 处 `#e1e4e8`→`${COLOR_BORDER}` 等）
- `#ffffff` 按语境区分：`color:` 属性用 `${COLOR_TEXT_ON_PRIMARY}`，`background:` 属性用 `${COLOR_BG_CARD}`
- `#f6f8fa` 按语境区分：应用底色用 `${COLOR_BG_APP}`，hover 背景用 `${COLOR_BG_HOVER}`
- 字号 `13px`→`${FONT_SIZE_BODY}`、`12px`→`${FONT_SIZE_SMALL}`、`18px`→`${FONT_SIZE_TITLE}`
- 圆角 `6px`→`${RADIUS_MD}`、`8px`→`${RADIUS_LG}`、`4px`→`${RADIUS_SM}`
- 新增 HeaderBar 样式：`QFrame#header_bar` 背景 `${COLOR_PRIMARY}`、高 `${HEADER_HEIGHT}`；header 内 QPushButton 透明背景/白色文字/选中态 `${COLOR_PRIMARY_DARK}`
- 新增 Sidebar 样式：`QListWidget#sidebar` 背景 `${COLOR_PRIMARY}`/白色文字；item 选中态 `${COLOR_PRIMARY_DARK}` + 左侧 3px `${COLOR_ACCENT}` 竖条；hover 态 rgba(255,255,255,0.1)
- 新增 `QStackedWidget#tab_stack` 背景 `${COLOR_BG_APP}`

### 步骤 3：更新 src/fuscan/gui/app.py

- 新增 `load_stylesheet() -> str` 函数：读取 `_QSS_PATH`，用 `string.Template.substitute(theme.QSS_TOKENS)` 替换占位符
- `launch()` 中 `app.setStyleSheet(_QSS_PATH.read_text(...))` 改为 `app.setStyleSheet(load_stylesheet())`
- 异常捕获扩展为 `except (OSError, KeyError) as exc:`（OSError 文件读取失败 + KeyError 令牌缺失）
- 保留 `_QSS_PATH` 常量不变（测试 monkeypatch 依赖）

### 步骤 4：更新 tests/test_gui.py（仅 2 处最小修改）

- `test_scan_btn_qss_uses_primary_blue`（L1371-1378）：`_QSS_PATH.read_text()` → `load_stylesheet()`
- `test_view_results_btn_qss_is_outline`（L1380-1388）：`_QSS_PATH.read_text()` → `load_stylesheet()`
- 断言不变（substituted QSS 仍含 `#0366d6`）
- L1458 severity color 检查不需改（`QColor.name()` 返回实际色值，theme 常量值相同）

### 步骤 5：检查点 — 运行 QSS 模板化测试

```bash
QT_QPA_PLATFORM=offscreen pytest tests/test_gui.py -x -m "not slow" -k "qss or launch or severity"
```

### 步骤 6：重写 src/fuscan/gui/main_window_ui.py

新 Widget 树结构（保留 menubar + 所有现有 `_ui` 属性）：

```
MainWindow (1280x800, minSize 800x600)
├── menubar (QMenuBar) — 保留不变
├── central (QWidget)
│   └── central_layout (QVBoxLayout, margins 0)
│       ├── header_bar (QFrame, objectName="header_bar", fixed height 40)
│       │   └── header_layout (QHBoxLayout)
│       │       ├── tab_scan_btn / tab_rules_btn / tab_history_btn (checkable)
│       │       ├── spacer
│       │       └── settings_btn / about_btn
│       └── tab_stack (QStackedWidget, objectName="tab_stack")
│           ├── scan_tab [0] — 含 sidebar_splitter(Sidebar + main_stack)
│           │   ├── sidebar (QListWidget, objectName="sidebar", width 220)
│           │   └── main_stack (QStackedWidget) ← 保留，3 页页序不变
│           │       ├── setup_page [0] — 移除 rules_group，保留 target_group + setup_action_bar
│           │       ├── scanning_page [1] — 不变
│           │       └── results_page [2] — 不变
│           ├── rules_tab [1] — 从 setup_page 移入 rules_group
│           └── history_tab [2] — 从 target_group 移入 history_label + history_list
```

关键保留点：
- `main_stack` 仍是 QStackedWidget，addWidget 顺序 setup→scanning→results 不变
- `setup_action_bar`/`file_menu`/`help_menu`/`about_action` 等 `_ui` 属性全部保留
- `rules_group`/`rules_file_list`/`rules_tree`/`history_list` 等 widget 移到新 Tab 但 `_ui` 属性名不变
- 窗口默认尺寸 1280×800（原 1176×742），最小 800×600（原 720×480）

### 步骤 7：更新 src/fuscan/gui/main_window.py

- `_bind_widgets()` 末尾新增：绑定 `_tab_stack`/`_sidebar`/`_tab_scan_btn`/`_tab_rules_btn`/`_tab_history_btn`/`_settings_btn`/`_about_btn`/`_sidebar_splitter`；创建 `_header_button_group`(QButtonGroup, exclusive)，addButton 时带 id 0/1/2
- `_configure_ui()` 新增：sidebar 项图标设置；header 按钮图标设置；信号槽连接（`_sidebar.currentRowChanged`→`_on_sidebar_stage_changed`、`_header_button_group.idClicked`→`_on_header_tab_changed`、`_settings_btn.clicked`→`_on_settings`、`_about_btn.clicked`→`_on_about`）；`_sidebar_splitter` 伸缩比例 (0,0)+(1,1)；`_tab_scan_btn.setChecked(True)` 初始选中
- `_configure_ui()` 修改：`setup_layout.setStretch` 从 3 项减为 2 项（移除 rules_group）；`target_group_layout.setStretch` 从 3 项减为 1 项（移除 history_label/list）；新增 `rules_tab_layout.setStretch(0, 1)` 和 `history_tab_layout.setStretch(1, 1)`
- 新增 `_on_header_tab_changed(tab_id: int)`：切换 `_tab_stack.setCurrentIndex(tab_id)`，`_sidebar.setVisible(tab_id == 0)`
- 新增 `_on_sidebar_stage_changed(row: int)`：映射 row→WorkflowStage，调用 `_switch_stage(stage)`
- `_switch_stage()` 末尾新增：`_sidebar.blockSignals(True)` → `setCurrentRow(page_index)` → `blockSignals(False)`（同步 sidebar 选中项，避免循环触发）
- `_SEVERITY_COLORS` 字典改用 `theme.COLOR_DANGER`/`COLOR_WARNING`/`COLOR_INFO`（实际色值不变）
- `_on_about()` 文本 `"Python + PySide2"` → `"Python + PySide"`（双兼容）

### 步骤 8：更新 src/fuscan/gui/detail_dialog.py

- `_SEVERITY_COLORS` 字典（L54-58）改用 `from fuscan import theme` 导入常量
- L371 `QColor(255, 165, 0)` 保持不变（高亮橙色，无对应令牌，无测试检查）

### 步骤 9：更新 src/fuscan/gui/detail_dialog_ui.py

- L30 移除 `info_label` 内联样式 `setStyleSheet("padding: 8px; background: #f5f5f5; ...")`
- 将 `info_label` objectName 改为 `hit_info_label`（匹配 styles.qss 已有的 `QLabel#hit_info_label` 规则）

### 步骤 10：全套门禁验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
QT_QPA_PLATFORM=offscreen uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| main_window_ui.py 重写遗漏 `_ui` 属性 | 对照计划属性清单逐一核对；优先跑 `TestMainWindow`/`TestWorkflowStage` |
| `_main_stack` 页序偏移 | 确保 addWidget 顺序 setup→scanning→results；跑 `TestWorkflowStage` |
| QSS 令牌缺失导致 KeyError | 步骤 3 后手动调用 `load_stylesheet()` 验证；`grep -oP '\$\{(\w+)\}' styles.qss \| sort -u` 与 `QSS_TOKENS.keys()` 比对 |
| QMenuBar 与 HeaderBar 视觉冲突 | QMenuBar 保留原生样式不模板化；HeaderBar 用 COLOR_PRIMARY 背景；如冲突可隐藏 menubar（测试不依赖可见性） |
| `_splitter` 命名冲突 | 新增 `_sidebar_splitter`，不复用现有 `_splitter`（results_splitter） |
| FakeApp 测试兼容 | `load_stylesheet()` 读真实 QSS 并替换令牌，FakeApp.setStyleSheet 是空操作，测试通过 |

## 关键文件

- `/home/zhou/fuscan/src/fuscan/theme.py`（新建）
- `/home/zhou/fuscan/src/fuscan/gui/main_window_ui.py`（重写）
- `/home/zhou/fuscan/src/fuscan/gui/main_window.py`（修改）
- `/home/zhou/fuscan/src/fuscan/gui/styles.qss`（模板化）
- `/home/zhou/fuscan/src/fuscan/gui/app.py`（新增 load_stylesheet）
- `/home/zhou/fuscan/src/fuscan/gui/detail_dialog.py`（色值改用 theme）
- `/home/zhou/fuscan/src/fuscan/gui/detail_dialog_ui.py`（移除内联样式）
- `/home/zhou/fuscan/tests/test_gui.py`（2 处最小修改）

## 验证方式

1. 单元测试：`QT_QPA_PLATFORM=offscreen uv run pytest tests/test_gui.py -x -m "not slow"`
2. 全套门禁：ruff check + ruff format --check + pyrefly check + pytest --cov-fail-under=96
3. 手动启动：`python -m fuscan gui`（验证 HeaderBar/Sidebar 视觉效果，确认 Tab 切换、Sidebar 切换、扫描流程、规则管理、历史查看全部正常）
