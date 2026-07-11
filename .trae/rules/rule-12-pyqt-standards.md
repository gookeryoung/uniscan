# PySide2/PySide6 (Qt5/Qt6) GUI 开发规范

适用于 `project_type=gui` 的生成项目。在 `rule-11-python-standards.md` 基础上补充 Qt 桌面应用特有的约束。

模板按 Python 版本自动区分绑定：`PySide2`（Python ≤ 3.10）/ `PySide6`（Python ≥ 3.11），代码须双兼容。

## 工具链

| 工具 | 配置要点 |
|------|---------|
| PySide2 | `>=5.15.2.1`，Qt5 官方绑定（LGPL），仅支持 Python 3.6-3.10 |
| PySide6 | `>=6.5.0`，Qt6 官方绑定（LGPL），支持 Python 3.8+，3.11+ 环境必选 |
| pytest-qt | `>=4.2.0`，Qt 测试框架（qapp/qtbot fixture），同时兼容两代绑定 |
| PyInstaller | `>=6.0`，打包为可执行文件 |
| pyside2-rcc / pyside6-rcc | 资源编译器（.qrc → _rc.py），按已安装绑定使用 |
| pyside2-uic / pyside6-uic | UI 编译器（.ui → .py），按已安装绑定使用 |

验证（每次修改后）：

```bash
uv run ruff check src tests
uv run pytest -m "not slow" --cov=uniscan --cov-fail-under=95
uv run pytest -m "not slow" --gui  # 若启用 GUI 测试标记
```

## 兼容性（关键约束）

### 版本与依赖

- **PySide2 仅支持 Python 3.6-3.10**：PyPI 官方 wheel 最新 `5.15.2.1`，无 Python 3.11+ wheel。
- **PySide6 支持 Python 3.8+**：3.11+ 环境下 PySide2 不可用，必须用 PySide6。
- **依赖声明**（模板自动生成，勿手改）：

```toml
dependencies = [
    "PySide2>=5.15.2.1; python_version <= '3.10'",
    "PySide6>=6.5.0; python_version >= '3.11'",
]
```

pip/uv 按 Python 版本只安装其中一个，不会同时安装。

### API 差异速查

| 场景 | PySide2 (Qt5) | PySide6 (Qt6) |
|------|---------------|---------------|
| 事件循环 | `app.exec_()` | `app.exec()`（`exec_` 已弃用） |
| 对齐枚举 | `Qt.AlignCenter` | `Qt.AlignmentFlag.AlignCenter` |
| 方向枚举 | `Qt.Horizontal` | `Qt.Orientation.Horizontal` |
| 键盘修饰 | `Qt.ControlModifier` | `Qt.KeyboardModifier.ControlModifier` |
| 窗口标志 | `Qt.Window` | `Qt.WindowType.Window` |
| 鼠标按钮 | `Qt.LeftButton` | `Qt.MouseButton.LeftButton` |
| itemDataRole | `Qt.DisplayRole` | `Qt.ItemDataRole.DisplayRole` |
| 拖放动作 | `Qt.CopyAction` | `Qt.DropAction.CopyAction` |

### 双兼容编码模式

import 用 try/except 兼容；枚举在高版本绑定用全路径，低版本用短名（PySide2 不支持命名空间写法）：

```python
try:
    from PySide2.QtWidgets import QApplication, QLabel
    from PySide2.QtCore import Qt, Signal, Slot
except ImportError:
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtCore import Qt, Signal, Slot
```

事件循环兼容写法（PySide2 无 `exec`，PySide6 推荐 `exec`）：

```python
run = app.exec if hasattr(app, "exec") else app.exec_
return run()
```

枚举兼容：若代码需跨版本运行，用短名 `Qt.AlignCenter`（两代均支持短名，PySide6 仅发 DeprecationWarning）；若仅 PySide6 则用全路径。

## 模块与入口

- 入口 `src/uniscan/main.py`：`QApplication(sys.argv)` → 构建主窗口 → 事件循环（见上兼容写法）。
- `main()` 加 `# pragma: no cover`（事件循环阻塞，难自动化），拆出 `create_main_window()` 等可测函数。
- 业务逻辑放纯 Python 模块（不 import PySide），便于单测；GUI 层只做信号槽连接与状态展示。
- 惰性导入重型部件（QWebEngineView 等）以加快启动。

## 界面布局（GitHub Desktop 风格）

主窗口顶层布局采用 GitHub Desktop 风格，自上而下分为 5 个区域：

```
┌────────────────────────────────────────────────────────┐
│ ① 菜单栏（QMenuBar）                                    │
├────────────────────────────────────────────────────────┤
│ ② 主操作区（按业务流程组织核心操作）                      │
├──────────────────────┬─────────────────────────────────┤
│ ③ 列表区             │ ④ 详情区                        │
│ ┌──────────────────┐ │ ┌─────────────────────────────┐ │
│ │ Tab 切换栏       │ │ │ 操作栏（空态/非空态切换）   │ │
│ │ (QTabWidget)     │ │ │                             │ │
│ ├──────────────────┤ │ ├─────────────────────────────┤ │
│ │ 列表（虚拟化）   │ │ │ 详情主体                    │ │
│ │                  │ │ │ （空态引导/命中预览）       │ │
│ ├──────────────────┤ │ │                             │ │
│ │ ⑤ 底部操作区    │ │ │                             │ │
│ │ （输入框+按钮组）│ │ │                             │ │
│ └──────────────────┘ │ └─────────────────────────────┘ │
└──────────────────────┴─────────────────────────────────┘
```

5 个区域职责：

1. **菜单栏**：按业务域分组的菜单项。
2. **主操作区**：按业务流程组织的核心操作（模式/目标/规则/扫描按钮/进度/统计）。
3. **列表区**：Tab 切换多视图 + 虚拟化列表 + 底部操作区。
4. **详情区**：操作栏（两态切换）+ 详情主体（空态引导/命中预览）。
5. **底部操作区**：列表区底部的输入框 + 按钮组。

### ① 顶部菜单栏

- 菜单按业务域分组（如「文件」「扫描」「视图」「帮助」），每组内 action 按操作粒度排序。
- 菜单 action、工具栏 action、快捷键必须复用同一 `QAction` 实例，禁止重复创建同名 action。
- 菜单项文案用 `self.tr(...)` 包裹（见「国际化」章节），禁止硬编码中文。

### ② 主操作区

- 位于菜单栏下方，承载按业务流程组织的核心操作（如扫描模式选择、目标路径、规则加载、扫描按钮、进度条、统计标签）。
- 高度固定、不随列表区滚动；用 `QVBoxLayout` 自上而下排列各操作行。
- 扫描进行中此处展示进度与统计，不切换为其他页面；扫描按钮在同一位置切换「开始/暂停/继续」文本。
- 主操作区用 `QFrame` 包裹并设置 objectName（如 `controlArea`），供 QSS 选择器定位。

### ③ 列表区（左侧）

- 顶部用 `QTabWidget` 切换不同视图（如「扫描结果」「规则文件」「扫描历史」），每个 Tab 持有独立列表部件与独立选中态。
- 列表大数据必须用 `QAbstractItemView` + 自定义 Model（`QAbstractListModel`/`QAbstractTableModel`），禁止 `QListWidget`/`QTreeWidget` 逐项 `add`（见「性能」章节）。
- Tab 切换不破坏当前选中态；跨 Tab 选中态独立持久化到 `QSettings`（如 `list/current_index_<tab>`）。
- 列表项双击或选中变化触发详情区更新（通过信号槽连接到详情区 controller）。

### ⑤ 列表区底部操作区

- 固定在列表区底部、不随列表滚动；与 Tab 切换栏、列表一起用 `QVBoxLayout` 排列：Tab 切换栏（`stretch=0`）+ 列表（`stretch=1`）+ 底部操作区（`stretch=0`）。
- 必须包含两类控件：
  - **提交信息类多行输入框**（`QPlainTextEdit`）：对应 GitHub Desktop 左下角 commit message 输入框，用于备注/批注/导出说明等。
  - **按钮组**（`QHBoxLayout`）：主操作按钮（如「导出」「批量处理」「应用」），与列表选中项联动，无选中时禁用。
- 输入框与按钮组用 `QFrame` 包裹并设置 objectName（如 `listActionBar`），供 QSS 选择器定位。
- 按钮顺序遵循「主操作靠右、辅助操作靠左」约定，主操作按钮用主色高亮（见「样式约束」）。

### ④ 详情区上部操作栏

- 紧贴详情区顶部，用 `QStackedWidget` 持久化两个页面，**禁止**动态 `add/remove` 控件：
  - **空态页**（详情内容为空）：显示全局操作，如「开始扫描」「加载规则」「查看历史」等引导按钮。
  - **非空态页**（选中具体项）：显示针对当前详情的操作，如「定位命中」「上一条/下一条」「打开文件位置」「复制路径」。
- 两态切换通过 `setCurrentIndex(0/1)` 触发，不重建控件实例；切换由列表选中变化信号驱动。
- 操作栏用 `QFrame` 包裹并设置 objectName（如 `detailActionBar`），供 QSS 选择器定位。

### ④ 详情区主体

- 空态显示引导文案 + 占位图标（如「未选中任何项」「请先开始扫描」），用 `QStackedWidget` 持久化空态/非空态两个页面。
- 非空态展示命中详情、命中位置上下文预览、前后命中跳转；命中位置高亮用 `QTextBrowser` 或自定义 `paintEvent`。
- 详情区主体与操作栏一起用 `QVBoxLayout` 排列：操作栏（`stretch=0`）+ 主体（`stretch=1`）。

### 分割器与伸缩

- 主分割器左右分栏用 `QSplitter(Qt.Horizontal)`，左:右默认比例 2:3，比例持久化到 `QSettings`（见「状态与配置」章节）。
- 列表区内部用 `QVBoxLayout`：Tab 切换栏（`stretch=0`）+ 列表（`stretch=1`）+ 底部操作区（`stretch=0`）。
- 详情区内部用 `QVBoxLayout`：操作栏（`stretch=0`）+ 主体（`stretch=1`）。
- 窗口尺寸策略：主窗口 `QSizePolicy.Expanding`；主操作区与底部操作区高度固定，列表与详情区随窗口伸缩。

### 样式约束（GitHub Desktop 配色）

- 配色：背景 `#f6f8fa`（中性灰），主色 `#0366d6`（蓝），危险色 `#d73a49`（红），边框 `#e1e4e8`。
- 字体层级：主操作按钮 14px > 列表项 13px > 详情正文 13px > 辅助说明 12px；标题加粗。
- QSS 选择器粒度到 objectName（如 `QPushButton#scanBtn`），禁止全局限定（见「样式（QSS）」章节）。
- 空态引导文案用 `QLabel` + 居中对齐 + 次要色 `#586069`。

## 信号槽

- 用新式信号槽，**禁用**旧式字符串 `SIGNAL/SLOT` 语法。
- 信号定义为类属性：

```python
from PySide2.QtCore import Signal  # 或 from PySide6.QtCore import Signal


class MainWindow(QMainWindow):
    value_changed = Signal(int)  # 类属性，不是实例属性
```

- 连接用方法引用：`button.clicked.connect(self._on_clicked)`，类型安全且可静态检查。
- 避免重复连接同一槽（多次 connect 会多次触发）；disconnect 时用 `try/except RuntimeError`（连接已断开会抛错）。
- 跨线程信号默认 `Qt.AutoConnection`（运行时判定直连/队列）；显式指定 `Qt.QueuedConnection` 用于 worker→UI 通信。

## 布局

- 优先 `QVBoxLayout`/`QHBoxLayout`/`QGridLayout`/`QFormLayout`，**禁用绝对定位** `setGeometry`（除固定尺寸弹窗）。
- 嵌套布局用 `addLayout()`，部件用 `addWidget()`。
- 伸缩比通过 `addWidget(widget, stretch=N)` 或 `addStretch()` 控制。
- 窗口尺寸策略用 `setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)`。
- 响应式布局用 `QSplitter` 而非固定比例。

主窗口顶层布局结构见《界面布局（GitHub Desktop 风格）》章节。

## 资源系统

- `.qrc` 文件管理图标/样式表/翻译等静态资源，编译为 `_rc.py`：

```bash
pyside2-rcc resources.qrc -o src/uniscan/resources_rc.py  # PySide2
pyside6-rcc resources.qrc -o src/uniscan/resources_rc.py  # PySide6
```

- 引用资源用 `:/` 前缀：`QIcon(":/icons/app.png")`，路径前缀在 `.qrc` 的 `<qresource prefix="/">` 定义。
- `.ui` 文件可用 `pyside2-uic`/`pyside6-uic` 编译或运行时 `QUiLoader` 加载；编译方式更快，推荐。
- 资源变更后须重新编译 `_rc.py`，加入版本控制（避免构建环境缺 rcc 工具链）。
- 大文件（视频/字体）不进 `.qrc`，用磁盘路径加载，避免二进制膨胀。

## 事件循环

- `QApplication` 全局单例，`sys.argv` 传入（解析 Qt 命令行参数如 `-style`）。
- 事件循环阻塞直至窗口关闭或 `app.quit()`（见兼容性段的 exec 写法）。
- 长任务**禁止在主线程执行**（会冻结 UI），用 `QThread` 或 `QThreadPool` + `QRunnable`。
- 定时器用 `QTimer.singleShot(ms, callback)` 或 `QTimer(timeout=callback).start(ms)`，不用 `time.sleep`。
- 事件过滤器：`obj.installEventFilter(self)` + 重写 `eventFilter()`，优先于子类化。

## QThread 线程

两种模式，按场景选择：

1. **Worker 模式（推荐）**：QObject 子类化，`moveToThread(thread)`，信号槽跨线程通信。
2. **子类化模式**：重写 `QThread.run()`，用 `self.start()` 启动，`finished` 信号通知结束。

```python
class Worker(QObject):
    progress = Signal(int)

    @Slot()
    def do_work(self) -> None:
        for i in range(100):
            self.progress.emit(i)
        # 不要在此操作 UI 部件
```

- **禁止在非主线程操作 GUI 部件**（QLabel.setText 等），只通过信号回主线程更新。
- 线程退出：`thread.quit()` + `thread.wait()`，或 `QThread.requestInterruption()` + `isInterruptionRequested()`。
- 线程清理：连接 `finished` 到 `deleteLater`，避免线程对象泄漏。
- 互斥锁用 `QMutex` + `QMutexLocker`（RAII），或标准库 `threading.Lock`（跨线程数据访问）。

## 样式（QSS）

- 样式表用 `.qss` 文件管理，`app.setStyleSheet(Path("style.qss").read_text())` 加载，**避免硬编码**。
- 选择器粒度到部件类型 + objectName：`QPushButton#okButton { ... }`，不用全局限定（易误伤）。
- 主题切换通过替换 `.qss` 文件重新加载，不在代码中分支样式。
- 平台差异：macOS 默认风格与 QSS 冲突时用 `app.setStyle("Fusion")` 统一。

主窗口配色与字体层级遵循 GitHub Desktop 风格，详见《界面布局（GitHub Desktop 风格）》章节。

## 测试（pytest-qt）

- `qapp` fixture 提供单例 QApplication（pytest-qt 自动管理生命周期，兼容 PySide2/PySide6）。
- `qtbot` fixture 模拟用户交互：`qtbot.mouseClick`、`qtbot.keyClicks`、`qtbot.addWidget`。
- 等待信号：`qtbot.waitSignal(widget.value_changed, timeout=1000)`。
- 非主线程测试用 `qtbot.wait` 或 `QTimer.singleShot` 回调断言。
- GUI 测试加 `@pytest.mark.gui`（或 `slow`），CI 默认 `-m "not slow"` 跳过（无显示环境）。
- 无头环境设 `QT_QPA_PLATFORM=offscreen`（CI 用 xvfb 或 offscreen 平台插件）。
- 测信号触发：`with qtbot.waitSignal(obj.signal_name) as blocker: ...`，断言 `blocker.args`。

## 打包（PyInstaller）

```bash
pyinstaller --noconsole --onefile --icon=assets/app.ico \
  --hidden-import=PySide2.QtWidgets \
  --add-data "assets;assets" \
  src/uniscan/main.py
```

- PySide6 项目把 `--hidden-import=PySide2.QtWidgets` 换成 `--hidden-import=PySide6.QtWidgets`。
- `--noconsole` 隐藏控制台窗口（GUI 应用）；调试时去掉以查看日志。
- `--hidden-import` 显式声明动态导入的 Qt 子模块。
- `--add-data` 格式 `源;目标`（Windows 用 `;`，Linux/macOS 用 `:`）。
- 资源路径在打包后变化，用 `sys._MEIPASS` 解析：

```python
def resource_path(relative: str) -> str:
    """获取打包后资源的绝对路径."""
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return str(Path(base) / relative)
```

- `.spec` 文件管理复杂配置（版本信息、签名、额外数据），提交版本控制。
- Nuitka 替代方案：`nuitka --standalone --enable-plugin=pyside2 main.py`（PySide6 用 `--enable-plugin=pyside6`），启动更快但编译慢。

## 状态与配置

- 持久化用 `QSettings`（自动选平台存储：注册表/plist/ini），**不用** 手写 JSON 配置。
- 设置 key 用 `organization`/`application` 名限定，避免冲突。
- 对话框状态（尺寸/位置）保存：`settings.setValue("geometry", saveGeometry())`。
- 大量配置用 dataclass + toml/json，QSettings 仅存 UI 状态。

## 国际化

- UI 字符串用 `self.tr("文本")` 包裹，**禁止** 硬编码中文字符串到 UI。
- `.ts` 翻译文件用 `pyside2-lupdate`/`pyside6-lupdate` 提取，`pyside2-lrelease`/`pyside6-lrelease` 编译为 `.qm`。
- 运行时 `QTranslator.load("app_zh.qm")` + `app.installTranslator(translator)`。
- 日期/数字本地化用 `QLocale`，不手动格式化。

## 性能

- 列表/表格大数据用 `QAbstractListModel`/`QAbstractTableModel` + `QTableView`（虚拟化），**不用** `QListWidget` 逐项 add。
- 图片缩放/裁剪用 `QPixmap.scaled`，避免在 paintEvent 内做重计算。
- 自定义 `paintEvent` 内只画，不布局；重绘触发用 `update()`（合并），不用 `repaint()`（立即）。
- 启动加速：延迟创建非首屏部件，`QStackedWidget` 按需加载页面。

## 代码风格

- 部件命名：`类型_用途`（如 `label_status`、`button_ok`、`table_results`），与 `rule-11` snake_case 一致。
- `objectName` 设置：`button.setObjectName("okButton")`，供 QSS 选择器使用。
- 信号槽方法用 `_on_` 前缀：`_on_button_clicked`、`_on_value_changed`。
- 主窗口类名 `MainWindow`/`<功能>Dialog`/`<功能>Widget`，PascalCase。
- 资源常量集中定义：`ICON_APP = ":/icons/app.png"`，禁止散落字符串。

## Git 与提交

遵循 `rule-09-git提交规则.md`，额外约束：
- `.qrc`/`.ui`/`.qss`/`.ts` 源文件提交，编译产物 `_rc.py`/`_ui.py`/`.qm` 提交（构建环境可能无 pyside 工具链）。
- `build/`/`dist/`/`*.spec`（PyInstaller 生成）加入 `.gitignore`，自定义 `.spec` 提交。
- 资源变更单独提交，与逻辑变更分离。
