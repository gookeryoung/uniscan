# iter-10: 路径过滤与内置通用规则

## 本轮目标

1. 在规则中增加路径过滤（`ignore_paths`），跳过特定文件夹及其子文件夹，加速扫描
2. 增加内置通用规则，在软件自身文件夹中定义，可被用户规则按名称覆盖

## 改动文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `src/pyfilescan/rules/model.py` | 修改 | `RuleSet` 新增 `ignore_paths: Tuple[str, ...]` 字段 |
| `src/pyfilescan/rules/parser.py` | 修改 | `parse_ruleset` 解析 `ignore_paths` 字段 |
| `src/pyfilescan/scanner/walker.py` | 修改 | `FileWalker` 新增 `ignore_paths` 参数与 `_matches_ignore_path` 方法，支持 glob 路径过滤 |
| `src/pyfilescan/scanner/scanner.py` | 修改 | 透传 `ignore_paths` 给 `FileWalker` |
| `src/pyfilescan/rules/merge.py` | 新增 | `merge_rulesets` 函数：按名称合并规则，ignore 列表取并集 |
| `src/pyfilescan/rules/__init__.py` | 修改 | 导出 `merge_rulesets` |
| `src/pyfilescan/builtin/__init__.py` | 新增 | `load_builtin_ruleset` / `load_with_builtin` / `BUILTIN_RULES_PATH` |
| `src/pyfilescan/builtin/rules.yaml` | 新增 | 8 条内置通用规则（AWS密钥、私钥、密码赋值、API密钥、数据库连接串、Bearer令牌、敏感文件名、备份文件）+ 22 个 ignore_dirs + 3 个 ignore_paths + 31 个 ignore_extensions |
| `src/pyfilescan/cli.py` | 修改 | `scan`/`tray` 子命令 `-r` 改为可选；新增 `--no-builtin` 标志；`_cmd_rules` 显示 ignore_paths |
| `src/pyfilescan/gui/main_window.py` | 修改 | 新增"使用通用规则"复选框；启动时默认加载内置规则；`_reload_ruleset` 按开关与用户路径加载 |
| `pyproject.toml` | 修改 | package-data 增加 `builtin/*.yaml` |
| `tests/test_walker.py` | 修改 | 新增 `TestIgnorePaths` 类（7 个测试） |
| `tests/test_rules_parser.py` | 修改 | 新增 ignore_paths 解析测试（3 个） |
| `tests/test_merge.py` | 新增 | `merge_rulesets` 单元测试（12 个） |
| `tests/test_builtin.py` | 新增 | 内置规则加载与合并测试（11 个） |
| `tests/test_cli.py` | 修改 | 新增 `TestBuiltinRules` 类（7 个测试）；更新 `scan_root` fixture 使用 20 字符 AWS 密钥 |
| `tests/test_gui.py` | 修改 | 更新 3 个受影响测试；新增 `TestBuiltinRulesToggle` 类（6 个测试） |

## 关键决策与依据

### 1. 路径过滤用 glob 通配符（fnmatch）

- **决策**：`ignore_paths` 使用 `fnmatch.fnmatch` 进行 glob 模式匹配
- **依据**：用户确认选择 glob 通配符（而非正则表达式），更直观易用
- **大小写不敏感**：模式与路径均转为小写后匹配
- **匹配逻辑**：检查目录相对路径是否匹配模式，同时检查 `路径 + "/x"` 是否匹配（处理 `*/vendor/*` 等描述目录内文件的模式）

### 2. 合并策略：按名称合并

- **决策**：用户规则中同名规则覆盖内置规则；`ignore_dirs`/`ignore_extensions`/`ignore_paths` 取并集
- **依据**：用户确认选择"按名称合并"策略
- **去重保序**：`_union` 辅助函数用 dict 去重并保持插入顺序（base 优先）

### 3. 内置规则随包分发

- **决策**：内置规则文件放在 `src/pyfilescan/builtin/rules.yaml`，通过 `pyproject.toml` 的 `package-data` 打包
- **依据**：随包分发确保安装后即可使用，无需额外下载

### 4. CLI `--no-builtin` 需配合 `-r`

- **决策**：`--no-builtin` 时必须指定 `-r`，否则报错
- **依据**：禁用内置规则后若无用户规则则无规则可用，需明确提示

### 5. GUI 默认加载内置规则

- **决策**：GUI 启动时默认加载内置规则，用户可通过复选框关闭
- **依据**：降低使用门槛，用户无需准备规则文件即可开始扫描；高级用户可关闭后仅用自定义规则

## 验证结果

- ruff: 全部通过
- pytest: 375 passed, 1 skipped
- 覆盖率: 87.99%（门槛 80%）
  - `builtin/__init__.py`: 100%
  - `rules/merge.py`: 100%
  - `rules/parser.py`: 97%
  - `scanner/walker.py`: 91%
  - `cli.py`: 89%
  - `gui/main_window.py`: 79%

## 遗留事项

- 无
