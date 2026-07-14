# iter-36 典型文件示例与性能基线

## 迭代目标

增加各支持格式的典型文件示例及其测试，建立性能基线（提取器单格式速度 + 混合格式扫描吞吐量 + slow 回归断言 + 基线文档），为未来性能优化提供可量化锚点。

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `benchmarks/sample_files.py` | 新建：动态生成 12 种格式（7 纯文本 + 5 二进制）的典型文件示例模块 |
| `benchmarks/baseline.md` | 新建：性能基线文档，记录测量环境、各格式提取速度、混合扫描吞吐量、阈值 |
| `benchmarks/bench_scan.py` | 重构：移除重复的 `generate_files`/`_make_content`/`_SECRETS`，改用 `sample_files.generate_files`，支持二进制格式 |
| `tests/test_sample_files.py` | 新建：41 个功能测试，验证各格式示例文件的提取正确性与扫描命中 |
| `tests/test_benchmark.py` | 重构：移除重复的 `_generate_bench_files` 内联实现，改用 `sample_files.generate_files`；新增 `TestExtractorBenchmark` 类（12 个 slow 测试） |
| `src/fuscan/extractors/legacy_office.py` | 修复：ruff SIM114 合并 CJK/全角标点两个相同体的 `elif` 分支；PLR5501 `else: if` → `elif` |

## 关键决策与依据

### 典型文件示例存放方式：动态生成

选择在代码中动态生成各格式文件（`benchmarks/sample_files.py`），而非提交二进制 fixture。理由：
1. 与现有 `test_extractors.py` 风格一致（docx/xlsx/pptx fixture 均动态生成）
2. 仓库零膨胀，无二进制文件入仓
3. 可配置大小，便于性能测试

### 可生成格式范围

| 类别 | 格式 | 生成方式 |
|------|------|---------|
| 纯文本 | txt/json/yaml/xml/csv/md/html | 字符串构造 |
| 二进制 | rtf | RTF 标记字符串 |
| 二进制 | docx | python-docx |
| 二进制 | xlsx | openpyxl |
| 二进制 | pptx | python-pptx |
| 二进制 | eml | email 标准库 |

不可生成格式（pdf/doc/ppt/xls/msg/odt/ods）未纳入性能基线，已有 mock 测试覆盖功能正确性。

### 性能基线四维度

1. **提取器单格式速度**：`TestExtractorBenchmark` 逐格式测量 `extract_from_bytes` 耗时，20 次取平均，断言不超过阈值
2. **混合格式扫描吞吐量**：`TestScanBenchmark` 生成 500 个混合格式文件，测量单线程/多线程/缓存场景的 files/s
3. **基线文档记录**：`benchmarks/baseline.md` 记录机器配置、实测数值、阈值，作为优化前后对比锚点
4. **slow 回归断言**：所有性能测试标记 `@pytest.mark.slow`，CI 默认跳过，手动运行验证

### 阈值设定原则

阈值基于实测均值 × 5-15 倍余量，保守以适应 CI 环境波动：
- 纯文本格式：实测 0.3-2.5ms → 阈值 15ms（6-50x 余量）
- DOCX/XLSX：实测 2.3-7.9ms → 阈值 30ms（4-13x 余量）
- PPTX/RTF：实测 0.8-5.8ms → 阈值 50ms（9-63x 余量）

### bench_scan.py 重构

原 `bench_scan.py` 自带 `generate_files`（仅文本格式），与 `sample_files.py` 的 `generate_files`（含二进制）重复。按 rule-02"三处相似才考虑提取"原则，两处重复已值得合并。重构后 `bench_scan.py` 导入 `sample_files.generate_files`，删除 ~35 行重复代码。

## 验证结果

- ruff check: All checks passed!
- ruff format --check: 78 files already formatted
- pyrefly: 0 errors
- pytest (含 slow): 1151 passed, 96.35% coverage
- pytest (不含 slow): 1135 passed, 16 deselected, 96.35% coverage

### 性能基线摘要

**提取器单格式速度**（4KB 内容，20 次平均）：

| 格式 | 平均耗时 (ms) | 阈值 (ms) |
|------|-------------:|----------:|
| eml  | 0.32 | 15.0 |
| json | 0.60 | 15.0 |
| rtf  | 0.82 | 50.0 |
| txt  | 0.96 | 15.0 |
| xlsx | 2.34 | 30.0 |
| md   | 2.50 | 15.0 |
| pptx | 5.78 | 50.0 |
| docx | 7.94 | 30.0 |

**混合格式扫描**（500 文件，2.5MB）：

| 场景 | 文件/秒 |
|------|--------:|
| 单线程 | 99.2 |
| 4 线程 | 171.6 |
| 4 线程+热缓存 | 164.3 |

## 遗留事项

- 覆盖率 96.35% 较 iter-35 的 96.36% 微降 0.01%，系 `legacy_office.py` 的 ruff SIM114 分支合并导致分支总数变化，非实际覆盖回退
- 不可生成格式（pdf/doc/ppt/xls/msg/odt/ods）未纳入提取器速度基准，需手动提供 fixture 才能测量
- `bench_scan.py` 的 `generate_files` 现在通过 `sample_files` 模块导出，保持了向后兼容的公共 API
