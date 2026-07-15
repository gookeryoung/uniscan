# 需求10：rule-12 PySide 开发规范合规整改

- [x] 1. 跨线程槽函数加 `@Slot()` 装饰器（`_on_scan_cancelled`/`_on_scan_progress`/`_on_scan_finished`/`_on_scan_failed`）。
- [x] 2. 内联 QSS 提到 theme：`rule_editor.ui` 的 `#editor` 等宽字体从硬编码改为 `FONT_FAMILY_MONO` 令牌，删除内联 `styleSheet` 属性。
- [x] 3. `.qrc` 资源系统改造：19 个 SVG 图标纳入 `resources.qrc`，编译为 `resources_rc.py`（双兼容 PySide2/PySide6），图标引用改为 `:/` 前缀，`_load_themed_icon` 支持 `QFile` 读取资源。
- [x] 4. Model/View 迁移评估：仅 `result_tree` 符合"大数据量"，当前 `setUpdatesEnabled` + 300ms 防抖节流已足够；完整迁移需 500+ 行重构 + 改 `.ui`，高回归风险，按 rule-01"避免过度工程化"延迟至万级文件性能瓶颈。
