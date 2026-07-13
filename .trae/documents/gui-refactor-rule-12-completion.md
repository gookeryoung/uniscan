# GUI 重构收尾计划：rule-12 验证与提交

## 背景

基于 `rule-12-gui-pyside-standards.md` 的 GUI 重构已由前两次会话完成绝大部分代码改动。本计划仅承接**最后收尾**：修复 1 个失败测试 → 全套门禁 → 文档 → 提交。

## 当前状态分析

### 已完成（代码改动全部就位，git status 显示为 modified/untracked）

| 文件 | 状态 | 改动内容 |
|------|------|---------|
| [theme.py](file:///home/zhou/fuscan/src/fuscan/theme.py) | untracked(新) | 37 个设计令牌 + `QSS_TOKENS` 字典 |
| [styles.qss](file:///home/zhou/fuscan/src/fuscan/gui/styles.qss) | modified | 全部硬编码替换为 `${TOKEN}` 占位符，新增 HeaderBar/Sidebar/TabStack 段 |
| [app.py](file:///home/zhou/fuscan/src/fuscan/gui/app.py) | modified | 新增 `load_stylesheet()`，`launch()` 改用令牌替换后的 QSS |
| [main_window_ui.py](file:///home/zhou/fuscan/src/fuscan/gui/main_window_ui.py) | modified | 重写为 HeaderBar + TabStack(3 Tab) + Sidebar + main_stack 结构，保留 menubar 与全部 `_ui` 属性名 |
| [main_window.py](file:///home/zhou/fuscan/src/fuscan/gui/main_window.py) | modified | `_bind_widgets`/`_configure_ui` 新增 header/sidebar 绑定；新增 `_on_header_tab_changed`/`_on_sidebar_stage_changed`；`_switch_stage` 同步 sidebar；`_SEVERITY_COLORS` 引用 theme |
| [detail_dialog.py](file:///home/zhou/fuscan/src/fuscan/gui/detail_dialog.py) | modified | `_SEVERITY_COLORS` 引用 theme；`_info_label` 改绑 `hit_info_label` |
| [detail_dialog_ui.py](file:///home/zhou/fuscan/src/fuscan/gui/detail_dialog_ui.py) | modified | `info_label` → `hit_info_label`（属性名+objectName），移除内联样式 |
| [test_gui.py](file:///home/zhou/fuscan/tests/test_gui.py) | modified | L1371-1388 色值测试改用 `load_stylesheet()`；`TestWorkflowStage` 新增 3 个测试 |
| [rule-12-gui-pyside-standards.md](file:///home/zhou/fuscan/.trae/rules/rule-12-gui-pyside-standards.md) | untracked(新) | 新规则文件（替换原 rule-12-pyqt-standards.md） |
| rule-12-pyqt-standards.md | deleted | 旧规则被新规则替代 |

### 唯一阻塞点：1 个失败测试

[tests/test_gui.py L1359-1371](file:///home/zhou/fuscan/tests/test_gui.py#L1359-L1371) `test_on_header_tab_changed_switches_tab_stack`：

```python
window._on_header_tab_changed(0)
assert window._tab_stack.currentIndex() == 0
assert window._sidebar.isVisible()  # ← FAIL: 返回 False
```

**根因**：`_on_header_tab_changed(0)` 调用了 `self._sidebar.setVisible(True)`，但窗口本身从未 `show()`，Qt 中 `isVisible()` 要求 widget 及其父链均已显示才返回 True。

**修复方案**：在 visibility 断言前加 `window.show()` + `qapp.processEvents()`，与本文件既有模式一致（L1180-1185 `test_view_results_btn_hidden_initially`、L2325-2331 `test_folder_mode_shows_folder_selectors` 均如此）。

## 待执行步骤

### 步骤 1：修复失败测试

[tests/test_gui.py L1359-1371](file:///home/zhou/fuscan/tests/test_gui.py#L1359-L1371)

在 `test_on_header_tab_changed_switches_tab_stack` 的 `window = MainWindow()` 后、visibility 断言前插入 `window.show()` + `qapp.processEvents()`。由于该测试需在切换 Tab 后检查 sidebar 可见性，`show()` 应在首次 `_on_header_tab_changed` 调用前执行一次即可（sidebar 作为子部件，窗口显示后其 `setVisible` 状态立即生效）。

修改后测试体：

```python
def test_on_header_tab_changed_switches_tab_stack(self, qapp: QApplication) -> None:
    """_on_header_tab_changed 应切换 tab_stack 页面。"""
    window = MainWindow()
    window.show()
    qapp.processEvents()
    window._on_header_tab_changed(1)
    assert window._tab_stack.currentIndex() == 1
    assert not window._sidebar.isVisible()
    window._on_header_tab_changed(2)
    assert window._tab_stack.currentIndex() == 2
    assert not window._sidebar.isVisible()
    window._on_header_tab_changed(0)
    assert window._tab_stack.currentIndex() == 0
    assert window._sidebar.isVisible()
    window.close()
```

### 步骤 2：全套门禁验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
QT_QPA_PLATFORM=offscreen uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

**预期**：
- ruff/pyrefly：0 错误（代码已在前次会话通过）
- pytest：964 passed（原 961 + 3 新测试），覆盖率 ≥ 96.05%（新方法 `_on_header_tab_changed`/`_on_sidebar_stage_changed` 被覆盖，覆盖率应上升）

**若覆盖率不足 96%**：检查 `_on_settings`/`_on_about` 是否已有测试覆盖（这两个方法连接了 header 按钮，但可能已被既有 `test_*_about*`/`test_*_settings*` 覆盖）。若未覆盖，补充针对性测试。

### 步骤 3：创建需求与迭代文档

- 创建 `.trae/req/req-08-gui重构rule12.md`：记录本次重构需求（HeaderBar+Sidebar+TabStack 布局、设计令牌集中化、QSS 模板化、保留全部既有功能）
- 创建 `.trae/docs/iter-28-gui重构rule12.md`：记录改动文件清单、关键决策（保留 menubar、保留 `_main_stack` 页序、色值偏离 rule-12 沿用 `#0366d6`、blockSignals 防循环）、验证结果

### 步骤 4：Git 提交与推送

按文件名 `git add`（不用 `git add -A`）以下文件：

```
src/fuscan/theme.py
src/fuscan/gui/app.py
src/fuscan/gui/detail_dialog.py
src/fuscan/gui/detail_dialog_ui.py
src/fuscan/gui/main_window.py
src/fuscan/gui/main_window_ui.py
src/fuscan/gui/styles.qss
tests/test_gui.py
.trae/rules/rule-12-gui-pyside-standards.md
.trae/rules/rule-12-pyqt-standards.md   (deleted)
.trae/req/req-08-gui重构rule12.md
.trae/docs/iter-28-gui重构rule12.md
.trae/documents/gui-refactor-rule-12.md
.trae/documents/gui-refactor-rule-12-continuation.md
.trae/documents/gui-refactor-rule-12-completion.md
```

提交信息（中文，遵循 rule-09 风格）：

```
refactor(gui): 按 rule-12 重构界面为 HeaderBar+Sidebar+TabStack 布局

新增 theme.py 集中管理设计令牌，styles.qss 改用 ${TOKEN} 模板化，
main_window_ui.py 重写为头部栏+侧边栏+三 Tab 页结构，保留 menubar
与全部既有 _ui 属性名及 main_stack 页序，确保测试零回归。
```

分支已跟踪 origin/main，push 自动执行。

## 假设与决策

| 决策 | 依据 |
|------|------|
| 修复用 `window.show()`+`processEvents()` 而非 `not isHidden()` | 匹配本文件既有模式（L1180-1185/L2325-2331），语义更准确 |
| 不改 `_on_header_tab_changed` 实现 | 实现正确（`setVisible(True)` 已设），问题在测试未 show 窗口 |
| 保留 menubar 与 HeaderBar 并存 | 既有测试依赖 `file_menu`/`help_menu` 对象 |
| 色值沿用 `#0366d6` 偏离 rule-12 表格 `#0887A0` | 用户前次会话明确要求保留原色 |
| req/iter 序号取 08/28 | 最近一次为 req-07/iter-27（commit a9238ff） |

## 验证方式

1. 步骤 2 全套门禁通过（ruff + pyrefly + pytest 覆盖率≥96%）
2. 3 个新测试全部 PASSED
3. git log 显示新提交，origin/main 已更新
