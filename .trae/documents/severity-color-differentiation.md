# 严重等级颜色区分

## 背景

当前 GUI 中 `Severity`（INFO/WARNING/CRITICAL）在 6 个位置以纯英文文本（`"info"`/`"warning"`/`"critical"`）显示，无任何颜色或视觉区分。用户要求按"严重/警告/一般"三等级在颜色或标识上区分。

## 改动文件

- `src/fuscan/gui/main_window.py` — 新增 severity 样式辅助函数 + 5 处调用
- `src/fuscan/gui/detail_dialog.py` — 1 处调用
- `tests/test_gui.py` — 新增颜色区分测试

## 实现方案

### 1. 新增模块级常量与辅助函数（main_window.py）

在 `_HIGHLIGHT_STYLE` 常量之后新增：

```python
# 严重等级 → 中文标签
_SEVERITY_LABELS = {
    Severity.CRITICAL: "严重",
    Severity.WARNING: "警告",
    Severity.INFO: "一般",
}

# 严重等级 → 前景色（QColor）
_SEVERITY_COLORS = {
    Severity.CRITICAL: QColor("#d73a49"),  # 红
    Severity.WARNING: QColor("#f0883e"),   # 橙
    Severity.INFO: QColor("#0366d6"),      # 蓝
}

def _severity_text(severity: Severity) -> str:
    """返回严重等级的中文标签。"""
    return _SEVERITY_LABELS.get(severity, severity.value)

def _apply_severity_to_tree_item(item: QTreeWidgetItem, column: int, severity: Severity) -> None:
    """为 QTreeWidgetItem 的指定列设置中文标签和颜色。"""
    item.setText(column, _severity_text(severity))
    item.setForeground(column, _SEVERITY_COLORS[severity])

def _apply_severity_to_table_item(item: QTableWidgetItem, severity: Severity) -> None:
    """为 QTableWidgetItem 设置中文标签和颜色。"""
    item.setText(_severity_text(severity))
    item.setForeground(_SEVERITY_COLORS[severity])
```

`detail_dialog.py` 复用同一套常量，从 `main_window` 导入 `_severity_text` 和 `_apply_severity_to_table_item`（或直接内联，因为只有一处）。为避免跨模块私有导入，将辅助函数改为放在一个共享位置——直接在 `detail_dialog.py` 内联 `_SEVERITY_LABELS`/`_SEVERITY_COLORS`（3 行常量 + 2 行函数，重复极少）。

### 2. 应用到 6 个显示位置

#### main_window.py — 5 处

| 方法 | 行号 | 当前代码 | 修改 |
|------|------|---------|------|
| `_populate_flat` | L1352 | `sr.max_severity.value`（file_item col 2） | 改为 `_apply_severity_to_tree_item(file_item, 2, sr.max_severity)`，构造时 col 2 传空字符串 |
| `_populate_flat` | L1362 | `hit.severity.value`（child col 2） | 改为 `_apply_severity_to_tree_item(child, 2, hit.severity)`，构造时 col 2 传空字符串 |
| `_populate_grouped_by_rule` | L1391 | `hit.severity.value`（child col 2） | 同上 |
| `_populate_grouped_by_severity` | L1411/L1421 | `severity` 字符串（top + child col 2） | 需将字符串转回 `Severity` 再调用辅助函数 |
| `_populate_detail_hits_table` | L1033 | `QTableWidgetItem(hit.severity.value)` | 改为创建 item 后调用 `_apply_severity_to_table_item` |
| `_refresh_rules_tree` | L1196 | `rule.severity.value`（col 1） | 改为 `_apply_severity_to_tree_item(item, 1, rule.severity)`，构造时 col 1 传空字符串 |

**注意**：`_populate_grouped_by_severity` 中 `severity` 是字符串（来自 `sr.max_severity.value`），需用 `Severity(severity)` 转回枚举。或者改用 `sr.max_severity` 直接作为枚举值，避免字符串转换。当前代码 L1403 `sev = sr.max_severity.value` 取了 `.value`，改为不取 `.value`，直接用 `sr.max_severity` 作为 dict key。

#### detail_dialog.py — 1 处

| 方法 | 行号 | 当前代码 | 修改 |
|------|------|---------|------|
| `_populate_hits_table` | L176 | `QTableWidgetItem(hit.severity.value)` | 同 main_window 模式，内联常量+辅助函数 |

### 3. 测试（tests/test_gui.py）

新增 `TestSeverityDisplay` 类（约 5 个测试）：

1. `test_severity_text_chinese_labels` — `_severity_text(Severity.CRITICAL)` 返回 `"严重"`，WARNING 返回 `"警告"`，INFO 返回 `"一般"`
2. `test_result_tree_flat_shows_severity_colors` — 扫描后 result_tree 中文件项 col 2 文本为中文且 foreground 为对应 QColor
3. `test_detail_hits_table_shows_severity_colors` — 选中结果后 detail_hits_table 中 col 1 有颜色
4. `test_rules_tree_shows_severity_colors` — 加载规则后 rules_tree 中 col 1 有颜色
5. `test_detail_dialog_shows_severity_colors` — 打开 HitDetailDialog 后 hits_table 中 col 1 有颜色

## 验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

## 决策

- **前景色（文字颜色）而非背景色**：更克制，不干扰行选中高亮；CRITICAL 红色已足够醒目
- **中文标签替代英文值**：用户明确使用"严重/警告/一般"描述，且项目要求中文 UI
- **detail_dialog.py 内联常量**：避免跨模块导入私有符号，重复 3 行常量可接受
