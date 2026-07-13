# 迭代 28：GUI 按 rule-12 重构界面设计

## 迭代目标

按 `rule-12-gui-pyside-standards.md` 重构 GUI 布局为 HeaderBar + Sidebar + TabStack + StatusBar
四区结构，新增 `theme.py` 集中管理设计令牌，`styles.qss` 改用 `${TOKEN}` 模板化，
严格保留全部既有功能与测试（零回归）。

## 改动文件清单

### 新建文件

- `src/fuscan/theme.py`：37 个设计令牌常量 + `QSS_TOKENS` 字典（色彩/排版/间距/圆角/尺寸）
- `.trae/rules/rule-12-gui-pyside-standards.md`：PySide2/PySide6 GUI 开发规范（替换旧 pyqt 规范）

### 修改文件

- `src/fuscan/gui/styles.qss`：全部硬编码色值/字号/圆角替换为 `${TOKEN}` 占位符；新增 HeaderBar/Sidebar/TabStack 样式段
- `src/fuscan/gui/app.py`：新增 `load_stylesheet()` 函数（`string.Template.substitute` 替换令牌）；`launch()` 改用替换后 QSS；`__all__` 增加 `load_stylesheet`
- `src/fuscan/gui/main_window_ui.py`：重写为 HeaderBar(QFrame#header_bar) + tab_stack(QStackedWidget 3 Tab) + sidebar(QListWidget) + main_stack 结构；rules_group 移入规则 Tab，history_list 移入历史 Tab；保留 menubar 与全部 `_ui` 属性名
- `src/fuscan/gui/main_window.py`：
  - `_bind_widgets` 新增 tab_stack/sidebar/header 按钮/sidebar_splitter 绑定
  - `_configure_ui` 新增 QButtonGroup(header tabs)/sidebar 填充/信号槽连接/splitter 初始比例
  - 新增 `_on_header_tab_changed`（切换 tab_stack + sidebar 可见性）
  - 新增 `_on_sidebar_stage_changed`（row→WorkflowStage 映射 + _switch_stage）
  - `_switch_stage` 末尾 blockSignals 包裹 setCurrentRow 同步 sidebar
  - `_SEVERITY_COLORS` 引用 theme.COLOR_DANGER/WARNING/INFO
  - `_on_about` 文本「Python + PySide2」→「Python + PySide」
- `src/fuscan/gui/detail_dialog.py`：`_SEVERITY_COLORS` 引用 theme 常量；`_info_label` 改绑 `hit_info_label`
- `src/fuscan/gui/detail_dialog_ui.py`：`info_label` → `hit_info_label`（属性名+objectName），移除内联 setStyleSheet
- `tests/test_gui.py`：
  - L1371-1388 色值测试改用 `load_stylesheet()` 替代 `_QSS_PATH.read_text()`
  - `TestWorkflowStage` 新增 3 个测试：`test_switch_stage_syncs_sidebar`/`test_on_header_tab_changed_switches_tab_stack`/`test_on_sidebar_stage_changed_switches_main_stack`

### 删除文件

- `.trae/rules/rule-12-pyqt-standards.md`：被 `rule-12-gui-pyside-standards.md` 替代

## 关键决策与依据

1. **保留 menubar 与 HeaderBar 并存**：既有测试依赖 `file_menu`/`help_menu` 等 QMenu 对象，删除 menubar 会破坏大量测试。HeaderBar 置于 menubar 下方，视觉上 menubar 承载传统菜单快捷键入口，HeaderBar 承载 Tab 切换。
2. **保留 `_main_stack` 页序不变**：38 处测试检查 `currentIndex` 0/1/2 对应 setup/scanning/results。将 main_stack 嵌入扫描 Tab 的 sidebar_splitter 内，页序与 addWidget 顺序完全保留。
3. **色值沿用 #0366d6 偏离 rule-12 表格**：用户明确要求保留现有 GitHub Desktop 配色，仅做集中化管理（theme.py），不改变视觉风格。
4. **blockSignals 防循环**：`_switch_stage` 调 `setCurrentRow` 会触发 `currentRowChanged`，进而回调 `_on_sidebar_stage_changed` → `_switch_stage` 形成循环。用 blockSignals(True/False) 包裹阻断。
5. **`hit_info_label` 改名**：原 `info_label` objectName 过于通用，易与其他 QLabel 冲突；改名后匹配 styles.qss 中 `QLabel#hit_info_label` 选择器，移除内联样式由 QSS 托管。
6. **QSS 模板用 `string.Template` 而非 f-string**：QSS 文件独立于 Python 代码，`string.Template` 的 `${TOKEN}` 语法与 QSS 原生 `${}` 无冲突，且 `substitute()` 缺令牌时抛 KeyError 利于及早发现。
7. **`test_on_header_tab_changed` 需 `window.show()`**：Qt 中 `isVisible()` 要求 widget 及父链均已显示才返回 True，测试需 `show()`+`processEvents()` 后才能断言 sidebar 可见性，匹配文件既有模式（L1180-1185）。

## 验证结果

- ruff check：All checks passed
- ruff format --check：70 files already formatted
- pyrefly check：0 errors (108 suppressed, 17 warnings)
- pytest -m "not slow" --cov：964 passed, 4 deselected, coverage 96.10%
- 3 个新增测试全部 PASSED

## 遗留事项

- 未做 `self.tr()` 国际化迁移（超出本次范围，UI 字符串仍为硬编码中文）
- 未做 QSettings 配置持久化迁移（超出本次范围，仍用 dataclass + JSON）
- 未做响应式侧边栏自动折叠（宽度 < 1000px 时折叠为图标条，超出本次范围）
- `main_window.py` 覆盖率 93%（1364-1372 等行为扫描中页文件列表交互分支，非本次新增代码）
