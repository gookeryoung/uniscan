# GUI 精简整合优化 — 收尾实施计划

## 摘要

延续已批准的 `gui-simplification.md` 方案。`.ui` 文件已修改、`_ui.py` 已重编译、`_bind_widgets` 中 9 个废弃绑定已移除、`_configure_ui` 中 8 个废弃信号连接已移除。但 `main_window.py` 仍有多处引用已删除 widget，导致代码当前无法运行。本计划完成剩余的全部修改并通过验证。

## 当前状态分析

### 已完成
- `.ui` 文件：10 个 widget 已删除，layout 已精简，tooltip 已添加
- `main_window_ui.py`：已用 pyside2-uic 重编译
- `main_window.py` `_bind_widgets`：9 个废弃绑定已移除
- `main_window.py` `_configure_ui` 信号槽：8 个废弃连接已移除

### 未完成（当前代码处于不可运行状态）
1. `main_window.py` 导入缺失 `QKeySequence`/`QAction`/`QMenu`/`QShortcut`
2. `main_window.py` `_configure_ui` 中 `filter_layout` stretch 仍为 6 项（实际仅 3 项）
3. `main_window.py` `_configure_ui` 末尾未调用 `_setup_context_menus()` 和 `_setup_shortcuts()`
4. `main_window.py` 缺少 5 个新方法：`_setup_context_menus`、`_on_result_tree_context_menu`、`_on_rules_file_list_context_menu`、`_setup_shortcuts`、`_set_use_builtin`
5. `main_window.py` 未删除 4 个旧方法：`_on_toggle_builtin`、`_on_batch_process`、`_on_locate_hit`、`_build_rules_label`
6. `main_window.py` 6 个方法仍引用已删除 widget（16 处引用）
7. `styles.qss` 第 226-242 行仍引用已删除按钮
8. `test_gui.py` 有 37 处引用已删除 widget、3 个废弃测试待删、6 个新测试待加

## 实施步骤

### 步骤 1：修复 `main_window.py` 导入

**文件**：`src/fuscan/gui/main_window.py` 第 34、35 行

**当前**：
```python
from PySide2.QtGui import QColor, QIcon, QTextCharFormat, QTextCursor
from PySide2.QtWidgets import (
    QAbstractButton,
    QApplication,
    ...
)
```

**改为**：
```python
from PySide2.QtGui import QColor, QIcon, QKeySequence, QTextCharFormat, QTextCursor
from PySide2.QtWidgets import (
    QAbstractButton,
    QAction,
    QApplication,
    ...
    QMenu,
    ...
    QShortcut,
    ...
)
```

在 QtGui 导入行添加 `QKeySequence`；在 QtWidgets 导入中按字母序添加 `QAction`（Appliction 前）、`QMenu`（QMessageBox 后）、`QShortcut`（QTableWidget 前）。

### 步骤 2：修复 `filter_layout` stretch

**文件**：`src/fuscan/gui/main_window.py` 第 280-285 行

**当前**（6 项，但 layout 实际只有 3 项）：
```python
ui.filter_layout.setStretch(0, 0)
ui.filter_layout.setStretch(1, 2)
ui.filter_layout.setStretch(2, 0)
ui.filter_layout.setStretch(3, 1)
ui.filter_layout.setStretch(4, 0)
ui.filter_layout.setStretch(5, 1)
```

**改为**（3 项：path_filter_input 占大头，两个 combo 各 1）：
```python
ui.filter_layout.setStretch(0, 2)  # path_filter_input
ui.filter_layout.setStretch(1, 1)  # rule_filter_combo
ui.filter_layout.setStretch(2, 1)  # group_mode_combo
```

### 步骤 3：在 `_configure_ui` 末尾添加调用

**文件**：`src/fuscan/gui/main_window.py`，`_configure_ui` 方法末尾（当前在 actions 信号槽连接之后）

在 `_configure_ui` 最后添加：
```python
# 右键菜单与快捷键
self._setup_context_menus()
self._setup_shortcuts()
```

### 步骤 4：新增 5 个方法

**文件**：`src/fuscan/gui/main_window.py`

在 `_configure_ui` 方法之后、`_apply_config` 方法之前添加以下方法：

```python
def _setup_context_menus(self) -> None:
    """为结果树和规则文件列表配置右键菜单策略。"""
    self._result_tree.setContextMenuPolicy(Qt.CustomContextMenu)
    self._result_tree.customContextMenuRequested.connect(self._on_result_tree_context_menu)
    self._rules_file_list.setContextMenuPolicy(Qt.CustomContextMenu)
    self._rules_file_list.customContextMenuRequested.connect(self._on_rules_file_list_context_menu)

def _on_result_tree_context_menu(self, pos) -> None:
    """结果树右键菜单：复制路径 / 在新窗口打开 / 打开文件位置。"""
    if self._detail_current_result is None:
        return
    menu = QMenu(self._result_tree)
    action_copy = QAction("复制路径", menu)
    action_open_window = QAction("在新窗口打开", menu)
    action_open_location = QAction("打开文件位置", menu)
    action_copy.triggered.connect(self._on_copy_path)
    action_open_window.triggered.connect(self._on_open_in_window)
    action_open_location.triggered.connect(self._on_open_file_location)
    menu.addAction(action_copy)
    menu.addAction(action_open_window)
    menu.addAction(action_open_location)
    menu.exec_(self._result_tree.viewport().mapToGlobal(pos))

def _on_rules_file_list_context_menu(self, pos) -> None:
    """规则文件列表右键菜单：上移 / 下移 / 移除。"""
    if self._rules_file_list.currentRow() < 0:
        return
    menu = QMenu(self._rules_file_list)
    action_up = QAction("上移", menu)
    action_down = QAction("下移", menu)
    action_remove = QAction("移除", menu)
    action_up.triggered.connect(self._on_move_rule_up)
    action_down.triggered.connect(self._on_move_rule_down)
    action_remove.triggered.connect(self._on_remove_rule)
    menu.addAction(action_up)
    menu.addAction(action_down)
    menu.addSeparator()
    menu.addAction(action_remove)
    menu.exec_(self._rules_file_list.viewport().mapToGlobal(pos))

def _setup_shortcuts(self) -> None:
    """创建全局快捷键：F3 下一条命中、Shift+F3 上一条命中。"""
    self._shortcut_next = QShortcut(QKeySequence("F3"), self)
    self._shortcut_next.activated.connect(self._on_next_detail_hit)
    self._shortcut_prev = QShortcut(QKeySequence("Shift+F3"), self)
    self._shortcut_prev.activated.connect(self._on_prev_detail_hit)
    self._shortcut_remove_rule = QShortcut(QKeySequence.Delete, self._rules_file_list)
    self._shortcut_remove_rule.activated.connect(self._on_remove_rule)

def _set_use_builtin(self, enabled: bool) -> None:
    """统一设置通用规则开关并刷新规则集。

    替代原 _on_toggle_builtin 的散落逻辑，供 _on_settings 和测试统一调用。
    """
    self._use_builtin = enabled
    try:
        self._reload_ruleset()
        self._refresh_rules_tree()
        self._refresh_rules_file_list()
        self._update_scan_button()
        if self._ruleset is not None:
            self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
        else:
            self._stats_label.setText("未加载规则")
    except RuleError as exc:
        QMessageBox.warning(self, "规则错误", f"重新加载规则失败:\n{exc}")
```

### 步骤 5：删除 4 个旧方法

**文件**：`src/fuscan/gui/main_window.py`

1. **`_on_toggle_builtin`**（第 538-553 行）：整段删除，已被 `_set_use_builtin` 替代
2. **`_on_batch_process`**（第 880-882 行）：整段删除，死功能
3. **`_on_locate_hit`**（第 1051-1053 行）：整段删除，自动滚动已覆盖
4. **`_build_rules_label`**（第 1127-1133 行）：整段删除，rules_label 已移除

### 步骤 6：修改 6 个现有方法

**文件**：`src/fuscan/gui/main_window.py`

#### 6.1 `_apply_config`（第 436-439 行）

**当前**：
```python
self._use_builtin = self._config.use_builtin
self._use_builtin_checkbox.blockSignals(True)
self._use_builtin_checkbox.setChecked(self._config.use_builtin)
self._use_builtin_checkbox.blockSignals(False)
```

**改为**：
```python
self._use_builtin = self._config.use_builtin
```
（删除后 3 行 checkbox 同步）

#### 6.2 `_init_rules`（第 514-526 行）

**当前**：
```python
if self._ruleset is not None:
    self._rules_label.setText("规则: 内置通用规则")
    self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条通用规则")
except RuleError as exc:
    logger.warning("内置规则加载失败: %s", exc)
    self._rules_label.setText("规则文件: 内置规则加载失败")
```

**改为**：
```python
if self._ruleset is not None:
    self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条通用规则")
except RuleError as exc:
    logger.warning("内置规则加载失败: %s", exc)
    self._stats_label.setText("内置规则加载失败")
```
（删除所有 `_rules_label.setText` 调用，保留 `_stats_label` 更新）

#### 6.3 `_on_load_rules`（第 624 行）

**当前**：
```python
self._reload_ruleset()
self._rules_label.setText(f"规则: {self._build_rules_label()}")
self._refresh_rules_tree()
```

**改为**：
```python
self._reload_ruleset()
self._refresh_rules_tree()
```
（删除 `_rules_label.setText` 行）

#### 6.4 `_on_settings`（第 860-878 行）

**当前**：
```python
self._use_builtin = self._config.use_builtin
self._use_builtin_checkbox.blockSignals(True)
self._use_builtin_checkbox.setChecked(self._config.use_builtin)
self._use_builtin_checkbox.blockSignals(False)
self._reload_ruleset()
self._refresh_rules_tree()
self._refresh_rules_file_list()
self._refresh_drive_buttons()
self._update_scan_button()
if self._ruleset is not None:
    self._rules_label.setText(f"规则: {self._build_rules_label()}")
    self._stats_label.setText(f"已加载 {len(self._ruleset.rules)} 条规则")
```

**改为**：
```python
self._set_use_builtin(self._config.use_builtin)
self._refresh_drive_buttons()
```
（用 `_set_use_builtin` 统一处理规则刷新，删除 checkbox 同步和 rules_label 更新）

#### 6.5 `_reload_and_refresh`（第 1190 行）

**当前**：
```python
self._reload_ruleset()
self._refresh_rules_tree()
self._rules_label.setText(f"规则: {self._build_rules_label()}")
self._update_scan_button()
```

**改为**：
```python
self._reload_ruleset()
self._refresh_rules_tree()
self._update_scan_button()
```
（删除 `_rules_label.setText` 行）

#### 6.6 `_update_detail_nav_label`（第 1055-1067 行）

**当前**：
```python
if total == 0:
    self._detail_nav_label.setText("无命中")
    self._detail_prev_btn.setEnabled(False)
    self._detail_next_btn.setEnabled(False)
    self._detail_locate_btn.setEnabled(False)
else:
    self._detail_nav_label.setText(f"{self._detail_current_hit_index + 1} / {total}")
    self._detail_prev_btn.setEnabled(True)
    self._detail_next_btn.setEnabled(True)
    self._detail_locate_btn.setEnabled(True)
```

**改为**：
```python
if total == 0:
    self._detail_nav_label.setText("无命中")
    self._detail_prev_btn.setEnabled(False)
    self._detail_next_btn.setEnabled(False)
else:
    self._detail_nav_label.setText(f"{self._detail_current_hit_index + 1} / {total}")
    self._detail_prev_btn.setEnabled(True)
    self._detail_next_btn.setEnabled(True)
```
（删除两处 `_detail_locate_btn.setEnabled` 调用）

### 步骤 7：修改 `styles.qss`

**文件**：`src/fuscan/gui/styles.qss` 第 226-242 行

**当前**：
```css
QPushButton#detail_prev_btn, QPushButton#detail_next_btn,
QPushButton#detail_locate_btn, QPushButton#detail_open_location_btn,
QPushButton#detail_copy_path_btn, QPushButton#detail_open_window_btn,
QPushButton#batch_btn {
    ...
}

QPushButton#detail_prev_btn:hover, QPushButton#detail_next_btn:hover,
QPushButton#detail_locate_btn:hover, QPushButton#detail_open_location_btn:hover,
QPushButton#detail_copy_path_btn:hover, QPushButton#detail_open_window_btn:hover,
QPushButton#batch_btn:hover {
    ...
}
```

**改为**：
```css
QPushButton#detail_prev_btn, QPushButton#detail_next_btn,
QPushButton#detail_open_location_btn {
    background: #ffffff;
    color: #24292e;
    border: 1px solid #e1e4e8;
    border-radius: 6px;
    font-size: 13px;
    padding: 6px 14px;
    min-height: 32px;
}

QPushButton#detail_prev_btn:hover, QPushButton#detail_next_btn:hover,
QPushButton#detail_open_location_btn:hover {
    background: #f6f8fa;
    border-color: #0366d6;
    color: #0366d6;
}
```
（移除 `detail_locate_btn`、`detail_copy_path_btn`、`detail_open_window_btn`、`batch_btn` 选择器）

### 步骤 8：修改 `test_gui.py`

**文件**：`tests/test_gui.py`

#### 8.1 替换 ~30 处 `_use_builtin_checkbox.setChecked(X)`

全部替换为 `window._set_use_builtin(X)`。

涉及行（由 Grep 定位）：193, 233, 310, 321, 323, 332, 334, 401, 431, 462, 494, 523, 547, 571, 597, 625, 724, 740, 2547, 2662, 3320, 3333, 3352, 3376。

注意 `setChecked(True)` → `_set_use_builtin(True)`，`setChecked(False)` → `_set_use_builtin(False)`。

第 302 行 `assert window._use_builtin_checkbox.isChecked()` → `assert window._use_builtin is True`。
第 702 行 `assert window._use_builtin_checkbox.isChecked() is False` → `assert window._use_builtin is False`。
第 3420 行 `assert window._use_builtin_checkbox.isChecked() == window._config.use_builtin` → `assert window._use_builtin == window._config.use_builtin`。

#### 8.2 替换 ~7 处 `_rules_label.text()` 断言

- 第 204 行 `assert "rules.yaml" in window._rules_label.text()` → 删除（stats_label 已覆盖）
- 第 331 行 `assert "通用规则" in window._rules_label.text()` → `assert window._use_builtin is True`
- 第 332-335 行 `setChecked(False)` + `assert "未加载"` + `setChecked(True)` + `assert "通用规则"` → `_set_use_builtin(False)` + `assert window._use_builtin is False` + `_set_use_builtin(True)` + `assert window._use_builtin is True`
- 第 358-359 行 `assert "通用规则" in ...` + `assert "rules.yaml" in ...` → 删除（改为检查 `_ruleset` 非空）
- 第 648-652 行（test_label_shows_all_filenames 内）：整个测试删除
- 第 650 行 `text = window._rules_label.text()` → 删除

#### 8.3 删除 2 处 `_detail_locate_btn` 断言

- 第 2976 行 `assert not window._detail_locate_btn.isEnabled()` → 删除
- 第 2988 行 `assert window._detail_locate_btn.isEnabled()` → 删除

#### 8.4 删除 3 个废弃测试

1. `test_label_shows_all_filenames`（第 638-653 行）：`_build_rules_label` 已删除
2. `test_detail_locate_hit_no_hits`（第 3045-3051 行）：`_on_locate_hit` 已删除
3. `test_batch_process_not_implemented`（第 3248-3258 行）：`_on_batch_process` 已删除

#### 8.5 新增 6 个测试

在 `TestDetailNavigation` 类中添加：
```python
def test_result_tree_context_menu_actions(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """结果树右键菜单应包含复制路径/新窗口打开/打开文件位置三个动作。"""
    window = MainWindow()
    # 模拟有选中结果
    window._detail_current_result = ...  # 需构造 ScanResult
    menu = window._on_result_tree_context_menu(...)  # 验证 action 列表
    ...
```

实际实现时需构造 `ScanResult` mock 或使用已有 fixture。具体测试设计：
1. `test_result_tree_context_menu_actions`：验证结果树右键菜单含 3 个 action
2. `test_rules_file_list_context_menu_actions`：验证规则列表右键菜单含 3 个 action
3. `test_result_tree_context_menu_no_selection`：无选中时右键菜单不弹出
4. `test_shortcut_next_hit`：F3 触发下一条命中
5. `test_shortcut_prev_hit`：Shift+F3 触发上一条命中
6. `test_set_use_builtin`：`_set_use_builtin` 正确切换状态并刷新规则

### 步骤 9：验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

## 假设与决策

1. **`_set_use_builtin` 设计**：封装 `_on_toggle_builtin` 的核心逻辑，接收 `bool` 而非 `int state`，不包含 rules_label 更新（已删除）。`_on_settings` 调用它一次性完成规则刷新，替代原来 6 行散落代码。
2. **Delete 快捷键作用域**：`QShortcut(QKeySequence.Delete, self._rules_file_list)` 以 rules_file_list 为 parent，仅在该控件聚焦时生效，避免全局冲突。
3. **右键菜单触发条件**：result_tree 仅在 `_detail_current_result is not None` 时弹出；rules_file_list 仅在 `currentRow() >= 0` 时弹出。
4. **测试中 `_set_use_builtin` 替换策略**：直接调用方法而非模拟 checkbox 事件，测试更简洁且不依赖 widget 存在。
5. **覆盖率保障**：新增 6 个测试覆盖 context menu 和 shortcut 逻辑，弥补删除 3 个测试的覆盖率损失。

## 关键文件

- `src/fuscan/gui/main_window.py` — 核心修改：修复导入、filter stretch、新增 5 方法、删除 4 方法、修改 6 方法
- `src/fuscan/gui/styles.qss` — 移除已删除按钮的 QSS 选择器
- `tests/test_gui.py` — 替换 37 处引用、删除 3 测试、新增 6 测试

## 风险

1. **`_on_settings` 简化后行为变化**：原来手动调用 `_reload_ruleset`/`_refresh_rules_tree`/`_refresh_rules_file_list`/`_update_scan_button`，现统一由 `_set_use_builtin` 处理。需确保 `_set_use_builtin` 覆盖所有这些步骤。
2. **filter_layout stretch 索引**：必须确认 .ui 文件中 filter_layout 确实只有 3 个 item（path_filter_input + rule_filter_combo + group_mode_combo），否则 stretch 会越界。
3. **context menu 测试构造**：需构造 `ScanResult` mock 或使用真实扫描结果，测试实现时需参考已有测试模式。
