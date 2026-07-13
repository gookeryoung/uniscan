# 迭代 29：界面布局优化与行尾规范化

## 迭代目标

按用户反馈优化 GUI 5 项布局/配色问题，并修复一项预存在的 Windows CRLF 行尾导致
`test_content_equals` 失败的 bug。

## 改动文件清单

### 修改文件

- `src/fuscan/theme.py`：`COLOR_PRIMARY_DARK` 由 `#0256c1` 调为 `#024aa0`，
  `COLOR_PRIMARY_DARKER` 由 `#024aa0` 调为 `#013d82`，拉开选中态与未选中态对比度。
- `src/fuscan/gui/styles.qss`：`QFrame#header_bar QPushButton:checked` 新增
  `border-bottom: 3px solid ${COLOR_ACCENT}` 与 `padding-bottom: 1px`，强化选中态视觉。
- `src/fuscan/gui/main_window_ui.py`：
  - 配置页 `setup_action_bar` 移除按钮间 `setup_btn_spacer`，改为前置
    `setup_btn_leading_spacer` 右对齐；`view_results_btn` 设 `setEnabled(False)` +
    `setMinimumSize(QSize(180, 44))`（与 `scan_btn` 一致），不再 `setVisible(False)`。
  - 扫描中页移除 `progress`/`current_file_label`/`stats_group`/`stats_counts_label`/
    `stats_time_label` 的创建与布局（统计面板与状态栏重复）。
  - `retranslateUi` 同步移除上述被删部件的文本设置。
- `src/fuscan/gui/main_window.py`：
  - `_bind_widgets` 移除 `_stats_counts_label`/`_stats_time_label` 绑定；新增
    `self._progress`（QProgressBar，fixedWidth=200）与 `self._current_file_label`
    （QLabel，maxWidth=400），通过 `statusBar().addPermanentWidget()` 挂到右侧。
  - `_configure_ui` 调整 `setup_layout` stretch 为 `0/0/2`，target_group 自然尺寸 +
    操作条紧随 + 底部弹簧填充，避免配置页大面积留白。
  - `_update_stage_actions` 中 `view_results_btn` 改为始终 `setVisible(is_setup)` +
    `setEnabled(has_report)`；`_progress`/`_current_file_label` 仅扫描中可见。
  - `_on_scan`/`_on_scan_progress` 移除已删部件的更新逻辑，速度信息合并到
    `_stats_label` 文本。
- `src/fuscan/extractors/text.py`：`TextExtractor._decode` 统一将 CRLF/CR 规范化为 LF，
  新增模块级 `_normalize_newlines` 辅助函数。修复 Windows 平台 `write_text` 写入
  CRLF 导致 CONTENT EQUALS 严格比较失败的预存在 bug。
- `tests/test_gui.py`：
  - `test_view_results_btn_hidden_initially` → `test_view_results_btn_disabled_initially`
    （断言改为可见但禁用）。
  - `test_view_results_btn_visible_with_report` → `test_view_results_btn_enabled_with_report`
    （断言改为可见且启用）。
  - `test_on_scan_progress_updates_stats_labels` 改为检查 `_stats_label` 文本含计数与速度。
  - 新增 `TestScanningPageLayout`（5 个测试）：统计面板移除、进度条/当前文件标签
    移至状态栏、非扫描阶段隐藏、扫描中更新值。
  - 新增 `TestThemeColorContrast`（2 个测试）：PRIMARY_DARK 与 PRIMARY 色值可区分、
    头部 Tab 选中态有 ACCENT 底边。
  - `TestSetupActionBar` 新增 3 个测试：查看结果按钮与扫描按钮同尺寸、相邻无 spacer、
    原 spacer 已移除。
- `tests/test_extractors.py`：`TestTextExtractor` 新增 3 个测试：
  `test_normalizes_crlf_to_lf`、`test_normalizes_cr_to_lf`、`test_lf_preserved`。

## 关键决策与依据

1. **选中态对比度调整用色相位移而非明度**：`COLOR_PRIMARY_DARK` 在 G/B 通道同时下移
   （ΔG≈28、ΔB≈54），比单纯降明度更能与 `COLOR_PRIMARY` 拉开视觉距离；再叠加
   `COLOR_ACCENT` 底边作为二次强调，符合「主色 + 强调色」配色最佳实践。
2. **查看结果按钮改为始终可见但禁用**：原方案无结果时隐藏，但按钮位空缺会让配置页
   操作条右半显得不平衡；改为禁用态保留占位，用户能感知「此功能存在但当前不可用」，
   符合 affordance 设计原则。
3. **进度条与当前文件标签用 `addPermanentWidget`**：`addWidget`（左侧带 stretch）会
   被压缩，`addPermanentWidget`（右侧永久区）保证进度条固定宽度不被挤压，且仅扫描中
   `setVisible(True)`，非扫描阶段自动隐藏。
4. **扫描中页移除统计面板**：状态栏 `_stats_label` 已承载计数/耗时/速度，Content 区
   再放一份 `stats_group` 是信息重复；移除后 Content 区仅保留跳过文件列表与匹配文件
   列表（扫描中实时填充），布局更聚焦。
5. **行尾规范化放在 TextExtractor 而非匹配器**：文本提取器天然负责编码/规范化，
   在此处统一 CRLF/CR → LF 最自然；对 CONTAINS/STARTSWITH 等模式无副作用（模式中
   含 `\r\n` 的情况极少，且规范化后内容与模式约定一致更符合直觉）。
6. **预存在 bug 顺带修复**：`test_content_equals` 在 Windows 上始终失败（CRLF），
   与本次 GUI 改动无关但阻塞门禁；root cause 明确且修复外科，顺带修复使门禁全绿，
   符合「闭环执行」原则。

## 验证结果

- ruff check：All checks passed
- ruff format：70 files already formatted
- pyrefly check：0 errors (108 suppressed, 17 warnings)
- pytest -m "not slow" --cov：977 passed, 4 deselected, coverage 96.38%
- 新增 11 个测试全部 PASSED（GUI 8 + extractors 3）

## 遗留事项

- 无
