# iter-41 数据层增强

## 需求清单

- [x] 对于规则为 AND、OR 的情况，把匹配命中的每个内容都标记出来，不仅仅是标记单一匹配规则的内容
- [x] 为每个 match 项也增加一个可选的描述字段，方便用户理解匹配规则的含义，在界面和导出结果时也包含描述字段

## 迭代目标

为需求 3（AND/OR 标记所有命中内容）与需求 4（match 项描述字段）建立数据层支撑：
扩展 MatchSpec/MatchResult/RuleHit 数据结构、改造匹配器收集所有子匹配器命中文本、
递增缓存兼容版本号以 JSON 序列化新字段、同步更新 GUI 表格与导出层。

## 改动文件清单

### `src/fuscan/rules/model.py`

为所有 MatchSpec 类型增加 `description: str = ""` 字段：

- `LeafMatch`：叶子匹配条件描述
- `AndMatch` / `OrMatch` / `NotMatch`：组合规则描述

所有字段均为 frozen dataclass 默认值，向后兼容旧规则文件。

### `src/fuscan/rules/parser.py`

`_parse_leaf` 与 `_parse_composite` 增加 description 解析：

- 叶子：`description = str(data.get("description", ""))`
- 组合：同上，在构造 AndMatch/OrMatch/NotMatch 时传入
- `parse_rule` 中的 Rule.description 保持不变（规则级描述，与 match 级描述分离）

### `src/fuscan/scanner/result.py`

`MatchResult` 与 `RuleHit` 增加两个字段：

- `match_texts: tuple[str, ...] = ()`：所有命中文本（去重保序），供 GUI 高亮所有命中关键词
- `match_description: str = ""`：match 级描述，来自 spec.description

导出方法同步更新：

- `to_csv`：列头改为 `path,size,severity,rule,description,match_count,detail`（在 rule 与 match_count 间插入 description 列）
- `to_text`：描述非空时在规则名后附加 ` - {description}`，空则不加后缀

### `src/fuscan/scanner/matchers.py`

核心重构：AndMatcher/OrMatcher/NotMatcherImpl 改为持有 spec（而非 children/child），
以读取 spec.description 并收集所有子匹配器命中文本。

- `LeafMatcher.matches()`：命中时填入 `match_texts=(match_text,)` 与 `match_description=self.spec.description`；未命中也填充 description
- `AndMatcher`：持有 `spec: AndMatch`，`__init__` 中从 `spec.children` 构造子匹配器；
  `matches()` 收集所有子结果的 match_texts，去重保序后填入；**target 设为空字符串**（组合规则无单一目标）
- `OrMatcher`：持有 `spec: OrMatch`，遍历所有子匹配器收集命中（不再遇到首个命中就返回）；
  match_count 为所有命中子匹配器之和；target 透传首个命中子匹配器的 target
- `NotMatcherImpl`：持有 `spec: NotMatch`，填充 description
- 新增 `_dedup_preserve_order(items: list[str]) -> list[str]`：剔除空字符串与重复项，保留首次出现顺序
- `build_matcher` 改为传 spec：`AndMatcher(spec)` / `OrMatcher(spec)` / `NotMatcherImpl(spec)`

### `src/fuscan/scanner/scanner.py`

4 处 RuleHit 构造均填入 `match_texts` 和 `match_description`：

1. `_scan_entry_uncached`（未缓存路径，行 636-648）
2. `_scan_entry_cached` 缓存命中路径（行 759-772）
3. `_scan_entry_cached` 未缓存命中路径（行 783-792）
4. `_build_hits_from_cache` 静态方法（行 855-873）

### `src/fuscan/cache/schema.py`

- `CURRENT_VERSION: int = 4`（从 3 递增）
- `CACHE_COMPAT_VERSION: int = 4`（从 3 递增）
  - v4 为 scan_results 新增 match_texts/match_description 字段
  - 旧缓存（v3）的 match_text 仅含首条命中，新 match_texts 含全部命中，语义变更需 purge
- `scan_results` 表增加 `match_texts TEXT` 和 `match_description TEXT` 列
- migrate 函数注释增加 v4→v5 路径说明

### `src/fuscan/cache/store.py`

- 新增 `import json`
- `get_cached_hits`：SELECT 增加 `match_texts, match_description`；
  `match_texts` 用 `json.loads` 反序列化（容错处理 NULL/空/非数组/解析失败均回退到空元组）
- `put_result`：INSERT/UPDATE 增加两字段，
  `texts_json = json.dumps(list(hit.match_texts), ensure_ascii=False) if hit.match_texts else None`
- `batch_put_results`：executemany 同步增加两字段

### `src/fuscan/gui/preview_utils.py`

`extract_keywords` 与 `build_keyword_to_rule_map` 均改为三级回退：

1. 优先遍历 `hit.match_texts`（含组合规则全部命中文本）
2. `match_texts` 为空时回退到 `(hit.match_text,)`（兼容旧缓存）
3. 两者均空时回退到从 `detail` 解析单引号包裹的内容

### `src/fuscan/gui/main_window_ui.py` / `detail_dialog_ui.py`

- `detail_hits_table` 列数从 5 改为 6，新增第 6 列 header "描述"
- `hits_table`（对话框）同上

### `src/fuscan/gui/main_window.py` / `detail_dialog.py`

- `_populate_detail_hits_table` / `_populate_hits_table` 增加第 5 列填充 match_description（带 ToolTip）

## 测试文件

### `tests/test_matchers.py`

新增两个测试类（共 20 个测试）：

- `TestMatchTexts`（10 个）：覆盖叶子/AND/OR/NOT 的 match_texts 收集与去重保序
- `TestMatchDescription`（10 个）：覆盖叶子/AND/OR/NOT 的 match_description 填充（命中与未命中两种情况）

同时更新 19 处现有测试：AndMatcher/OrMatcher/NotMatcherImpl 构造接口变更
（旧：接受 children tuple；新：接受 spec），
改为 `build_matcher(AndMatch(children=...))` 等公共工厂接口。
`test_or_matcher_uses_first_matched_count` 重命名为 `test_or_matcher_sums_matched_child_counts`
（语义变更：从"首个命中分支"改为"所有命中分支之和"）。

### `tests/test_rules_parser.py`

新增 7 个 description 解析测试：

- `test_parse_leaf_description` / `test_parse_leaf_description_default_empty`
- `test_parse_and_description` / `test_parse_or_description` / `test_parse_not_description`
- `test_parse_composite_description_default_empty`

### `tests/test_cache.py`

新增 4 个 match_texts/match_description 序列化测试：

- `test_put_and_get_match_texts_and_description`：多文本+描述的序列化与反序列化
- `test_put_and_get_empty_match_texts`：空元组的序列化（兼容旧缓存）
- `test_put_and_get_unicode_match_texts`：中文 match_texts（JSON ensure_ascii=False）
- `test_batch_put_results_match_texts_and_description`：批量写入接口

### `tests/test_scanner.py`

新增 4 个导出层测试：

- `test_to_csv_includes_description`：CSV description 列填充
- `test_to_csv_description_empty_when_not_set`：未设置时 description 列为空
- `test_to_text_includes_description`：text 在规则名后附加 " - 描述"
- `test_to_text_description_empty_omits_suffix`：空描述不加后缀

同时更新 2 个现有测试的期望 CSV header（新增 description 列）。

### `tests/test_gui.py`

新增 8 个 preview_utils 与 GUI 表格测试：

- `test_extract_keywords_prefers_match_texts`：优先遍历 match_texts
- `test_extract_keywords_match_texts_dedup_across_hits`：跨 hit 去重
- `test_extract_keywords_match_texts_falls_back_to_match_text`：回退到 match_text
- `test_extract_keywords_match_texts_falls_back_to_detail`：回退到 detail 解析
- `test_build_keyword_to_rule_map_uses_match_texts`：映射优先 match_texts
- `test_build_keyword_to_rule_map_dedup_first_wins`：同关键词归属首条规则
- `test_build_keyword_to_rule_map_skips_filename_target`：跳过 filename target
- `test_dialog_hits_table_description_column_filled` / `test_detail_hits_table_description_column_filled`：第 6 列填充

同时更新 2 个现有测试的期望表格列数（5→6，含描述列）。

### `tests/test_cli.py`

更新 `test_scan_csv_output` 的期望 CSV header。

## 关键决策与依据

### AND/OR 多 match_text 收集的语义

- AndMatcher 收集所有子匹配器的 match_texts，去重保序后填入
- OrMatcher 遍历所有子匹配器（不再遇到首个命中就返回），match_count 为所有命中子匹配器之和
- 依据：需求 3 要求"把匹配命中的每个内容都标记出来"，不止标记单一匹配规则

### MatchSpec 持有方式重构

AndMatcher/OrMatcher/NotMatcherImpl 改为持有 spec，在 `__init__` 中从 spec.children/child
构造子匹配器，以读取 spec.description。否则组合规则无法获取 description 字段。

### target 字段语义保持

- AndMatcher `target=""`（组合规则无单一目标）
- OrMatcher `target=first_matched_child_target`（透传首个命中分支，符合既有测试期望）

### 缓存版本递增决策

将 CACHE_COMPAT_VERSION 从 3 递增到 4，因为 match_texts 字段语义变更
（原 match_text 仅含首条命中，新 match_texts 含全部命中），需清空旧缓存重新扫描。
match_description 是新增字段，旧缓存无此字段，递增版本一并 purge。

### match_texts JSON 序列化

在 SQLite 中以 JSON 数组形式存储 tuple，读取时 json.loads 反序列化。
含容错处理：NULL/空/非数组/解析失败均回退到空元组，避免损坏数据阻塞扫描。
JSON 使用 `ensure_ascii=False` 以正确存储中文关键词。

### preview_utils 三级回退

extract_keywords 和 build_keyword_to_rule_map 优先 match_texts，
回退 match_text，再回退 detail 解析（兼容旧缓存与 NotMatcher 等无原始文本的场景）。

## 测试验证结果

- ruff check：无新增错误（基线 ARG005/F405 等均为既有问题）
- ruff format --check：79 files already formatted
- pyrefly check：源文件 67 错误（基线一致），测试文件 160 错误（基线一致），无新增
- pytest：1272 passed, 16 deselected, 3 warnings
- 覆盖率：96.06% ≥ 95%

## 遗留事项

- 需求 1（PDF 导出）与需求 2（Excel 导出）留待 iter-42
- 需求 5/6/7（扫描中 UI 增强）留待 iter-43
- 需求 8（Splitter 美化）与需求 9（性能优化）留待 iter-44

## 下一轮计划

iter-42：PDF/Excel 导出功能

- 基于 ScanReport.to_csv/to_text/to_json 现有导出层，新增 PDF 与 Excel 导出
- PDF：使用 reportlab（与用户手册生成脚本一致的字体方案），含命中文件、规则、描述、匹配数表格
- Excel：使用 openpyxl（项目已有依赖），多 sheet（汇总 + 每文件明细）
- GUI 导出菜单扩展：新增 "导出为 PDF..." 与 "导出为 Excel..." 选项
- CLI 导出：`--format pdf|excel` 参数支持
