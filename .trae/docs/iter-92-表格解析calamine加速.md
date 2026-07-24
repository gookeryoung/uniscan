# iter-92 表格解析 calamine 加速

## 需求清单

- [x] 评估文档类（含表格）是否能通过 Rust/C 加速 Python 库提速
- [x] 引入 `python-calamine==0.3.1`（Rust + PyO3）替代 openpyxl/xlrd 提取 XLSX/XLS（req-29）
- [x] 保持 Python 3.8 兼容性
- [x] XLSX/XLS 速度档次从 T4 慢速降至 T2 快速
- [x] ODS 维持 odfpy（calamine 0.3.1 对 odfpy 生成 ODS 解析不完整）

## 迭代目标

评估文档提取器（DOCX/DOC/XLSX/XLS/ODS/PPTX/PPT/ODT/RTF/WPS/MSG/PDF）中可被 Rust/C 加速的部分，针对表格类（XLSX/XLS/WPS 表格）引入 `python-calamine`（Rust + PyO3）替代纯 Python 库（openpyxl/xlrd），实现速度档次升级并降低 GIL 占用。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `pyproject.toml` | 修改 | 新增 `python-calamine==0.3.1` 依赖，移除 `openpyxl>=3.1.0` 与 `xlrd>=2.0.1`（移入 `test` 可选依赖，仅生成样本） |
| `src/fuscan/extractors/spreadsheet.py` | 修改 | 新增 `_extract_calamine_workbook` 公共函数；`XlsxExtractor` 切换至 calamine，speed_tier 由 T4 降至 T2；`OdsExtractor` 维持 odfpy |
| `src/fuscan/extractors/legacy_office.py` | 修改 | `XlsExtractor` 切换至 calamine，speed_tier 由 T4 降至 T2；模块 docstring 同步说明 |
| `src/fuscan/extractors/wps.py` | 修改 | `_extract_as_xlsx` 复用 `_extract_calamine_workbook`，docstring 标注 iter-92 |
| `tests/test_extractors.py` | 修改 | `TestXlsExtractor` mock 从 xlrd 改为 `CalamineWorkbook.from_filelike`；新增 `test_xls_import_error_raises` 校验 "python-calamine 未安装" |
| `tests/test_extractor_benchmark.py` | 修改 | `XlsxExtractor`/`XlsExtractor` 从 `TestTier4Slow` 迁移到 `TestTier2Fast`；模块 docstring 同步 |
| `uv.lock` | 自动 | 依赖锁定刷新 |

## 关键决策与依据

### 1. python-calamine 版本选择（0.3.1）

**约束**：fuscan 最低支持 Python 3.8。

- `python-calamine>=0.4.0` 要求 Python 3.9+，含 ODS 解析修复
- `python-calamine==0.3.1` 仍支持 Python 3.8，但 ODS 解析不完整

**决策**：固定 `0.3.1` 以兼容 Python 3.8，ODS 暂保留 odfpy 实现（T4 慢速）。待 fuscan 抛弃 3.8 支持后可升级并移除 odfpy 依赖。

### 2. 共享提取函数 `_extract_calamine_workbook`

XLSX/XLSM/XLS/WPS 表格共用同一 calamine 后端，提取到 `spreadsheet.py` 模块级函数：

```python
def _extract_calamine_workbook(
    data: bytes,
    max_rows: int = _MAX_ROWS,
    max_cols: int = _MAX_COLS,
    error_label: str = "工作簿",
) -> str: ...
```

`error_label` 参数让 XLSX/XLS/WPS 表格复用同一函数但保留各自错误前缀，便于定位。

### 3. panic 规避：`to_python()` 替代 `iter_rows()`

calamine 0.3.1 的 `iter_rows()` 在空 sheet 上触发 Rust panic：

```
thread '<unnamed>' panicked at src\types\sheet.rs:223:34:
called `Option::unwrap()` on a `None` value
```

改用 `sheet.to_python()` 一次性返回二维列表，规避 panic 且减少 PyO3 边界调用次数。

### 4. 依赖调整

- 新增 `python-calamine==0.3.1` 至主依赖（XLSX/XLS 是核心支持格式）
- `openpyxl` 与 `xlrd` 从主依赖移除：openpyxl 仅测试生成 XLSX 样本所需，迁移到 `test` 可选依赖；xlrd 不再使用（XLS 改由 calamine 读取）
- `uv lock` 后审阅：无新增 CVE 风险

### 5. ODS 保留 odfpy

测试发现 calamine 0.3.1 对 odfpy 生成的标准 ODS 单元格解析不完整（部分文本缺失）。保留 `OdsExtractor` 走 odfpy 后端，`speed_tier` 维持 T4 慢速（XML 解析 + TableRow/Cell 遍历）。

### 6. WPS 表格 speed_tier

WPS 表格（.et）实际委托 calamine 提取，但 `WpsExtractor.speed_tier` 仍返回 T3 中速。原因：WPS 文档类型由 OOXML 子类型分发（DOCX/XLSX/PPTX 三种都可能），统一返回 T3 是综合结果，与实际单次提取的档次不一定一致（与 iter-90 设计一致）。

## 代码实现情况

### `_extract_calamine_workbook`（spreadsheet.py）

```python
def _extract_calamine_workbook(data, max_rows=_MAX_ROWS, max_cols=_MAX_COLS, error_label="工作簿"):
    from python_calamine import CalamineError, CalamineWorkbook
    workbook = CalamineWorkbook.from_filelike(io.BytesIO(data))
    parts = []
    for sheet_idx, sheet_name in enumerate(workbook.sheet_names):
        sheet = workbook.get_sheet_by_index(sheet_idx)
        rows = sheet.to_python()  # 避免 iter_rows() 在空 sheet panic
        # ... 逐行逐单元格提取非空文本，截断到 max_rows/max_cols
    return "\n".join(parts)
```

### XlsExtractor 委托

```python
class XlsExtractor(Extractor):
    @property
    def speed_tier(self): return SpeedTier.FAST  # T4 → T2

    def extract_from_bytes(self, data: bytes) -> str:
        from fuscan.extractors.spreadsheet import _extract_calamine_workbook
        return _extract_calamine_workbook(data, error_label="XLS")
```

## 测试验证结果

- ruff check：All checks passed
- ruff format：105 files already formatted
- pyrefly：0 errors（561 suppressed, 59 warnings）
- pytest：1599 passed, 43 deselected
- 覆盖率：95.04%（branch，≥ 95% 门禁）

### 测试调整要点

- `TestXlsExtractor.test_extract_from_bytes_with_mock`：mock `CalamineWorkbook.from_filelike` 替代 xlrd
- `test_xls_import_error_raises`：mock `python_calamine` import 抛 ImportError，断言 "python-calamine 未安装"
- `TestTier2Fast`：新增 `test_xlsx_extractor_tier` / `test_xlsx_extraction_speed` / `test_xls_extractor_tier`
- `TestTier4Slow`：移除 XLSX/XLS 相关测试（已迁出）

## 遗留事项

- ODS 提取仍走 odfpy（T4 慢速），待 Python 3.8 支持移除后升级 calamine 0.4+
- DOC/PPT 维持 olefile + UTF-16LE 字节扫描（T4 慢速），无成熟 Rust 替代
- PPTX 维持 python-pptx（T4 慢速），无成熟 Rust 替代

## 下一轮计划

无明确下一轮计划。文档类剩余 T4/T5 提取器（ODS/DOC/PPT/PPTX）均无成熟 Rust/C 加速库可用，或受 Python 3.8 兼容性约束无法升级。
