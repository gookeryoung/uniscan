# iter-35 新增文件格式支持

## 迭代目标

扩展 fuscan 支持的文件格式，新增 RTF、旧版 Office（DOC/XLS/PPT）、EML/MSG 共 6 种格式的文本提取器，使扫描器能覆盖更多常见文档类型。

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `pyproject.toml` | 新增 4 个依赖：`striprtf`、`xlrd`、`olefile`、`extract-msg` |
| `src/fuscan/extractors/rtf.py` | 新建 RTF 提取器，使用 striprtf 转纯文本 |
| `src/fuscan/extractors/email.py` | 新建 EML + MSG 提取器，EML 用标准库 email，MSG 用 extract-msg |
| `src/fuscan/extractors/legacy_office.py` | 新建 XLS/DOC/PPT 提取器，XLS 用 xlrd，DOC/PPT 用 olefile 读 OLE 流 |
| `src/fuscan/extractors/registry.py` | 注册 6 个新提取器 |
| `src/fuscan/extractors/__init__.py` | 导出 6 个新提取器类，更新 docstring |
| `tests/test_extractors.py` | 新增 57 个测试（8 个测试类）覆盖提取逻辑、异常分支、集成扫描 |

## 关键决策与依据

### 依赖选择

| 格式 | 库 | 理由 |
|------|-----|------|
| RTF | `striprtf` | 轻量纯 Python 库，无 C 扩展依赖 |
| XLS | `xlrd>=2.0.1` | Excel 97-2003 读取标准库，2.0+ 仅支持 .xls |
| DOC/PPT | `olefile` | OLE 复合文档读取库，可访问 WordDocument/PowerPoint Document 流 |
| MSG | `extract-msg` | Outlook MSG 格式专用解析库 |

### DOC/PPT 文本提取策略

DOC/PPT 为 OLE 复合文档二进制格式，完整解析需依赖 antiword/catdoc 等外部工具。本项目采用轻量方案：通过 olefile 读取 WordDocument/PowerPoint Document 流，扫描 UTF-16LE 编码的文本片段（ASCII 可打印 + CJK 汉字 + 全角标点），过滤长度 < 2 的噪声片段。

此方案不解析复杂格式（修订、嵌入对象等），但能满足密码/敏感词扫描需求。docstring 中已注明限制。

### EML 正文提取优先级

遍历 `msg.walk()`，优先 `text/plain`，回退 `text/html`（去标签）。跳过 `Content-Disposition: attachment` 的部分。charset 无效时回退 UTF-8 解码。

### 惰性导入

所有第三方库在 `extract_from_bytes` / `extract` 方法内部 `try: import xxx` 延迟导入，ImportError 时抛出 `ExtractorError`。与既有 PDF/DOCX/PPTX 提取器保持一致，避免模块导入时强依赖。

### `_extract_utf16le_text` 辅助函数

扫描字节流，按 2 字节为单位识别 UTF-16LE 编码字符：
- 高字节 0x00 + 低字节 0x20-0x7E：ASCII 可打印
- 高字节 0x4E-0x9F：CJK 统一汉字（U+4E00-U+9FFF）
- 高字节 0x30：全角标点（U+3000-U+30FF）
- 连续非文本字节作为分隔符，长度 < 2 的片段过滤

## 验证结果

- ruff check: All checks passed!
- ruff format --check: 74 files already formatted
- pyrefly: 0 errors
- pytest: 1098 passed, 4 deselected, 96.36% coverage（高于 iter-34 的 96.26%）

### 新提取器覆盖率

| 文件 | 覆盖率 |
|------|--------|
| `rtf.py` | 100% |
| `email.py` | 99% |
| `legacy_office.py` | 96% |

## 遗留事项

- DOC/PPT 仅做简单 UTF-16LE 文本扫描，不解析复杂格式；如需完整提取建议先转 DOCX/PPTX
- `legacy_office.py` 中 `_extract_utf16le_text` 的部分分支（短片段过滤边界）未完全覆盖，属次要分支
- 新增依赖 `extract-msg` 带传递依赖 `oletools`、`rtfde` 等，已通过 `uv sync` 验证安装正常
