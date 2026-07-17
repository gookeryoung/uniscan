# iter-50 性能优化与代码清理

## 需求清单

- [x] 代码清理重构，性能优化

## 迭代目标

对 GUI 层进行代码清理与性能优化，重点解决 DetailPanel 命中导航热路径上的
`toPlainText()` 重复调用问题，以及 ResultTreeView 中表头列表的重复定义。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/detail_panel.py` | 修改 | P1：缓存 `_plain_text`，消除导航时重复 `toPlainText()` |
| `src/fuscan/gui/result_tree.py` | 修改 | P2：提取 `_HEADERS` 常量，消除 4 处表头列表重复 |
| `tests/test_gui.py` | 修改 | 同步 `test_highlight_skips_out_of_range_position` 设置 `_plain_text` 缓存 |

## 关键决策与依据

### P1：DetailPanel `_plain_text` 缓存（性能优化）

- **问题**：`_find_hit_positions` / `_highlight_current_hit` / `_scroll_to_current_hit`
  各自调用 `self._c.preview.toPlainText()` 获取文档纯文本或长度。对 100KB 文档：
  - 结果显示时：3 次 `toPlainText()` → 3 次 100KB 字符串分配
  - F3/Shift+F3 导航时：2 次 `toPlainText()` → 2 次 100KB 字符串分配
  - `toPlainText()` 是 O(N) 操作（遍历 QTextDocument 全部段落）
- **方案**：在 `_find_hit_positions` 中一次性取 `toPlainText()` 缓存到
  `self._plain_text`，后续 `_highlight_current_hit` / `_scroll_to_current_hit`
  复用 `len(self._plain_text)` 做长度校验。`clear()` 时重置缓存为空串。
- **收益**：显示时 3→1 次调用，导航时 2→0 次调用。F3 连续导航不再分配大字符串。
- **依据**：`_plain_text` 在结果展示期间不变（文档内容仅在 `_populate_preview`
  中通过 `setHtml`/`setPlainText` 设置），缓存生命周期与 `_hit_positions` 一致。
  `clear()` 与 `_populate_preview` 的所有提前返回路径不需要缓存（不会触发导航）。

### P2：ResultTreeView `_HEADERS` 常量提取（代码清理）

- **问题**：`["路径", "规则", "严重等级", "命中数", "条数", "详情"]` 在
  `__init__` / `populate` / `refresh` / `clear_results` 4 处重复定义。
  `clear()` 会清空表头，每次重建模型后须重新 `setHorizontalHeaderLabels`。
- **方案**：提取为模块级常量 `_HEADERS`，4 处引用统一替换。
- **依据**：DRY 原则，表头列定义变更时单点更新。

## 代码实现情况

### detail_panel.py

- `__init__`：新增 `self._plain_text: str = ""` 字段
- `clear()`：新增 `self._plain_text = ""` 重置
- `_find_hit_positions()`：`plain = self._c.preview.toPlainText()` 改为
  `self._plain_text = self._c.preview.toPlainText()`，后续 `finditer` 用 `self._plain_text`
- `_highlight_current_hit()`：`len(self._c.preview.toPlainText())` 改为 `len(self._plain_text)`
- `_scroll_to_current_hit()`：同上

### result_tree.py

- 新增模块级常量 `_HEADERS: list[str] = ["路径", "规则", "严重等级", "命中数", "条数", "详情"]`
- `__init__` / `populate` / `refresh` / `clear_results` 中 4 处字面量替换为 `_HEADERS`

### test_gui.py

- `test_highlight_skips_out_of_range_position`：在 `setPlainText("short")` 后
  同步设置 `window._detail_panel._plain_text = "short"`，确保缓存与文档内容一致。
  其他测试（`prev_hit`/`next_hit`/`_on_hits_row_clicked`）不依赖 `_plain_text`
  的具体值（仅检查索引与导航标签），无需修改。

## 测试验证结果

| 门禁 | 结果 | 基线（iter-49） | 变化 |
|------|------|----------------|------|
| ruff check | 0 errors | 0 errors | — |
| ruff format --check | 通过 | 通过 | — |
| pyrefly check | 0 errors (452 suppressed) | 0 errors (452 suppressed) | — |
| pytest | 1324 passed / 0 failed | 1324 passed / 0 failed | — |
| coverage | 96.04% | 96.04% | — |

## 遗留事项

- 无

## 下一轮计划

- 无具体计划，视用户需求而定
