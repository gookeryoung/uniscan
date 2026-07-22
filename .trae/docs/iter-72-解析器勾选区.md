# iter-72：解析器勾选区

## 需求清单

详见 `req-18-解析器勾选区.md`。

## 迭代目标

将文件后缀过滤从"用户手动配置后缀列表"（iter-71 的 `scan_extensions`）改为"按解析器粒度勾选"——每个提取器对应一组文件类型，用户在主界面勾选区取消某些解析器以提高扫描速度。

## 改动文件清单

### 提取器改动

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/extractors/base.py` | Extractor 基类新增 `display_name` 属性（默认返回类名）；ExtractorRegistry 新增 `list_extractors()` 方法 |
| `src/fuscan/extractors/text.py` | TextExtractor 实现 `display_name` → "纯文本" |
| `src/fuscan/extractors/pdf.py` | PdfExtractor 实现 `display_name` → "PDF" |
| `src/fuscan/extractors/office.py` | DocxExtractor → "Word（DOCX）"，PptxExtractor → "PowerPoint（PPTX）" |
| `src/fuscan/extractors/spreadsheet.py` | XlsxExtractor → "Excel（XLSX）"，OdsExtractor → "ODS 表格" |
| `src/fuscan/extractors/odf.py` | OdtExtractor → "ODT 文档" |
| `src/fuscan/extractors/wps.py` | WpsExtractor → "WPS 文档" |
| `src/fuscan/extractors/rtf.py` | RtfExtractor → "RTF" |
| `src/fuscan/extractors/email.py` | EmlExtractor → "邮件（EML）"，MsgExtractor → "Outlook 邮件（MSG）" |
| `src/fuscan/extractors/legacy_office.py` | XlsExtractor → "Excel（XLS）"，DocExtractor → "Word（DOC）"，PptExtractor → "PowerPoint（PPT）" |

### Config 改动

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/config.py` | `scan_extensions: list[str] \| None` → `disabled_extractors: list[str]`（默认空=全部启用） |

### GUI 改动

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/gui/main_window.ui` | 新增"文件类型"分组（file_types_group/hint_label/container/grid） |
| `src/fuscan/gui/main_window_ui.py` | 同步 .ui 生成的控件代码 |
| `src/fuscan/gui/main_window.py` | 新增 `_setup_file_types`/`_on_extractor_toggled`/`_compute_scan_extensions` 方法；导入 QCheckBox 和 default_registry；`_apply_config` 恢复勾选状态；`_start_scan` 用 `_compute_scan_extensions()` 替代 `self._config.scan_extensions` |
| `src/fuscan/gui/settings_dialog.py` | 移除 `_load_config`/`_save_config` 中 scan_extensions 相关逻辑 |
| `src/fuscan/gui/settings_dialog.ui` | 移除"后缀过滤"分组 |

### 测试改动

| 文件 | 改动内容 |
|------|---------|
| `tests/test_extractors.py` | 新增 `test_list_extractors_returns_unique_entries`/`test_list_extractors_entry_format`/`test_display_name_returns_chinese` |
| `tests/test_config.py` | 新增 `test_default_disabled_extractors`/`test_save_and_load_disabled_extractors` |

## 关键决策与依据

### D1：按解析器粒度勾选替代手动后缀配置

**决策**：将 iter-71 的 `Config.scan_extensions`（用户手动输入后缀列表）替换为 `Config.disabled_extractors`（按解析器类名记录禁用状态）。

**依据**：
- 用户需求明确"文件后缀需和扫描解析器挂钩，每个解析器对应配置其适用的文件类型"
- 按解析器粒度勾选比手动输入后缀更直观：用户看到的是"PDF"、"Word（DOCX）"等可读名称，而非 "pdf"、"docx" 等扩展名
- 14 个提取器涵盖所有已注册文件类型，勾选区紧凑（2 列 GridLayout）

### D2：默认全部勾选，存储禁用列表而非启用列表

**决策**：`disabled_extractors` 存储被禁用的提取器类名列表（默认空=全部启用），而非存储启用的列表。

**依据**：
- 默认全部启用是用户预期行为
- 存储禁用列表更节省空间（典型场景用户只取消 1-2 个重型解析器如 PDF/DOCX）
- 向后兼容：旧配置文件无此字段时默认为空列表

### D3：全部勾选时 scan_extensions 为 None

**决策**：`_compute_scan_extensions()` 在全部勾选时返回 None（而非全部扩展名元组）。

**依据**：
- Scanner 的 `scan_extensions=None` 走快速路径（`_should_scan` 直接返回 True），无需构建 frozenset
- 部分取消时才计算启用扩展名并集，传给 Scanner 做全局过滤

### D4：勾选区放在主界面而非设置对话框

**决策**：文件类型勾选区放在主界面扫描路径选择下方，而非设置对话框。

**依据**：
- 用户需求明确"整合到扫描文件夹选择下方"
- 文件类型选择是扫描前的核心配置步骤，放在主界面更便捷
- 设置对话框中移除 iter-71 的"后缀过滤"分组，避免配置分散

## 代码实现情况

### _setup_file_types 方法

从 `default_registry.list_extractors()` 获取提取器列表，为每个创建 QCheckBox，2 列 GridLayout 布局。复选框显示格式：`{display_name} ({ext_hint})`，ext_hint 取前 5 个扩展名。

### _compute_scan_extensions 方法

```python
def _compute_scan_extensions(self) -> tuple[str, ...] | None:
    disabled = self._config.disabled_extractors
    if not disabled:
        return None  # 全部启用，走快速路径
    all_extractors = default_registry.list_extractors()
    enabled_exts: set[str] = set()
    for class_name, _display_name, exts in all_extractors:
        if class_name not in disabled:
            enabled_exts.update(exts)
    return tuple(sorted(enabled_exts))
```

### list_extractors 方法

```python
def list_extractors(self) -> list[tuple[str, str, tuple[str, ...]]]:
    """返回 [(class_name, display_name, supported_extensions), ...]，按 display_name 排序。"""
    seen: dict[int, tuple[str, str, tuple[str, ...]]] = {}
    for _ext, extractor in self._extractors.items():
        obj_id = id(extractor)
        if obj_id not in seen:
            exts = extractor.supported_extensions
            seen[obj_id] = (
                type(extractor).__name__,
                extractor.display_name,
                tuple(sorted(e.lower().lstrip(".") for e in exts)),
            )
    return sorted(seen.values(), key=lambda x: x[1])
```

## 测试验证结果

- ruff check: All checks passed
- ruff format: 93 files already formatted
- pyrefly: 0 errors (465 suppressed, 60 warnings)
- pytest: 1450 passed (+5 新增), coverage 95.88%

## 遗留事项

无。

## 下一轮计划

无。本次迭代已完整交付用户需求。
