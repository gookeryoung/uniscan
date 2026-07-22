# iter-64：问题修复与 QML 改造计划（req-14）

## 需求清单

来源：`.trae/req/req-14-问题修复.md`

- [x] R1：选中的列表项目有时是黑色字体，有时又是白色字体，请统一为白色字体
- [x] R2：项目能否通过 qml 进行界面美化设计，请制定计划

## 迭代目标

R1 定位并修复列表选中态字体颜色不一致问题；R2 客观评估 QML 改造的可行性、
成本与收益，给出推荐方案与渐进式计划（仅产出计划文档，不实施改造）。

## R1 根因分析

### 现象

用户感知：列表/树/表格选中项的字体颜色"有时黑色、有时白色"。

### 根因

**根因 A（QSS 层配色低对比度）**：

`styles.qss` 中 4 处 `::item:selected` 选择器把选中态配色设为：

- `background: ${COLOR_BG_SELECTED}` → `#f1f8ff`（浅蓝）
- `color: ${COLOR_PRIMARY}` → `#40a9ff`（亮蓝）

浅蓝背景配亮蓝字对比度低（WCAG AA 不达标），视觉感受不稳定，在不同
DPI/系统主题下可能被感知为"非白"或近似黑色。

侧边栏 `QListWidget#sidebar::item:selected` 未显式设 `color`，继承自
`QListWidget#sidebar` 的 `color: ${COLOR_TEXT_ON_PRIMARY}`（白）+ 深蓝
背景——视觉清晰、是用户期望的"白字"效果。

**根因 B（代码层 setForeground 覆盖 QSS 选中态）**：

`result_tree.py` / `detail_panel.py` / `main_window.py` 中
`_apply_severity_to_*` 函数对 severity 列通过 `setForeground()` 设置
红/橙/蓝色。Qt 中显式 `setForeground` 会覆盖 QSS `::item:selected` 的
`color`——导致选中时该列字体颜色仍保持红/橙/蓝色，不变白。

### 修复方案

1. **styles.qss**：4 处 `::item:selected` 改为
   `background: ${COLOR_PRIMARY_DARK}; color: ${COLOR_TEXT_ON_PRIMARY};`
   （深蓝底+白字，与侧边栏一致）
2. **代码层**：移除 severity 列的 `setForeground` 调用，保留 `setBackground`
   表达严重等级颜色编码；让 QSS `::item:selected` 的 `color` 在选中态生效
3. **死代码清理**：`SEVERITY_COLORS` 常量无任何使用方，按 rule-01
   "不为未来预留扩展点"原则删除

### 副作用与权衡

- 未选中态：severity 列从"浅底+红/橙/蓝字"变为"浅底+黑字"
  （`COLOR_TEXT_PRIMARY` 由 `QTreeWidget` 的 `color` 令牌提供）
- 实际改善：浅底深字对比度高于原"浅底+彩色字"，可读性提升
- 严重等级颜色编码通过背景色仍能一眼区分（浅红/浅橙/浅蓝）

## R2 QML 改造计划

### 现状评估

| 维度 | 现状 |
|------|------|
| 技术栈 | PySide2 + QSS + .ui 文件（pyside2-uic 编译为 .py） |
| 迭代次数 | 63 轮，代码稳定 |
| UI 结构 | 表单 + 列表 + 树形结果 + 详情面板，桌面工具型应用 |
| 视觉风格 | GitHub Desktop 风格，QSS 令牌化（`theme.py` + `styles.qss`） |
| 自定义控件 | `ResultTreeView`（QTreeView 子类）、`ScanListUpdater` 等 |

### QML 适配性分析

**QML 优势**：

- GPU 加速动画（启动 Loading、扫描进度、结果切换过渡）
- 自定义视觉特效更灵活（圆角/阴影/渐变/模糊）
- 跨平台视觉一致性更高（不依赖系统 QWidget 风格）
- 声明式 UI 更易维护复杂布局

**QML 劣势（针对 fuscan）**：

- 与 QWidget 工具链不兼容：`.ui` 文件、QSS、`QStyledItemDelegate`、
  `QStandardItemModel` 不能直接复用，需全部重写
- PySide2 的 QML 调试工具链弱（PySide6 改善但仍不及 QWidgets 成熟）
- 表单+列表+树形结果的桌面工具应用 QML 收益有限——动态动画并非核心需求
- 全量重写风险高：63 轮迭代积累的功能（扫描/缓存/压缩包/规则编辑/
  导出/详情面板/快捷键/上下文菜单等）需逐一验证，回归测试代价大
- 团队学习成本：QML/QtQuick 生态与 Python+QWidget 差异大

### 推荐方案：不推荐全量 QML 重写

**理由**：

1. fuscan 作为表单+列表+树形结果的桌面扫描工具，当前 QSS+QWidget 方案
   已能良好满足视觉与交互需求，无核心功能瓶颈
2. QML 的核心优势（动态动画、移动端适配、自定义视觉特效）非 fuscan
   核心诉求
3. 全量重写的投入产出比低：工作量等同于新建项目，但功能需对齐现有
   63 轮迭代成果
4. PySide2 已停止维护（最后版本 5.15.2.1，无 Python 3.11+ wheel），
   未来迁移 PySide6 时可同步评估 QML，当前不建议引入新依赖

### 备选方案：局部 QML 增强（可选，低优先级）

若未来确有视觉增强需求，可考虑局部嵌入 QML（不重写主架构）：

**阶段 1（评估，1 个迭代）**：

- 试点：用 `QQuickWidget`（PySide2/PySide6 均支持）在"关于"对话框
  嵌入一个 QML 动画（如版本号渐显 + 图标动效），评估 QML 与现有
  QWidget 混合的可行性、性能与维护成本
- 验证：QML 渲染是否正常、与 QSS 主题是否冲突、打包体积影响

**阶段 2（若阶段 1 验证通过）**：

- 扫描中页进度条改用 QML 动画（环形进度 + 数字滚动）
- 结果统计面板改用 QML 图表（命中数/严重等级分布饼图）
- 启动 Loading 动画（品牌 logo + 扫描准备动效）

**阶段 3（不推荐，仅作记录）**：

- 主框架迁移至 QML（QQuickView 替代 QMainWindow）——需重写全部 UI，
  等同于新建项目，仅在 fuscan 全面重构时考虑

### 推荐执行路径

**当前迭代不实施 QML 改造**。若用户希望提升视觉体验，建议优先：

1. **QSS 主题增强**（低成本）：在现有 `theme.py` + `styles.qss` 基础上
   增加微动画（`QPropertyAnimation`）、卡片阴影（`QGraphicsDropShadowEffect`）、
   悬浮态过渡（QSS `:hover` 已有，可加 `transition` 但 Qt QSS 支持有限）
2. **深色主题**（中成本）：`theme.py` 已令牌化，新增暗色令牌集 + 运行时
   切换，比 QML 改造性价比更高
3. **关键交互动画**（中成本）：阶段切换、详情面板展开/收起等用
   `QPropertyAnimation` 平滑过渡，无需 QML

## 改动文件清单

### 修改文件

| 文件 | 说明 |
|------|------|
| `src/fuscan/gui/styles.qss` | R1：4 处 `::item:selected`（`QListWidget`/`QTreeWidget`/`QTreeWidget#result_tree`/`QTableWidget`）配色改为 `${COLOR_PRIMARY_DARK}` 深蓝底 + `${COLOR_TEXT_ON_PRIMARY}` 白字，与侧边栏一致 |
| `src/fuscan/gui/result_tree.py` | R1：`_apply_severity_to_standard_item` 移除 `setForeground` 调用，避免覆盖 QSS 选中态白字；调整 docstring 说明 |
| `src/fuscan/gui/detail_panel.py` | R1：`_apply_severity_to_table_item` 移除 `setForeground` 调用；移除 `SEVERITY_COLORS` 导入 |
| `src/fuscan/gui/main_window.py` | R1：`_apply_severity_to_tree_item` 移除 `setForeground` 调用；移除 `SEVERITY_COLORS` 导入 |
| `src/fuscan/gui/preview_utils.py` | R1：删除无使用方的 `SEVERITY_COLORS` 常量与 `__all__` 条目；移除不再使用的 `theme` 导入；补充 `SEVERITY_BACKGROUNDS` 注释说明 |
| `.trae/req/req-14-问题修复.md` | R1 标记完成 |

### 新建文件

| 文件 | 说明 |
|------|------|
| `.trae/docs/iter-64-问题修复.md` | 本迭代记录（含 R2 QML 改造计划） |

## 关键决策与依据

### 决策1：选中态配色与侧边栏对齐（COLOR_PRIMARY_DARK + 白字）

经评估，侧边栏选中态（深蓝底+白字）是项目既有约定，用户期望"统一为白色字体"
即与此对齐。采用 `COLOR_PRIMARY_DARK`（#096dd9）而非 `COLOR_PRIMARY`
（#40a9ff）作为选中背景，对比度更高（白字在深蓝底上 WCAG AAA 达标）。

### 决策2：移除 setForeground 而非引入 QStyledItemDelegate

`QStyledItemDelegate` 可在选中态时覆盖前景色，保留 severity 列未选中态的
彩色字。但：

- 增加 4 个 delegate 子类（QTreeWidget×2 + QTableWidget×1 + 复用 1 个）
- 严重等级颜色编码已通过 `setBackground` 表达，前景色非必需
- 移除 `setForeground` 后未选中态变为"浅底+黑字"，对比度反而提升

按 rule-01 "避免代码膨胀"原则，选择更简方案。

### 决策3：不实施 QML 改造，仅制定计划

R2 用户提"能否通过 qml 进行界面美化设计，请制定计划"——按字面理解是
"制定计划"而非"立即实施"。经客观评估，fuscan 作为桌面工具型应用，
QML 改造投入产出比低，建议优先 QSS 主题增强。详细分析见上文 R2 章节。

## 代码实现情况

- R1：`styles.qss` 4 处 `::item:selected` 配色统一为深蓝底+白字
- R1：3 处 `_apply_severity_to_*` 移除 `setForeground` 调用
- R1：`SEVERITY_COLORS` 死代码清理（preview_utils.py + 3 处 import）
- R2：本迭代记录文档包含完整 QML 改造计划

## 整合优化情况

- 修复了选中态字体颜色不一致问题（QSS 配色 + setForeground 覆盖）
- 删除 `SEVERITY_COLORS` 死代码（按 rule-01 "不为未来预留扩展点"）
- 移除 preview_utils.py 中不再使用的 `theme` 导入（ruff F401 规避）

## 测试验证结果

- ruff check：全部通过
- ruff format --check：93 files already formatted
- pyrefly check：0 errors（463 suppressed, 58 warnings not shown）
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：1419 passed, 16 deselected, 覆盖率 96.05%
- 测试调整：3 个 `TestSeverityDisplay` 测试由断言 `foreground()` 改为断言 `background()`，反映"前景色由 QSS 选中态接管"的新行为

## 遗留事项

- R2 的 QML 改造计划已制定但未实施——按当前评估不推荐全量重写，
  若用户确认需要局部 QML 增强（如启动动画/进度动画），可单独立项

## 下一轮计划

- 无（req-14 R1 完成，R2 已制定计划，全门禁通过）
