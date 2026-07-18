# iter-56 main_window 字面量常量化与规则集刷新 helper 抽取

## 需求清单

- [x] 1. 继续优化 `main_window.py` 内部代码（用户请求"继续"）

## 迭代目标

延续 iter-54 的表驱动重构思路，识别 `main_window.py` 中两类剩余的散落模式
并集中消除：

1. **字面量字典常量化**：扫描模式（`full`/`drive`/`folder`）与工作流阶段
   （`SETUP`/`SCANNING`/`RESULTS`）的双向映射散落在 5 处方法内（每次调用
   重建字面量字典），抽到模块级常量并显式表达双向关系。
2. **规则集刷新 helper 抽取**：4 处方法（`_set_use_builtin` / `_init_rules` /
   `_on_load_rules` 成功路径 / `_on_load_rules` 失败回滚路径）各自重复
   「`_reload_ruleset` + `_refresh_rules_tree` + `_refresh_rules_file_list` +
   `_update_scan_button`」4 行调用序列，抽到 `_apply_ruleset_loaded` helper。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/main_window.py` | 修改 | 新增 4 个模块级常量 + 1 个 helper 方法；5 处字面量字典替换为常量引用；4 处 4 行调用序列替换为 helper 调用 |
| `tests/test_gui_scan_path_history.py` | 修改 | 修复 iter-55 遗留的 F401（未使用 `Path` 导入）与 PLW0108（不必要 lambda）两处 lint 问题 |

## 关键决策与依据

### 字面量字典常量化的触发点

iter-55 收尾时未扫描到字面量字典散落模式，本轮通过
`grep '\{[0-9"'"'"':a-z_]+:\s*[0-9"'"'"']'` 定位到 3 处扫描模式字典 +
2 处工作流阶段字典（互为反向映射）。

**风险点**：原 `_on_scan_mode_changed` 的 `{0: "full", 1: "drive", 2: "folder"}`
与 `_update_target_visibility` 的 `{"full": 0, "drive": 1, "folder": 2}`
是手工维护的反向映射，若新增扫描模式（如 `archive`）需改两处且保持 keys 一致，
易漂移。常量化后通过 `_INDEX_TO_SCAN_MODE = {v: k for k, v in _SCAN_MODE_TO_INDEX.items()}`
自动派生反向映射，单一数据源。

### 常量定义位置选择

`_STAGE_TO_PAGE_INDEX` / `_SIDEBAR_ROW_TO_STAGE` 引用 `WorkflowStage` 枚举，
必须在 `class WorkflowStage` 定义之后声明。初次实现放在枚举之前触发
`ruff F821 Undefined name WorkflowStage`，调整为枚举之后定义，与
`_SCAN_MODE_TO_INDEX`（不依赖枚举，放在最前）分组。

### `_apply_ruleset_loaded` 参数化决策

初稿考虑让 helper 接受 `refresh_file_list: bool = True` 参数，使
`_reload_and_refresh`（少刷新 file_list）也能复用。但：
1. `_reload_and_refresh` 的命名明确表示「reload + refresh tree」，行为差异是其语义的一部分
2. 引入参数会降低 helper 的可读性，且 `_reload_and_refresh` 重复仅 3 行，不构成提取门槛
3. rule-11「三处相似才考虑提取」约束：4 行序列出现 4 次满足提取门槛（已抽 helper），
   `_reload_and_refresh` 的 3 行序列仅 1 次出现，不满足提取门槛

故 `_reload_and_refresh` 保持原样，不强行统一到 `_apply_ruleset_loaded`。

### stats_label 文案差异处理

4 处调用点的 stats_label 文案略有差异：
- `_init_rules`：「已加载 N 条**通用**规则」（启动加载内置规则）
- `_set_use_builtin` / `_on_load_rules`：「已加载 N 条规则」
- `_on_load_rules` 失败回滚路径：不更新 stats_label（保留原文案）

让 helper 不更新 stats_label，由调用方根据上下文设置。这避免了 stats_template
参数的引入，保持 helper 单一职责（仅刷新 UI 状态控件，不处理文案）。

## 代码实现情况

### 模块级常量定义

```python
# 扫描模式 ↔ combo index 双向映射
_SCAN_MODE_TO_INDEX: dict[str, int] = {"full": 0, "drive": 1, "folder": 2}
_INDEX_TO_SCAN_MODE: dict[int, str] = {v: k for k, v in _SCAN_MODE_TO_INDEX.items()}

# 工作流阶段 ↔ main_stack page index / sidebar row 双向映射（定义在 WorkflowStage 之后）
_STAGE_TO_PAGE_INDEX: dict[WorkflowStage, int] = {
    WorkflowStage.SETUP: 0,
    WorkflowStage.SCANNING: 1,
    WorkflowStage.RESULTS: 2,
}
_SIDEBAR_ROW_TO_STAGE: dict[int, WorkflowStage] = {v: k for k, v in _STAGE_TO_PAGE_INDEX.items()}
```

### 5 处字面量替换

```python
# _apply_config: 删除局部 mode_index_map
self.scan_mode_combo.setCurrentIndex(_SCAN_MODE_TO_INDEX[self._scan_mode])

# _on_scan_mode_changed: 内联字典 → 常量查找
self._scan_mode = _INDEX_TO_SCAN_MODE.get(index, "folder")

# _update_target_visibility: 内联字典 → 常量查找
self.target_stack.setCurrentIndex(_SCAN_MODE_TO_INDEX.get(self._scan_mode, 2))

# _switch_stage: 5 行内联字典 → 1 行常量查找
page_index = _STAGE_TO_PAGE_INDEX[stage]

# _on_sidebar_stage_changed: 局部 stage_map → 常量查找
stage = _SIDEBAR_ROW_TO_STAGE.get(row)
```

### `_apply_ruleset_loaded` helper

```python
def _apply_ruleset_loaded(self) -> None:
    """重新加载规则集并同步刷新 UI（rules_tree / rules_file_list / scan_button）。

    统一封装 4 处重复的 ``_reload_ruleset + _refresh_rules_tree +
    _refresh_rules_file_list + _update_scan_button`` 调用序列。
    ``stats_label`` 文案因调用场景不同（内置/用户加载），由调用方在调用后设置。
    """
    self._reload_ruleset()
    self._refresh_rules_tree()
    self._refresh_rules_file_list()
    self._update_scan_button()
```

### 4 处调用点简化

```python
# _set_use_builtin: 4 行 → 1 行
self._apply_ruleset_loaded()

# _init_rules: 4 行 → 1 行
self._apply_ruleset_loaded()

# _on_load_rules 成功路径: 4 行 → 1 行
self._apply_ruleset_loaded()

# _on_load_rules 失败回滚路径: 4 行 → 1 行
self._rules_paths.remove(path)
self._apply_ruleset_loaded()
```

### iter-55 测试文件 lint 修复

```python
# 删除未使用的 from pathlib import Path
# lambda idx: emitted.append(idx) → emitted.append（直接传方法引用）
combo.currentIndexChanged.connect(emitted.append)
```

## 整合优化情况

- **代码量减负**：`main_window.py` 减少约 20 行（5 处字面量字典共 ~15 行 +
  4 处重复调用序列 12 行 - 12 行 helper 与常量定义）。
- **单一数据源**：扫描模式与工作流阶段的映射集中在模块级常量，新增枚举值
  或调整映射只需改一处；反向映射通过字典推导自动派生。
- **DRY**：4 处规则集刷新调用序列统一到 `_apply_ruleset_loaded`，未来若需
  新增刷新控件（如「规则统计标签」），只需改 helper 一处。
- **公开 API 兼容**：所有改动的都是 MainWindow 私有方法与模块级常量，
  测试中调用的 `window._set_use_builtin` / `window._init_rules` /
  `window._on_load_rules` / `window._reload_ruleset` 等签名不变。
- **iter-55 遗留修复**：测试文件的 F401 与 PLW0108 一并解决，符合
  rule-01「测试/lint/类型失败直接定位根因并修复」约束。

## 测试验证结果

| 门禁 | 结果 | 基线（iter-55） | 变化 |
|------|------|----------------|------|
| ruff check | All checks passed | 0 errors | 修复 iter-55 遗留 2 errors |
| ruff format --check | 43 files already formatted | 42 files | +1（修复后 test 文件） |
| pyrefly check | 0 errors (62 suppressed) | 0 errors (65 suppressed) | — |
| pytest | 1363 passed / 0 failed | 1363 passed | — |
| coverage | 96.29% | 96.23% | +0.06% |

覆盖率小幅提升 0.06% 来自 `main_window.py` 中 `_apply_ruleset_loaded` helper
被 4 处调用路径覆盖（含 `_on_load_rules` 失败回滚路径，原 4 行重复序列中
每行单独计数，现 helper 整体覆盖），整体行数减少带来比例上升。

## 遗留事项

- `main_window.py` 仍约 1060 行。剩余可优化点：
  - **`_reload_and_refresh`** 的 3 行调用序列出现 1 次，不满足提取门槛（rule-11「三处相似」）。
  - **`_on_scan_mode_changed` 与 `_update_target_visibility`** 仍分别调用
    `_update_scan_button` 与 `_update_target_visibility`，可考虑合并为
    `_apply_scan_mode_change` 方法，但仅 2 处调用，不构成提取门槛。
  - **`_update_scan_button`** 是 `_update_stage_actions` 的薄包装（仅 1 行），
    可删除直接调用 `_update_stage_actions`，但会破坏 `_on_drive_selected` 等
    测试中的 monkeypatch 路径，不在本次范围。

## 下一轮计划

无明确下一轮计划。`main_window.py` 内部散落模式已通过常量化与 helper 抽取
集中消除，剩余重复均不满足「三处相似」提取门槛。如用户提出新需求再行迭代。
