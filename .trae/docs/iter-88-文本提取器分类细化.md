# iter-88 文本提取器分类细化

## 需求清单

- [x] 将"纯文本"分类（原 TextExtractor 含 57 个扩展名）细分为 5 个子分类（req-25）

## 迭代目标

将原 `TextExtractor`（57 个扩展名）拆分为 5 个子提取器，让 GUI 勾选树按文件用途展示独立分类，方便用户按"纯文本 / 源代码 / 配置文件 / 标记与数据 / 样式表"分别勾选。

## 关键决策与依据

1. **保留 TextExtractor 为基类**：5 个子提取器共享相同的提取逻辑（编码检测、BOM、大文件流式读取），仅扩展名子集与 display_name 不同。继承 `TextExtractor` 后只 override `supported_extensions` 与 `display_name`，避免重复实现。
2. **保留 TEXT_EXTENSIONS 向后兼容**：部分代码（如 Config.scan_extensions 默认值、ArchiveScanner 内部条目过滤）仍引用 `TEXT_EXTENSIONS` 全集，保留为 5 组并集避免破坏。
3. **注册顺序**：5 个子提取器在 `register_all()` 中先于其他格式注册，保持注册表稳定的扩展名分发优先级。
4. **_EXTRACTOR_CATEGORIES 与 _CATEGORY_ORDER 同步扩展**：新增 5 个分类键，`_CATEGORY_ORDER` 从 5 项扩展到 10 项（文档/表格/演示/邮件/纯文本/源代码/配置文件/标记与数据/样式表/压缩包）。空分类仍初始化显示，让用户看到全部分类结构。
5. **测试 stub 增加 DocxExtractor**：原 `_build_registry()` 只注册 PdfExtractor/PlainTextExtractor/XlsxExtractor 3 个 stub，导致文档分类只有 1 个子项，无法验证 PartiallyChecked 状态。新增 DocxExtractor stub（display_name="Word（DOCX）"，display_name 排序在 PDF 之后）让文档有 2 个子项以覆盖父子勾选联动场景。

## 改动文件清单

修改（源码）：
- `src/fuscan/extractors/text.py`：拆分 `TEXT_EXTENSIONS` 为 5 个分组常量，新增 `PlainTextExtractor`/`SourceCodeExtractor`/`ConfigFileExtractor`/`MarkupDataExtractor`/`StylesheetExtractor` 5 个子类
- `src/fuscan/extractors/registry.py`：`register_all()` 注册 5 个子提取器替代原 `TextExtractor`
- `src/fuscan/extractors/__init__.py`：导出 5 个子提取器类与 5 个扩展名分组常量
- `src/fuscan/gui/extractor_model.py`：`_EXTRACTOR_CATEGORIES` 新增 5 个子提取器到对应分类键，`_CATEGORY_ORDER` 新增 5 个分类

修改（测试）：
- `tests/test_extractor_model.py`：
  - 新增 `DocxExtractor` stub 让文档分类有 2 个子项以验证父子勾选联动
  - 更新 `_build_registry()` 注册 4 个 stub（PDF + Word + 纯文本 + Excel）
  - 更新所有受影响的断言：分类数 5→10、archive 索引 4→9、total_count 4→5、checked_count 与 enabled_extensions 列表加 docx
  - 修复 `test_enabled_extensions_includes_archive`：取消的是压缩包分类（索引 9）而非纯文本分类（索引 4）

修改（文档）：
- `.trae/req/req-25-文本分类细化.md`：新建需求清单
- `.trae/docs/iter-88-文本提取器分类细化.md`：新建迭代记录

## 代码实现情况

### text.py 子提取器结构

```python
class TextExtractor(Extractor):
    """基类：保留 extract/extract_from_bytes/_extract_large/_decode 全部提取逻辑。
    supported_extensions 返回 TEXT_EXTENSIONS 全集，display_name 返回 "纯文本"。
    不再注册到 default_registry，仅作为基类被 5 个子类继承。
    """

class PlainTextExtractor(TextExtractor):
    supported_extensions = PLAIN_TEXT_EXTENSIONS  # txt, log
    display_name = "纯文本"

class SourceCodeExtractor(TextExtractor):
    supported_extensions = SOURCE_CODE_EXTENSIONS  # py/js/ts/java/c/...29 项
    display_name = "源代码"

class ConfigFileExtractor(TextExtractor):
    supported_extensions = CONFIG_FILE_EXTENSIONS  # ini/yaml/toml/env/...10 项
    display_name = "配置文件"

class MarkupDataExtractor(TextExtractor):
    supported_extensions = MARKUP_DATA_EXTENSIONS  # md/json/xml/html/csv/...11 项
    display_name = "标记与数据"

class StylesheetExtractor(TextExtractor):
    supported_extensions = STYLESHEET_EXTENSIONS  # css/scss/sass/less
    display_name = "样式表"
```

### 扩展名分组

| 分组 | 常量 | 扩展名 |
|------|------|--------|
| 纯文本 | `PLAIN_TEXT_EXTENSIONS` | txt, log |
| 源代码 | `SOURCE_CODE_EXTENSIONS` | py, js, ts, jsx, tsx, java, c, cpp, h, hpp, cs, go, rs, rb, php, kt, swift, scala, lua, pl, r, dart, vue, svelte, sh, bash, bat, cmd, ps1 |
| 配置文件 | `CONFIG_FILE_EXTENSIONS` | conf, ini, cfg, properties, yaml, yml, toml, env, gradle, gitignore, dockerignore |
| 标记与数据 | `MARKUP_DATA_EXTENSIONS` | md, rst, html, htm, tex, bib, json, xml, csv, tsv, sql |
| 样式表 | `STYLESHEET_EXTENSIONS` | css, scss, sass, less |

### GUI 分类结构（10 项）

```
文档（6 项）→ 表格（3 项）→ 演示（2 项）→ 邮件（2 项）
→ 纯文本（1 项）→ 源代码（1 项）→ 配置文件（1 项）→ 标记与数据（1 项）→ 样式表（1 项）
→ 压缩包（1 虚拟项）
```

## 整合优化情况

- `TEXT_EXTENSIONS` 保留为 5 组并集，向后兼容现有引用（Config 默认值、ArchiveScanner 等）
- `TextExtractor` 保留为基类，提供 `extract`/`extract_from_bytes`/`_extract_large`/`_decode` 全部提取逻辑，子类仅 override `supported_extensions` 与 `display_name`
- `__all__` 同步导出 5 个扩展名分组常量与 5 个子提取器类，方便外部引用
- 测试 stub 引入 DocxExtractor 让文档分类有 2 项，保持 PartiallyChecked/批量勾选/父子联动等关键测试覆盖

## 测试验证结果

- `uv run ruff check src tests`：通过
- `uv run ruff format --check src tests`：通过（104 files already formatted）
- `uv run pyrefly check`：0 errors（555 suppressed, 62 warnings not shown）
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：1575 passed，覆盖率 95.11%

### test_extractor_model.py 测试结果（53 项全部通过）

- 构造与基础：21 项（含 `test_category_count_includes_all_order_categories` 验证 10 个分类）
- flags/setData：7 项
- 父子勾选联动：7 项（含 `test_partial_check_shows_partially_checked` 验证 PartiallyChecked）
- disabled_extractors：6 项
- enabled_extensions：7 项（含 `test_enabled_extensions_includes_archive` 验证白名单统一制）
- checked_count/total_count：4 项

## 遗留事项

无。所有验收标准达成。

## 下一轮计划

无（迭代收尾）。
