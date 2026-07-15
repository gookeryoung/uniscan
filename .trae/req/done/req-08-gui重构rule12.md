# 需求：GUI 按 rule-12 重构界面设计

## 核心需求

- [x] 按 rule-12-gui-pyside-standards.md 重构 GUI 布局为 HeaderBar + Sidebar + Content + StatusBar 四区结构
- [x] 新增 `theme.py` 集中管理设计令牌（色彩/排版/间距/圆角/尺寸），禁止散落硬编码
- [x] `styles.qss` 改用 `${TOKEN}` 占位符模板化，由 `string.Template.substitute()` 替换
- [x] Header 区含 3 个 Tab（扫描/规则管理/扫描历史）+ 右侧通用功能按钮（设置/关于）
- [x] 扫描 Tab 内含 Sidebar（配置/扫描中/结果 三项）+ main_stack 三页工作流
- [x] 规则管理与扫描历史移入独立 Tab 页
- [x] 严格保留全部既有功能与测试（零回归）

## 设计令牌

- [x] 色彩令牌沿用现有 GitHub Desktop 配色（COLOR_PRIMARY=#0366d6），偏离 rule-12 表格 #0887A0
- [x] 37 个令牌常量 + QSS_TOKENS 字典
- [x] `detail_dialog.py`/`main_window.py` 的 `_SEVERITY_COLORS` 引用 theme 常量

## 兼容性约束

- [x] 保留 QMenuBar（file_menu/scan_menu/help_menu）与 HeaderBar 并存，测试依赖菜单对象
- [x] 保留 `_main_stack` QStackedWidget 及 setup/scanning/results 页序不变（38 处 currentIndex 断言）
- [x] 保留全部 `_ui` 属性名不变（rules_group/history_list/target_group 等）
- [x] PySide2/PySide6 双兼容导入

## 验收标准

- [x] ruff check + ruff format --check 通过
- [x] pyrefly check 0 错误
- [x] pytest 全套通过，覆盖率 ≥ 96%
- [x] 3 个新增测试（sidebar 同步/header Tab 切换/sidebar 阶段切换）全部通过
