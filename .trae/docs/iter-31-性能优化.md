# iter-31 性能优化：双重 I/O 修复与大文件流式处理

## 迭代目标

1. 修复缓存模式下 `default_extract_content_with_hash` 双重 I/O bug：先 `read_bytes` 算哈希，再让提取器 `extract(path)` 重读磁盘。
2. 优化 CONTAINS 不区分大小写模式：避免对整个大文本做 `text.lower()` 创建临时字符串。
3. 大文件流式处理：超过 10MB 的文本文件分块读取 + 增量解码，降低内存峰值。

## 需求确认

- 优化范围：双重 I/O 修复、CONTAINS 大小写优化、大文件流式处理
- 验收方式：门禁通过（ruff/pyrefly/pytest --cov ≥ 95%）

## 改动文件清单

### 新增接口

- `src/fuscan/extractors/base.py`：Extractor 基类新增 `extract_from_bytes(data)` 抽象方法；ExtractorRegistry 新增 `extract_from_bytes(data, extension)`；模块级新增 `extract_content_from_bytes(data, extension)` 函数。
- `src/fuscan/extractors/__init__.py`：导出 `extract_content_from_bytes`。

### 各提取器实现 extract_from_bytes

- `src/fuscan/extractors/text.py`：
  - `_DEFAULT_MAX_SIZE` 从 50MB 提高到 100MB（配合流式读取降低内存压力）。
  - 新增常量 `_LARGE_FILE_THRESHOLD=10MB`、`_HEADER_SIZE=64KB`、`_CHUNK_SIZE=4MB`。
  - `extract(path)` 对 >10MB 文件调用 `_extract_large(path)` 流式解码。
  - `extract_from_bytes(data)` 直接调 `_decode(data)`。
  - 新增 `_extract_large(path)`：文件头检测编码 + `codecs.getincrementaldecoder` 分块解码。
  - 新增 `_detect_encoding_from_header(header)`：BOM 检测（UTF-8-sig/UTF-32/UTF-16）+ UTF-8/GBK 启发式。
  - `_decode(data)` 对大 bytes（>10MB）用文件头检测跳过 charset-normalizer 全量分析。
- `src/fuscan/extractors/office.py`：`extract(path)` 改为 `read_bytes` 后调 `extract_from_bytes`；`extract_from_bytes` 用 `io.BytesIO(data)` 传给 `Document()`/`Presentation()`。
- `src/fuscan/extractors/pdf.py`：同上，`PdfReader(io.BytesIO(data))`。
- `src/fuscan/extractors/odf.py`：同上，`load(io.BytesIO(data))`。
- `src/fuscan/extractors/spreadsheet.py`：同上，`load_workbook(io.BytesIO(data))` / `load(io.BytesIO(data))`。
- `src/fuscan/extractors/wps.py`：完整重写——
  - 删除 `_temp_with_ext`/`_safe_unlink`/`_is_ooxml(path)`（不再依赖临时文件与扩展名分发）。
  - 新增 `_detect_ooxml_type(data)` 通过 ZIP 内部条目名区分子类型（`word/document.xml`→docx，`xl/workbook.xml`→xlsx，`ppt/presentation.xml`→pptx）。
  - 所有 `_extract_as_*` 方法接收 `bytes` 参数用 `BytesIO`。

### 核心修复

- `src/fuscan/scanner/scanner.py`：
  - import 新增 `extract_content_from_bytes`（修复之前缺失导入导致 NameError 的 bug）。
  - `default_extract_content_with_hash` 改为一次 `read_bytes` 后调 `extract_content_from_bytes(data, entry.extension)`，消除双重 I/O。提取异常时回退到 `data.decode("utf-8", errors="ignore")`。

### CONTAINS 优化

- `src/fuscan/scanner/matchers.py`：
  - 重构 `_apply_leaf` 拆分为 `_apply_regex`/`_apply_contains`/`_apply_equality` 三个子函数（解决 PLR0912 分支过多）。
  - `_apply_contains` 不区分大小写时用 `re.finditer(re.escape(pattern), text, re.IGNORECASE)` 替代 `text.lower().count()`，避免对大文本创建临时字符串。pattern 经 `re.escape` 处理，正则特殊字符按字面量匹配。

### 示例与测试

- `examples/custom_extractor.py`：`IniExtractor` 实现 `extract_from_bytes`（新抽象方法）。
- `tests/test_extractors.py`：
  - 新增 `_make_ooxml_zip` 辅助函数创建有效 ZIP 测试数据。
  - 修复 WPS 测试：`test_wps_invalid_*_raises` 改用有效 ZIP + 损坏内容；`test_wps_is_ooxml_nonexistent`/`test_temp_with_ext_os_error_raises` 删除（方法已移除），替换为 `_detect_ooxml_type` 系列测试；import error 测试改用有效 ZIP 触发类型检测。
  - 新增 `TestExtractFromBytes` 类（12 测试）：各提取器从 bytes 提取与从 path 提取结果一致性。
  - 新增 `TestExtractContentFromBytes` 类（5 测试）：模块函数正确性。
  - 新增 `TestLargeFileStreaming` 类（18 测试）：大文件流式读取、编码检测、charset-normalizer 跳过/回退。
- `tests/test_matchers.py`：新增 `TestContainsOptimization` 类（10 测试）：大小写不敏感计数、正则特殊字符转义、空 pattern 防御、非重叠计数、大文本计数。
- `tests/test_scanner.py`：新增 4 个 `default_extract_content_with_hash` 测试：单次 I/O 验证、超限跳过、OSError 处理、提取器异常回退。
- `tests/test_multiformat_scan.py`：`test_large_file_skipped` 改用 monkeypatch 临时降低 max_size 到 1MB，避免写 100MB 文件。

## 关键决策与依据

1. **`extract_from_bytes` 抽象方法而非可选混入**：所有提取器都应支持从 bytes 提取，抽象方法强制子类实现，避免运行时 AttributeError。
2. **WPS 用 ZIP 内部条目名而非扩展名分发**：`extract_from_bytes` 无路径信息，必须从数据本身判断子类型；ZIP 条目名是 OOXML 规范定义的，可靠区分 docx/xlsx/pptx。
3. **大文件阈值 10MB**：charset-normalizer 对 >10MB 数据全量分析耗时显著；文件头 64KB 足以检测 BOM 和常见编码。
4. **`_detect_encoding_from_header` 启发式**：UTF-8 严格解码 + GBK 回退覆盖 Windows 中文环境常见编码；无法确定时返回 None 让调用方回退到 charset-normalizer。
5. **CONTAINS 用 `re.finditer` 替代 `lower().count()`**：对 100MB 文本，`lower()` 创建 100MB 临时字符串；`re.finditer` 流式扫描无临时分配，且 `re.escape` 确保 pattern 中的 `.` `*` 等按字面量匹配。
6. **`_apply_leaf` 重构**：拆分后每个子函数分支数 ≤ 4，可读性更好且通过 PLR0912 检查。
7. **scanner.py 缺失导入修复**：前序改动中 `extract_content_from_bytes` 被使用但未导入，属于潜在 NameError，本轮一并修复。

## 验证结果

- `uv run ruff check src tests`：All checks passed
- `uv run ruff format --check src tests`：70 files already formatted
- `uv run pyrefly check`：0 errors (111 suppressed, 18 warnings not shown)
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：1032 passed, 4 deselected, coverage 96.15%

## 遗留事项

- `default_extract_content_with_hash` 中 50MB 上限与 TextExtractor 的 100MB `_DEFAULT_MAX_SIZE` 不一致，后续可统一。
- 流式读取暂未覆盖 UTF-8 多字节字符跨块边界场景（`IncrementalDecoder` 已正确处理，但未显式测试）。
