# iter-67：列表选中项失去焦点变黑修复

## 需求清单

来源：用户反馈"界面列表选中的项目，失去焦点以后白色文字变成黑色了，请分析解决，应当统一为白色"

- [x] R1：列表选中项失去焦点后文字颜色保持白色，不回退到系统默认黑色

## 迭代目标

iter-66（req-14）将 4 处 `::item:selected` 改为深蓝底+白字，但用户反馈
"失去焦点后白字变黑"再次出现。根因：QSS `::item:selected` 只控制有焦点时
（Active 状态）的选中样式，失去焦点时 Qt 回退到 QPalette Inactive Highlight
（Windows 默认灰底黑字）。

本迭代在 6 处 item view 控件本身设置 `selection-background-color` 和
`selection-color` 属性（控件级，不论焦点状态都生效），彻底消除失去焦点
变黑问题。

## 关键决策与依据

### 决策1：控件级 selection-* 属性而非 ::item:selected:!active

Qt QSS 的 `::item:selected:!active` 伪状态在 Qt 5.x 上支持不稳定。
控件级 `selection-background-color` / `selection-color` 是
QAbstractItemView 的属性，**不论焦点状态都生效**，是最可靠的方案。

`::item:selected`（item 级）会覆盖控件级 `selection-*` 属性（有焦点时），
两者颜色一致（深蓝底+白字）时视觉效果统一。

### 决策2：6 处控件全覆盖，包括 QComboBox 下拉列表

| 控件 | 说明 |
|------|------|
| `QListWidget#sidebar` | 侧边栏（已有 `color` 但缺 `selection-*`） |
| `QTreeWidget#result_tree` | 结果树 |
| `QTreeWidget`（通用） | 规则树等 |
| `QListWidget`（通用） | 通用列表 |
| `QTableWidget` | 详情命中表 |
| `QComboBox QAbstractItemView` | 下拉列表（iter-67 顺带统一为深蓝底+白字） |

### 决策3：QMenuBar/QMenu::item:selected 不改

菜单项的"选中"是 hover 触发，且菜单失去焦点即关闭，不存在"失去焦点变黑"
问题。保持原 `COLOR_BG_SELECTED` + `COLOR_PRIMARY`（浅色底+主色文字）。

## 改动文件清单

| 文件 | 说明 |
|------|------|
| `src/fuscan/gui/styles.qss` | 6 处 item view 控件块新增 `selection-background-color` + `selection-color`；QComboBox 下拉列表从浅色底+主色文字改为深蓝底+白字 |
| `tests/test_gui.py` | `TestThemeColorContrast` 新增 `test_item_views_have_selection_color_for_inactive_focus` 回归测试 |

## 代码实现情况

每处控件块追加两行（以 QTreeWidget 为例）：

```css
QTreeWidget {
    /* ... 原有属性 ... */
    /* 控件级选中色：不论是否有焦点，选中项统一深蓝底+白字（iter-67 修复失去焦点变黑） */
    selection-background-color: ${COLOR_PRIMARY_DARK};
    selection-color: ${COLOR_TEXT_ON_PRIMARY};
}
```

## 测试验证结果

- ruff check / format：通过
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1437 passed**, 覆盖率 **96.03%**
- 新增回归测试 `test_item_views_have_selection_color_for_inactive_focus` 验证 6 处控件块均包含 `selection-color: #ffffff` 与 `selection-background-color: #096dd9`

## 遗留事项

无。若未来新增 item view 控件，须同步设置 `selection-*` 属性，回归测试会
通过选择器列表提醒。

## 下一轮计划

无。等待用户反馈是否还有其他 UI 问题。
