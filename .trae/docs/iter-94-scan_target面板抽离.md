# iter-94 scan_target 面板抽离

## 需求清单

- [x] 为 `scan_target.ui` 设计对应的 `scan_target.py` 控制器
- [x] 采取信号槽与 main_window 交互，提高内聚性
- [x] `main_window.ui` 中的 `target_group` 替换为 `scan_target.ui` 加载的 `ScanTargetPanel`

## 迭代目标

将 `target_group` 从 `main_window.ui` 中移除，改为通过 `ScanTargetPanel`（继承 QWidget + `Ui_scan_target`）加载 `scan_target.ui` 生成全部子控件，放入 `main_window.ui` 中的 `scan_target_container` 容器。`ScanTargetPanel` 通过信号槽与主窗口交互，`target_group` 的布局设置与信号连接内聚到面板内部。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/scan_target.py` | 重写 | `ScanTargetPanel` 继承 QWidget + `Ui_scan_target`，构造时调 `setupUi(self)` 加载 `scan_target.ui`；`bind(scan_mode_panel)` 连接信号 |
| `src/fuscan/gui/main_window.ui` | 修改 | `target_group` QGroupBox 替换为空 QWidget `scan_target_container`（含 QHBoxLayout） |
| `src/fuscan/gui/main_window_ui.py` | 重新生成 | `pyside2-uic` 编译，不再含 `target_group` / `scan_mode_combo` / `path_combo` 等控件 |
| `src/fuscan/gui/main_window.py` | 修改 | `__init__` 中创建 `ScanTargetPanel` 并放入容器；`ScanPathHistory` 引用改为 `self._scan_target_panel.path_combo`；`_setup_scan_mode_panel` 控件引用改为 `self._scan_target_panel.xxx`；移除 `_setup_layouts` 中 `target_group_layout.setStretch`（已内聚到面板） |
| `tests/test_gui.py` | 修改 | `window.path_combo` / `window.scan_mode_combo` / `window.target_stack` 等改为 `window._scan_target_panel.xxx` |

## 关键决策与依据

### 1. ScanTargetPanel 继承 QWidget + Ui_scan_target

`ScanTargetPanel` 继承 QWidget + `Ui_scan_target`（由 `scan_target.ui` 编译生成），构造时调 `self.setupUi(self)` 生成全部子控件。主窗口在 `__init__` 中创建面板实例并放入 `scan_target_container_layout`。依据：这是 PySide2 UI 组件复用的标准模式（与 `QMainWindow, Ui_MainWindow` 一致），`.ui` 文件作为 UI 源被真正加载，不再在 `main_window.ui` 中重复定义。

### 2. bind 延迟连接信号

`ScanTargetPanel.__init__` 只调 `setupUi`，不连接信号——因为 path_combo 切换需要 `ScanModePanel.set_folder_root`，而 `ScanModePanel` 创建需要 `ScanTargetPanel` 的控件引用（`scan_mode_combo` / `target_stack` / `drive_buttons_layout`）。创建顺序：`ScanTargetPanel` → `ScanModePanel`（接收控件引用）→ `ScanTargetPanel.bind(scan_mode_panel)` 连接信号。

### 3. target_group_layout 布局内聚

`target_group_layout.setStretch(0, 0)` 从主窗口 `_setup_layouts` 移入 `ScanTargetPanel.__init__`，布局设置与 UI 定义内聚到同一面板，主窗口不再操作 `target_group_layout`。

### 4. ScanModePanel 与 ScanTargetPanel 分工不变

`ScanModePanel` 仍独立管理模式 combo / 盘符按钮组 / folder 路径状态（46 处 `window._scan_mode_panel` 测试引用无需改动）。`ScanTargetPanel` 负责 UI 加载 + path_combo / select_path_btn 信号连接。

## 代码实现情况

### ScanTargetPanel (`src/fuscan/gui/scan_target.py`)

- 继承 QWidget + `Ui_scan_target`，构造时调 `setupUi(self)` 生成 `target_group` 全部子控件
- `target_group_layout.setStretch(0, 0)` 在构造时设置（内聚布局）
- `bind(scan_mode_panel)`：连接 `path_combo.currentIndexChanged` → `_on_path_selected`；`select_path_btn.clicked` → `select_path_requested` 信号
- 信号：`select_path_requested`（主窗口弹出 QFileDialog）
- 内部槽：`_on_path_selected(index)`（path_combo 切换 → set_folder_root）

### 主窗口集成

- `__init__`：创建 `ScanTargetPanel` 并 `scan_target_container_layout.addWidget`
- `ScanPathHistory` 引用 `self._scan_target_panel.path_combo`
- `_setup_scan_mode_panel`：控件引用从 `self.scan_mode_combo` 改为 `self._scan_target_panel.scan_mode_combo`；调 `bind` 连接信号
- `_setup_layouts`：移除 `target_group_layout.setStretch`
- `_apply_config`：`path_combo` 引用改为 `self._scan_target_panel.path_combo`

## 测试验证结果

```
uv run ruff check src tests          # All checks passed
uv run ruff format --check src tests # All files already formatted
uv run pyrefly check                 # 0 errors
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95
# 1685 passed, 43 deselected
# Required test coverage of 95% reached. Total coverage: 95.89%
```

覆盖率从 95.05% 提升至 95.89%（`main_window_ui.py` 不再含 `target_group` 重复定义，未覆盖语句数减少）。

## 遗留事项

- 无

## 下一轮计划

- 无（本次需求已全部完成）
