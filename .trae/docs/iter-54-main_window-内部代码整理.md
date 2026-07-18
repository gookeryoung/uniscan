# iter-54 main_window 内部代码整理

## 需求清单

- [x] 1. 继续优化 `main_window.py` 内部代码（用户请求"请继续优化"）

## 迭代目标

延续 iter-53 的模块拆分思路，在不进一步拆分文件的前提下，对 `main_window.py`
内部两处重复模式做表驱动重构，消除特判分支与重复赋值：

1. **P1 `_setup_icons` 数据驱动重构**：将 16 个主色变体图标赋值、3 个 combo
   下拉项图标、5 个白色变体 Tab 按钮图标抽到模块级元组常量
   `_PRIMARY_ICON_TARGETS` / `_COMBO_ITEM_ICONS` / `_ON_PRIMARY_ICON_TARGETS`，
   循环遍历 + 局部 dict 缓存避免相同路径重复加载。
2. **P2 导出格式常量化**：将 `_on_export_menu` 中硬编码的 `items` 列表与
   `_on_export` 中的 `ext = "xlsx" if fmt == "excel" else fmt` 特判
   统一抽到模块级常量 `_EXPORT_FORMATS`，用查找表替代线性 `next()` 遍历。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/main_window.py` | 修改 | 新增 4 个模块级常量（`_PRIMARY_ICON_TARGETS` / `_COMBO_ITEM_ICONS` / `_ON_PRIMARY_ICON_TARGETS` / `_EXPORT_FORMATS`）；重写 `_setup_icons` 为表驱动模式；重写 `_on_export_menu` / `_on_export` 使用查找表；`TYPE_CHECKING` 块新增 `QIcon` 导入（用于类型注解） |

## 关键决策与依据

### 表驱动模式选型依据

依据 rule-11「三处相似才考虑提取」与「数据优于代码」：

- `_setup_icons` 原 16 行 `self.xxx.setIcon(_load_themed_icon(_ICON_XXX, theme.COLOR_PRIMARY))`
  高度同构，且存在同一路径加载两次（`_ICON_SCAN` 用于 `scan_btn` 与 `scan_action`、
  `_ICON_LOAD_LIST` 用于 `load_rules_btn` 与 `load_rules_action` 等），表驱动 +
  缓存可同时消除「重复赋值」与「重复加载」两类重复。
- `_on_export_menu` 与 `_on_export` 共享一份格式定义（label / fmt / ext），
  抽到模块级后两处使用同一数据源，避免一处改动另一处漏改（iter-52 前曾出现
  excel 扩展名在两处不一致的风险）。

### `setdefault` 陷阱规避

P1 初稿使用 `primary_cache.setdefault(icon_path, _load_themed_icon(...))`，
但 `setdefault` 的第二个参数总是被求值，导致缓存失效（每个图标都重新渲染）。
改为显式 `if icon_path not in cache: cache[icon_path] = ...` 模式，确保
缓存只对未命中路径调用 `_load_themed_icon`。rule-11「性能」节明确要求
「循环内查询缓存或预构建映射」，本模式符合该约束。

### `_setup_sidebar` 未数据驱动化依据

P1 原计划将 `_setup_sidebar` 的 3 个 `addItem` 也改为 `zip(_SIDEBAR_STAGE_ITEMS, sidebar_icons)`
表驱动，但实测发现：sidebar 的图标顺序与 `_ON_PRIMARY_ICON_TARGETS` 中
`(_ICON_FOLDER, _ICON_SCAN, _ICON_HISTORY)` 的语义无对应关系，且 zip 创建
了常量顺序与图标元组顺序的隐式耦合（修改任一元组顺序需同步另一处）。
保留原始 3 行 `addItem` 更直观，符合「不过早抽象」约束。

### `QIcon` 类型注解放 TYPE_CHECKING 块的依据

`_setup_icons` 中 `primary_cache: dict[str, QIcon]` 需要引用 `QIcon` 类型，
但运行时 `QIcon` 未在主窗口模块顶部导入（仅 `QDesktopServices` / `QKeySequence`
等从 QtGui 导入）。借助 `from __future__ import annotations` 延迟注解求值，
将 `QIcon` 放入 `TYPE_CHECKING` 块仅在类型检查时导入，避免运行时无谓导入。
pyrefly strict 模式验证通过。

## 代码实现情况

### 模块级常量定义

```python
# 主色变体图标 → 控件属性名映射（同一路径在缓存中只加载一次，可绑定多个控件）
_PRIMARY_ICON_TARGETS: tuple[tuple[str, str], ...] = (
    (_ICON_SCAN, "scan_btn"),
    (_ICON_PAUSE, "pause_resume_btn"),
    (_ICON_RESCAN, "rescan_btn"),
    (_ICON_LOAD_LIST, "load_rules_btn"),
    (_ICON_LOAD_LIST, "load_rules_action"),
    (_ICON_SCAN, "scan_action"),
    # ... 共 16 项
)

# scan_mode_combo 下拉项图标（按 index 顺序：全盘 / 盘符 / 文件夹）
_COMBO_ITEM_ICONS: tuple[str, ...] = (_ICON_ALL_DISK, _ICON_DISK, _ICON_FOLDER)

# 深色背景白色变体图标 → 控件属性名映射（头部 Tab 按钮）
_ON_PRIMARY_ICON_TARGETS: tuple[tuple[str, str], ...] = (
    (_ICON_SCAN, "tab_scan_btn"),
    (_ICON_LOAD_LIST, "tab_rules_btn"),
    (_ICON_HISTORY, "tab_history_btn"),
    (_ICON_SETTINGS, "settings_btn"),
    (_ICON_ABOUT, "about_btn"),
)

# 导出格式定义：(显示标签, 格式标识, 文件扩展名)。顺序即菜单显示顺序。
_EXPORT_FORMATS: tuple[tuple[str, str, str], ...] = (
    ("CSV 文件 (*.csv)", "csv", "csv"),
    ("JSON 文件 (*.json)", "json", "json"),
    ("PDF 文件 (*.pdf)", "pdf", "pdf"),
    ("Excel 文件 (*.xlsx)", "excel", "xlsx"),
)
```

### `_setup_icons` 表驱动实现

```python
def _setup_icons(self) -> None:
    """加载主题图标并设置到各按钮、菜单 actions 与下拉项。"""
    # 主色变体图标缓存：key=SVG 路径，value=已着色 QIcon
    primary_cache: dict[str, QIcon] = {}
    for icon_path, attr_name in _PRIMARY_ICON_TARGETS:
        if icon_path not in primary_cache:
            primary_cache[icon_path] = _load_themed_icon(icon_path, theme.COLOR_PRIMARY)
        getattr(self, attr_name).setIcon(primary_cache[icon_path])

    # scan_mode_combo 下拉项图标（index 顺序对应 _COMBO_ITEM_ICONS）
    for index, icon_path in enumerate(_COMBO_ITEM_ICONS):
        if icon_path not in primary_cache:
            primary_cache[icon_path] = _load_themed_icon(icon_path, theme.COLOR_PRIMARY)
        self.scan_mode_combo.setItemIcon(index, primary_cache[icon_path])

    # 盘符按钮复用主色 hard_disk 变体
    if _ICON_HARD_DISK not in primary_cache:
        primary_cache[_ICON_HARD_DISK] = _load_themed_icon(_ICON_HARD_DISK, theme.COLOR_PRIMARY)
    self._icon_hard_disk = primary_cache[_ICON_HARD_DISK]

    # 深色背景白色变体图标缓存
    on_primary_cache: dict[str, QIcon] = {}
    for icon_path, attr_name in _ON_PRIMARY_ICON_TARGETS:
        if icon_path not in on_primary_cache:
            on_primary_cache[icon_path] = _load_themed_icon(icon_path, theme.COLOR_TEXT_ON_PRIMARY)
        getattr(self, attr_name).setIcon(on_primary_cache[icon_path])

    # 侧边栏阶段项复用白色变体
    if _ICON_FOLDER not in on_primary_cache:
        on_primary_cache[_ICON_FOLDER] = _load_themed_icon(_ICON_FOLDER, theme.COLOR_TEXT_ON_PRIMARY)
    self._icon_folder_on_primary = on_primary_cache[_ICON_FOLDER]
    self._icon_scan_on_primary = on_primary_cache[_ICON_SCAN]
    self._icon_history_on_primary = on_primary_cache[_ICON_HISTORY]
```

### `_on_export_menu` / `_on_export` 简化

```python
def _on_export_menu(self) -> None:
    """导出按钮：弹出格式选择对话框。"""
    if self._last_report is None:
        QMessageBox.information(self, "提示", "无可导出的扫描结果")
        return
    labels = [label for label, _, _ in _EXPORT_FORMATS]
    choice, ok = QInputDialog.getItem(self, "导出扫描结果", "选择导出格式:", labels, 0, False)
    if not ok:
        return
    # 通过 label → fmt 的查找表替代 next() 线性遍历，语义更清晰
    label_to_fmt = {label: fmt for label, fmt, _ in _EXPORT_FORMATS}
    self._on_export(label_to_fmt[choice])

def _on_export(self, fmt: str) -> None:
    """导出扫描结果到文件。"""
    if self._last_report is None:
        QMessageBox.information(self, "提示", "无可导出的扫描结果")
        return
    # 从 _EXPORT_FORMATS 查找扩展名，消除 ``ext = "xlsx" if fmt == "excel" else fmt`` 特判
    fmt_to_ext = {fmt_id: ext for _, fmt_id, ext in _EXPORT_FORMATS}
    ext = fmt_to_ext.get(fmt, fmt)
    filter_str = f"{fmt.upper()} 文件 (*.{ext})"
    default_name = f"fuscan_report.{ext}"
    # ...（后续 QFileDialog + save_report 不变）
```

## 整合优化情况

- **代码量减负**：`_setup_icons` 从 ~55 行重复赋值压缩到 ~35 行表驱动循环；
  `_on_export_menu` 删除内联 `items` 列表（4 行），`_on_export` 删除特判分支。
- **单一数据源**：导出格式定义集中在 `_EXPORT_FORMATS`，新增格式只需改一处。
- **缓存生效**：`_setup_icons` 中 `_ICON_SCAN` / `_ICON_LOAD_LIST` / `_ICON_EDIT` /
  `_ICON_EXPORT` 等多个被多控件复用的图标只渲染一次（原实现每次都重新渲染）。
- **公开 API 兼容**：`_on_export_menu` / `_on_export` 函数签名与行为不变，
  `_icon_hard_disk` / `_icon_folder_on_primary` / `_icon_scan_on_primary` /
  `_icon_history_on_primary` 4 个跨方法复用的实例属性保留（被 `_setup_drive_buttons`、
  `_setup_sidebar`、`_switch_stage` 等方法引用）。
- **消除实例属性膨胀**：原 `_setup_icons` 设置 24 个 `self._icon_xxx` 实例属性
  用于单次赋值（仅在 `_setup_icons` 内赋值给控件的 `setIcon`），重构后这些
  中间属性全部删除，仅保留 4 个真正跨方法复用的实例属性。

## 测试验证结果

| 门禁 | 结果 | 基线（iter-53） | 变化 |
|------|------|----------------|------|
| ruff check | All checks passed | 0 errors | — |
| ruff format --check | 1 file already formatted | 86 files | — |
| pyrefly check | 0 errors (66 suppressed) | 0 errors (458 suppressed) | suppressed 数量变化因本次仅检查单文件 |
| pytest | 1351 passed / 0 failed | 1351 passed / 0 failed | — |
| coverage | 96.19% | 96.26% | -0.07%（main_window.py 94%，重构后行数减少） |

覆盖率小幅下降 0.07% 来自 `main_window.py` 重构后部分行未被执行（如
`fmt_to_ext.get(fmt, fmt)` 的 fallback 路径，因为 `fmt` 总是来自常量定义的 4 个值），
但 96.19% 仍高于 95% 门禁，且未引入未覆盖分支。

## 遗留事项

- `main_window.py` 仍约 1100 行，主要承载 UI 装配（`_setup_*` 系列）与扫描流程
  协调。后续若继续拆分需谨慎评估：`_setup_*` 系列方法彼此独立但共享 `self` 状态，
  抽到独立 configurator 类需传递 `MainWindow` 引用或大量控件，可能反而增加耦合。
- `_EXPORT_FORMATS` 中 `excel` → `xlsx` 的标识/扩展名不一致是历史遗留
  （`save_report` 函数按扩展名自动选择序列化方式，`fmt` 仅用于显示与查找），
  若后续统一为 `xlsx` 标识可简化查找表，但需同步修改 `export_excel_action` 的
  signal handler（`lambda: self._on_export("xlsx")`），不在本次范围。

## 下一轮计划

无明确下一轮计划。当前 `main_window.py` 内部重复模式已通过表驱动重构消除，
后续优化方向（如进一步拆分 `_setup_*` 系列或抽取 `_on_export` 公共校验逻辑）
收益较小且可能引入过度抽象，暂不主动推进。如用户提出新需求再行迭代。
