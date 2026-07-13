# iter-34 提取器回退函数提取

## 迭代目标

继续推进代码清理与精简，消除 3 处"提取器失败回退到纯文本"重复 try/except 模式，提取为公共函数。

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `src/fuscan/extractors/base.py` | 新增 `extract_content_with_fallback(path) -> str` 函数 |
| `src/fuscan/extractors/__init__.py` | 导出新函数 |
| `src/fuscan/scanner/scanner.py` | `default_extract_content` 改为调用新函数，删除 7 行 try/except |
| `src/fuscan/gui/detail_dialog.py` | `_populate_preview` 改用新函数，外层保留 `except OSError` |
| `src/fuscan/gui/main_window.py` | `_populate_detail_preview` 改用新函数，外层保留 `except OSError` |
| `tests/test_extractors.py` | 新增 3 个测试覆盖回退逻辑 |
| `tests/test_scanner.py` | 更新 monkeypatch 目标路径 |

## 关键决策与依据

### 提取依据

rule-02 规定"三处相似才考虑提取"。以下 3 处代码模式完全一致：

1. `scanner.py:default_extract_content` — `extract_content(path)` 失败 → `path.read_text`
2. `detail_dialog.py:_populate_preview` — 同上 + UI 错误提示
3. `main_window.py:_populate_detail_preview` — 同上 + UI 错误提示

提取为 `extract_content_with_fallback(path) -> str` 后，GUI 两处仅需在外层捕获 `OSError` 处理纯文本读取失败的 UI 提示。

### `except Exception` 保留

`extract_content_with_fallback` 内部使用 `except Exception` 捕获提取器异常。这是"提取器失败回退"的语义，需要捕获所有可能的异常（ExtractorError、OSError、XMLSyntaxError、第三方库异常等）。rule-11 允许"包装重抛"和"第三方回调异常仅记录"的例外场景。

### 不改造 `archive/scanner.py`

`archive/scanner.py:_extract_via_temp` 的回退逻辑不同：失败时调用 `_decode_bytes(data)`（从原始内存字节解码），而非 `read_text`（从临时文件读取）。且需要 `finally` 清理临时文件。不适合用 `extract_content_with_fallback`。

## 验证结果

- ruff check: All checks passed!
- ruff format --check: 71 files already formatted
- pyrefly: 0 errors
- pytest: 1035 passed, 4 deselected, 96.26% coverage

## 遗留事项

- 约 30 处 `except Exception` 保留现状（提取器解析包装、扫描继续、资源关闭等合理场景）
- `archive/scanner.py:_extract_via_temp` 的回退模式独立，未提取
