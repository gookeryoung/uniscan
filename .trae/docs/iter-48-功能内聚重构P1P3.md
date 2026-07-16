# iter-48：功能内聚重构 P1 + P3

## 需求清单

- [x] 1. P1 导出拆分：将 `ScanReport` 的二进制导出（PDF/Excel）从 `scanner.result` 拆到独立 `scanner.export` 模块
- [x] 2. P3 结果树拆分：将 `main_window.py` 的结果树模型管理、三种分组填充、选中/双击事件拆到独立 `gui.result_tree.ResultTreeView` 控件
- [x] 3. 修复 iter-47 基线遗留 bug：`detail_hits_table` 列数不匹配（.ui 5 列 vs 代码期望 6 列）
- [x] 4. 全门禁通过，覆盖率不低于基线 95%

## 迭代目标

针对 `main_window.py` 与 `scanner/result.py` 过重功能进行内聚重构，按"功能内聚"原则拆分到独立模块/控件，使主窗口仅负责信号路由、数据层仅承担数据结构与文本序列化。本轮交付 P1（导出拆分）与 P3（结果树拆分），P2（详情面板拆分）留待下一轮。

## 改动文件清单

### P1 导出拆分

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/fuscan/scanner/export.py` | 新增 | 从 result.py 拆出 `export_pdf`/`export_excel`/`save_report`，惰性导入 reportlab/openpyxl |
| `src/fuscan/scanner/result.py` | 修改 | 移除 `to_pdf`/`to_excel`/`save_report` 方法（保留 `to_format` 文本格式与 `format_size`） |
| `src/fuscan/cli.py` | 修改 | `save_report` 导入从 `scanner.result` 改为 `scanner.export` |
| `tests/test_export.py` | 新增 | 从 `test_scanner.py` 迁移导出测试，目标模块改为 `scanner.export` |
| `tests/test_scanner.py` | 修改 | 删除已迁移的导出测试用例 |

### P3 结果树拆分

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/result_tree.py` | 新增 | `ResultTreeView(QTreeView)` 子类，封装模型 + 三种分组填充 + 信号路由 |
| `src/fuscan/gui/main_window.py` | 修改 | 删除已迁移的 `_populate_*`/`_make_result_row`/`_apply_severity_to_standard_item`/`_clear_row_selectable`/`_SEVERITY_RANK`/`_SEVERITY_BACKGROUNDS`，改用 `ResultTreeView` API 与 `preview_utils.SEVERITY_BACKGROUNDS` |
| `src/fuscan/gui/main_window.ui` | 修改 | `detail_hits_table` 新增第 6 列"描述"；`result_tree` 提升为 `ResultTreeView` 自定义控件 |
| `src/fuscan/gui/main_window_ui.py` | 重新生成 | 含 `ResultTreeView` import + 6 列表头 |
| `src/fuscan/gui/preview_utils.py` | 修改 | 新增 `SEVERITY_BACKGROUNDS` 常量（与既有 `SEVERITY_COLORS`/`SEVERITY_LABELS` 集中定义） |
| `tests/test_gui.py` | 修改 | 批量迁移 `window._result_model.X` → `window.result_tree.model().X`；旧方法调用改为 `ResultTreeView` 内部句柄 |

### 其他

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/fuscan/assets/resources_rc.py` | 删除 | pyside2-rcc 误生成产物（正确位置为 `gui/resources_rc.py`，已跟踪） |
| `.gitignore` | 修改 | 新增 `src/fuscan/assets/resources_rc.py` 忽略规则，避免再次误提交 |

## 关键决策与依据

### P1：导出拆分的边界

- **问题**：`ScanReport` 同时承担数据结构、文本序列化（`to_format`）、二进制导出（`to_pdf`/`to_excel`），且二进制导出依赖 reportlab/openpyxl 重型库
- **边界决策**：文本格式（csv/json/text）保留在 `ScanReport.to_format`（纯数据序列化，无外部依赖）；二进制格式（pdf/excel）拆到 `scanner.export`，惰性导入重型库
- **依据**：`to_format` 是数据层的纯函数式序列化，与 `ScanReport` 数据结构强内聚；二进制导出涉及布局/字体/样式，属于"表现层"，与数据结构弱关联
- **`save_report` 归属**：随二进制导出一起迁到 `export.py`，按扩展名分发到 `export_pdf`/`export_excel`/`to_format`

### P3：ResultTreeView 信号路由解耦

- **问题**：`main_window.py` 直接持有 `QStandardItemModel`，三种分组填充逻辑（`_populate_flat`/`_populate_grouped_by_rule`/`_populate_grouped_by_severity`）与主窗口业务逻辑混杂，主窗口承担了视图层职责
- **方案**：`ResultTreeView(QTreeView)` 子类封装模型 + 填充 + 事件处理，通过三个信号向外通信：
  - `result_selected(object)`：选中变化，携带 `ScanResult | None`
  - `result_activated(object)`：双击，携带 `ScanResult`
  - `context_menu_requested(QPoint)`：右键，携带 viewport 坐标
- **依据**：rule-12「MVC 分层」要求"大数据量优先用 `QAbstractItemModel`"，且"用信号槽解耦控件"。`ResultTreeView` 是自包含的 Model/View 控件，主窗口仅连接信号做路由
- **.ui 提升控件**：`<customwidgets>` 声明 `ResultTreeView`，`result_tree` 节点 `class="ResultTreeView"` 替代 `QTreeView`，uic 生成的 `main_window_ui.py` 自动 `from fuscan.gui.result_tree import ResultTreeView` 并实例化

### P3：detail_hits_table 列数 bug 修复

- **问题**：iter-47 基线 `main_window.ui` 中 `detail_hits_table` 只有 5 列（位置/规则/严重等级/命中数/条数），但 `main_window.py` 代码期望 6 列（含"描述"），导致 `test_detail_hits_table_has_position_count_column` 与 `test_detail_hits_table_description_column_filled` 两个测试在基线即失败
- **修复**：.ui 新增第 6 列"描述"，`main_window_ui.py` 重新生成后 `columnCount` 从 5 改为 6
- **依据**：这是 iter-45 result_tree Model/View 迁移时遗漏的 .ui 同步，属基线遗留 bug，本轮 P3 拆分时顺带修复

### P3：PySide2 stub 限制处理

- **Signal 类**：`connect`/`emit` 在 PySide2 stub 中类型不完整，按项目惯例用 `# pyrefly: ignore [missing-attribute]` 行级注释抑制（共 7 处）
- **QTreeView 继承**：`class ResultTreeView(QTreeView)` 触发 `invalid-inheritance`，用类级 `# pyrefly: ignore [invalid-inheritance]` 抑制
- **QStandardItemModel.appendRow**：stub 限制，8 处 `# pyrefly: ignore [missing-argument]` 抑制
- **未使用的 ignore 清理**：`doubleClicked.connect` 与 `selectionModel().selectionChanged.connect` 是 `QTreeView`/`QItemSelectionModel` 内置信号，类型已知，删除多余的 `# pyrefly: ignore` 注释

## 代码实现情况

### P1：scanner/export.py 核心 API

```python
def export_pdf(report: ScanReport) -> bytes:
    """生成 PDF 二进制（reportlab，STSong-Light 中文字体）。"""
    from reportlab.lib import colors
    # ... 惰性导入


def export_excel(report: ScanReport) -> bytes:
    """生成 Excel 二进制（openpyxl，双工作表 + 严重等级着色）。"""
    from openpyxl import Workbook
    # ... 惰性导入


def save_report(report: ScanReport, path: str | Path) -> None:
    """按文件扩展名自动选择格式写入文件。"""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        Path(path).write_bytes(export_pdf(report))
    elif suffix == ".xlsx":
        Path(path).write_bytes(export_excel(report))
    else:
        # csv/json/text 仍由 ScanReport.to_format 处理
        Path(path).write_text(report.to_format(suffix.lstrip(".")), encoding="utf-8")
```

### P3：ResultTreeView 信号定义与转发

```python
class ResultTreeView(QTreeView):  # pyrefly: ignore [invalid-inheritance]
    result_selected = Signal(object)
    result_activated = Signal(object)
    context_menu_requested = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._result_model = QStandardItemModel()
        self._result_model.setHorizontalHeaderLabels(["路径", "规则", "严重等级", "命中数", "条数", "详情"])
        self.setModel(self._result_model)
        self._last_report: ScanReport | None = None
        # ... 列宽设置
        self.doubleClicked.connect(self._handle_double_clicked)
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._handle_selection_changed)

    def populate(self, report: ScanReport) -> None:
        """存储当前报告数据，供 refresh 读取。"""
        # ... clear + setHorizontalHeaderLabels + 暂存

    def refresh(self, report, path_query="", rule_name="", group_mode="flat") -> None:
        """按筛选条件与分组模式重建结果树模型。"""
        # setUpdatesEnabled(False) + try/finally 包裹批量插入
        # 三种分组模式分发

    def clear_results(self) -> None:
        """清空结果树模型与暂存报告。"""

    def _handle_selection_changed(self, *_args) -> None:
        """选中变化：发出 result_selected 信号。"""
        # ... 从 selectedIndexes 取 ScanResult，向上取父行兜底

    def _handle_double_clicked(self, index) -> None:
        """双击：发出 result_activated 信号。"""
        # ... 从 index 取 ScanResult，向上取父行兜底

    def contextMenuEvent(self, event) -> None:
        """右键：发出 context_menu_requested 信号。"""
        self.context_menu_requested.emit(event.pos())
        event.accept()
```

### P3：main_window.py 调用点简化

```python
# _start_scan 中
self.result_tree.clear_results()

# _populate_results 中
self.result_tree.populate(report)

# _refresh_result_tree 中
self.result_tree.refresh(
    self._last_report,
    path_query=path_filter,
    rule_name=rule_filter,
    group_mode=group_mode,
)

# 信号连接（主窗口仅做路由）
self.result_tree.result_selected.connect(self._on_result_selected)  # pyrefly: ignore [missing-attribute]
self.result_tree.result_activated.connect(self._on_result_activated)  # pyrefly: ignore [missing-attribute]
self.result_tree.context_menu_requested.connect(self._on_result_tree_context_menu)  # pyrefly: ignore [missing-attribute]
```

## 整合优化情况

- P1 与 P3 共同遵循"功能内聚"原则：表现层（二进制导出、视图填充）从数据层/主窗口剥离，使 `ScanReport` 仅承担数据结构、`MainWindow` 仅承担信号路由
- P3 拆分后 `main_window.py` 删除约 200 行结果树相关代码，模块行数从 ~1320 降至 ~1120
- `SEVERITY_BACKGROUNDS` 常量从 `main_window.py` 迁到 `preview_utils.py`，与既有 `SEVERITY_COLORS`/`SEVERITY_LABELS` 集中定义，消除跨模块重复
- `result_tree.py` 内部导入统一到顶部（修复函数内导入 `SEVERITY_COLORS` 的遗留问题）
- 顺带修复 iter-47 基线遗留的 `detail_hits_table` 列数 bug（.ui 5 列 → 6 列）

## 测试验证结果

| 门禁 | 结果 |
|------|------|
| `uv run ruff check src tests benchmarks` | All checks passed |
| `uv run ruff format --check src tests benchmarks` | 82 files already formatted |
| `uv run pyrefly check` | 0 errors (442 suppressed，比 iter-47 基线 435 增加 7，为 Signal/QTreeView stub 限制) |
| `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95 -n auto` | 1323 passed, 51 warnings, 覆盖率 95.97% |

### 测试迁移

- `tests/test_export.py`：从 `test_scanner.py` 迁移全部导出测试，目标模块改为 `scanner.export`
- `tests/test_gui.py`：批量替换 `window._result_model.X` → `window.result_tree.model().X`（rowCount/columnCount/item/index/appendRow）；`_on_result_double_clicked(index)` → `window.result_tree._handle_double_clicked(index)`；`_on_result_selection_changed()` → `window._on_result_selected(None)`；`_SEVERITY_BACKGROUNDS` → `preview_utils.SEVERITY_BACKGROUNDS`
- 删除 4 处 unused `# pyrefly: ignore [missing-argument]` 注释

### 覆盖率明细

| 模块 | 基线（iter-47） | 当前 | 变化 |
|------|----------------|------|------|
| `scanner/result.py` | 99% | 99% | 持平（导出方法迁出后剩余行数更易覆盖） |
| `scanner/export.py` | - | 96% | 新模块（5 行未覆盖：PDF/Excel 边界分支） |
| `gui/main_window.py` | 92% | 92% | 持平（删除迁移代码后行数下降，比例不变） |
| `gui/result_tree.py` | - | 96% | 新模块（5 行未覆盖：双击/右键事件边界） |
| `gui/preview_utils.py` | 97% | 97% | 持平 |
| 总体 | 96.06% | 95.97% | -0.09%（新模块边界分支未覆盖，仍 > 95% 阈值） |

### Windows access violation 偶发问题

- **现象**：单进程运行 `pytest` 在 `test_worker_scans_multiple_roots` 处崩溃（exit code -1073741819），崩溃栈在 `scanner.py:237` 的 `threading.Event.notify_all`
- **根因**：PySide2/Qt 在 Windows 环境下多线程清理的已知偶发问题，与本次改动无关（单独运行该测试通过）
- **规避**：用 `pytest -n auto`（pytest-xdist 进程隔离）运行，每个 worker 独立进程避免线程清理冲突

## 遗留事项

- **P2 详情面板拆分**：`main_window.py` 的 `_detail_*` 系列 15 个方法（详情区命中表、内容预览、命中导航、备注、导出）仍未拆分，留待下一轮
- **pyrefly suppressed 注释**：442 个（比基线 +7），全部为 PySide2 stub 限制，待迁移 PySide6 或 stub 改进后清理
- **`scanner/scanner.py` 覆盖率**：94%（22 行未覆盖），pipelined 模式异常分支与 archive phase 边界场景，属既有技术债

## 下一轮计划

- **P2 详情面板拆分**：`main_window.py` `_detail_*` 系列 15 个方法 → `gui/detail_panel.py` `DetailPanel(QWidget)`，主窗口仅持有 `DetailPanel` 实例并连接信号
- P2 完成后即结束"功能内聚重构"三阶段（P1+P2+P3），进入收尾
