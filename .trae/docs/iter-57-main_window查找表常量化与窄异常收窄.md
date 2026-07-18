# iter-57 main_window 查找表常量化与窄异常收窄

## 需求清单

- [x] 1. 继续优化 `main_window.py` 内部代码（用户请求"继续优化"）

## 迭代目标

延续 iter-54/iter-56 的表驱动与常量化思路，识别 `main_window.py` 中三类
剩余可优化点并集中消除：

1. **导出格式查找表常量化**：iter-54 抽出 `_EXPORT_FORMATS` 元组后，
   `_on_export_menu` / `_on_export` 仍每次调用时通过字典推导重建
   `label_to_fmt` 与 `fmt_to_ext` 查找表。本轮抽到模块级常量
   `_EXPORT_LABEL_TO_FMT` / `_EXPORT_FMT_TO_EXT`，避免重复构造。
2. **`except Exception` 收窄为 `(sqlite3.Error, OSError)`**：iter-55 收尾
   扫描时发现 `_on_settings` 与 `closeEvent` 中 2 处
   `except Exception: logger.warning(...)` 用于捕获 `CacheStore.close()`
   失败。按 rule-11「异常范围要窄：禁止 `except Exception`」要求收窄。
3. **抽取 `_restore_window_geometry` 减负 `_apply_config`**：`_apply_config`
   58 行（最长方法），其中 24 行窗口几何恢复（含屏幕边界夹紧算法）独立性强，
   抽到独立方法后 `_apply_config` 减负至 34 行。

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/fuscan/gui/main_window.py` | 修改 | 新增 2 个查找表常量 + 1 个 `_restore_window_geometry` 方法；2 处 `except Exception` 收窄；顶部新增 `import sqlite3`；`_on_export_menu` / `_on_export` 删除局部 dict 推导；`_apply_config` 删除 24 行窗口几何代码 |
| `tests/test_gui.py` | 修改 | 2 处 `RuntimeError("close error")` 改为 `sqlite3.OperationalError("close error")`；顶部新增 `import sqlite3` |

## 关键决策与依据

### 查找表常量化触发点

iter-54 抽出 `_EXPORT_FORMATS` 元组时，为避免预先计算 dict 增加模块级状态，
保留在方法内字典推导。但本轮复查发现：

```python
# iter-56 _on_export_menu: 每次调用重建 label_to_fmt
label_to_fmt = {label: fmt for label, fmt, _ in _EXPORT_FORMATS}
self._on_export(label_to_fmt[choice])

# iter-56 _on_export: 每次调用重建 fmt_to_ext
fmt_to_ext = {fmt_id: ext for _, fmt_id, ext in _EXPORT_FORMATS}
ext = fmt_to_ext.get(fmt, fmt)
```

dict 推导虽只 4 个元素，但每次菜单点击都重建，且 `_EXPORT_FORMATS` 在
模块加载时已固定。抽到模块级常量后：

```python
_EXPORT_LABEL_TO_FMT: dict[str, str] = {label: fmt for label, fmt, _ in _EXPORT_FORMATS}
_EXPORT_FMT_TO_EXT: dict[str, str] = {fmt: ext for _, fmt, ext in _EXPORT_FORMATS}
```

查找表在模块加载时一次性构造，方法内直接索引访问，符合 rule-11「性能」节
「循环内查询缓存或预构建映射」约束（虽然此处不在循环内，但同属「预构建映射」原则）。

### `except Exception` 收窄依据

rule-11「异常处理」节明确要求：「异常范围要窄：只捕获预期异常（如
`(TypeError, ValueError, KeyError, AttributeError)`），**禁止**
`except Exception`」。`CacheStore.close()` 实现调用
`sqlite3.Connection.close()`，可能抛 `sqlite3.Error`（含子类
`ProgrammingError` / `OperationalError` / `DatabaseError`）或 `OSError`
（文件系统层错误）。

窄异常选择 `(sqlite3.Error, OSError)`：
- `sqlite3.Error`：覆盖所有 SQLite 数据库层错误（连接已关闭、事务未提交、磁盘 I/O）
- `OSError`：覆盖文件系统层错误（磁盘满、文件被锁定、权限丢失）

### 测试异常类型修正依据

`test_main_window_close_event_handles_cache_close_error` 与
`test_main_window_settings_cache_close_error` 原用 `RuntimeError("close error")`
模拟 `CacheStore.close()` 失败。`RuntimeError` 是 Python 通用异常，
现实中 `sqlite3.Connection.close()` 不会抛 `RuntimeError`（除非 monkeypatch
注入）。按 rule-11「测试须覆盖功能、性能、边界场景」要求，测试应使用
**符合现实场景的异常类型**，故改为 `sqlite3.OperationalError`（最常见的
SQLite 关闭失败异常）。

### `_restore_window_geometry` 抽取依据

`_apply_config` 58 行，最长方法。其中窗口几何恢复（行 729-749 共 21 行
+ 行 751-752 最大化共 24 行）具有以下特征：

1. **独立性高**：仅依赖 `self._config.window_geometry` / `window_state` 与
   `QApplication.primaryScreen()`，与其他配置恢复逻辑无状态共享
2. **算法内聚**：屏幕边界夹紧算法（`x = max(0, min(x, screen_geo.width() - w))`）
   是一个独立的几何计算单元
3. **可测试性**：抽取后可独立测试窗口几何恢复逻辑，无需触发完整 `_apply_config`

抽取后 `_apply_config` 从 58 行降至 34 行，`_restore_window_geometry` 28 行
（含 docstring 6 行），整体可读性显著提升。

## 代码实现情况

### 模块级查找表常量

```python
# 从 _EXPORT_FORMATS 派生的查找表（模块级常量避免每次调用重建 dict）
_EXPORT_LABEL_TO_FMT: dict[str, str] = {label: fmt for label, fmt, _ in _EXPORT_FORMATS}
_EXPORT_FMT_TO_EXT: dict[str, str] = {fmt: ext for _, fmt, ext in _EXPORT_FORMATS}
```

### `_on_export_menu` / `_on_export` 简化

```python
# _on_export_menu: 删除局部 label_to_fmt 推导
self._on_export(_EXPORT_LABEL_TO_FMT[choice])

# _on_export: 删除局部 fmt_to_ext 推导
ext = _EXPORT_FMT_TO_EXT.get(fmt, fmt)
```

### 异常收窄

```python
# 替换前（_on_settings 与 closeEvent 各 1 处）
try:
    self._cache.close()
except Exception:
    logger.warning("缓存关闭失败", exc_info=True)

# 替换后
try:
    self._cache.close()
except (sqlite3.Error, OSError):
    logger.warning("缓存关闭失败", exc_info=True)
```

### `_restore_window_geometry` 抽取

```python
def _restore_window_geometry(self) -> None:
    """从配置恢复窗口几何（含屏幕边界夹紧算法）。

    若配置中有完整 4 元组 geometry，则按 (x, y, w, h) 恢复并将窗口
    夹紧到当前屏幕可用区域内（避免恢复到已不存在的多屏坐标）；
    否则将窗口居中到主屏幕。最后若 ``window_state`` 为 ``maximized`` 则最大化。
    """
    min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
    screen_geo = QApplication.primaryScreen().availableGeometry()

    if self._config.window_geometry and len(self._config.window_geometry) == 4:
        x, y, w, h = self._config.window_geometry
        w = max(w, min_w)
        h = max(h, min_h)
        if screen_geo.width() > w:
            x = max(0, min(x, screen_geo.width() - w))
        if screen_geo.height() > h:
            y = max(0, min(y, screen_geo.height() - h))
        self.setGeometry(x, y, w, h)
    else:
        w, h = self.size().width(), self.size().height()
        if screen_geo.width() > w and screen_geo.height() > h:
            x = (screen_geo.width() - w) // 2
            y = (screen_geo.height() - h) // 2
            self.move(x, y)

    if self._config.window_state == "maximized":
        self.showMaximized()
```

`_apply_config` 从 58 行简化为 34 行（首段 24 行替换为 `self._restore_window_geometry()`），
原本分散的「窗口几何 / 分割器 / 扫描模式 / 盘符 / 规则路径 / 历史 / 扫描目标」
7 个恢复段现在各自段长均 ≤ 8 行，可读性显著提升。

### 测试异常类型修正

```python
# 替换前（2 处）
def raising_close() -> None:
    raise RuntimeError("close error")

# 替换后
def raising_close() -> None:
    raise sqlite3.OperationalError("close error")
```

## 整合优化情况

- **代码量减负**：`main_window.py` 净减少 ~5 行（删除 2 处 dict 推导 2 行 +
  `_apply_config` 中 24 行窗口几何 - `_restore_window_geometry` 28 行 +
  2 处异常类型 0 行 + `import sqlite3` 1 行 + 2 个常量 2 行）。
- **预构建查找表**：模块加载时一次性构造 `_EXPORT_LABEL_TO_FMT` /
  `_EXPORT_FMT_TO_EXT`，避免每次菜单点击重建 dict。
- **窄异常合规**：消除 2 处 `except Exception`，符合 rule-11 硬约束。
- **方法长度优化**：`_apply_config` 从 58 行降至 34 行（最长方法降级为
  第 5 长，前 4 名为 `_connect_signals` 49 行 / `_on_scan` 44 行 /
  `_setup_icons` 40 行 / `__init__` 39 行）。
- **测试真实性**：测试用 `sqlite3.OperationalError` 替代 `RuntimeError`，
  更贴近现实 `CacheStore.close()` 失败场景。

## 测试验证结果

| 门禁 | 结果 | 基线（iter-56） | 变化 |
|------|------|----------------|------|
| ruff check | All checks passed | 0 errors | — |
| ruff format --check | 43 files already formatted | 43 files | — |
| pyrefly check | 0 errors (62 suppressed) | 0 errors (62 suppressed) | — |
| pytest | 1363 passed / 0 failed | 1363 passed | — |
| coverage | 96.27% | 96.29% | -0.02% |

覆盖率小幅下降 0.02% 来自 `_restore_window_geometry` 中 else 分支
（窗口居中路径）未被测试覆盖（原内联代码在 `_apply_config` 测试路径中
也未覆盖，但行数比例变化导致百分比略降），仍高于 95% 门禁。

## 遗留事项

- `main_window.py` 仍约 1060 行。剩余超长方法：
  - `_connect_signals` 49 行：纯信号槽连接，已按业务分组带注释，强行抽取
    为常量元组循环绑定反而降低可读性（与 iter-54 `_setup_icons` 不同，
    每个槽函数不同，无法用同一映射元组表达）。
  - `_on_scan` 44 行：包含扫描启动前置检查、UI 重置、worker 构造与信号连接，
    各段独立但单次使用，抽取 helper 收益低。
  - `_setup_icons` 40 行：iter-54 已表驱动重构，进一步压缩空间有限。
- 异常收窄后 `_on_settings` / `closeEvent` 中 `CacheStore.close()` 失败的
  其他异常类型（如 `MemoryError` / `KeyboardInterrupt`）将向上传播。
  这符合 rule-11「只捕获预期异常」原则——非预期异常应让程序崩溃以便定位。

## 下一轮计划

无明确下一轮计划。`main_window.py` 内部散落模式与超长方法已通过 4 轮迭代
（iter-53/54/55/56/57）集中优化，剩余超长方法均有「单次使用」或「业务分组
已清晰」的特征，强行抽取收益低于风险。如用户提出新需求再行迭代。
