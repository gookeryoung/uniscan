# iter-79：扫描体验优化

## 需求清单

- [x] 需求1：分析 Terminal#13-36 损坏 ZIP traceback 是否为异常问题，并精简日志
- [x] 需求2：暂停/取消按钮改为常规按钮背景，不要红色
- [x] 需求3：取消响应优化——点击后立即显示"取消中"，后台异步调用取消操作
- [x] 需求4：扫描过程分为四阶段（准备扫描、解析目录、文件解析、扫描完成），下方提示显式体现，不同阶段切换与侧边栏功能禁用状态关联
- [x] 需求5：解析目录阶段按所选文件类型和忽略规则快速分析出需解析的文件（白名单制度）
- [x] 需求6：压缩文件（zip/7z/rar 等）单独列分类，不在配置中设计；不勾选则不计待解析数量
- [x] 需求7：设置中的忽略项移到配置页文件类型右侧，通过 TAB 切换忽略目录和忽略扩展名

## 迭代目标

围绕扫描体验做一次集中优化：损坏压缩包日志降噪、按钮视觉去红、
取消即时反馈、扫描四阶段提示、压缩包独立分类、忽略项位置重构。
7 个需求合并为一个迭代交付。

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/archive/scanner.py` | 两处 `logger.warning(..., exc_info=True)` 去掉 `exc_info=True`，文案改为「（已跳过）」，避免损坏压缩包 traceback 刷屏 |
| `src/fuscan/gui/styles.qss` | `pause_resume_btn` 从 `COLOR_DANGER`（红色）改为 `COLOR_BG_CARD`（白色卡片）+ `COLOR_BORDER` 边框；`cancel_btn` hover 从 `COLOR_DANGER` 改为 `COLOR_PRIMARY`；两者新增 `:disabled` 样式 |
| `src/fuscan/gui/extractor_model.py` | 新增压缩包分类（`_ARCHIVE_CLASS_NAME="ArchiveFiles"`、`_ARCHIVE_CATEGORY="压缩包"`、`_ARCHIVE_DISPLAY_NAME="压缩文件"`）；`__init__` 末尾从 `archive.default_factory.registered_extensions` 加载压缩包扩展名创建虚拟 `ExtractorItem`；`enabled_extensions()` 排除压缩包分类；新增 `archives_enabled()` 方法；`_CATEGORY_ORDER` 新增「压缩包」 |
| `src/fuscan/gui/main_window.py` | 导入 `ExtractorTreeModel`；`_PHASE_LABELS` 四阶段命名（walk→「解析目录」、scan→「文件解析」、archive→「扫描压缩包」）；`_on_cancel_scan` 立即禁用按钮+显示「取消中...」+「正在取消扫描...」；`_update_stage_actions` 新增 `self.sidebar.setEnabled(not is_scanning)`；`_on_extractor_toggled` 同步 `Config.scan_archives`；`_apply_config` 向后兼容处理 `scan_archives=False`；`_on_scan` 初始文案改为「准备扫描...」；新增 `_ignore_save_timer` 节流保存（500ms）；`_setup_file_types` 连接 `ignore_dirs_edit`/`ignore_extensions_edit` 的 `textChanged`；新增 `_on_ignore_changed`/`_save_ignore_to_config` 方法；`_apply_config` 加载忽略项到编辑器（blockSignals 包裹）；`_on_scan` 启动前 flush 节流 timer |
| `src/fuscan/gui/main_window.ui` | `file_types_group` 从 QVBoxLayout 改为 QHBoxLayout；左侧保留 `file_types_count_label`+`file_types_view`（QVBoxLayout 包装）；右侧新增 `ignore_tab_widget`（QTabWidget）含两个 Tab：`ignore_dirs_tab`（忽略目录 QPlainTextEdit）+ `ignore_extensions_tab`（忽略扩展名 QPlainTextEdit）；`file_types_count_label` 默认文本「已勾选 15/15 项」 |
| `src/fuscan/gui/main_window_ui.py` | 由 `pyside2-uic` 从 .ui 重新生成（uic 产物，勿手改） |
| `src/fuscan/gui/settings_dialog.py` | 移除 `ignore_page_layout` 的 stretch 设置；`_load_config`/`_save_config` 移除 `ignore_dirs`/`ignore_extensions` 读写；模块 docstring 更新说明忽略项已迁移到配置页 |
| `src/fuscan/gui/settings_dialog.ui` | 移除「忽略项」Tab（`ignore_page` 含 `ignore_dirs_group`/`ignore_extensions_group` 及内部控件） |
| `src/fuscan/gui/settings_dialog_ui.py` | 由 `pyside2-uic` 从 .ui 重新生成（uic 产物，勿手改） |
| `src/fuscan/scanner/result.py` | `ProgressInfo.summary()` 文案更新：walk 阶段「正在分析目录结构」→「解析目录」，archive 阶段「正在扫描压缩包」→「扫描压缩包」 |
| `tests/test_scanner.py` | `test_summary_walk_phase` 断言「解析目录」；`test_summary_archive_phase` 断言「扫描压缩包」 |
| `tests/test_extractor_model.py` | 11 项断言更新适配压缩包分类；4 项新增测试（archive_display_text、archives_enabled_default_true、archives_enabled_false_after_uncheck、enabled_extensions_excludes_archive） |
| `tests/test_gui.py` | `TestSettingsDialogIgnore`（8 项）替换为 `TestMainWindowIgnore`（10 项）：测试主窗口配置页的忽略项控件存在性、Tab 切换、默认值加载、自定义值加载、`_save_ignore_to_config` 写入、strip 空白、`_on_ignore_changed` 启动 timer、`_apply_config` 不触发保存循环 |

## 关键决策与依据

### D1：损坏压缩包日志降噪而非完全静默

**决策**：去掉 `exc_info=True`，保留 `logger.warning` 并改文案为「（已跳过）」。

**依据**：
- Terminal#13-36 的 traceback 是 `scan_archive()` 正确捕获 `ArchiveError` 后的
  日志输出，不是 bug——扫描流程正常推进，仅日志过于冗长
- 完全静默会让用户误以为压缩包被正常扫描；保留 warning 但去掉 traceback
  既提示用户跳过了损坏文件，又不污染控制台

### D2：压缩包独立分类通过虚拟 ExtractorItem 实现

**决策**：在 `ExtractorTreeModel` 中新增虚拟「ArchiveFiles」项，扩展名从
`archive.default_factory.registered_extensions` 加载，不来自 `ExtractorRegistry`。

**依据**：
- 需求6要求压缩包「单独列分类，不在配置中设计」——压缩包扫描由
  `ArchiveScanner` 处理而非 `ExtractorRegistry`，强行注册到 registry 会破坏
  既有架构
- 虚拟项复用树形勾选 UI，用户勾选/取消与普通提取器体验一致
- `enabled_extensions()` 排除压缩包分类，避免压缩包扩展名参与 `scan_extensions`
  过滤（压缩包由 `Config.scan_archives` 单独控制）
- `archives_enabled()` API 让主窗口同步 `Config.scan_archives`，向后兼容旧配置

### D3：向后兼容旧配置 scan_archives=False

**决策**：`_apply_config` 中检测旧配置 `scan_archives=False` 但
`disabled_extractors` 中无「ArchiveFiles」时，补充禁用压缩包分类。

**依据**：
- iter-78 之前的配置文件 `disabled_extractors` 不含「ArchiveFiles」
- 直接用 `set_disabled_extractors(disabled)` 会让压缩包分类默认勾选，
  覆盖用户原本 `scan_archives=False` 的意图
- 补充禁用后，压缩包分类显示为未勾选，与旧配置语义一致

### D4：取消即时反馈通过禁用按钮+文案切换实现

**决策**：`_on_cancel_scan` 立即禁用 `cancel_btn`/`pause_resume_btn`，
`stats_label` 显示「取消中...」，`current_file_label` 显示「正在取消扫描...」，
然后调用 `self._worker.cancel()`。

**依据**：
- 需求3要求「点击后立即显示取消中（转圈），后台调用取消操作」
- `ScanWorker.cancel()` 是非阻塞的（设置 `_cancel_event`），后台线程检测到
  后自然退出，无需额外异步机制
- 立即禁用按钮避免用户重复点击；文案切换给用户即时反馈

### D5：忽略项节流保存而非即时保存

**决策**：新增 `_ignore_save_timer`（QTimer，500ms，singleShot），
`textChanged` 信号触发 `_on_ignore_changed` 启动 timer，timer 超时调用
`_save_ignore_to_config`。`_on_scan` 启动前 flush timer。

**依据**：
- QPlainTextEdit 每次按键都触发 `textChanged`，即时保存会导致每次按键
  都写文件 I/O，长列表编辑时卡顿
- 500ms 节流是常见的"停止输入后保存"策略，平衡响应性与性能
- `_on_scan` 启动前 flush 确保用户编辑后立即点扫描也能使用最新配置
- `_apply_config` 加载时 `blockSignals` 包裹，避免 `setPlainText` 触发
  节流保存循环

### D6：忽略项 TAB 放在文件类型右侧而非下方

**决策**：`file_types_group` 从 QVBoxLayout 改为 QHBoxLayout，左侧文件类型树，
右侧 `QTabWidget` 切换忽略目录/忽略扩展名。

**依据**：
- 需求7明确要求「移到Content页面下文件类型右侧，通过TAB切换」
- 左右并排让用户能同时查看文件类型勾选与忽略规则，理解「勾选的文件类型
  与忽略规则共同决定扫描范围」
- QTabWidget 切换节省垂直空间，避免忽略目录长列表占据过多高度

## 代码实现情况

### 需求1：损坏压缩包日志精简

`archive/scanner.py` 两处 warning 去掉 `exc_info=True`，文案统一改为
「（已跳过）」。Terminal#13-36 的 traceback 不再出现。

### 需求2：按钮样式去红色

`styles.qss` 中 `pause_resume_btn` 改为白色卡片背景（`COLOR_BG_CARD`）+
边框（`COLOR_BORDER`），`cancel_btn` hover 改为 `COLOR_PRIMARY`（主色蓝）。
两者新增 `:disabled` 样式（灰色背景+浅色文字）。

### 需求3：取消即时反馈

`_on_cancel_scan` 立即禁用按钮 + 显示「取消中...」+「正在取消扫描...」，
然后调用 `self._worker.cancel()`（非阻塞）。

### 需求4：扫描四阶段 + 侧边栏关联

- `_PHASE_LABELS` 映射：walk→「解析目录」、scan→「文件解析」、archive→「扫描压缩包」
- `_on_scan` 初始文案「准备扫描...」（阶段1）
- `ProgressInfo.summary()` 文案同步更新
- `_update_stage_actions` 新增 `self.sidebar.setEnabled(not is_scanning)`，
  扫描中禁用侧边栏（切换页面）

### 需求5：解析目录白名单优化

扫描器两阶段架构（iter-71）已实现白名单：阶段1按 `scan_extensions` 过滤
收集文件清单，阶段2只扫描清单内文件。本次迭代通过压缩包独立分类（需求6）
让 `scan_extensions` 更精确——压缩包扩展名不再参与过滤，由 `scan_archives`
单独控制。

### 需求6：压缩文件独立分类

`ExtractorTreeModel` 新增「压缩包」分类，虚拟 `ArchiveFiles` 项从
`archive.default_factory.registered_extensions` 加载扩展名。
`archives_enabled()` API 同步 `Config.scan_archives`。向后兼容旧配置。

### 需求7：忽略项位置重构

- `main_window.ui`：`file_types_group` 改水平布局，右侧新增 `ignore_tab_widget`
- `settings_dialog.ui`：移除「忽略项」Tab
- `main_window.py`：新增节流保存 timer + `_on_ignore_changed`/`_save_ignore_to_config`
- `_apply_config` 加载忽略项到编辑器（blockSignals 包裹）
- `_on_scan` 启动前 flush timer

## 整合优化情况

- `_PHASE_LABELS` 与 `ProgressInfo.summary()` 文案统一，避免 GUI 与数据层不一致
- 忽略项节流保存复用既有 `_result_filter_timer` 模式（QTimer singleShot + timeout 连接）
- 压缩包分类复用树形勾选 UI，无需新增控件类型

## 测试验证结果

- `ruff check src tests`：通过
- `ruff format --check src tests`：通过
- `pyrefly check`：0 errors
- `pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：1555 passed, 16 deselected, coverage 95.07%
- `TestMainWindowIgnore`：10 项全部通过
- `TestExtractorTreeModelArchive`（压缩包分类）：4 项全部通过
- `TestSettingsDialog`：14 项全部通过（移除忽略项后无回归）

## 遗留事项

- 无

## 下一轮计划

- 无（本次迭代需求全部交付）
