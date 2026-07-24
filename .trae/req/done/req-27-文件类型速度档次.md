# req-27 文件类型速度档次

## 需求

- [x] 为每类文件类型设计解析速度基准测试，验证 `speed_tier` 声明与实测性能一致
- [x] 将提取器解析速度划分为 5 档（T1 极速 / T2 快速 / T3 中速 / T4 慢速 / T5 极慢）
- [x] 在 GUI 勾选树子项末尾标注速度档次短标签，便于用户按需勾选
- [x] 子项 tooltip 展示扩展名 + 速度档次 + 解析方式说明

## 档次划分依据

按实现复杂度与典型 1MB 文件解析耗时划分：

| 档次 | 标签 | 耗时 | 实现特征 | 对应提取器 |
|------|------|------|---------|-----------|
| `VERY_FAST` | T1 极速 | < 10ms/MB | 纯字节解码，无第三方库 | 纯文本/源代码/配置文件/标记与数据/样式表 |
| `FAST` | T2 快速 | 10-50ms/MB | 标准库解析 | EML 邮件 |
| `MEDIUM` | T3 中速 | 50-200ms/MB | 单次 XML 解析 + 树遍历 | DOCX/ODT/RTF/WPS/MSG |
| `SLOW` | T4 慢速 | 200-1000ms/MB | 单元格遍历或字节级扫描 | XLSX/ODS/XLS/PPTX/DOC/PPT |
| `VERY_SLOW` | T5 极慢 | > 1000ms/MB | 复杂页面布局分析或解压+条目提取 | PDF / 压缩包 |

## 验收标准

- `Extractor` 抽象基类新增 `speed_tier` 抽象属性，所有子类必须实现
- `ExtractorRegistry.list_extractors()` 返回元组扩展为 4 元（含 `SpeedTier`）
- GUI 勾选树子项 DisplayRole 末尾附加 ` · {档次标签}`（如 `Word（docx） · T3 中速`）
- 子项 ToolTipRole 三行展示：扩展名 / 速度档次 / 解析方式
- 基准测试 `tests/test_extractor_benchmark.py` 标记 `@pytest.mark.slow`，CI 默认跳过
- 全套门禁通过：ruff/format/pyrefly/pytest（覆盖率不低于 95%）
