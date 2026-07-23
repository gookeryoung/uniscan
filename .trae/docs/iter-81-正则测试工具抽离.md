# iter-81：正则表达式测试工具抽离为独立窗口

## 需求清单

- [x] 需求：把正则表达式验证单独设计为独立窗口，作为工具调用

## 迭代目标

将 `RuleEditorDialog` 内嵌的正则表达式验证面板（`regex_test_group`）抽离为
独立的 `RegexTesterDialog` 窗口，使其：

1. 可作为工具独立调用（不依赖规则编辑器），通过主窗口「工具(&T)」菜单入口
2. 规则编辑器中保留一个按钮调用此独立窗口，便于编辑规则时验证正则
3. 支持通过 `initial_pattern` 参数预填待测正则表达式

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/gui/regex_tester.ui` | 新增：独立正则验证窗口 UI（720×680），从 `rule_editor.ui` 的 `regex_test_group` 迁出，调整为顶层 QDialog 布局（regex_input_layout + regex_io_layout + regex_cheatsheet_label + regex_cheatsheet_view + close_btn） |
| `src/fuscan/gui/regex_tester_ui.py` | 新增：由 `pyside2-uic` 从 `regex_tester.ui` 生成 |
| `src/fuscan/gui/regex_tester.py` | 新增：`RegexTesterDialog(QDialog, Ui_RegexTesterDialog)` 实现，迁入 `_REGEX_CHEATSHEET` 常量与 `_on_test_regex` 方法；构造函数支持 `initial_pattern` 参数预填；`_configure_ui` 设置信号槽连接（test_btn.clicked / pattern_edit.returnPressed）+ 速查手册内容 + layout stretch |
| `src/fuscan/gui/rule_editor.ui` | 移除 `regex_test_group`（含 6 个子控件 + 4 层嵌套布局），窗口高度 780→600；在 `btn_layout` 中 `reload_btn` 后插入 `regex_tester_btn`（"正则测试工具..."） |
| `src/fuscan/gui/rule_editor_ui.py` | 重新生成（移除 regex_* 控件，新增 regex_tester_btn） |
| `src/fuscan/gui/rule_editor.py` | 移除 `_REGEX_CHEATSHEET` 常量、`_on_test_regex` 方法、`re` 导入、正则相关信号槽连接与 layout stretch；新增 `_on_open_regex_tester` 方法（模态弹出 `RegexTesterDialog`）；模块 docstring 同步更新 |
| `src/fuscan/gui/main_window.ui` | 在 `scan_menu` 与 `help_menu` 之间新增 `tools_menu`（"工具(&T)"），包含 `regex_tester_action`（"正则表达式测试工具..."，快捷键 Ctrl+R） |
| `src/fuscan/gui/main_window_ui.py` | 重新生成（新增 tools_menu 与 regex_tester_action） |
| `src/fuscan/gui/main_window.py` | 新增 `_on_open_regex_tester` 方法（延迟导入 `RegexTesterDialog` + 模态 exec_）；`_setup_actions` 中连接 `regex_tester_action.triggered → _on_open_regex_tester`；`_PRIMARY_ICON_TARGETS` 新增 `(_ICON_SEARCH, "regex_tester_action")` 图标绑定 |
| `tests/test_gui.py` | 原 `TestRuleEditorRegexPanel`（14 测试）改造为 `TestRegexTesterDialog`（16 测试，去除 rules_path 依赖，新增 `test_initial_pattern_prefilled` / `test_initial_pattern_empty_by_default`）；新增 `TestRuleEditorRegexTesterButton`（2 测试：按钮存在性 + 点击弹出 mock 验证）；新增 `TestMainWindowRegexTesterAction`（3 测试：action 存在性 + 快捷键 + `_on_open_regex_tester` 弹出 mock 验证） |

## 关键决策与依据

### D1：抽离为独立工具而非保留内嵌面板

**决策**：将 `regex_test_group` 从 `RuleEditorDialog` 完全迁出为独立的
`RegexTesterDialog`，主窗口新增「工具」菜单独立调用，规则编辑器保留按钮入口。

**依据**：
- 用户需求明确"作为工具调用"，意味着不仅服务于规则编辑场景
- 独立窗口可在不加载任何规则文件的情况下使用，降低使用门槛
- 规则编辑器窗口高度从 780 降至 600，编辑区获得更大空间
- 与 DetailPanel/RulesFilePanel 等 iter-80 控制器解耦思路一致：
  单一职责的 UI 单元独立成类

### D2：`initial_pattern` 参数设计

**决策**：`RegexTesterDialog.__init__(parent=None, initial_pattern="")` 接收
可选的初始正则表达式，便于规则编辑器调用时预填待测内容。

**依据**：
- 当前规则编辑器按钮入口暂未传 `initial_pattern`（用户可能从空白开始测试），
  但保留参数为未来「编辑当前规则正则时一键带入测试工具」预留扩展点
- 默认空字符串保持工具独立调用时的清洁状态
- 测试覆盖 `test_initial_pattern_prefilled` 与 `test_initial_pattern_empty_by_default`
  两种场景

### D3：图标复用 SEARCH 而非新增图标资源

**决策**：`regex_tester_action` 复用既有 `_ICON_SEARCH`（放大镜）图标。

**依据**：
- `icons.py` 无专用"工具"或"正则"图标，新增需补 SVG + qrc 资源
- SEARCH 语义（搜索/匹配）与正则测试工具的"在文本中查找匹配"行为契合
- 与 `select_path_action` 共用同一图标资源，符合 rule-12「同一路径在缓存中
  只加载一次，可绑定多个控件」的既有模式
- 菜单图标风格保持一致（与 select_path_action 同为搜索类操作）

### D4：工具菜单位置与快捷键

**决策**：新增 `tools_menu` 位于 `scan_menu` 与 `help_menu` 之间；
`regex_tester_action` 快捷键 `Ctrl+R`。

**依据**：
- 菜单顺序「文件 → 扫描 → 工具 → 帮助」符合常见 GUI 应用习惯
  （工具类操作介于主流程与帮助之间）
- `Ctrl+R` 语义贴近 "Regex"，且当前未与其他 action 冲突
  （`Ctrl+O/E/S/Shift+S/Q/,` 已被文件菜单占用，`F5` 扫描，`F1` 手册）
- 工具菜单作为独立入口，未来可扩展更多工具（如哈希计算、编码转换等）

### D5：测试 mock 策略

**决策**：`TestMainWindowRegexTesterAction.test_on_open_regex_tester_opens_dialog`
通过 `monkeypatch.setattr(regex_tester_module, "RegexTesterDialog", FakeDialog)`
mock 延迟导入的类。

**依据**：
- `_on_open_regex_tester` 内部使用 `from fuscan.gui.regex_tester import RegexTesterDialog`
  延迟导入（加速主窗口启动），故 mock `regex_tester_module.RegexTesterDialog`
  即可在 `from ... import` 时生效
- `TestRuleEditorRegexTesterButton.test_regex_tester_btn_click_opens_dialog`
  同理 mock `rule_editor_module.RegexTesterDialog`
- FakeDialog 记录 `parent` 与 `initial_pattern` 构造参数 + `exec_` 调用，
  验证模态弹出行为而不真正启动事件循环

## 代码实现情况

### 新增 RegexTesterDialog 类结构

```python
class RegexTesterDialog(QDialog, Ui_RegexTesterDialog):
    def __init__(self, parent=None, initial_pattern="") -> None: ...
    def _configure_ui(self, initial_pattern: str) -> None: ...
    def _on_test_regex(self) -> None: ...
```

- `_configure_ui`：信号槽连接 + 速查手册初始化 + `initial_pattern` 预填 +
  layout stretch（输入行/速查手册标签/关闭按钮固定，文本结果列与速查手册内容各占 1）
- `_on_test_regex`：与扫描引擎 `matchers._apply_regex` 行为一致，
  `re.compile(...).finditer(text)` 收集所有非重叠匹配，显示位置/文本/捕获组/命名组

### 主窗口入口集成

- `main_window.ui`：新增 `tools_menu` + `regex_tester_action`（Ctrl+R）
- `main_window.py._setup_actions`：`regex_tester_action.triggered.connect(self._on_open_regex_tester)`
- `main_window.py._on_open_regex_tester`：延迟导入 + `RegexTesterDialog(parent=self).exec_()`

### 规则编辑器入口集成

- `rule_editor.ui`：移除 `regex_test_group`，`btn_layout` 新增 `regex_tester_btn`
- `rule_editor.py._configure_ui`：`regex_tester_btn.clicked.connect(self._on_open_regex_tester)`
- `rule_editor.py._on_open_regex_tester`：`RegexTesterDialog(parent=self).exec_()`

## 测试验证结果

- ruff check：All checks passed
- ruff format --check：104 files already formatted
- pyrefly check：0 errors（46 suppressed）
- pytest：1571 passed（+7）, 16 deselected, coverage 95.14%
  - `regex_tester.py`：100% 覆盖率
  - `rule_editor.py`：100% 覆盖率
  - `main_window.py`：86%（既有水平，新增方法已被测试覆盖）

### 新增测试清单（+7 净增）

| 测试类 | 测试方法 | 说明 |
|--------|---------|------|
| TestRegexTesterDialog | test_initial_pattern_prefilled | 新增：initial_pattern 预填 |
| TestRegexTesterDialog | test_initial_pattern_empty_by_default | 新增：默认空 |
| TestRegexTesterDialog | 其余 14 个 | 从 TestRuleEditorRegexPanel 迁移，改用 RegexTesterDialog |
| TestRuleEditorRegexTesterButton | test_regex_tester_btn_exists | 新增 |
| TestRuleEditorRegexTesterButton | test_regex_tester_btn_click_opens_dialog | 新增：mock 验证 |
| TestMainWindowRegexTesterAction | test_regex_tester_action_exists | 新增 |
| TestMainWindowRegexTesterAction | test_regex_tester_action_shortcut | 新增 |
| TestMainWindowRegexTesterAction | test_on_open_regex_tester_opens_dialog | 新增：mock 验证 |

## 遗留事项

- `regex_tester_btn` 当前未传入 `initial_pattern`，未来如需「编辑当前规则正则时
  一键带入测试工具」可在 `_on_open_regex_tester` 中解析当前光标位置的正则并传入
- 工具菜单目前仅含正则测试工具一项，未来新增工具（哈希计算、编码转换等）可直接
  `addaction` 到 `tools_menu`

## 下一轮计划

正则测试工具抽离完成，独立工具入口与规则编辑器入口均已打通。后续如用户提出
新工具需求，可直接挂载到「工具」菜单下。
