# iter-91 速度档次着色与 PDF 加速

## 需求清单

- [x] 为 5 档速度配置对应的标签颜色，从绿（T1）到红（T5）（req-28）
- [x] GUI 勾选树子项按速度档次着色显示
- [x] 评估并引入 `pdf_oxide`（Rust + PyO3）加速 PDF 解析
- [x] 评估 ZIP/压缩包解析的 PyO3 收益

## 迭代目标

为 5 档速度标签配置从绿到红的颜色梯度（T1 绿 → T2 青 → T3 琥珀 → T4 橙 → T5 红），GUI 勾选树子项按档次着色；评估 PDF 与 ZIP 解析能否通过 PyO3（Rust 绑定）显著提速，对 PDF 引入 `pdf_oxide` 作为优先后端。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/extractors/base.py` | 修改 | `SpeedTier` 新增 `color` 属性返回十六进制色值 |
| `src/fuscan/gui/extractor_model.py` | 修改 | `data()` 新增 `ForegroundRole` 分支按 `speed_tier.color` 着色 |
| `src/fuscan/extractors/pdf.py` | 修改 | 优先使用 `pdf_oxide` 后端，回退 `pypdf`；`speed_tier` 动态返回 |
| `pyproject.toml` | 修改 | 新增 `pdf_oxide>=0.3` 依赖 |
| `tests/test_extractors.py` | 修改 | 新增 `TestPdfExtractorOxideBackend` 测试类，补充 pypdf 空页测试 |
| `tests/test_extractor_benchmark.py` | 修改 | 新增 pdf_oxide 后端基准测试，pypdf 回退测试条件跳过 |

## 关键决策与依据

### 1. 颜色梯度方案

采用 GitHub 风格的状态色（与 `scan_stats_label` 内联 HTML 一致），属于 rule-12 例外（程序化着色无法引用 QSS 令牌，在 docstring 注明）：

| 档次 | 色值 | 含义 |
|------|------|------|
| T1 极速 | `#28A745` | 绿色 |
| T2 快速 | `#17A2B8` | 青色 |
| T3 中速 | `#FFC107` | 琥珀 |
| T4 慢速 | `#FD7E14` | 橙色 |
| T5 极慢 | `#DC3545` | 红色 |

通过 `Qt.ForegroundRole` 返回 `QBrush(QColor(color))` 实现子项文字着色，不影响分类节点。

### 2. pdf_oxide 引入决策

**问题**：PDF 解析标记为 T5 极慢（pypdf 纯 Python，12.1ms/文档，持有 GIL 饿死主线程）。

**方案**：引入 `pdf_oxide`（Rust + PyO3，0.8ms/文档，释放 GIL）作为优先后端：

- 15 倍于 pypdf 的提取速度
- Rust 核心执行期间释放 GIL，不饿死主线程（解决 iter-90 GIL 争用问题的根因）
- 100% 通过率（3,830 个测试 PDF）
- MIT/Apache-2.0 许可证

**回退策略**：`import` 失败时回退到 `pypdf`，`speed_tier` 动态返回 T2/T5。

**API 选择**：`to_plain_text_all()` 一次性提取全部页面纯文本，避免逐页 Python 循环开销。

### 3. ZIP/压缩包 PyO3 评估

**结论**：不引入额外 Rust 依赖。原因：

1. `zipfile.ZipFile` 底层调用 `zlib`（C 库），解压阶段已释放 GIL，非纯 Python
2. 压缩包扫描的真正瓶颈是逐条目调用提取器链（条目数决定总耗时），非解压本身
3. 压缩包内 PDF 条目已由 `pdf_oxide` 加速，其他条目走既有提取器
4. 引入 Rust ZIP 库（如 `zip-rs`）需重写 `ArchiveReader` 接口，收益不抵成本

压缩包分类维持 T5 极慢（条目数决定总耗时），通过 iter-90 的 `max_workers=3` + `max_file_size=50MB` 已缓解 GIL 争用。

### 4. 测试双后端覆盖

- `TestPdfExtractor`：`monkeypatch` 强制 `_PDF_OXIDE_AVAILABLE=False`，验证 pypdf 回退路径
- `TestPdfExtractorOxideBackend`：`pdf_oxide` 已安装时验证真实 PDF 提取与 `speed_tier` 动态返回
- 基准测试：`pdf_oxide` 可用时跑 T2 测试，不可用时跑 T5 测试（条件跳过）

### 5. 覆盖率修复

- `ImportError` 分支标记 `# pragma: no cover`（环境依赖，pdf_oxide 已安装时不可达）
- 新增 `test_oxide_invalid_bytes_raises` / `test_oxide_empty_bytes_raises` / `test_oxide_extract_missing_file_raises` / `test_oxide_returns_empty_for_empty_pdf` 覆盖 pdf_oxide 错误路径
- 新增 `test_empty_page_text_skipped` 覆盖 pypdf 空页跳过分支

## 代码实现情况

### SpeedTier.color（base.py）

```python
@property
def color(self) -> str:
    mapping = {
        SpeedTier.VERY_FAST: "#28A745",
        SpeedTier.FAST: "#17A2B8",
        SpeedTier.MEDIUM: "#FFC107",
        SpeedTier.SLOW: "#FD7E14",
        SpeedTier.VERY_SLOW: "#DC3545",
    }
    return mapping[self]
```

### GUI 着色（extractor_model.py）

```python
if role == Qt.ForegroundRole:
    return QBrush(QColor(item.speed_tier.color))
```

### pdf_oxide 后端（pdf.py）

```python
try:
    from pdf_oxide import PdfDocument as _PdfOxideDocument
    _PDF_OXIDE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PDF_OXIDE_AVAILABLE = False
    _PdfOxideDocument = None

@property
def speed_tier(self) -> SpeedTier:
    return SpeedTier.FAST if _PDF_OXIDE_AVAILABLE else SpeedTier.VERY_SLOW

def extract_from_bytes(self, data: bytes) -> str:
    if _PDF_OXIDE_AVAILABLE:
        return self._extract_with_pdf_oxide(data)
    return self._extract_with_pypdf(data)
```

## 测试验证结果

- ruff check：All checks passed
- ruff format：105 files already formatted
- pyrefly：0 errors（562 suppressed, 67 warnings）
- pytest：1599 passed, 43 deselected, 1 warning
- 覆盖率：95.07%（branch）

## 遗留事项

- 暗色主题支持（`color` 属性为固定色值，暗色主题下可能对比度不足）
- `regex_tester.py` 中 HTML 着色仍使用内联色值（rule-12 例外，已在 docstring 注明）

## 下一轮计划

无明确下一轮计划。当前实现已覆盖用户全部需求（颜色梯度 + PDF 加速 + ZIP 评估）。
