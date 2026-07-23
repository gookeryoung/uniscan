# iter-84 现代 QSS 与按钮差异化

## 需求清单

- [x] 编写现代风格 QSS 并对主功能按钮大小进行差异化设计（req-21-现代QSS与按钮差异化.md）

## 迭代目标

回退 iter-83「移除主题系统」决策，重新引入设计令牌（theme.py）与 QSS 样式层（styles.qss），采用 GitHub Desktop 风格扁平配色，并按三级层级（主/次/辅）对主功能按钮尺寸与样式进行差异化设计。同步更新 rule-12-pyside-dev.md 与测试用例。

## 关键决策与依据

1. **三级按钮层级差异化**：用户明确要求"对主功能按钮大小进行差异化设计"。按视觉权重分三档：
   - **L1 主操作**（`scan_btn`/`rescan_btn` 主色填充；`view_results_btn`/`export_btn` 主色边框）：高 48px、字号 15px、圆角 8px、`padding 12px 28px`，醒目入口
   - **L2 次要操作**（`pause_resume_btn`/`cancel_btn`/`select_path_btn`）：高 40px、字号 14px、圆角 6px、灰边框，扫描流程与路径选择
   - **L3 辅助操作**（详情导航、规则管理、子对话框）：高 32px、字号 13px、圆角 4px、扁平弱化视觉权重
   - `cancel_btn` hover 时呈现淡红边框，与暂停按钮形成危险倾向区分
2. **设计令牌集中化**：所有色彩/字号/圆角/间距/按钮层级令牌定义在 `theme.py` 的模块级常量，`__all__` 显式导出。QSS 通过 `string.Template.substitute(QSS_TOKENS)` 替换占位符，禁止 QSS 内硬编码色值。令牌覆盖 53 项：色彩 18、排版 7、间距 5、圆角 3、按钮层级 12、其他 8。
3. **配色策略**：沿用 GitHub Desktop 浅色背景 + 主色蓝（#40a9ff）+ 中性灰，便于后续主题切换。选中态 `COLOR_PRIMARY_DARK`（#096dd9）与主色拉大对比（L*8、a*4），避免视觉过近。控件级 `selection-background-color` 强制选中项深蓝底白字，无论是否有焦点。
4. **回退 iter-83 的规则修改**（用户授权）：rule-12-pyside-dev.md 重新写入"颜色、尺寸在 theme.py 定义，QSS 用 `${TOKEN}` 引用，禁止硬编码"约束，详细参考段落注明 fuscan 采用 SKILL 中的令牌/QSS 系统。
5. **app.py 容错加载**：`load_stylesheet()` 在 QSS 缺失或令牌不匹配时记录 warning 并返回空串，不阻塞应用启动（回退 Qt 原生样式）。捕获 `(OSError, ValueError, KeyError)` 三类预期异常。
6. **styles.qss 打包**：在 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel.force-include]` 添加 `src/fuscan/gui/styles.qss` → `fuscan/gui/styles.qss`，确保 wheel 包含样式资源。
7. **about_dialog.py PySide 兼容**：PySide6 下 `QDialog` 基类被 pyrefly 误判为 `invalid-inheritance`，加 `# pyrefly: ignore [invalid-inheritance]` 抑制；导入改 `try PySide2 except PySide6` 双版本兼容。

## 改动文件清单

新增：
- `src/fuscan/theme.py`：设计令牌集中定义（53 个常量 + QSS_TOKENS 字典）
- `src/fuscan/gui/styles.qss`：现代风格 QSS（770 行，覆盖全部控件类型）
- `.trae/req/req-21-现代QSS与按钮差异化.md`：本次需求记录

修改：
- `src/fuscan/gui/app.py`：新增 `load_stylesheet()`、`_QSS_PATH` 常量；`launch()` 调用 `app.setStyleSheet(load_stylesheet())`；`__all__` 加入 `load_stylesheet`
- `src/fuscan/gui/about_dialog.py`：PySide2/6 兼容导入、`Optional[QWidget]` 类型注解、`invalid-inheritance` 抑制
- `src/fuscan/gui/main_window.ui`：主操作按钮 minimumSize 200x48 / 180x48；次要按钮 140x40 / 0x40；辅助按钮依赖 QSS 兜底
- `tests/test_gui.py`：新增 `TestThemeAndStylesheet`（5 个测试：令牌覆盖、值类型、层级差异、QSS 替换、容错处理）；调整 `test_about_dialog` mock `AboutDialog.show()`；`test_setup_btn_spacer_removed` 重命名断言 `setup_btn_leading_spacer`
- `pyproject.toml`：`force-include` 添加 `src/fuscan/gui/styles.qss`
- `.trae/rules/rule-12-pyside-dev.md`：恢复令牌与 QSS 强制约束，记录三级按钮层级差异化设计要求

## 代码实现情况

- **theme.py**：`__all__` 排序列出 53 个令牌常量；色彩 18 项（PRIMARY/PRIMARY_DARK/PRIMARY_DARKER/ACCENT/DANGER/DANGER_DARK/WARNING/INFO/TEXT_*/BG_*/BORDER_*/SPLITTER_*），排版 7 项（FONT_FAMILY/FONT_FAMILY_MONO + 5 级字号），间距 5 项（XS~XL，8px 基准网格），圆角 3 项（SM 4px / MD 6px / LG 8px），按钮层级 12 项（高度/字号/padding/圆角 ×3 级 + 字重）；`QSS_TOKENS` 字典与 `__all__` 一一对应。
- **styles.qss**：按区块组织（全局基础/头部栏/侧边栏/内容容器/分组框/菜单栏/状态栏/扫描模式/盘符按钮/L1-L3 按钮/输入控件/进度条/标签/树列表/选项卡/滚动条/分隔符/工具提示/对话框按钮盒），所有色值/尺寸引用 `${TOKEN}` 占位符。
- **app.py**：`load_stylesheet()` 使用 `string.Template.substitute()` 替换占位符，比 `safe_substitute()` 更严格——任何未定义令牌立即抛 `KeyError` 被捕获并 warning。
- **main_window.ui**：`scan_btn`/`view_results_btn` minimumSize 200x48；`rescan_btn`/`export_btn` 180x48；`pause_resume_btn`/`cancel_btn` 140x40；`select_path_btn` 0x40（宽度由布局伸展）。
- **测试**：`TestThemeAndStylesheet` 5 个用例覆盖令牌完整性（`__all__` 与 `QSS_TOKENS` 一一映射）、值类型（全部 str）、层级差异（48 > 40 > 32 / 8 > 6 > 4）、QSS 替换（无残留 `${`）、容错（缺失/无效模板返回空串）。

## 整合优化情况

- 修复 `about_dialog.py` 既有 PySide 兼容性问题（之前 iter 引入但未完全处理 PySide6 路径）。
- 修复 `tests/test_gui.py` 中 `test_about_dialog` 依赖 `QMessageBox.about` 的过时断言，改 mock `AboutDialog.show()`。
- 重命名 `main_window.ui` 中 spacer 为 `setup_btn_leading_spacer`，使测试断言更具语义。

## 测试验证结果

- ruff check src tests：**All checks passed**
- ruff format --check src tests：**104 files already formatted**
- pyrefly check：**0 errors**（554 suppressed, 62 warnings not shown）
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1587 passed**，覆盖率 **95.15%**（≥ 95% 阈值，高于 iter-83 的 95.05%）
- 新增的 `TestThemeAndStylesheet` 5 个用例全部通过；`theme.py` 覆盖率 100%。

## 遗留事项

- 暗色主题切换：当前仅浅色主题，未来可扩展为多主题（通过切换 `QSS_TOKENS` 字典实现）。
- QSS 不支持 transition 动画，hover/pressed 状态切换为瞬时，与原生 Qt 行为一致。
- `regex_tester.py` 的 HTML 速查表仍使用内联色值（iter-83 改动），未引用 theme 令牌——HTML 内联样式无法直接引用 Python 常量，保持现状。

## 下一轮计划

无。本次需求已完成，等待用户实测确认 GUI 视觉效果。
