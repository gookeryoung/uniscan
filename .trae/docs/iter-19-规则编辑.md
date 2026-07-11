# iter-19：GUI 内嵌规则编辑器

## 本轮目标

实现需求02-10：在 GUI 内提供规则文件编辑功能，支持选择已加载的规则文件、编辑 YAML 内容、保存并重新加载规则集。

## 改动文件清单

### 源代码（2 文件）

- `src/fuscan/gui/rule_editor.py`（新增）：
  - `RuleEditorDialog(QDialog)`：规则文件编辑对话框
  - 文件选择下拉框（QComboBox）切换已加载的规则文件
  - 等宽字体 QTextEdit 编辑区
  - `_on_save()`：YAML 语法验证 → 写入文件 → 规则解析验证 → 发射 `rules_saved` 信号
  - `_on_reload()`：放弃修改，从文件重新加载内容
  - `rules_saved = Signal(str)`：保存成功后通知主窗口重新加载
  - 空规则文件列表时禁用编辑器并显示提示

- `src/fuscan/gui/main_window.py`：
  - 左侧规则文件列表按钮栏新增"编辑"按钮
  - 文件菜单新增"编辑规则..."菜单项
  - `_on_edit_rules()`：打开 RuleEditorDialog，连接 `rules_saved` 信号
  - `_on_rules_saved(_path)`：调用 `_reload_and_refresh()` 重新加载规则集并刷新 UI

### 测试（1 文件）

- `tests/test_gui.py`：
  - 顶部导入块新增 `from fuscan.gui.detail_dialog import HitDetailDialog`（修复 P3 遗留 F821）
  - `TestRuleEditor` 测试类（14 项测试）：
    - 编辑按钮存在性、无规则时提示
    - 编辑器加载文件内容、切换文件
    - 保存写入文件并发射信号、无效 YAML 报错
    - 重新加载恢复内容、空规则文件列表
    - MainWindow 编辑保存后重新加载规则集
    - 无效索引清空编辑器、读取失败禁用编辑器
    - 无效索引保存无操作、写入失败报错
    - 规则解析失败仍发射信号（文件已保存）

### 需求文档（1 文件）

- `.trae/req/需求02.md`：需求02-10 标记为 `[x]`，需求02 全部 12 项完成

## 关键决策与依据

1. **GUI 内嵌编辑器而非外部调用**：用户确认使用 GUI 内嵌编辑器，无需依赖外部编辑器，体验更连贯。
2. **双重验证**：保存时先验证 YAML 语法（`yaml.safe_load`），写入文件后再验证规则解析（`load_ruleset`），确保规则文件语法和语义均有效。
3. **规则解析失败仍发射信号**：文件已写入磁盘，即使规则解析失败也通知主窗口重新加载（主窗口会处理解析错误），避免文件与内存规则集不一致。
4. **QWidget | None 替代 Optional[QWidget]**：新文件使用 `X | None` 语法（`from __future__ import annotations` 延迟求值），符合 rule-11 Python 3.8+ 兼容性要求。
5. **mock QMessageBox 避免 modal 阻塞**：测试中 `QMessageBox.information/warning` 是模态对话框会阻塞测试，通过 monkeypatch 替换为空函数。

## 验证结果

- ruff check：rule_editor.py 0 errors；main_window.py 8 errors（均为既有 UP006/UP045/ARG002）
- ruff format：全部通过
- pytest：523 passed, 1 skipped, 1 deselected（既有 `test_window_geometry_restored`）
- coverage：89.92%（较 P3 的 89.70% 提升 0.22%）；rule_editor.py 100% 覆盖

## 遗留事项

- `test_window_geometry_restored`：既有 PySide2 offscreen 环境问题。
- coverage 89.92% 低于 95% 门槛：既有技术债。
- main_window.py UP006/UP045 全量迁移：需单独迭代。
- 需求02 全部 12 项已完成，需求01 全部 5 项已完成。
