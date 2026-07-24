# iter-94 scan_target 面板抽离

## 需求清单

- [x] 为 `scan_target.ui` 设计对应的 `scan_target.py` 控制器
- [x] 采取信号槽与 main_window 交互，提高内聚性

## 迭代目标

将 `target_group` 中 `path_combo` 与 `select_path_btn` 的信号交互从主窗口抽离到独立的 `ScanTargetPanel` 控制器，通过信号槽与主窗口通信，减少主窗口散落的信号连接。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/scan_target.py` | 新增 | `ScanTargetPanel` 控制器：接管 path_combo 切换与 select_path_btn 点击信号 |
| `src/fuscan/gui/main_window.py` | 修改 | 集成 `ScanTargetPanel`；移除 `_on_path_selected`（逻辑移入面板）；`_on_select_path` 改由 `select_path_requested` 信号触发；`_connect_signals` 移除 path_combo/select_path_btn 直接连接 |
| `tests/test_gui.py` | 修改 | `TestOnPathSelectedEdgeCases` 调用路径从 `window._on_path_selected` 改为 `window._scan_target_panel._on_path_selected` |

## 关键决策与依据

### 1. ScanTargetPanel 与 ScanModePanel 分工

`ScanModePanel` 仍独立管理模式 combo / 盘符按钮组 / folder 路径状态（含 `apply_config` / `save_config` / `can_start_scan` / `build_scan_roots` 等公共 API）。`ScanTargetPanel` 仅接管 `path_combo.currentIndexChanged` 与 `select_path_btn.clicked` 的信号连接，不重复 `ScanModePanel` 的状态管理。依据：`ScanModePanel` 已有完整测试覆盖，拆分两个面板避免破坏现有测试（46 处 `window._scan_mode_panel` 引用无需改动）。

### 2. path_combo 切换内聚到面板内部

`_on_path_selected` 逻辑（path_combo 切换 → set_folder_root）移入 `ScanTargetPanel._on_path_selected`，主窗口不再直接连接 `path_combo.currentIndexChanged`。`set_folder_root` 内部 emit `mode_changed`，触发主窗口 `_update_scan_button`，信号链路无需经过 `ScanTargetPanel` 转发。

### 3. select_path_btn 通过信号通知主窗口

`select_path_btn.clicked` 由 `ScanTargetPanel` 内部连接，发 `select_path_requested` 信号给主窗口。主窗口收到后弹出 `QFileDialog` 选择目录，回写 `set_folder_root` 与 `ScanPathHistory.add`。QFileDialog 交互保留在主窗口（依赖 `folder_root` 作为起始目录与 `_add_scan_path_history` 持久化）。

## 代码实现情况

### ScanTargetPanel (`src/fuscan/gui/scan_target.py`)

- 信号：`select_path_requested`（select_path_btn 点击）
- 内部槽：`_on_path_selected(index)`（path_combo 切换 → set_folder_root）
- 构造函数接收 `ScanModePanel` 引用 + `path_combo` + `select_path_btn`

### 主窗口集成

- `_setup_scan_mode_panel` 中创建 `ScanTargetPanel`（`self._scan_target_panel`）
- `_connect_signals` 中 `select_path_requested` → `_on_select_path`
- 移除 `_on_path_selected` 方法
- `_on_select_path` docstring 更新为响应 `select_path_requested` 信号

## 测试验证结果

```
uv run ruff check src tests          # All checks passed
uv run ruff format --check src tests # 106 files already formatted
uv run pyrefly check                 # 0 errors
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95
# 1685 passed, 43 deselected
# Required test coverage of 95% reached. Total coverage: 95.05%
```

`scan_target.py` 覆盖率 100%（27 stmts / 4 branches，0 miss / 0 brpart）。

## 遗留事项

- 无

## 下一轮计划

- 无（本次需求已全部完成）
