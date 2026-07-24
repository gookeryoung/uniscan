# req-31 scan_target 面板抽离

- [x] 为 `scan_target.ui` 设计对应的 `scan_target.py` 控制器
- [x] 采取信号槽与 main_window 交互，提高内聚性
- [x] `main_window.ui` 中的 `target_group` 替换为 `scan_target.ui` 加载的 `ScanTargetPanel`
