更新日志
=========

v0.1.8
------

- **feat**：扫描中断加速——取消时对未启动 future 调 ``cancel()`` 跳过 ``as_completed`` 阻塞，配合大文件跳过将单 worker 阻塞上限控制在百毫秒级
- **feat**：新增大文件跳过阈值配置（默认 100MB），超过阈值的文件不读取内容避免卡死；0 表示不限制，缓存/非缓存/archive 三种模式一致生效
- **feat**：新增 7Z 压缩包扫描支持，基于 py7zr 纯 Python 库，跨平台无需系统工具；采用 ``readall()`` 预读缓存避免多次调用 ``read()`` 触发死锁
- **feat**：规则编辑器新增正则表达式验证面板——速查手册（字符类/量词/锚点/分组/零宽断言/常用示例）、测试文本输入、命中位置与捕获组显示、大小写敏感性切换
- **fix**：修复 ``_scan_entry_uncached`` 未应用 ``max_file_size`` 导致非缓存模式不跳过大文件内容
- **fix**：修复 ``scan_archives=True`` 时 ``ignore_extensions`` 未剔除已注册 archive 扩展名导致压缩包被 walker 过滤

v0.1.7
------

- **feat**：新增 PDF/Excel 导出功能，覆盖 CLI/GUI/数据层三入口
- **feat**：扫描中页新增分类统计面板（已通过/命中/跳过/错误）与命中文件双击定位
- **feat**：数据层增强，支持 AND/OR 多命中标记与 match 描述字段
- **feat**：优化结果列表筛选性能（300ms 防抖 + ``setUpdatesEnabled(False)`` 批量插入）
- **style**：美化 QSplitter 颜色令牌（独立 ``COLOR_SPLITTER`` 不复用 ``COLOR_BORDER``）
- **fix**：修复命中详情对话框反复打开卡死问题，新增窗口图标
- **docs**：新增 PySide 开发规范文档（rule-12-pyside-dev.md）

v0.1.6
------

- **feat**：新增用户手册 PDF（reportlab + STSong-Light CID 字体），GUI 帮助菜单 F1 打开随包 PDF
- **feat**：新增 RTF/EML/MSG/XLS/DOC/PPT 六种文件格式提取器
- **feat**：新增 JSON 导出能力
- **perf**：缓存优化——切换 BLAKE2b + LRU 命中缓存 + mtime 预筛，热缓存吞吐量提升约 36 倍
- **perf**：扫描优化——批量写入 + archive 并行 + 提取内容缓存 + 大小文件分流哈希，单线程吞吐提升 24%
- **refactor**：下沉业务逻辑到数据层，统一报告与 UI 展示逻辑
- **refactor**：精简 ``main_window.py`` UI 设计，迁移静态属性到 .ui 并拆分 ``_configure_ui``
- **refactor**：``detail_dialog`` / ``rule_editor`` / ``settings_dialog`` 改为多继承模式
- **chore**：重构项目配置管理，拆分工具链配置到独立文件（ruff.toml/pyrefly.toml/pytest.ini/.coveragerc/.bumpversion.toml/uv.toml）

v0.1.5
------

- **feat**：命中规则表支持点击行跳转高亮并增加位置数列
- **feat**：增加匹配条数字段区分命中规则数与实际匹配处数
- **feat**：增加盘符图标尺寸配置项并优化 UI 布局
- **fix**：修复数据库连接串与 Bearer 令牌详情定位失败
- **fix**：``QDialog``/``QApplication`` 回退为 ``exec_()`` 以兼容 PySide2
- **fix**：PySide2/PySide6 双兼容导入以支持 Python 3.11+
- **chore**：统一项目中 PySide 相关的命名表述

v0.1.4
------

- **feat**：严重等级颜色区分与中文标签
- **feat**：扫描进度界面与严重等级背景色增强
- **feat**：接入按钮/菜单图标，新增系列图标资源
- **refactor**：``ignore_dirs`` / ``ignore_extensions`` 全局化迁移并优化扫描性能
- **refactor**：重构主窗口为工作流阶段化三页切换布局
- **refactor**：精简主窗口界面，新增右键菜单与快捷键
- **style**：优化扫描按钮位置与配色，调整主窗口尺寸与控件布局属性

v0.1.3
------

- **refactor**：完善 pyrefly 类型检查、测试覆盖率与文档
- **style**：替换 typing 模块大写类型为小写内置类型

v0.1.2
------

- **feat**：新增设置对话框功能并优化界面
- **feat**：添加扫描配置项与设置对话框，支持自定义扫描参数
- **feat**：盘符按钮用 hard_disk 图标 + 字母，目标选择区改用 ``QStackedWidget`` 稳定布局
- **feat**：增加高分辨率 DPI 支持，兼容 WIN7 低分辨率
- **refactor**：完成项目重命名为 fuscan
- **refactor**：GUI 主窗口重构为 GitHub Desktop 5 区布局
- **refactor**：GUI 界面改用 .ui 文件构建，QSS 迁移到独立文件
- **refactor**：适配 ``QGroupBox`` 分组布局，统计信息移至状态栏
- **fix**：补充遗漏的 hard_disk.svg 图标资源，修复 main_window.ui alignment 属性错误

v0.1.1
------

- 项目工程化基础：copier 模板初始化、CI/CD 配置、tox 多版本测试
- 内置通用规则与示例规则脚本

v0.1.0
------

- 项目初始化
