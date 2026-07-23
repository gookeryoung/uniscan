# iter-87 白名单制文件过滤与扫描逻辑修复

## 需求清单

- [x] 移除忽略扩展名配置项，按照白名单制明确待扫描文件（req-24）
- [x] 修复扫描逻辑：仅勾选压缩文件（7z/rar/zip）时不应出现文本类型

## 迭代目标

完成两项修复：1) 彻底移除 `Config.ignore_extensions` 黑名单字段及所有引用（config/scanner/walker/workers/watcher/cli/UI），统一为 `scan_extensions` 白名单制；2) 修复扫描逻辑缺陷——仅勾选压缩文件时仍扫描文本类型文件的根因是 `enabled_extensions()` 排除压缩包扩展名 + `_should_scan()` 对压缩包走特例，导致压缩包扩展名不在白名单中时仍被收集扫描。

## 关键决策与依据

1. **统一白名单制替代黑名单+特例**：iter-71 引入 `scan_extensions` 白名单后，`ignore_extensions` 黑名单成为冗余配置——两者功能重叠且语义冲突（黑名单排除 vs 白名单包含）。同时压缩包扩展名由 `scan_archives` 单独控制 walk 阶段过滤，形成特例代码路径。统一为白名单制后：
   - 压缩包扩展名（zip/rar/7z）与其他扩展名统一进入 `scan_extensions` 白名单
   - `scan_archives` 字段保留作为 ArchiveScanner 构造开关，由勾选区 `archives_enabled` 同步推导
   - `_should_scan()` 三种语义：`None`（全选快速路径）/ 空 frozenset（全不选防御性边界）/ 非空 frozenset（仅扫白名单内文件）
2. **压缩包内部条目同样按白名单过滤**：ArchiveScanner 新增 `scan_extensions` 参数，内部条目过滤逻辑与 Scanner._should_scan 一致——用户勾选压缩包但未勾选文本类型时，压缩包内 .txt 被跳过
3. **enabled_extensions 返回值语义扩展**：`None` 表示所有分类全选（含压缩包）走快速路径；空 tuple 表示全部取消勾选；非空 tuple 含压缩包扩展名（由勾选区 `archives_enabled` 控制是否包含 zip/rar/7z）
4. **移除"忽略扩展名"UI TAB**：配置页 `content_tab_widget` 从 3 个 TAB 缩减为 2 个（文件类型 + 忽略目录），`content_panel.py` 移除 `exts_edit` 参数与相关保存/加载逻辑

## 改动文件清单

修改（源码）：
- `src/fuscan/config.py`：移除 `ignore_extensions` 字段与 30 项默认值列表
- `src/fuscan/scanner/scanner.py`：
  - 移除 `ignore_extensions` 参数
  - `_should_scan` 统一为白名单制三种语义，移除 archive 特例（旧代码 `scan_archives` 时强制收集压缩包）
  - `ArchiveScanner` 构造时传入 `scan_extensions=self._scan_extensions`
- `src/fuscan/scanner/walker.py`：移除 `ignore_extensions` 参数与扩展名黑名单过滤，docstring 说明扩展名过滤改由 Scanner._should_scan 统一管理
- `src/fuscan/archive/scanner.py`：新增 `scan_extensions` 参数，`scan_archive` 中按白名单过滤内部条目
- `src/fuscan/gui/extractor_model.py`：`enabled_extensions` 统一含压缩包扩展名，三种返回值语义（None/空 tuple/非空 tuple）
- `src/fuscan/gui/content_panel.py`：移除 `exts_edit` 参数与忽略扩展名保存/加载逻辑，TAB 从 3 个缩减为 2 个
- `src/fuscan/gui/main_window.py`：FileStatsWorker/ScanWorker 构造时移除 `ignore_extensions` 传参
- `src/fuscan/gui/main_window.ui`：移除 `ignore_extensions_tab` widget（45 行）
- `src/fuscan/gui/main_window_ui.py`：由 pyside2-uic 重新生成，移除 27 行 ignore_extensions 相关代码
- `src/fuscan/workers/stats_worker.py`：移除 `ignore_extensions` 参数
- `src/fuscan/workers/scan_worker.py`：移除 `ignore_extensions` 参数
- `src/fuscan/watcher/monitor.py`：移除 `MonitorConfig.ignore_extensions` 字段、`_EventHandler` 扩展名过滤逻辑、`FileMonitor` 中 ignore_extensions 处理
- `src/fuscan/watcher/tray.py`：移除 `ignore_extensions` 参数
- `src/fuscan/watcher/incremental.py`：移除 `ignore_extensions` 参数
- `src/fuscan/cli.py`：移除 `ignore_extensions=config.ignore_extensions` 传参

修改（测试）：
- `tests/test_scanner.py`：`test_scan_respects_ignore_extensions` 替换为 `test_scan_respects_scan_extensions_whitelist`（验证白名单过滤：pyc 不在白名单被跳过，txt 被扫描）；新增 `test_scan_extensions_empty_whitelist_scans_nothing`（空白名单边界：全跳过）
- `tests/test_walker.py`：移除 4 个 `ignore_extensions` 测试（`test_walk_ignore_extensions`、`test_walk_ignore_extensions_with_dot`、`test_walk_ignore_extensions_case_insensitive`、`test_on_skip_dir_not_called_for_ignored_files`）
- `tests/test_config.py`：移除 `test_default_ignore_extensions`；移除序列化测试中 `ignore_extensions` 字段
- `tests/test_gui.py`：`test_ignore_widgets_exist_with_placeholders` 移除 ignore_extensions_edit 断言；`test_content_tab_widget_has_three_tabs` 改为 `test_content_tab_widget_has_two_tabs`（3→2 TAB）；移除 `test_default_ignore_extensions_loaded` 与 `test_save_ignore_to_config_writes_extensions`
- `tests/test_watcher.py`：移除 `test_monitor_ignores_extensions`；两处 `_EventHandler` 构造移除 `ignore_extensions=set()` 参数
- `tests/test_archive.py`：`test_scan_archives_7z_not_in_ignore_extensions` 替换为 `test_scan_archives_7z_in_whitelist`（白名单含 7z 时扫描）；新增 `test_archive_internal_entries_filtered_by_whitelist`（压缩包内部 .pyc 不在白名单被跳过）
- `tests/test_extractor_model.py`：`test_set_disabled_extractors_updates_state` 预期值加入 7z/rar/zip；`test_partial_enabled_returns_union` 预期值加入压缩包扩展名；`test_all_disabled_via_category_toggle` 增加取消压缩包分类（cat 4）；`test_enabled_extensions_excludes_archive` 重写为 `test_enabled_extensions_includes_archive`（验证取消压缩包后白名单不含 zip/rar/7z 但含其余扩展名）

## 代码实现情况

### 1. Config.ignore_extensions 移除

`config.py` 中移除 `ignore_extensions: list[str] = field(default_factory=lambda: [...30 项...])` 字段。旧配置文件中保留的 `ignore_extensions` 键由 `Config.__post_init__` / `load_config` 的 dataclass 默认行为忽略（不报错，不加载）。

### 2. Scanner._should_scan 统一白名单制

旧代码 `_should_scan` 中压缩包扩展名有特例：`scan_archives=True` 时强制返回 True（即使扩展名不在白名单中），导致仅勾选压缩文件时压缩包被收集但文本文件也被扫描（因为 `enabled_extensions()` 排除了压缩包扩展名，白名单为空时 Scanner 走 None 快速路径扫所有文件）。

修复后：
- `enabled_extensions()` 含压缩包扩展名——仅勾选压缩包时返回 `("7z", "rar", "zip")`
- `_should_scan` 移除 archive 特例——白名单为 `("7z", "rar", "zip")` 时仅 .7z/.rar/.zip 文件通过，.txt/.py 等被跳过
- `None` 快速路径仅在所有分类（含压缩包）全选时触发

### 3. ArchiveScanner 内部条目过滤

`archive/scanner.py` 新增 `scan_extensions: frozenset[str] | None = None` 参数，`scan_archive` 遍历内部条目时按白名单过滤：`None` 扫所有条目（向后兼容全选快速路径）；非空 frozenset 仅扫白名单内扩展名的条目。

### 4. UI 移除"忽略扩展名"TAB

`main_window.ui` 移除 `ignore_extensions_tab` widget（含 `ignore_extensions_hint_label` 与 `ignore_extensions_edit`）。`main_window_ui.py` 由 `pyside2-uic` 重新生成。`content_panel.py` 移除 `exts_edit` 构造参数与 `_save_ignore_to_config` 中扩展名保存逻辑。`content_tab_widget` 从 3 个 TAB 缩减为 2 个。

### 5. watcher 模块清理

`monitor.py` 移除 `MonitorConfig.ignore_extensions` 字段、`_EventHandler` 中扩展名过滤逻辑、`FileMonitor.__init__` 中 ignore_extensions 处理。`tray.py` / `incremental.py` 移除 `ignore_extensions` 参数。`cli.py` 移除 `ignore_extensions=config.ignore_extensions` 传参。

## 整合优化情况

- `enabled_extensions()` docstring 明确三种返回值语义（None/空 tuple/非空 tuple），消除歧义
- `_should_scan` docstring 说明压缩包扩展名由 `ExtractorTreeModel.enabled_extensions` 在勾选压缩包分类时加入白名单，与其他扩展名统一过滤
- `scanner.py` 中 ArchiveScanner 构造注释说明 `scan_extensions` 三种语义（None 全选 / 空 frozenset 全不选 / 非空按白名单）
- `walker.py` docstring 说明扩展名过滤改由 Scanner._should_scan 按 `scan_extensions` 判断

## 测试验证结果

- ruff check src tests：**All checks passed**
- ruff format --check src tests：**104 files already formatted**
- pyrefly check：**0 errors**（555 suppressed, 62 warnings not shown）
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1575 passed**，覆盖率 **95.10%**（≥ 95% 阈值）

## 遗留事项

- `src/fuscan/rules/parser.py` 中 `ignore_extensions` 字段的静默忽略逻辑保留（处理旧规则文件中可能存在的 `ignore_extensions` 键，向后兼容）
- `src/fuscan/rules/model.py` / `merge.py` 中 docstring 注释提及 `ignore_extensions` 迁移至全局 Config，作为历史说明保留
- 旧配置文件中保留的 `ignore_extensions` 键被静默忽略（dataclass 不报错），不影响加载

## 下一轮计划

无。本次需求已完成，等待用户实测确认白名单制扫描行为正确。
