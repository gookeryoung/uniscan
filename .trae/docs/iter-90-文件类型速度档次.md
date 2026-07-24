# iter-90 文件类型速度档次

## 需求清单

- [x] 为每类文件类型设计解析速度基准测试（req-27）
- [x] 将解析速度划分 5 档并在 GUI 勾选树展示

## 迭代目标

在 `Extractor` 抽象基类新增 `SpeedTier` 枚举与 `speed_tier` 抽象属性，按实现复杂度将所有提取器划分到 5 个速度档次；GUI 勾选树子项末尾附加档次标签，tooltip 展示扩展名+档次+解析方式；新增 `tests/test_extractor_benchmark.py` 验证档次声明与实测性能一致。

## 关键决策与依据

1. **档次依据实现复杂度而非实测耗时**：实测受文件大小/内容/磁盘缓存影响波动大，按实现复杂度（纯字节解码 / 标准库 / XML / 单元格遍历 / 页面布局分析）划分档次更稳定可复现。
2. **抽象属性强制子类声明**：`speed_tier` 为 `@abstractmethod`，新增提取器必须显式声明档次，避免遗漏。`TestSpeedTierCompleteness.test_all_extractors_have_valid_speed_tier` 在非 slow 测试中验证所有注册提取器都返回有效 `SpeedTier`。
3. **`list_extractors()` 元组扩展为 4 元**：原 `(class_name, display_name, extensions)` 扩展为 `(class_name, display_name, extensions, speed_tier)`，GUI 直接消费无需二次查表。
4. **压缩包分类为 T5 极慢**：压缩包非提取器实例（虚拟 `ExtractorItem`），但在 GUI 模型中硬编码 `SpeedTier.VERY_SLOW`，因解压 + 内部条目循环提取的总耗时随条目数线性增长，与 PDF 同档。
5. **基准测试标记 `@pytest.mark.slow`**：CI 默认 `-m "not slow"` 跳过耗时测试，避免拖慢流水线。阈值宽松（5-10 倍余量）仅验证档次声明合理，不作为性能回归门禁。
6. **样本动态生成**：所有样本用对应库（python-docx/openpyxl/python-pptx/odfpy/pypdf/reportlab）程序化生成，避免二进制 fixture 入仓，保持测试可维护。
7. **`_TIER_TIME_LIMITS` 阈值设定**：T1=500ms / T2=1s / T3=2s / T4=5s / T5=10s，为典型 100KB-1MB 样本的宽松上限，CI 环境差异不会触发 flaky。
8. **MSG 归 T3 中速**：MSG 由 `extract_msg` 库解析，与 OOXML 复杂度相近，归 MEDIUM 档。原 EML（标准库 email.parser）保持 T2。

## 改动文件清单

修改（源码）：
- `src/fuscan/extractors/base.py`：新增 `SpeedTier` 枚举（含 `label`/`description` 属性），`Extractor` 新增 `speed_tier` 抽象属性，`list_extractors()` 返回类型扩展为 4 元
- `src/fuscan/extractors/text.py`：5 个子提取器 `speed_tier = SpeedTier.VERY_FAST`
- `src/fuscan/extractors/email.py`：`EmlExtractor.speed_tier = FAST`，`MsgExtractor.speed_tier = MEDIUM`
- `src/fuscan/extractors/office.py`：`DocxExtractor.speed_tier = MEDIUM`，`PptxExtractor.speed_tier = SLOW`
- `src/fuscan/extractors/spreadsheet.py`：`XlsxExtractor.speed_tier = SLOW`，`OdsExtractor.speed_tier = SLOW`
- `src/fuscan/extractors/odf.py`：`OdtExtractor.speed_tier = MEDIUM`
- `src/fuscan/extractors/rtf.py`：`RtfExtractor.speed_tier = MEDIUM`
- `src/fuscan/extractors/wps.py`：`WpsExtractor.speed_tier = MEDIUM`（委托到 OOXML 子类型）
- `src/fuscan/extractors/legacy_office.py`：`DocExtractor/PptExtractor/XlsExtractor.speed_tier = SLOW`
- `src/fuscan/extractors/pdf.py`：`PdfExtractor.speed_tier = VERY_SLOW`
- `src/fuscan/extractors/__init__.py`：导出 `SpeedTier`
- `src/fuscan/gui/extractor_model.py`：
  - `ExtractorItem` 新增 `speed_tier: SpeedTier` 字段
  - `tree_display_text` 末尾附加 ` · {档次标签}`
  - `tooltip_text` 三行展示扩展名+档次+解析方式
  - 模型构造时从 `list_extractors()` 取 `speed_tier` 元组位
  - 压缩包虚拟项硬编码 `SpeedTier.VERY_SLOW`

修改（测试）：
- `tests/test_extractors.py`：`list_extractors` 测试更新为 4 元组断言
- `tests/test_extractor_model.py`：
  - `_StubExtractor` 实现 `speed_tier` 抽象属性返回 `VERY_FAST`
  - `test_child_display_text_format`/`test_archive_display_text`/`test_tooltip_lists_all_extensions` 等断言末尾的档次标签
- `tests/test_cli.py`/`tests/test_export.py`：CSV 头断言不受影响，仅校验字段顺序

新增（测试）：
- `tests/test_extractor_benchmark.py`：25 个 slow 基准测试 + 3 个完整性测试
  - `TestTier1VeryFast`：纯文本/源代码提取器档次声明 + 文本提取耗时
  - `TestTier2Fast`：EML 提取器档次声明 + 提取耗时
  - `TestTier3Medium`：DOCX/ODT/RTF/WPS/MSG 档次声明 + 提取耗时
  - `TestTier4Slow`：XLSX/ODS/PPTX/XLS/DOC/PPT 档次声明 + 提取耗时
  - `TestTier5VerySlow`：PDF 档次声明 + 提取耗时
  - `TestSpeedTierCompleteness`：所有注册提取器档次有效性 + 中文标签/说明

修改（文档）：
- `.trae/req/req-27-文件类型速度档次.md`：新建需求清单
- `.trae/docs/iter-90-文件类型速度档次.md`：新建迭代记录

## 代码实现情况

### SpeedTier 枚举（base.py）

```python
class SpeedTier(enum.Enum):
    VERY_FAST = 1  # T1 极速：纯字节解码，< 10ms/MB
    FAST = 2      # T2 快速：标准库解析，10-50ms/MB
    MEDIUM = 3    # T3 中速：XML 解析，50-200ms/MB
    SLOW = 4      # T4 慢速：单元格遍历，200-1000ms/MB
    VERY_SLOW = 5 # T5 极慢：页面布局/解压，> 1000ms/MB

    @property
    def label(self) -> str: ...        # "T1 极速" 等短标签
    @property
    def description(self) -> str: ...  # "纯字节解码，无第三方库（< 10ms/MB）"
```

### Extractor 抽象属性

```python
class Extractor(ABC):
    @property
    @abstractmethod
    def speed_tier(self) -> SpeedTier:
        """子类按实现复杂度返回对应 SpeedTier。"""
```

### GUI 子项展示格式

```
原: PDF（pdf）
新: PDF（pdf） · T5 极慢
```

Tooltip 三行：
```
扩展名: pdf
速度档次: T5 极慢
解析方式: 复杂布局分析或解压+条目提取（> 1000ms/MB）
```

### 档次分配表

| 提取器 | 档次 | 依据 |
|--------|------|------|
| PlainTextExtractor | T1 | 纯字节解码 |
| SourceCodeExtractor | T1 | 同上 |
| ConfigFileExtractor | T1 | 同上 |
| MarkupDataExtractor | T1 | 同上 |
| StylesheetExtractor | T1 | 同上 |
| EmlExtractor | T2 | email.parser 标准库 |
| MsgExtractor | T3 | extract_msg 库解析 OLE 结构 |
| DocxExtractor | T3 | 单次 ZIP + XML 树遍历 |
| OdtExtractor | T3 | odfpy 单次 XML |
| RtfExtractor | T3 | 正则 + 控制字解析 |
| WpsExtractor | T3 | 委托到 DOCX/XLSX/PPTX |
| XlsxExtractor | T4 | openpyxl 单元格逐行遍历 |
| OdsExtractor | T4 | odfpy 单元格遍历 |
| PptxExtractor | T4 | python-pptx 形状/文本框遍历 |
| DocExtractor | T4 | antiword 字节扫描 |
| PptExtractor | T4 | olefile 二进制解析 |
| XlsExtractor | T4 | xlrd 二进制读取 |
| PdfExtractor | T5 | pdfplumber 页面布局分析 |
| 压缩包（虚拟项） | T5 | 解压 + 内部条目循环提取 |

## 整合优化情况

- `list_extractors()` 元组从 3 元扩展到 4 元，向后兼容性通过更新所有调用点（GUI 模型 + 测试）一次性收口，无遗留旧调用
- 基准测试样本生成器复用 `tests/test_extractors.py` 的 fixture 工厂模式（动态生成避免二进制入仓），但样本量级更大（100KB-1MB）以稳定测量
- `TestSpeedTierCompleteness` 在非 slow 测试中验证所有注册提取器的档次声明完整性，避免新增提取器时遗漏 `speed_tier` 实现

## 测试验证结果

- `uv run ruff check src tests`：通过
- `uv run ruff format --check src tests`：通过（105 files already formatted）
- `uv run pyrefly check`：0 errors（559 suppressed, 64 warnings not shown）
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：1588 passed，覆盖率 95.15%
- `uv run pytest tests/test_extractor_benchmark.py -m slow -v --no-cov`：25 passed, 3 deselected

### 基准测试分布（25 项 slow 测试）

- T1 极速：3 项（2 档次声明 + 1 耗时）
- T2 快速：2 项
- T3 中速：10 项（5 档次声明 + 5 耗时）
- T4 慢速：6 项（XLS/DOC/PPT 因二进制难生成仅验证档次声明）
- T5 极慢：2 项
- 完整性：3 项（非 slow，含所有提取器档次有效性校验）

### ODS 样本生成器修复

首轮测试发现 `TableRow(stylename="", cells=cells)` 在 odfpy 1.4.x 抛 `AttributeError: Attribute cells is not allowed`，原因是 `TableRow` 不支持 `cells=` 关键字参数，须改用 `row.addElement(cell)` 逐个添加。修复后 ODS 基准测试通过。

## 遗留事项

无。所有验收标准达成。

## 下一轮计划

无（迭代收尾）。
