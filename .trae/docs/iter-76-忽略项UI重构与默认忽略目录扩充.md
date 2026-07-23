# iter-76：忽略项 UI 重构与默认忽略目录扩充

## 需求清单

- [x] 忽略目录和忽略扩展名的 UI 不好，内容显示太少且大小被压缩
- [x] 默认忽略目录应包含更多内容（Program Files、Visual Studio、Cargo 缓存等含众多无关文件的目录）

## 迭代目标

iter-75 收尾后用户反馈设置对话框中「忽略项」两个问题：

1. **UI 拥挤**：忽略目录/扩展名原放在「扫描设置」Tab 的 `ignore_group` 内，
   用 `QFormLayout` 把 `QLabel` 放左侧、`QPlainTextEdit` 放右侧，编辑器无最小高度，
   被 5 个同级 GroupBox 挤压，仅显示 2-3 行，长列表无法查看
2. **默认列表不足**：原默认仅 21 项开发工具缓存，缺少 Windows 系统目录
   （Program Files / Windows / WinSxS）、Visual Studio 项目产物（.vs / packages / .nuget）、
   Cargo 缓存（.cargo / .rustup）等含大量无关文件的目录，全盘扫描时浪费大量时间

## 改动文件清单

| 文件 | 改动内容 |
|------|---------|
| `src/fuscan/config.py` | `Config.ignore_dirs` 默认列表由 21 项扩充至 55 项，按语言生态/用途分组注释；新增 Rust/Cargo、.NET/VS、Java、PHP、Apple、Flutter、Node 生态扩展、缓存/临时/日志、Windows 系统目录 |
| `src/fuscan/gui/settings_dialog.ui` | 对话框最小尺寸 500×460 → 640×620；新增「忽略项」Tab（`ignore_page`），左右双栏 `QHBoxLayout` 放置 `ignore_dirs_group` 与 `ignore_extensions_group`，各含 hint `QLabel` + `QPlainTextEdit`（`minimumHeight=320`）；从「扫描设置」Tab 移除原 `ignore_group` |
| `src/fuscan/gui/settings_dialog_ui.py` | 由 `pyside2-uic` 从 .ui 重新生成（uic 产物，勿手改） |
| `src/fuscan/gui/settings_dialog.py` | 模块 docstring 更新为 3 Tab 结构；`_configure_ui` 新增 `ignore_page_layout.setStretch(0,2)` / `setStretch(1,1)` 让目录栏比扩展名栏更宽（列表更长） |
| `tests/test_config.py` | `test_default_ignore_dirs` 扩充断言：Cargo（.cargo/.rustup/target）、VS（.vs/packages/.nuget）、vendor/Pods/.m2、Windows 系统目录（Program Files/Windows/WinSxS/$Recycle.Bin），`len >= 50` |
| `tests/test_gui.py` | `TestSettingsDialogIgnore` 新增 `test_ignore_page_tab_with_large_editors`：断言 `ignore_page` 为 TabWidget 第三 Tab、标题「忽略项」、两编辑器 `minimumHeight >= 300`、`ignore_page_layout` 拉伸比 2:1 |

## 关键决策与依据

### D1：忽略项独立为第三个 Tab，而非原地放大

**决策**：将 `ignore_dirs_edit` / `ignore_extensions_edit` 从「扫描设置」Tab
的 `ignore_group` 移出，独立为第三个 Tab「忽略项」，左右双栏布局。

**依据**：
- 「扫描设置」Tab 原含 5 个 GroupBox（线程/深度/大文件/选项/忽略项）+ spacer，
  垂直空间被均分，忽略编辑器被压缩到 2-3 行；原地放大需大幅增加对话框高度且仍与
  其它 GroupBox 争抢空间
- 独立 Tab 后编辑器独占整页，配合 `minimumHeight=320` 与对话框 620 高，
  可显示约 18-20 行，足够查看长列表
- 左右双栏（`QHBoxLayout`）让两个编辑器同时可见，避免上下堆叠时其中一个被挤；
  按宽度 2:1 分配（目录栏更宽）因目录列表（55 项）远长于扩展名列表（32 项）

### D2：stretch 在 `_configure_ui` 设置而非 .ui 属性

**决策**：`ignore_page_layout` 的 2:1 拉伸比在 `settings_dialog.py` 的
`_configure_ui` 中通过 `setStretch(0, 2)` / `setStretch(1, 1)` 设置，
而非用 .ui 的 `<property name="stretch">`。

**依据**：
- 在 .ui 的 `QHBoxLayout` 上加 `<property name="stretch"><string>2,1</string></property>`
  会让 `pyside2-uic` 生成 `self.ignore_page_layout.setStretch("2,1")`——
  `QBoxLayout.setStretch` 签名为 `(index: int, stretch: int)`，单字符串参数会
  在 `retranslateUi` 运行时抛 `TypeError`
- `.ui` 无法静态表达「按索引设拉伸」这种命令式语义，放 `_configure_ui`（专放
  「.ui 无法静态表达的配置」）符合现有分工

### D3：默认忽略目录扩充为跨平台静态列表

**决策**：`Config.ignore_dirs` 默认列表扩充为 55 项，**不**按平台条件分支，
Windows 系统目录（Program Files/Windows/WinSxS 等）在所有平台都包含。

**依据**：
- `Config.ignore_dirs` 按**目录名**匹配任意层级（大小写不敏感），在非 Windows
  平台出现名为 "Program Files" 的目录概率极低，包含也无副作用
- 静态列表保证配置可预测、序列化干净（`save_config` 写 YAML 时不依赖运行平台）
- 与 `fuscan.watcher.ignore_dirs.default_ignore_dirs()`（监控用，平台条件分支）
  分工不同：扫描配置需跨平台可持久化，监控配置需平台精确——两者用途不同故未合并，
  待第三处相似需求出现再考虑提取共享常量（遵循 rule-01「三处相似才提取」）

### D4：保留 objectName 与 placeholder 关键字以维持测试契约

**决策**：`ignore_dirs_edit` / `ignore_extensions_edit` 的 objectName 不变；
placeholder 文本保留「目录名」/「扩展名」关键字。

**依据**：
- `test_gui.py::TestSettingsDialogIgnore` 通过 objectName 访问控件、通过
  `placeholderText()` 含关键字断言，保持这两个契约使现有测试无需改动即通过

## 代码实现情况

### Config 默认列表扩充

按语言生态/用途分组（版本控制 / Python / Node / Rust / Java / .NET / PHP / Apple /
Flutter / 构建输出 / IDE / 缓存临时日志 / Windows 系统目录），新增 34 项，
保留全部原 21 项。

### 忽略项 Tab 布局

```xml
<widget class="QWidget" name="ignore_page">
  <layout class="QHBoxLayout" name="ignore_page_layout">
    <item><widget class="QGroupBox" name="ignore_dirs_group">
      <layout class="QVBoxLayout">
        <item><QLabel hint: "按目录名匹配任意层级..."/></item>
        <item><QPlainTextEdit name="ignore_dirs_edit" minimumHeight=320/></item>
      </layout>
    </widget></item>
    <item><widget class="QGroupBox" name="ignore_extensions_group">
      <layout class="QVBoxLayout">
        <item><QLabel hint: "不含点，大小写不敏感..."/></item>
        <item><QPlainTextEdit name="ignore_extensions_edit" minimumHeight=320/></item>
      </layout>
    </widget></item>
  </layout>
</widget>
```

`_configure_ui` 设置拉伸比：

```python
self.ignore_page_layout.setStretch(0, 2)  # 目录栏
self.ignore_page_layout.setStretch(1, 1)  # 扩展名栏
```

## 整合优化情况

- 从「扫描设置」Tab 移除 `ignore_group`，该 Tab 现仅剩 4 个 GroupBox + spacer，
  布局更舒展
- `settings_dialog.py` 模块 docstring 同步更新为 3 Tab 结构说明
- 临时移除 .ui 中错误的 `<property name="stretch">` 并改用 `_configure_ui` 命令式
  设置，避免 uic 生成运行时抛错的 `setStretch("2,1")` 调用

## 测试验证结果

### 单元测试

- `tests/test_config.py::test_default_ignore_dirs`：扩充断言覆盖 Cargo / VS /
  vendor / Pods / .m2 / Windows 系统目录，`len >= 50`
- `tests/test_gui.py::TestSettingsDialogIgnore::test_ignore_page_tab_with_large_editors`：
  断言 `ignore_page` 为第三 Tab、标题「忽略项」、两编辑器 `minimumHeight >= 300`、
  拉伸比 2:1

### 全套门禁

| 检查项 | 结果 |
|--------|------|
| `ruff check src tests` | All checks passed |
| `ruff format --check src tests` | 95 files already formatted |
| `pyrefly check` | 0 errors (478 suppressed, 60 warnings) |
| `pytest -m "not slow" --cov=fuscan --cov-fail-under=95` | **1485 passed**（较 iter-75 的 1484 +1），coverage **96.12%** |

## 遗留事项

- 已有用户保存的 `config.yaml` 若含旧 `ignore_dirs` 列表，加载时会覆盖默认值，
  不会自动获得新默认项；用户可在「忽略项」Tab 手动补充。未引入配置版本迁移
  （超出本次范围，需独立的 config 版本机制）
- `pytest.ini` 仅注册 `slow` marker，`gui` marker 未注册导致
  `PytestUnknownMarkWarning`（已有问题，本次未触及）
- `fuscan.watcher.ignore_dirs` 与 `Config.ignore_dirs` 存在两份相似但分工不同的
  忽略目录列表，待第三处相似需求出现再提取共享常量

## 下一轮计划

无。本次迭代两个用户问题全部修复，门禁全通过，进入收尾提交。
