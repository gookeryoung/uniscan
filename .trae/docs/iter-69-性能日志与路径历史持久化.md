# iter-69：性能日志与路径历史持久化

## 需求清单

来源：用户"1.启用性能日志设置以后应当能记住。2.选择的历史文件夹应当能记住。"

- [x] R1：性能日志开关（PerfTimer）状态持久化到配置文件，下次启动自动恢复
- [x] R2：选择扫描路径后立即持久化到配置文件，避免应用异常退出时历史丢失

## 迭代目标

iter-66 新增的性能日志开关（`perf_log_action`）仅调用 `set_perf_enabled`，
不保存到配置，下次启动总是关闭。扫描路径历史虽在 `closeEvent` 时保存，
但选择路径后不立即持久化，应用崩溃时历史丢失。

本迭代将性能日志开关状态和路径历史改为即时持久化。

## 关键决策与依据

### 决策1：Config 新增 perf_log_enabled 字段

`Config.perf_log_enabled: bool = False`，默认关闭。`_apply_config` 恢复时
用 `blockSignals` 包裹 `setChecked` 避免 `toggled` 信号触发 `_save_config`
循环。`_on_toggle_perf_log` 中实时更新 `self._config.perf_log_enabled` 并
调用 `_save_config()`。

### 决策2：_save_config 不再读 perf_log_action.isChecked()

`_on_toggle_perf_log` 已实时更新 `self._config.perf_log_enabled`，
`_save_config` 直接用 `_config` 的值。避免测试中直接调用
`_on_toggle_perf_log(True)` 时 `perf_log_action` 未被 `setChecked` 导致
状态不一致。

### 决策3：_add_scan_path_history 立即调用 _save_config

选择路径不是高频操作，立即写磁盘的开销可忽略。确保应用异常退出时
历史不丢失。

## 改动文件清单

| 文件 | 说明 |
|------|------|
| `src/fuscan/config.py` | `Config` 新增 `perf_log_enabled: bool = False` 字段 |
| `src/fuscan/gui/main_window.py` | `_apply_config` 恢复 perf_log 开关（blockSignals）；`_on_toggle_perf_log` 实时保存；`_add_scan_path_history` 立即保存 |
| `tests/test_config.py` | 新增 `test_default_perf_log_enabled` / `test_save_and_load_perf_log_enabled` |
| `tests/test_gui.py` | 新增 3 个测试：`test_toggle_perf_log_persists_to_config` / `test_perf_log_enabled_restored_on_startup` / `test_add_scan_path_history_persists_immediately` |

## 测试验证结果

- ruff check / format：通过
- pyrefly check：0 errors
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1444 passed**, 覆盖率 **96%**
- 新增 5 个测试全部通过

## 遗留事项

无。

## 下一轮计划

无。
