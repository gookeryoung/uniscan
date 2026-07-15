# iter-42 PDF/Excel 导出功能

## 需求清单

- [x] 增加PDF格式导出功能，需要面向用户，告知扫描结果，提高可读性和用户友好性
- [x] 增加Excel格式导出功能，需要面向用户，告知扫描结果，提高数据处理效率和用户友好性

## 迭代目标

为扫描报告新增 PDF 与 Excel 两种二进制导出格式，覆盖 GUI 导出菜单、CLI 输出与
数据层 `ScanReport` 方法三个入口，统一委托给 `save_report(path)` 按扩展名自动选择
序列化方式，避免展示层重复实现二进制写入逻辑。

## 改动文件清单

### `pyproject.toml`（修改）

- `reportlab` 从 `[project.optional-dependencies].dev` 提升到 `dependencies`，
  按版本分流：`reportlab>=3.6.13,<4.0; python_version < '3.9'` 与
  `reportlab>=4.0.0; python_version >= '3.9'`。
  理由：PDF 导出是面向终端用户的核心功能，reportlab 必须随包分发。

### `src/fuscan/scanner/result.py`（修改）

新增三个公共方法与两个模块级私有函数：

- `ScanReport.to_pdf() -> bytes`：委托给 `_build_pdf`，使用 reportlab 生成 PDF，
  含标题、扫描统计、命中文件表格。中文字体 `STSong-Light` CID（跨平台一致，无需字体文件）。
- `ScanReport.to_excel() -> bytes`：委托给 `_build_excel`，使用 openpyxl 生成 xlsx，
  双工作表："扫描汇总"（10 行统计键值对）与"命中明细"（7 列表头 + 严重等级着色：
  CRITICAL 红 `FADBD8` / WARNING 黄 `FCF3CF` / INFO 绿 `D4EFDF`）。
- `ScanReport.save_report(path: Path) -> None`：按扩展名自动选择序列化方式，
  `.pdf`/`.xlsx` 调用 `to_pdf`/`to_excel` 写 bytes，`.csv`/`.json` 调用
  `to_format` 写 UTF-8 文本，其他扩展名按 text 格式输出。
- `_build_pdf(report)`：惰性导入 reportlab，注册 CID 字体用
  `contextlib.suppress(Exception)` 容错已注册场景；A4 页面，左右 20mm 边距；
  表头蓝底白字 `#0887A0`，斑马纹 `#F5F8FA`；Paragraph 包装单元格支持自动换行。
- `_build_excel(report)`：惰性导入 openpyxl，`wb.active` 后加
  `assert ws1 is not None` 缩窄 pyrefly 类型推断；`freeze_panes="A2"` 冻结表头；
  `wrap_text=True` 自动换行。

关键设计：
- **返回 bytes 而非 str**：PDF/Excel 是二进制格式，不能复用 `to_format` 的 str 返回值。
- **惰性导入**：reportlab/openpyxl 虽为核心依赖，但导入较重，方法内部 import 避免模块加载开销。
- **`list[Any]` 容纳 reportlab Flowable 子类**：`story` 与 `rows` 用 `list[Any]`
  容纳 Paragraph/Spacer/Table 等动态类型，避免 pyrefly 严格类型推断错误。

### `src/fuscan/cli.py`（修改）

- `--output-format` choices 从 `["text", "json", "csv"]` 扩展为
  `["text", "json", "csv", "pdf", "excel"]`，help 文本注明"pdf/excel 需配合 -f 输出到文件"。
- 新增 `_output_report(report, fmt, output_file)` 函数处理二进制格式：
  - `pdf`/`excel` 必须配合 `-f` 输出到文件，否则 `logger.error` 并返回；
  - 文本格式仍走原 `_write_output` 函数。
- 输出逻辑从直接调用 `to_format` 改为统一委托给 `_output_report`。

### `src/fuscan/gui/main_window.py`（修改）

`_on_export_menu` 与 `_on_export` 重构：

- `_on_export_menu`：items 从 `["CSV 文件 (*.csv)", "JSON 文件 (*.json)"]`
  扩展为四元组列表 `[(label, fmt), ...]`，新增 PDF 与 Excel 选项；
  用 `next(fmt for label, fmt in items if label == choice)` 取得格式标识。
- `_on_export`：扩展名映射 `excel → .xlsx`，其他格式直接同名；
  写入逻辑从 `to_format(fmt)` + `write_text` 改为统一委托给 `save_report(path)`，
  由其按扩展名自动选择序列化方式（文本写 UTF-8，二进制写 bytes）。

### `docs/manual.md`（修改）

第 7 节"导出扫描结果"重写：

- 从"CSV/JSON 两种格式"扩展为"CSV/JSON/PDF/Excel 四种格式"。
- 新增 PDF 与 Excel 格式说明：PDF 含标题、统计与命中表格适合汇报归档；
  Excel 双工作表并按严重等级着色。
- 新增 CLI 命令示例：`fuscan scan /path -o pdf -f report.pdf`。

### `src/fuscan/gui/settings_dialog_ui.py`（修改）

ruff `--fix` 自动应用 Python 3 现代化规则：
- 删除冗余 `# -*- coding: utf-8 -*-` 声明（Python 3 默认 UTF-8）。
- `class Ui_SettingsDialog(object)` → `class Ui_SettingsDialog`（Python 3 不需继承 object）。

## 关键决策与依据

### reportlab 提升为核心依赖

- **方案对比**：
  - A：保持 reportlab 为 dev 依赖，PDF 导出功能可选（try import）。
  - B：提升 reportlab 为核心依赖，随包分发。
- **决策**：选 B。PDF 导出是面向终端用户的核心功能（需求1明确要求"面向用户"），
  保持 dev 依赖会导致普通用户安装后无法使用 PDF 导出，体验割裂。
  openpyxl 已是核心依赖（多格式扫描需要），reportlab 提升后与 openpyxl 同级别。

### to_pdf/to_excel 返回 bytes 而非 str

- **理由**：PDF 与 Excel 是二进制格式，不能复用 `to_format(fmt) -> str` 的返回值模式。
  独立的 `to_pdf() -> bytes` / `to_excel() -> bytes` 方法明确区分文本与二进制格式，
  `save_report(path)` 作为统一入口按扩展名分发，避免调用方处理 bytes/str 分支。

### save_report 按扩展名自动选择格式

- **理由**：GUI `_on_export` 与 CLI `_output_report` 均需按格式选择写入方式，
  将分发逻辑下沉到 dataclass 方法，避免展示层重复实现 if-else 分支。
  GUI 直接调用 `save_report(path)`，CLI 仍单独处理 stdout 输出场景（文本格式可输出到 stdout，
  二进制格式必须输出到文件）。

### PDF 中文字体 STSong-Light CID

- **理由**：与 `scripts/generate_manual_pdf.py` 一致，CID 字体跨平台无需字体文件，
  避免中文 TTF 字体打包进 wheel 的体积与版权风险。reportlab 内置 Adobe 亚洲字体包。

### Excel 严重等级着色

- **理由**：CRITICAL 红 / WARNING 黄 / INFO 绿 提高可读性，用户一眼分辨严重等级。
  颜色采用柔和的浅色系（`FADBD8`/`FCF3CF`/`D4EFDF`），避免刺眼。

### openpyxl `wb.active` 类型推断修复

- **问题**：openpyxl 类型 stub 中 `Workbook.active` 返回 `Worksheet | None`，
  pyrefly 报告 5 个 `NoneType has no attribute` 错误。
- **方案**：加 `assert ws1 is not None` 缩窄类型，注释说明"Workbook 新建时 active 一定非空"。
  这不是运行时风险，仅是第三方库类型 stub 保守推断。

### reportlab Flowable 类型用 list[Any]

- **问题**：`story: list[object]` 与 `doc.build(story)` 期望的 `list[Flowable]` 类型不匹配；
  `rows: list[list[object]] = [header]` 中 header 是 `list[Paragraph]`，list 不变性导致赋值失败。
- **方案**：将 `story` 与 `rows` 类型改为 `list[Any]` / `list[list[Any]]`。
  reportlab 的 Flowable 是动态类型，Paragraph/Spacer/Table 均为其子类，
  `Any` 在此场景合理（符合规则"Any 仅用于真正动态场景"）。

## 代码实现情况

### ScanReport 导出方法

```python
def to_pdf(self) -> bytes:
    return _build_pdf(self)

def to_excel(self) -> bytes:
    return _build_excel(self)

def save_report(self, path: Path) -> None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        path.write_bytes(self.to_pdf())
        return
    if ext == ".xlsx":
        path.write_bytes(self.to_excel())
        return
    content = self.to_format(ext.lstrip(".") if ext.lstrip(".") in ("csv", "json") else "text")
    path.write_text(content, encoding="utf-8")
```

### CLI _output_report 函数

```python
def _output_report(report: ScanReport, fmt: str, output_file: Path | None) -> None:
    if fmt == "pdf":
        if output_file is None:
            logger.error("PDF 格式必须配合 -f/--output-file 输出到文件")
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(report.to_pdf())
        return
    if fmt == "excel":
        if output_file is None:
            logger.error("Excel 格式必须配合 -f/--output-file 输出到文件")
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(report.to_excel())
        return
    _write_output(report.to_format(fmt), output_file)
```

### GUI _on_export 统一委托

```python
def _on_export(self, fmt: str) -> None:
    ...
    ext = "xlsx" if fmt == "excel" else fmt
    filter_str = f"{fmt.upper()} 文件 (*.{ext})"
    default_name = f"fuscan_report.{ext}"
    path_str, _ = QFileDialog.getSaveFileName(self, "导出扫描结果", default_name, filter_str)
    if not path_str:
        return
    path = Path(path_str)
    try:
        self._last_report.save_report(path)
        QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
    except OSError as exc:
        QMessageBox.warning(self, "导出失败", str(exc))
```

## 测试验证结果

### 新增测试

- `tests/test_scanner.py`：13 个测试
  - `to_pdf`：返回 bytes + `%PDF-` 头、空命中也能生成、PDF 结构标记可见
  - `to_excel`：返回 bytes + `PK` 头、空命中也能生成、openpyxl 读回验证工作表名与表头
  - `save_report`：csv/json/txt/pdf/xlsx/未知扩展名 6 种调度场景
- `tests/test_cli.py`：4 个测试
  - `-o pdf -f` 生成 PDF 文件、`-o excel -f` 生成 xlsx 文件
  - `-o pdf` 不带 `-f` 不崩溃（记错误日志）
- `tests/test_gui.py`：4 个测试
  - `_on_export("pdf")` / `_on_export("excel")` 直接调用生成文件
  - `_on_export_menu` 选择 PDF / Excel 格式生成文件

### 门禁检查

- `ruff check`：仅 ARG005 基线错误（tests/ 既有 lambda 模式），无新增规则违例
- `ruff format --check`：79 files already formatted
- `pyrefly check`：801 errors（与基线一致，无新增）
- `pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：
  - 1291 passed, 16 deselected
  - 覆盖率 96.01% ≥ 95%

## 遗留事项

无。需求1与需求2已闭环。

## 下一轮计划

iter-43：扫描中 UI 增强（需求5/6/7）

- 需求5：扫描中查看匹配情况与定位文件
- 需求6：命中文件下方增加已处理文件列表
- 需求7：颜色区分命中文件与已处理文件（绿/红/黄/红）
