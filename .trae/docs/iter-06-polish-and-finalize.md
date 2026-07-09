# iter-06 测试补齐与项目收尾

迭代日期：2026-07-09
阶段：P5（打磨与收尾）

## 本轮目标

补齐 CLI tray 子命令测试与提取器测试覆盖率，清理归档旧迭代记录，
完成项目最终验证。

## 验收标准（P5 范围）

- [x] CLI tray 子命令测试覆盖（3 例：缺规则文件/PySide2 缺失/正常调用）
- [x] 提取器覆盖率提升（pdf 45%→93%、odf 49%→95%、spreadsheet 64%→92%、wps 57%→89%）
- [x] TextExtractor 回退路径测试（charset-normalizer 缺失回退、GBK 解码）
- [x] iter-01～05 归档至 skills/pyfilescan-development.md
- [x] 全套门禁通过：ruff + pytest + coverage
- [x] 总覆盖率 87.48%（≥80% 门槛）

## 改动文件清单

### 测试（tests/）
- `test_cli.py`：新增 TestTrayCommand（3 例）+ TestMainModuleImport（1 例）；
  添加 QT_QPA_PLATFORM=offscreen 设置
- `test_extractors.py`：新增 17 例测试
  - TestTextExtractor：charset_normalizer 回退、GBK 解码
  - TestXlsxExtractor：max_cols 截断、openpyxl 导入失败
  - TestWpsExtractor：dps 演示提取、docx 表格、三种格式解析失败、_is_ooxml 文件不存在
  - TestPdfExtractor：mock PdfReader 页面提取、加密 PDF、页面异常跳过、pypdf 导入失败
  - TestOdfExtractors：真实 ODT/ODS 文件提取、ODS 解析失败、odfpy 导入失败

### 文档
- `.trae/skills/pyfilescan-development.md`：归档 iter-01～05 的可复用模式、
  踩坑总结、设计决策
- 删除 iter-01～05 迭代记录（已归档至 skills/）

## 关键决策

### 1. PDF 测试用 mock 而非真实 PDF
pypdf 不支持创建带文本的 PDF（只能写不能提取）。用 mock PdfReader
模拟 pages 列表和 extract_text()，覆盖 _extract_pages 的正常/异常/加密路径。

### 2. ODT/ODS 用 odfpy 创建真实文件
odfpy 支持 OpenDocumentText/OpenDocumentSpreadsheet 创建真实 ODT/ODS。
注意 H 元素需要 outlinelevel 属性。

### 3. Windows chmod 限制的处理
Windows 上 chmod(0o000) 不阻止文件所有者读取。_is_ooxml 的 OSError
分支用不存在的文件路径测试，而非权限限制。

### 4. GBK 短文本误判
charset-normalizer 对短 GBK 文本可能误判为韩文。测试中使用 20+ 字符的
长 GBK 文本确保正确检测。

## 验证结果

- pytest：304 passed, 1 skipped（RAR 需 unrar）
- coverage：87.48%（≥80% 门槛）
- ruff：All checks passed
- 提取器覆盖率：pdf 93% / odf 95% / spreadsheet 92% / wps 89% / text 83%
- CLI 覆盖率：91%

## 项目总结

pyfilescan 通用文件扫描器已完成全部 P0-P5 阶段交付：

- **P0**：规则引擎（YAML 配置 + AND/OR/NOT 逻辑）+ CLI 骨架
- **P1**：多格式提取器（PDF/DOCX/PPTX/XLSX/ODT/ODS/WPS/纯文本）
- **P2**：压缩文件扫描（ZIP/RAR 内条目规则匹配）
- **P3**：PySide2 GUI（主窗口 + 后台扫描 + 结果展示 + 导出）
- **P4**：托盘驻守（watchdog 监控 + 增量扫描 + 系统托盘）
- **P5**：测试补齐与收尾（覆盖率 82%→87%）

最终交付：304 个测试通过，覆盖率 87.48%，ruff 全部通过。
