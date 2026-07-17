# iter-52 UI 静态配置整合到 .ui 文件

## 需求清单

- [x] 1. 继续优化性能，整合 .py 代码到 .ui 中（用户请求）
- [x] 2. P1: 将 `detail_dialog.py` 中 hits_table 的 editTriggers/selectionBehavior 静态配置整合到 `detail_dialog.ui`
- [x] 3. P2: 将 `main_window.py` 中动态创建的 scan_stats_label 整合为 `main_window.ui` 静态控件
- [x] 4. P3: 扫描其他性能优化机会（重复计算/缓存/字符串分配）

## 迭代目标

将 GUI 模块中可在 `.ui` 文件静态表达的配置代码（控件属性、控件创建）从 `.py`
下沉到 `.ui`，遵循 rule-12「UI 仅在 `.ui` 定义，禁止 `.py` 内实现 UI 初始配置
代码」的分层约束；同时扫描其他性能优化机会。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/detail_dialog.ui` | 修改 | hits_table 添加 editTriggers / selectionBehavior / horizontalHeaderStretchLastSection 属性 |
| `src/fuscan/gui/detail_dialog_ui.py` | 修改 | 手动同步 setEditTriggers / setSelectionBehavior / setStretchLastSection(True) |
| `src/fuscan/gui/detail_dialog.py` | 修改 | 删除 _configure_ui 中已整合的 setEditTriggers/setSelectionBehavior；清理未使用的 QTableWidget 导入 |
| `src/fuscan/gui/main_window.ui` | 修改 | scanning_layout 中插入 scan_stats_label 静态控件（QLabel，富文本对齐居中） |
| `src/fuscan/gui/main_window_ui.py` | 修改 | IDE 自动增量更新：添加 scan_stats_label 创建与 retranslateUi 初始文本 |
| `src/fuscan/gui/main_window.py` | 修改 | 简化 _setup_scan_stats_panel：删除 7 行动态控件创建代码，仅保留 _update_scan_stats 调用 |

## 关键决策与依据

### pyside2-uic 5.15.2 能力边界（关键约束）

通过创建临时 `.ui` 文件测试验证 pyside2-uic 5.15.2 的支持情况，确认如下：

**支持**（可整合到 .ui）：
- `editTriggers` / `selectionBehavior` / `alignment` / `textFormat` / `wordWrap`
- `readOnly` / `placeholderText` / `alternatingRowColors`
- `horizontalHeaderStretchLastSection`（作为 `<attribute>` 写在 widget 内）

**不支持**（无法整合到 .ui，必须保留在 .py）：
- `<property name="stretch">`（错误生成到 retranslateUi）
- `<item stretch="N">`（报错 "Unexpected attribute stretch"）
- `QSplitter.setStretchFactor` / `setSizes`
- `QHeaderView.setSectionResizeMode(Stretch)` 整体设置（仅支持单 section）
- `QStatusBar` 子 widget 自动 addWidget（statusBar 子控件无法静态声明）

依据：pyside2-uic 5.15.2 是 PySide2 最后一个稳定版本，能力上限即此。rule-12
要求 UI 在 .ui 定义，但工具链限制下 .py 仍需保留动态属性配置。

### P1 hits_table 静态属性整合

- **问题**：`detail_dialog.py` 的 `_configure_ui` 在运行时设置
  `hits_table.setEditTriggers(NoEditTriggers)` 和
  `setSelectionBehavior(SelectRows)`，违反 rule-12「UI 初始配置代码禁在 .py」。
- **方案**：将这两项属性写入 `detail_dialog.ui` 的 `<widget name="hits_table">`
  节点，`_ui.py` 同步 `setEditTriggers`/`setSelectionBehavior` 调用。
  `setSectionResizeMode(QHeaderView.Stretch)` 整体设置因 pyside2-uic 不支持，
  保留在 `_configure_ui`。
- **依据**：editTriggers / selectionBehavior 是控件静态属性，与运行时状态无关，
  适合 .ui 表达；setSectionResizeMode 是 header 整体模式设置，必须保留 .py。
- **副作用清理**：删除 setEditTriggers 后 `QTableWidget` 不再被 detail_dialog.py
  直接使用（QTableWidgetItem 仍用），从 PySide2/PySide6 两个导入分支删除
  `QTableWidget`。

### P2 scan_stats_label 静态化

- **问题**：`main_window.py` 的 `_setup_scan_stats_panel` 动态创建 QLabel
  并配置 alignment/textFormat/objectName 共 7 行代码，违反 rule-12。
- **方案**：在 `main_window.ui` 的 `scanning_layout` 中
  `lists_splitter` 与 `scanning_btn_row` 之间插入静态 QLabel 节点，
  声明 `alignment=Qt::AlignCenter` 与 `textFormat=Qt::RichText`，
  `_setup_scan_stats_panel` 仅保留 `_update_scan_stats(0,0,0,0)` 调用。
- **依据**：scan_stats_label 是固定位置的展示控件，无动态创建需求；
  颜色标识通过 HTML 内联样式（`<span style="color:...">`）实现，
  在 `_update_scan_stats` 中动态拼接文本，无需 QSS。
- **IDE 自动重新生成风险**：编辑 .ui 后 IDE 会增量更新 `_ui.py`，本次保持了
  基线风格（无 u 前缀、无 (object) 基类、无 coding 注释）。iter-45/本次 P1
  均出现过 IDE 全量重新生成破坏基线风格的情况，需通过 `git checkout HEAD --`
  恢复后手动添加。

### P3 性能优化扫描结果

扫描了以下热路径与候选模块，未发现明显优化机会（代码质量已很高）：

| 模块 / 路径 | 现状 | 结论 |
|------------|------|------|
| `toPlainText()` 调用 | iter-50/51 已通过 `_plain_text` 缓存优化 | 无重复调用 |
| `_on_scan_progress` | 已有 0.5 秒节流 + 增量 append（非全量重建） | 已优化 |
| `_update_skipped_dirs_list` / `_update_matched_files_list` | 增量 append + setUpdatesEnabled(False) | 已优化 |
| `result_tree.refresh` | 已用 `setUpdatesEnabled(False)` 批量插入 | 已优化 |
| `preview_utils.build_preview_html` | 单次正则替换插入高亮 span，关键词去重 | 已优化 |
| `extract_keywords` / `build_keyword_to_rule_map` | 两次遍历 hits，但 hits 通常 < 10 个 | 收益微小 |

## 代码实现情况

### detail_dialog.ui

在 `<widget class="QTableWidget" name="hits_table">` 节点添加：

```xml
<property name="editTriggers">
 <set>QAbstractItemView::NoEditTriggers</set>
</property>
<property name="selectionBehavior">
 <enum>QAbstractItemView::SelectRows</enum>
</property>
<attribute name="horizontalHeaderStretchLastSection">
 <bool>true</bool>
</attribute>
```

### detail_dialog_ui.py

手动在 hits_table 创建后添加（保持基线风格，无 u 前缀）：

```python
self.hits_table.setObjectName("hits_table")
self.hits_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
self.hits_table.setSelectionBehavior(QAbstractItemView.SelectRows)
self.hits_table.horizontalHeader().setStretchLastSection(True)
self.hits_table.verticalHeader().setVisible(False)
```

### detail_dialog.py

`_configure_ui` 删除 setEditTriggers/setSelectionBehavior 调用：

```python
def _configure_ui(self) -> None:
    """配置 .ui 无法静态表达的动态属性与信号槽连接。"""
    # 命中规则表：列头拉伸模式（editTriggers/selectionBehavior 已在 .ui 中声明）
    self.hits_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # pyrefly: ignore [missing-argument]
    self.hits_table.cellClicked.connect(self._on_hits_row_clicked)
```

导入分支删除 `QTableWidget`（仅保留 `QTableWidgetItem`）。

### main_window.ui

在 `scanning_layout` 中 `lists_splitter` 与 `scanning_btn_row` 之间插入：

```xml
<item>
 <widget class="QLabel" name="scan_stats_label">
  <property name="alignment">
   <set>Qt::AlignCenter</set>
  </property>
  <property name="textFormat">
   <enum>Qt::RichText</enum>
  </property>
  <property name="text">
   <string/>
  </property>
 </widget>
</item>
```

### main_window_ui.py

IDE 自动增量更新（保持基线风格）：

```python
self.scan_stats_label = QLabel(self.scanning_page)
self.scan_stats_label.setObjectName(u"scan_stats_label")
self.scan_stats_label.setAlignment(Qt.AlignCenter)
self.scan_stats_label.setTextFormat(Qt.RichText)
```

### main_window.py

`_setup_scan_stats_panel` 简化为单行：

```python
def _setup_scan_stats_panel(self) -> None:
    """初始化扫描中页的已扫描文件分类统计面板。

    ``scan_stats_label`` 已在 ``main_window.ui`` 中声明（位于 ``lists_splitter``
    与 ``scanning_btn_row`` 之间），本方法仅设置初始文本。
    """
    self._update_scan_stats(0, 0, 0, 0)
```

## 测试验证结果

| 门禁 | 结果 | 基线（iter-51） | 变化 |
|------|------|----------------|------|
| ruff check | 0 errors | 0 errors | — |
| ruff format --check | 80 files already formatted | 通过 | — |
| pyrefly check | 0 errors (452 suppressed) | 0 errors (452 suppressed) | — |
| pytest | 1324 passed / 0 failed | 1324 passed / 0 failed | — |
| coverage | 96.07% | 96.10% | -0.03% |

覆盖率轻微下降 0.03% 来自 detail_dialog.py 删除 setEditTriggers/
setSelectionBehavior 调用导致的行号变化，非功能行丢失。仍在 95% 阈值之上。

## 整合优化情况

- 静态属性下沉到 .ui 后，.py 仅保留真正需要运行时配置的逻辑（信号槽、
  setSectionResizeMode、setStretch、状态栏 addWidget 等 pyside2-uic 不支持项）。
- _ui.py 与 .ui 保持严格同步，遵循项目既有基线风格。
- 无新增重复代码或抽象。

## 遗留事项

- 状态栏子控件（stats_label / current_file_label / progress）因 pyside2-uic
  5.15.2 不支持 QStatusBar 子 widget 自动 addWidget，无法整合到 .ui，
  保留在 `main_window.py:_setup_status_bar`。
- layout stretch / QSplitter setStretchFactor / setSizes 同因工具链限制
  保留在 `_setup_layouts` / `_setup_splitters`。
- 若未来迁移到 PySide6 + pyside6-uic，可重新评估上述限制项是否解除。

## 下一轮计划

- 无具体计划，视用户需求而定
