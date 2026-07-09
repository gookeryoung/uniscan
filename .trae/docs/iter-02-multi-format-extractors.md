# iter-02 多格式文件提取器

迭代日期：2026-07-09
阶段：P1（多格式解析器）

## 本轮目标

实现文件内容提取器框架，支持 PDF、DOCX、PPTX、XLSX、ODS、ODT、WPS 等多种
文件格式的文本提取，并集成到 Scanner 的内容提供链，使规则引擎能够扫描
办公文档内容。

## 验收标准（P1 范围）

- [x] Extractor 抽象基类与注册表机制
- [x] 纯文本提取器（含编码自动检测）
- [x] PDF 提取器（pypdf，处理加密文档）
- [x] DOCX 提取器（python-docx，段落+表格+页眉页脚）
- [x] PPTX 提取器（python-pptx，文本框+表格+备注）
- [x] XLSX 提取器（openpyxl，多工作表+行列限制）
- [x] ODS 提取器（odfpy）
- [x] ODT 提取器（odfpy）
- [x] WPS 提取器（OOXML 兼容格式，旧版二进制跳过）
- [x] 集成到 Scanner 默认内容提供器
- [x] 单元测试覆盖率 ≥ 80%（实际 82.67%）
- [x] ruff lint + format 全部通过

## 改动文件清单

### 提取器子包（src/pyfilescan/extractors/）
- `base.py`：Extractor 抽象基类、ExtractorRegistry、ExtractorError、
  default_registry 单例、get_extractor / extract_content 函数
- `text.py`：TextExtractor + TEXT_EXTENSIONS 常量（60+ 扩展名），
  charset-normalizer 编码检测，UTF-8/GBK/latin-1 回退链
- `pdf.py`：PdfExtractor，pypdf 提取，加密 PDF 跳过，页面级容错
- `office.py`：DocxExtractor（段落+表格+页眉页脚）、
  PptxExtractor（文本框+表格+备注）
- `spreadsheet.py`：XlsxExtractor（多工作表，max_rows/max_cols 限制）、
  OdsExtractor（odfpy TableCell 提取）
- `odf.py`：OdtExtractor（odfpy 段落 P + 标题 H）
- `wps.py`：WpsExtractor，ZIP 魔数检测 OOXML，临时文件改名绕过扩展名检查，
  旧版二进制格式跳过
- `registry.py`：register_all() 注册所有内置提取器
- `__init__.py`：公共 API 导出，模块导入时自动注册

### 扫描器集成（src/pyfilescan/scanner/）
- `scanner.py`：新增 default_extract_content 函数，Scanner 默认使用提取器注册表；
  提取失败时回退到纯文本读取

### 测试（tests/）
- `test_extractors.py`：36 个测试用例，覆盖各提取器的正常提取、空文档、
  损坏文档、扩展名注册、Scanner 集成等场景。使用对应库动态生成 fixture 文件

## 关键决策与依据

### 1. 提取器懒加载依赖
各提取器类在 `extract` 方法内部 `import` 第三方库（pypdf、python-docx 等），
模块导入时不强依赖。这样即使某些库未安装，其他格式仍可用，且模块导入速度快。
依赖缺失时抛 ExtractorError，由 Scanner 捕获并记录。

### 2. 编码检测策略
TextExtractor 使用 charset-normalizer 自动检测编码。检测失败时按
UTF-8 → GBK → latin-1 顺序回退。latin-1 不会失败（单字节全映射），
保证最终能解码。GBK 短文本检测可能不准确，但实际文件通常足够长。

### 3. WPS 格式兼容性
WPS 文档有两种形态：
- OOXML 兼容（ZIP 打包 XML）：复用 python-docx/openpyxl/python-pptx 提取
- 旧版二进制：无法解析，记录 info 日志并返回空字符串

通过检查文件头 ZIP 魔数（PK\\x03\\x04）判断格式类型。
openpyxl 会检查扩展名拒绝 .et，通过复制到临时 .xlsx 文件绕过。
Windows 上 openpyxl 关闭后仍可能锁定文件，使用 _safe_unlink 忽略 PermissionError。

### 4. 提取器注册表设计
ExtractorRegistry 按 `supported_extensions` 建立扩展名到提取器的映射。
注册表查找大小写不敏感，扩展名自动去除前导点。
`default_registry` 是模块级单例，`register_all()` 幂等注册所有内置提取器。
`extract_content(path)` 是便捷函数，未注册扩展名返回空字符串。

### 5. Scanner 集成
Scanner 默认使用 `default_extract_content` 作为 content_provider。
该函数调用 `extract_content(path)`，失败时回退到 `path.read_text(errors="ignore")`。
保留 content_provider 参数，允许 GUI 阶段注入带进度回调的提供器。

### 6. PDF 加密处理
加密 PDF（reader.is_encrypted）直接返回空字符串并记录 info 日志，
不尝试密码破解。扫描版 PDF（无文本层）extract_text 返回空，自然处理为未命中。

### 7. XLSX 性能限制
XlsxExtractor 默认 max_rows=10000、max_cols=256，避免超大工作表导致内存溢出。
使用 read_only=True + data_only=True 模式，流式读取，计算结果值优先。

## 验证结果

```
测试：171 passed in 1.54s（含 P0 的 135 + P1 的 36）
覆盖率：82.67%（branch coverage，阈值 80%）
ruff check：All checks passed!
ruff format：34 files already formatted
```

手动验证：
- TextExtractor：UTF-8 中文文本正确提取
- DocxExtractor：段落、表格内容均提取
- PptxExtractor：幻灯片标题、内容、备注提取
- XlsxExtractor：多工作表、单元格内容提取
- WpsExtractor：OOXML 兼容 .wps/.et 文件提取，旧版二进制跳过
- Scanner 集成：扫描含 DOCX/XLSX 的目录，内容规则正确命中

## 遗留事项

1. **PDF/ODT/ODS 测试覆盖不足**：动态生成这些格式的 fixture 较复杂，
   当前仅测试了损坏文件抛 ExtractorError。P5 阶段可补充真实 fixture 文件。
2. **GBK 短文本编码检测不准**：charset-normalizer 对短文本（<20 字符）
   可能误判。实际文件通常足够长，影响有限。
3. **WPS 旧版二进制格式未支持**：旧版 .wps/.et/.dps 是私有二进制格式，
   当前直接跳过。如需支持，需引入 antiword 或 LibreOffice 转换。
4. **提取器并发安全**：ExtractorRegistry 的提取器实例是共享的，
   TextExtractor 等无状态提取器线程安全；WpsExtractor 使用临时文件，
   并发时需注意（P5 阶段引入并发时再评估）。
5. **大文件处理**：TextExtractor 有 50MB 限制，但 PDF/DOCX 等无限制，
   超大文档可能导致内存问题。P5 阶段可加全局大小限制。

## 下一阶段（P2）重点

- 设计 ArchiveScanner 压缩文件扫描器
- 实现 ZIP 递归解压扫描（zipfile，标准库）
- 实现 RAR 递归解压扫描（rarfile，依赖 unrar 系统工具）
- 压缩文件内文件的内容提取（复用 Extractor 注册表）
- 嵌套压缩文件支持（压缩包内含压缩包）
- 配套单元测试
