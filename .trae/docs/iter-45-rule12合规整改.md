# iter-45：rule-12 PySide 开发规范合规整改

## 需求清单

参见 `.trae/req/req-10-rule12合规整改.md`，共 4 项（3 项实施 + 1 项评估延迟）。

## 迭代目标

依据 `rule-12-pyside-dev.md` 四节规范，对现有 GUI 代码进行合规整改：
1. 跨线程槽加 `@Slot()` 装饰
2. 内联 QSS 提到 theme 令牌
3. SVG 图标纳入 `.qrc` 资源系统
4. Model/View 迁移评估

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `src/fuscan/theme.py` | 新增 `FONT_FAMILY_MONO` 令牌与 `QSS_TOKENS` 条目 |
| `src/fuscan/gui/styles.qss` | `#rule_editor` 字体从硬编码改为 `${FONT_FAMILY_MONO}` |
| `src/fuscan/gui/rule_editor.ui` | objectName `editor`→`rule_editor`，删除内联 `styleSheet` |
| `src/fuscan/gui/rule_editor_ui.py` | 恢复基线风格（双兼容 try/except、无 u 前缀、无 `(object)`），保留 `self.rule_editor` |
| `src/fuscan/gui/rule_editor.py` | `self.editor`→`self.rule_editor`（7 处） |
| `src/fuscan/gui/main_window.py` | 加 `Slot`/`QFile` 导入（双兼容），4 槽加 `@Slot` 装饰，19 个图标路径改 `:/` 前缀，新增 `_read_svg_text` 支持 `QFile` 读取，import `resources_rc` 注册资源 |
| `src/fuscan/gui/detail_dialog.py` | `_ICON_TARGET` 改 `:/icons/target.svg`，移除未用的 `Path` 导入 |
| `src/fuscan/gui/resources_rc.py` | 新增：pyside2-rcc 编译产物 + 双兼容补丁 |
| `src/fuscan/assets/resources.qrc` | 新增：19 个 SVG 图标资源声明 |
| `tests/test_gui.py` | `dialog.editor`→`dialog.rule_editor`（13 处） |

## 关键决策与依据

### P1：@Slot 装饰 + 内联 QSS 令牌化

- **@Slot 装饰**：rule-12 要求"跨线程必走信号槽，槽建议加 `@Slot()` 装饰"。`ScanWorker` 在 QThread 中 emit 信号，主窗口 4 个槽（`_on_scan_cancelled`/`_on_scan_progress`/`_on_scan_finished`/`_on_scan_failed`）此前无装饰，加 `@Slot(object)`/`@Slot(str)`。
- **FONT_FAMILY_MONO 令牌**：`rule_editor.ui` 的 `#editor` 硬编码 `"Cascadia Code", "Consolas", "Courier New", monospace`，违反 rule-12"QSS 用 `${TOKEN}` 引用，禁止硬编码"。新增 `FONT_FAMILY_MONO` 令牌入 `theme.py` + `QSS_TOKENS`，`styles.qss` 用 `${FONT_FAMILY_MONO}` 引用。
- **objectName 对齐**：`rule_editor.ui` objectName 从 `editor` 改为 `rule_editor`，与 QSS 选择器 `#rule_editor` 对齐。删除内联 `styleSheet` 属性（rule-12："UI 仅在 `.ui` 定义，禁止 `.py` 内实现 UI 初始配置代码"——内联 styleSheet 属于 UI 初始配置）。
- **_ui.py 恢复基线**：编辑 `.ui` 后 `rule_editor_ui.py` 被重新生成为 uic 原始输出（star imports + u 前缀 + `(object)`），引入 48 个 ruff 错误。手动恢复基线风格（双兼容 try/except、无 u 前缀、`class Ui_RuleEditorDialog:` 无基类），保留 `self.rule_editor` 匹配新 objectName。

### P2：.qrc 资源系统改造

- **范围**：19 个 SVG 图标（共 28KB）纳入 `.qrc`，编译为 `resources_rc.py`。QSS 和 PDF 留磁盘（QSS 需运行时令牌替换，PDF 由外部阅读器打开）。
- **双兼容**：pyside2-rcc 可用，pyside6-rcc 不可用。编译后手动补丁 import 为 `try: from PySide2 import QtCore / except ImportError: from PySide6 import QtCore`，与 `_ui.py` 文件同模式。
- **_read_svg_text 辅助函数**：`_load_themed_icon` 原用 `Path(svg_path).read_text()` 读取 SVG 文本着色，不支持 `:/` 路径。新增 `_read_svg_text`：`:/` 前缀用 `QFile` 读取，否则回退 `Path.read_text`。着色逻辑不变（strip fill → inject theme color → QSvgRenderer 渲染）。
- **资源注册**：`main_window.py` 顶部 `from fuscan.gui import resources_rc  # noqa: F401`，import 时自动调 `qInitResources()` 注册。测试中 `import MainWindow` 也会触发注册。
- **打包**：`resources_rc.py` 在 `src/fuscan/gui/` 下，hatchling 默认包含；SVG 原文件保留在 `assets/icons/` 供 rcc 重新编译，不影响运行时（资源已嵌入二进制）。

### P3：Model/View 迁移评估（延迟）

- **评估 7 个 widget**：仅 `result_tree`（扫描结果，可达上千条）符合 rule-12"大数据量"。其余（rules_tree/history_list/matched_files_list/skipped_dirs_list/rules_file_list/sidebar）数据量小，无迁移收益。
- **延迟依据**：`result_tree` 当前已有 `setUpdatesEnabled(False)` + 300ms 防抖节流（iter-44），典型扫描量下性能充足。完整迁移需：改 `.ui`（QTreeWidget→QTreeView）、重写 3 种分组模式（flat/by-rule/by-severity）、severity 着色、排序、筛选，500+ 行重构，高回归风险。
- **rule-12 用词**："优先用"非"必须用"，rule-01 要求"避免过度工程化"。延迟至万级文件性能瓶颈再迁移。

## 代码实现情况

- P1：7 文件改动，@Slot 装饰 4 槽 + FONT_FAMILY_MONO 令牌 + objectName 对齐 + _ui.py 恢复基线
- P2：4 文件改动 + 2 新增文件，.qrc 编译 + 双兼容补丁 + 图标路径迁移 + _read_svg_text 辅助
- P3：仅评估，无代码改动

## 整合优化情况

- `_read_svg_text` 从 `_load_themed_icon` 提取为独立函数，支持 `:/` 与磁盘路径双模式
- `detail_dialog.py` 移除未用的 `Path` 导入（图标路径改 `:/` 后不再需要）

## 测试验证结果

| 门禁 | 结果 |
|------|------|
| ruff check | 605 errors（基线一致） |
| ruff format | 80 files already formatted |
| pyrefly | 814 errors（812 基线 + 2 PySide2 stub：`QFile.open` overload + `PySide6` import） |
| pytest | 1306 passed, 16 deselected, coverage 96.00% ≥ 95% |

## 遗留事项

- P3（Model/View 迁移）延迟，待万级文件性能瓶颈再实施
- `resources_rc.py` 重新编译需 `pyside2-rcc`（在 `.venv\Scripts\` 中），SVG 变更后须重新编译并提交

## 下一轮计划

无明确下一轮。rule-12 合规整改已闭环（3 项实施 + 1 项评估延迟）。
