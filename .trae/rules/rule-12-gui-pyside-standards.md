# PySide2/PySide6 (Qt5/Qt6) GUI 开发规范

适用于 `project_type=gui` 的生成项目。在 `rule-11-python-standards.md` 基础上补充 Qt 桌面应用的设计规范与技术约束。

模板按 Python 版本自动区分绑定：`PySide2`（Python ≤ 3.10）/ `PySide6`（Python ≥ 3.11），代码须双兼容。

## 设计系统（Design Tokens）

基于桌面 GUI 工作流设计稿，定义以下设计令牌。所有 QSS 与代码须引用令牌常量，禁止散落硬编码颜色/尺寸。

### 色彩系统

| 令牌 | 色值 | 用途 |
|------|------|------|
| `COLOR_PRIMARY` | `#0887A0` | 主色：头部条、侧边栏背景、主操作按钮、选中态 |
| `COLOR_PRIMARY_DARK` | `#00829E` | 主色按下态、分割线 |
| `COLOR_ACCENT` | `#87C6BB` | 强调色：成功状态、辅助高亮 |
| `COLOR_TEXT_ON_PRIMARY` | `#FFFFFF` | 主色背景上的文字/图标 |
| `COLOR_TEXT_PRIMARY` | `#2C3E50` | 主文字（深色，用于白底内容区） |
| `COLOR_TEXT_SECONDARY` | `#518394` | 次级文字、说明、禁用态 |
| `COLOR_BG_APP` | `#FFFFFF` | 应用底色、内容区背景 |
| `COLOR_BG_MUTED` | `#E5EDE0` | 浅底：卡片间隙、分组背景 |
| `COLOR_BORDER` | `#D1DDE2` | 边框、分割线 |
| `COLOR_DANGER` | `#E74C3C` | 错误/危险操作 |
| `COLOR_WARNING` | `#F39C12` | 警告 |
| `COLOR_SUCCESS` | `#27AE60` | 成功 |

色彩令牌集中定义在 `src/{{ package_name }}/theme.py` 作为模块常量，QSS 文件通过字符串模板引用。

### 排版

| 令牌 | 字号 | 字重 | 用途 |
|------|------|------|------|
| `FONT_TITLE` | 18px | Bold | 窗口标题、页面标题 |
| `FONT_HEADING` | 15px | Bold | 区块标题、分组标题 |
| `FONT_BODY` | 13px | Regular | 正文、表单标签 |
| `FONT_CAPTION` | 11px | Regular | 说明文字、状态栏、表头 |

字体族：`"PingFang SC", "Microsoft YaHei", "Segoe UI", "Helvetica Neue", Arial, sans-serif`（macOS/Windows/Linux 顺序回退）。

### 间距尺度

8px 基准网格，所有间距须为 8 的倍数：

| 令牌 | 值 | 用途 |
|------|-----|------|
| `SPACING_XS` | 4px | 图标与文字间隙 |
| `SPACING_SM` | 8px | 控件内边距、紧凑间隙 |
| `SPACING_MD` | 16px | 控件间间隙、表单字段间距 |
| `SPACING_LG` | 24px | 区块内边距 |
| `SPACING_XL` | 32px | 区块间间隙 |

### 圆角与尺寸

| 令牌 | 值 | 用途 |
|------|-----|------|
| `RADIUS_SM` | 4px | 按钮、输入框 |
| `RADIUS_MD` | 6px | 卡片、面板 |
| `CONTROL_HEIGHT` | 32px | 按钮/输入框标准高度 |
| `CONTROL_HEIGHT_SM` | 26px | 紧凑控件 |
| `SIDEBAR_WIDTH` | 220px | 侧边栏宽度 |
| `HEADER_HEIGHT` | 40px | 头部条高度 |
| `TOOLBAR_HEIGHT` | 44px | 工具栏高度 |
| `STATUSBAR_HEIGHT` | 28px | 状态栏高度 |

## 布局规范

### 主窗口结构

采用「头部 + 侧边栏 + 内容区 + 状态栏」四区结构：

```
┌──────────────────────────────────────────────────────────┐
│ HeaderBar  (COLOR_PRIMARY, 高 HEADER_HEIGHT)             │
├──────────────────────────────────────────────────────────┤
│            │                                             │
│  Sidebar   │           Content Area                      │
│ (COLOR_    │  (COLOR_BG_APP, 可滚动)                     │
│  PRIMARY,  │                                             │
│  宽 SIDEBAR│                                             │
│  _WIDTH)   │                                             │
│            │                                             │
├────────────┴─────────────────────────────────────────────┤
│ StatusBar  (COLOR_BG_MUTED, 高 STATUSBAR_HEIGHT)         │
└──────────────────────────────────────────────────────────┘
```

实现用 `QVBoxLayout`（外层）嵌套 `QHBoxLayout`（中区），**禁用绝对定位** `setGeometry`。

### 布局实现要点

- 外层 `QVBoxLayout` 顺序：header → (sidebar+content 的 `QHBoxLayout`) → statusbar
- 中区 `QHBoxLayout` 中 sidebar 与 content 之间用 `QSplitter` 实现可拖拽分隔（用户体验更好）
- Content 区用 `QStackedWidget` 配合侧边栏切换页面
- 侧边栏可折叠（`QSplitter` 设置 `setSizes([0, width])` 或动画展开）
- 所有 Layout 的 `setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)`

### 响应式策略

- 窗口最小尺寸 `800×600`，默认 `1280×800`
- 宽度 < 1000px 时侧边栏自动折叠为图标条（宽度 → 56px）
- 用 `QSplitter` 而非固定比例，让用户可调整各区大小
- 内容区内的卡片用 `QGridLayout` 自适应列数（`resizeEvent` 中重算列数）

## 导航模式

### Header 区设计要点

- Header 区分为左右两侧，中间用 Spacer 分隔
- Header 左侧为 Tab 切换功能，按照项目业务流程从左至右布局，切换过程中下方 Sidebar 和 Content 也一并变化
- Header 右侧为软件通用功能按钮，包括 `设置`, `帮助`, `关于`等，点击后进入独立的对话框进行操作

### 侧边栏导航（首选）

侧边栏为一级导航，`QListWidget` 或自定义 `QWidget` 实现：

- 背景 `COLOR_PRIMARY`，文字 `COLOR_TEXT_ON_PRIMARY`
- 每项高度 40px，图标 20×20px + 文字 `FONT_BODY`
- 选中态：背景 `COLOR_PRIMARY_DARK` + 左侧 3px `COLOR_ACCENT` 竖条
- Hover 态：背景透明度 10% 白色叠加
- 点击触发 `currentRowChanged` → `QStackedWidget.setCurrentIndex`

```python
sidebar = QListWidget()
sidebar.setObjectName("sidebar")
for icon, text in NAV_ITEMS:
    item = QListWidgetItem(QIcon(icon), text)
    sidebar.addItem(item)
sidebar.currentRowChanged.connect(stack.setCurrentIndex)
```

### 选项卡导航（次级）

内容区内多视图切换用 `QTabWidget`：

- Tab 高度 36px，文字 `FONT_BODY`
- 选中 Tab 底部 2px `COLOR_PRIMARY` 下划线
- Tab 内容区边框 `COLOR_BORDER`，圆角 `RADIUS_MD`

### 面包屑（路径导航）

层级深时用 `QLabel` + `>` 分隔符实现面包屑：

- 文字 `FONT_CAPTION`，颜色 `COLOR_TEXT_SECONDARY`
- 当前页用 `COLOR_TEXT_PRIMARY` + Bold
- 点击上级触发 `navigation_requested` 信号

## 工具链

| 工具 | 配置要点 |
|------|---------|
| PySide2 | `>=5.15.2.1`，Qt5 官方绑定（LGPL），仅支持 Python 3.6-3.10 |
| PySide6 | `>=6.5.0`，Qt6 官方绑定（LGPL），支持 Python 3.8+，3.11+ 环境必选 |
| pytest-qt | `>=4.2.0`，Qt 测试框架（qapp/qtbot fixture），同时兼容两代绑定 |
| pyside2-rcc / pyside6-rcc | 资源编译器（.qrc → _rc.py），按已安装绑定使用 |
| pyside2-uic / pyside6-uic | UI 编译器（.ui → .py），按已安装绑定使用 |

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

- 入口 `src/{{ package_name }}/main.py`：`QApplication(sys.argv)` → 构建主窗口 → 事件循环（见上兼容写法）。
- `main()` 加 `# pragma: no cover`（事件循环阻塞，难自动化），拆出 `create_main_window()` 等可测函数。
- 业务逻辑放纯 Python 模块（不 import PySide），便于单测；GUI 层只做信号槽连接与状态展示。
- 惰性导入重型部件（QWebEngineView 等）以加快启动。

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

## 资源系统

- `.qrc` 文件管理图标/样式表/翻译等静态资源，编译为 `_rc.py`：

```bash
pyside2-rcc resources.qrc -o src/{{ package_name }}/resources_rc.py  # PySide2
pyside6-rcc resources.qrc -o src/{{ package_name }}/resources_rc.py  # PySide6
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

### 设计令牌引用

QSS 不支持变量，用 Python 字符串模板渲染。`theme.py` 定义令牌，`style.qss` 用占位符，加载时替换：

```python
# theme.py
COLOR_PRIMARY = "#0887A0"
COLOR_TEXT_ON_PRIMARY = "#FFFFFF"
# ...其他令牌

QSS_TOKENS = {
    "COLOR_PRIMARY": COLOR_PRIMARY,
    "COLOR_TEXT_ON_PRIMARY": COLOR_TEXT_ON_PRIMARY,
    # ...
}
```

```css
/* style.qss */
QListWidget#sidebar {
    background-color: ${COLOR_PRIMARY};
    color: ${COLOR_TEXT_ON_PRIMARY};
    border: none;
    font-size: 13px;
}
QListWidget#sidebar::item {
    padding: 8px 16px;
    border-left: 3px solid transparent;
}
QListWidget#sidebar::item:selected {
    background-color: ${COLOR_PRIMARY_DARK};
    border-left: 3px solid ${COLOR_ACCENT};
}
```

```python
# main.py 加载 QSS
from pathlib import Path
from string import Template
from {{ package_name }} import theme

def load_stylesheet() -> str:
    """加载 QSS 并替换设计令牌占位符."""
    qss = Path(__file__).parent / "style.qss"
    return Template(qss.read_text("utf-8")).substitute(theme.QSS_TOKENS)

app.setStyleSheet(load_stylesheet())
```

### 样式组织要点

- 样式表用 `.qss` 文件管理，**避免硬编码**内联样式。
- 选择器粒度到部件类型 + objectName：`QPushButton#okButton { ... }`，不用全局限定（易误伤）。
- 主题切换通过替换 `.qss` 文件重新加载，不在代码中分支样式。
- 平台差异：macOS 默认风格与 QSS 冲突时用 `app.setStyle("Fusion")` 统一。

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
  src/{{ package_name }}/main.py
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
