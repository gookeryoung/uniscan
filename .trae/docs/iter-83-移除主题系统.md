# iter-83 移除主题系统

## 需求清单

- [x] 移除所有主题相关代码，简化项目设计，避免混入过多的主题配置相关内容（req-19-功能更新.md）

## 迭代目标

彻底移除 fuscan 的设计令牌（theme.py）与 QSS 样式层（styles.qss），GUI 改用 Qt 原生样式，简化项目设计。同步更新 rule-12 规则与测试用例。

## 关键决策与依据

1. **移除范围界定**：用户明确"移除所有令牌和 qss"。据此删除 theme.py（设计令牌 + QSS_TOKENS 字典）、styles.qss（100+ `${TOKEN}` 占位符）、app.py 的 `load_stylesheet()` 与 `string.Template` 替换机制。GUI 不再应用自定义 QSS，使用 Qt 原生样式。
2. **regex_tester.py HTML 着色**：速查手册此前用 `theme.COLOR_PRIMARY` 等令牌驱动 HTML 着色。令牌移除后改为内联十六进制色值（#40a9ff / #ffffff / #0366d6 / #586069 / 字体族 / 13px），保持视觉效果不变。
3. **rule-12 同步修改**（用户授权）：移除"颜色、尺寸在 theme.py 定义...QSS 用 ${TOKEN} 引用，禁止硬编码"强制约束，改为"GUI 采用 Qt 原生样式，不维护 QSS 主题层与设计令牌系统"。详细参考段落注明 fuscan 不采用 SKILL 中的令牌/QSS 系统。
4. **resources_rc.py 排除**（用户授权）：该文件由 pyside-rcc 自动生成（与 `*_ui.py` 同类），ruff format 失败。在 ruff.toml 的 extend-exclude 添加 "resources_rc.py"，与既有自动生成文件排除模式一致，避免每次重新生成需重新格式化。
5. **__init__.py 修复**：HEAD 既有 ruff 失败（I001/E402，源于 resources_rc 别名注册的 sys.modules 技巧）。加 `# isort: skip_file` 与 `# noqa: E402` + 格式空行修复，无配置改动。

## 改动文件清单

删除：
- `src/fuscan/theme.py`（设计令牌 + QSS_TOKENS）
- `src/fuscan/gui/styles.qss`（QSS 样式表）

修改：
- `src/fuscan/gui/app.py`：移除 theme 导入、`load_stylesheet()`、`_QSS_PATH`、`string.Template`/`pathlib`/`logging` 导入、`setStyleSheet` 调用；`__all__` 仅保留 `launch`
- `src/fuscan/gui/regex_tester.py`：移除 theme 导入，HTML 速查表改用内联色值
- `src/fuscan/gui/preview_utils.py`：移除 docstring 中 `:mod:fuscan.theme` 引用
- `src/fuscan/gui/__init__.py`：修复既有 ruff 失败（isort skip + noqa E402 + 空行）
- `tests/test_gui.py`：删除 test_scan_btn_qss_uses_primary_blue、test_view_results_btn_qss_is_outline、TestThemeColorContrast 类、test_launch_qss_load_error_logged；test_regex_cheatsheet_rendered_as_html 改用内联色值断言；清理 FakeApp.setStyleSheet 死代码
- `.trae/rules/rule-12-pyside-dev.md`：移除 theme.py+QSS 强制约束
- `ruff.toml`：extend-exclude 添加 "resources_rc.py"

## 代码实现情况

- theme.py 与 styles.qss 完全删除，无残留引用（grep 验证仅历史迭代记录/已完成需求中提及）。
- app.py 的 `launch()` 不再加载样式表，仅保留高 DPI 配置与事件循环。
- regex_tester.py 的 `_build_cheatsheet_html()` 视觉效果与原先一致（同色值内联）。
- resources.qrc 不含 styles.qss，无需改动。

## 整合优化情况

- 顺带修复 HEAD 既有 ruff 失败（__init__.py + resources_rc.py），使全量 `ruff check`/`format --check` 通过。
- 清理 launch 测试中因 QSS 移除而失效的 FakeApp.setStyleSheet 死代码。

## 测试验证结果

- ruff check src tests：All checks passed
- ruff format --check src tests：102 files already formatted
- pyrefly check：0 errors
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1580 passed**，覆盖率 **95.05%**（≥ 95% 阈值，且高于上次 95.02%）
- 首次 pytest 在 test_worker_scans_multiple_roots 处发生 Windows 访问违例（scan_worker 线程内 perf.py:merge_dict），单独运行通过、重跑全量通过，确认为偶发线程问题，与本次改动无关（scan_worker/perf 未引用 theme）。

## 遗留事项

- GUI 改用 Qt 原生样式后，部分控件视觉一致性需用户实测确认（原先由 QSS 统一的选中态、边框、间距等现依赖原生风格）。
- 偶发的 scan_worker 线程访问违例为既有问题，建议后续排查 perf.py:merge_dict 的线程安全性。

## 下一轮计划

无。本次需求已完成，等待用户反馈 GUI 原生样式实测效果。
