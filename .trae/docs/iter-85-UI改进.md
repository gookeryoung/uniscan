# iter-85 UI 改进

## 需求清单

- [x] 去除设置对话框中重复的"扫描压缩包"全局开关（req-22-UI改进.md）
- [x] 全盘扫描等图标整合到 scan_mode_combo
- [x] 统一 select_path_btn 与同行 combo 高度
- [x] 扫描结果详情 Content 区布局优化（QSplitter）
- [x] 结果树首列改为文件名（路径在 tooltip 与右侧详情区）
- [x] 结果树严重等级/命中数/条数列自动最小宽度

## 迭代目标

针对用户实测反馈的 6 项 UI 问题进行修复：去除设置中重复的扫描压缩包开关、为扫描模式 combo 添加图标、统一按钮与 combo 高度、用 QSplitter 优化详情 Content 区拥挤布局、将结果树首列从路径改为文件名以节省横向空间、严重等级等列自动收缩到最小宽度。

## 关键决策与依据

1. **去除设置中的扫描压缩包开关**：iter-79 已将"压缩包"勾选移至主界面文件类型树统一管理，设置对话框的 `scan_archives_check` 属于重复入口，易造成用户认知混乱。保留主界面勾选项作为唯一控制点，符合"配置、扫描、结果切换不应处于禁用状态"的设计原则。`scan_archives` 配置项本身保留在 `ScanConfig` 中，由文件类型树勾选状态映射，仅 UI 层去除。
2. **scan_mode_combo 图标绑定**：通过 `setItemIcon(index, QIcon(path))` 在 `ScanModePanel._apply_mode_icons()` 中绑定三个模式图标，资源来自既有 `resources.qrc`（`all_disk.svg`/`disk.svg`/`folder.svg`），未新增资源文件。图标路径常量化为模块级 `_MODE_ICON_PATHS`，按 combo item 索引对齐。
3. **按钮高度语义重新定义**：原令牌 `BTN_HEIGHT_*` 既被 QSS 用作 `min-height`、又被 .ui 用作 `minimumSize.height`，导致 padding 叠加后实际总高度超出预期（L1=72px、L2=56px，远超 .ui 的 48/40px，且与同行 QComboBox 40px 不一致）。新语义明确：`BTN_HEIGHT_*` 表示 QSS `min-height`（内容区高度），实际控件总高度 = `padding-top + min-height + padding-bottom`。重新调整为：
   - L1：`min-height 32px + padding 8px 28px` = 48px（与 .ui `minimumSize 200x48` 一致）
   - L2：`min-height 32px + padding 4px 20px` = 40px（与 .ui `minimumSize 140x40` 及同行 `QComboBox 40px` 一致）
   - L3：`min-height 24px + padding 4px 14px` = 32px（与 .ui `minimumSize` 兜底一致）
4. **详情 Content 区 QSplitter**：原 `QVBoxLayout` 中 `hits_table` 与 `preview` 用固定 stretch 比例分配空间，无法让用户根据内容动态调整。改为 `QSplitter(Qt.Vertical)`：`childrenCollapsible=false` 防止折叠隐藏、`handleWidth=6` 提供可视拖拽手柄、初始 stretch 比例 1:2（hits_table:preview）通过 `setSizes()` 在 `main_window.py` 中设置。`sizePolicy` verstretch=1 让 splitter 占据详情区剩余纵向空间。
5. **结果树首列改为文件名**：原第 0 列显示完整路径 `str(sr.path)`，宽路径在 6 列表格中占用过多横向空间。改为显示 `sr.path.name`（文件名），完整路径通过 `setToolTip(str(sr.path))` 在鼠标悬停时展示。路径信息在右侧详情区 `info_label` 已可见，避免重复展示。此改动同时应用于 flat、by-rule、by-severity 三种分组模式。
6. **列宽 ResizeToContents**：严重等级（"严重"/"警告"/"信息"）、命中数（数字）、条数（数字）三类列内容宽度可预测且短小，设为 `QHeaderView.ResizeToContents` 让 Qt 按内容自动收缩到最小所需宽度。文件名/规则/详情列保持 `Interactive` 用户可调，并设置初始宽度 220/140/200。`stretchLastSection=True` 让详情列填充剩余空间。

## 改动文件清单

修改：
- `src/fuscan/gui/settings_dialog.ui`：移除 `options_group`（含 `scan_archives_check`）整个分节
- `src/fuscan/gui/settings_dialog_ui.py`：由 `settings_dialog.ui` 重新生成
- `src/fuscan/gui/settings_dialog.py`：移除 `_load_config`/`_save_config` 中 `scan_archives_check` 相关代码；更新模块 docstring 说明扫描压缩包开关已由主界面文件类型树统一管理（iter-85）
- `src/fuscan/gui/scan_mode_panel.py`：新增 `QIcon` 导入与 `_MODE_ICON_PATHS` 常量；`_apply_mode_icons()` 方法为 combo 三项设置图标；`__init__` 末尾调用一次
- `src/fuscan/theme.py`：重新定义 `BTN_HEIGHT_PRIMARY/SECONDARY/GHOST` 为 32/32/24px（QSS `min-height` 语义）；`BTN_PADDING_PRIMARY/SECONDARY/GHOST` 调整为 8/4/4px 上下，确保实际总高度 48/40/32px；更新令牌注释说明高度计算公式
- `src/fuscan/gui/styles.qss`：更新 L1/L2/L3 按钮区块顶部注释，说明实际高度计算（padding*2 + min-height）；选择器与令牌引用不变
- `src/fuscan/gui/main_window.ui`：详情区 Content 部分用 `QSplitter`（`detail_content_splitter`，Vertical，handleWidth=6，childrenCollapsible=false）替换原 `QVBoxLayout` 中的 `detail_hits_table` 与 `detail_preview`；`detail_hits_table` 的 `sizePolicy` verstretch=1
- `src/fuscan/gui/main_window_ui.py`：由 `main_window.ui` 重新生成
- `src/fuscan/gui/main_window.py`：新增 `_configure_detail_splitter()` 设置 splitter 初始 sizes 比例 1:2；移除原布局 stretch 配置
- `src/fuscan/gui/result_tree.py`：`_HEADERS` 第 0 列从"路径"改为"文件名"；`_setup_header()` 配置列 resize 模式（0/1/5 Interactive，2/3/4 ResizeToContents，stretchLastSection=True）与初始宽度；`_populate_flat`/`_populate_grouped_by_rule`/`_populate_grouped_by_severity` 中 `sr.path` 改为 `sr.path.name`，第 0 列 `setToolTip(str(sr.path))`
- `tests/test_gui.py`：更新 `test_button_hierarchy_tokens_distinct` 断言新语义（`BTN_HEIGHT_*` 为 QSS `min-height`，实际总高度 = padding*2 + min-height，48 > 40 > 32）；移除 `test_settings_dialog_save_and_get_config` 中 `scan_archives` 相关断言

## 代码实现情况

### 1. 设置对话框去重

`settings_dialog.ui` 删除 `options_group` 整段；`settings_dialog.py` 中 `_load_config` 不再读取 `config.scan_archives`，`_save_config` 不再写入该项，docstring 注明"扫描压缩包开关由主界面文件类型树统一管理（iter-85）"。

### 2. scan_mode_combo 图标

`scan_mode_panel.py` 模块顶部新增：
```python
_MODE_ICON_PATHS: tuple[str, ...] = (
    ":/assets/icons/all_disk.svg",   # 全盘扫描
    ":/assets/icons/disk.svg",       # 选择盘符
    ":/assets/icons/folder.svg",     # 选择文件夹
)
```
`_apply_mode_icons()` 通过 `setItemIcon(index, QIcon(path))` 绑定，`__init__` 末尾调用一次，确保图标与 combo 选项同步。

### 3. 按钮高度统一

`theme.py` 令牌调整（语义从"控件总高度"改为"QSS min-height 内容区高度"）：
```python
BTN_HEIGHT_PRIMARY = "32px"      # 实际总高度 8*2 + 32 = 48px
BTN_HEIGHT_SECONDARY = "32px"     # 实际总高度 4*2 + 32 = 40px
BTN_HEIGHT_GHOST = "24px"        # 实际总高度 4*2 + 24 = 32px
BTN_PADDING_PRIMARY = "8px 28px"
BTN_PADDING_SECONDARY = "4px 20px"
BTN_PADDING_GHOST = "4px 14px"
```
`styles.qss` 中 L1/L2/L3 按钮区块顶部注释更新为"实际 Xpx = padding Y*2 + min-height Z"，明确计算方式。

### 4. 详情 Content 区 QSplitter

`main_window.ui` 中详情区 Content 部分从：
```xml
<layout class="QVBoxLayout">
  <item><widget class="QTableWidget" name="detail_hits_table"/></item>
  <item><widget class="QTextEdit" name="detail_preview"/></item>
</layout>
```
替换为：
```xml
<widget class="QSplitter" name="detail_content_splitter">
  <property name="orientation"><enum>Qt::Vertical</enum></property>
  <property name="handleWidth"><number>6</number></property>
  <property name="childrenCollapsible"><bool>false</bool></property>
  <widget class="QTableWidget" name="detail_hits_table">...</widget>
  <widget class="QTextEdit" name="detail_preview">...</widget>
</widget>
```
`main_window.py` 中 `_configure_detail_splitter()` 通过 `setSizes([height//3, height*2//3])` 设置 1:2 初始比例。

### 5. 结果树首列文件名

`result_tree.py` 中 `_HEADERS` 改为 `["文件名", "规则", "严重等级", "命中数", "条数", "详情"]`；三个 `_populate_*` 方法中 `str(sr.path)` 改为 `sr.path.name`，紧接 `file_row[0].setToolTip(str(sr.path))`（child 行同理）。

### 6. 列宽 ResizeToContents

`result_tree.py` 中 `_setup_header()`：
```python
header.setStretchLastSection(True)
header.setSectionResizeMode(0, QHeaderView.Interactive)      # 文件名
header.setSectionResizeMode(1, QHeaderView.Interactive)      # 规则
header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # 严重等级
header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # 命中数
header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # 条数
header.setSectionResizeMode(5, QHeaderView.Interactive)      # 详情
self.setColumnWidth(0, 220)
self.setColumnWidth(1, 140)
self.setColumnWidth(5, 200)
```

## 整合优化情况

- `_make_result_row` docstring 中"路径/规则/..."的列名描述同步更新为"文件名/规则/..."。
- `scan_mode_panel.py` 的 `_apply_mode_icons()` 注释引用 iter-85 编号便于追溯。
- `theme.py` 令牌注释明确"调整 padding 时须同步评估实际总高度是否仍与 .ui minimumSize 匹配"，防止后续再次踩坑。

## 测试验证结果

- ruff check src tests：**All checks passed**
- ruff format --check src tests：**104 files already formatted**
- pyrefly check：**0 errors**（555 suppressed, 62 warnings not shown）
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1587 passed**，覆盖率 **95.14%**（≥ 95% 阈值）
- `test_button_hierarchy_tokens_distinct` 更新后断言三级实际总高度 48 > 40 > 32，全部通过
- `test_settings_dialog_save_and_get_config` 移除 `scan_archives` 断言后通过

## 遗留事项

- 暗色主题支持（与 iter-84 共同遗留）。
- `regex_tester.py` 的 HTML 速查表内联色值未引用 theme 令牌（HTML 限制，与 iter-84 共同遗留）。
- QSplitter 初始比例在窗口尺寸变化后由用户拖拽调整，状态不持久化（符合 QSplitter 默认行为，无需求要求持久化）。

## 下一轮计划

无。本次需求已完成，等待用户实测确认 GUI 视觉效果与交互体验。
