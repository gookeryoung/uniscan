# 扫描按钮位置与配色优化

## 背景

当前 `scan_btn` 位于 `setup_btn_row` 布局最右侧，由水平 spacer 推到右下角，视觉上孤立不和谐。颜色用 GitHub 绿 `#2ea44f`，与项目 PRIMARY 主题蓝 `#0366d6` 不一致。用户要求改为 PRIMARY 主题色并完善布局。

## 当前状态分析

### `src/fuscan/gui/main_window.ui` (L364-415)

`setup_btn_row` 是 setup_layout 的第 3 个 item（裸 QHBoxLayout），结构：
```
spacer(expanding) → view_results_btn(默认隐藏) → scan_btn(高 60px, 绿色)
```
- `scan_btn` minimumSize height=60，与扫描中页按钮（44px）不一致，显得臃肿
- `view_results_btn` 位于 scan_btn 左侧，可见时两个按钮挤在右下角
- 无视觉分隔，与上方 rules_group 之间缺少过渡

### `src/fuscan/gui/styles.qss` (L180-225)

- `QPushButton#scan_btn` 用绿色 `#2ea44f`/`#2c974b`/`#27873f`
- `QPushButton#export_btn, #rescan_btn, #view_results_btn` 共用蓝色 `#0366d6` 填充样式
- 若 scan_btn 也改蓝，会与 view_results_btn 视觉混淆，丢失主次层次

### `src/fuscan/gui/main_window.py` (L324-327)

```python
ui.setup_layout.setStretch(0, 0)  # target_group
ui.setup_layout.setStretch(1, 1)  # rules_group
ui.setup_layout.setStretch(2, 0)  # setup_btn_row (将变为 setup_action_bar)
```
包裹 QFrame 后，item 2 从 layout 变为 QFrame，`setStretch(2, 0)` 仍然有效，无需改代码。

## 改动文件

- `src/fuscan/gui/main_window.ui` — 重构 `setup_btn_row` 为 QFrame 包裹的操作条
- `src/fuscan/gui/main_window_ui.py` — 重新编译生成
- `src/fuscan/gui/styles.qss` — `scan_btn` 改色 + `view_results_btn` 改次级样式 + 新增操作条样式
- `tests/test_gui.py` — 新增结构验证测试

## 实现方案

### 1. `src/fuscan/gui/main_window.ui` — 布局重构

将 `setup_btn_row` 从裸 QHBoxLayout 改为包裹在 QFrame 中的布局：

**当前结构**（L364-415）：
```
setup_layout (QVBoxLayout)
├── target_group
├── rules_group
└── setup_btn_row (QHBoxLayout: spacer + view_results_btn + scan_btn)
```

**改为**：
```
setup_layout (QVBoxLayout)
├── target_group
├── rules_group
└── setup_action_bar (QFrame, objectName="setup_action_bar")
    └── setup_btn_row (QHBoxLayout: view_results_btn + spacer + scan_btn)
```

具体 .ui 改动（替换 L364-414 的 `<item>` 块）：
- 外层包裹 `<widget class="QFrame" name="setup_action_bar">`，设置 `frameShape=NoFrame`
- 内层保留 `<layout class="QHBoxLayout" name="setup_btn_row">`，margins 设为 `left=0, top=12, right=0, bottom=0`（仅顶部留白配合 border-top）
- **调整子项顺序**：`view_results_btn` → `setup_btn_spacer` → `scan_btn`（view_results 移到左侧）
- `scan_btn` 的 `minimumSize` 高度从 60 改为 44，新增 `minimumWidth=180`

保留 `setup_btn_spacer` 的 objectName 不变（仅位置从第 1 项变为第 2 项）。

### 2. `src/fuscan/gui/styles.qss` — 样式调整

#### 新增操作条容器样式
```css
QFrame#setup_action_bar {
    background: transparent;
    border: none;
    border-top: 1px solid #e1e4e8;
}
```
（不加水平 padding，因 setup_layout 已有 12px 边距；仅用 border-top 做视觉分隔）

#### `scan_btn` 改为 PRIMARY 蓝（替换 L180-203）
```css
QPushButton#scan_btn {
    background: #0366d6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
    padding: 8px 32px;
    min-width: 180px;
    min-height: 44px;
}

QPushButton#scan_btn:hover {
    background: #0256c1;
}

QPushButton#scan_btn:pressed {
    background: #024aa0;
}

QPushButton#scan_btn:disabled {
    background: #e1e4e8;
    color: #ffffff;
}
```
移除原绿色 `#2ea44f`/`#2c974b`/`#27873f`。

#### `view_results_btn` 改为次级轮廓样式（从 L207 共享规则中拆出）
```css
QPushButton#view_results_btn {
    background: #ffffff;
    color: #0366d6;
    border: 1px solid #0366d6;
    border-radius: 6px;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 16px;
    min-height: 36px;
}

QPushButton#view_results_btn:hover {
    background: #f1f8ff;
    border-color: #0256c1;
    color: #0256c1;
}

QPushButton#view_results_btn:disabled {
    background: #f6f8fa;
    color: #959da5;
    border-color: #e1e4e8;
}
```
原 `QPushButton#export_btn, #rescan_btn, #view_results_btn` 共享规则改为仅 `#export_btn, #rescan_btn`。

**理由**：scan_btn 改蓝后若 view_results_btn 也保持蓝色填充，两个按钮视觉混淆。轮廓样式建立主次层次：scan_btn（填充蓝，主操作）> view_results_btn（轮廓蓝，次操作）。

### 3. `src/fuscan/gui/main_window_ui.py` — 重新编译

```bash
uv run pyside2-uic src/fuscan/gui/main_window.ui -o src/fuscan/gui/main_window_ui.py
```

### 4. `src/fuscan/gui/main_window.py` — 无需改动

- `self._scan_btn = ui.scan_btn` / `self._view_results_btn = ui.view_results_btn` 绑定不变
- `setup_layout.setStretch(2, 0)` 对 QFrame 仍生效
- 信号槽连接不变

### 5. `tests/test_gui.py` — 新增测试

在 `TestWorkflowStage` 或新建 `TestSetupActionBar` 类中新增：

```python
def test_scan_btn_height_reduced_to_44(self, qapp: QApplication) -> None:
    """scan_btn 最小高度应为 44（与扫描中页按钮一致）。"""
    window = MainWindow()
    assert window._scan_btn.minimumHeight() == 44
    window.close()

def test_scan_btn_minimum_width_180(self, qapp: QApplication) -> None:
    """scan_btn 最小宽度应为 180。"""
    window = MainWindow()
    assert window._scan_btn.minimumWidth() >= 180
    window.close()

def test_setup_action_bar_exists(self, qapp: QApplication) -> None:
    """配置页应包含 setup_action_bar 容器。"""
    window = MainWindow()
    assert hasattr(window._ui, "setup_action_bar")
    assert window._ui.setup_action_bar is not None
    window.close()

def test_scan_btn_qss_uses_primary_blue(self) -> None:
    """QSS 中 scan_btn 应使用 PRIMARY 蓝 #0366d6，不应保留绿色 #2ea44f。"""
    qss = Path("src/fuscan/gui/styles.qss").read_text(encoding="utf-8")
    scan_btn_section = qss[qss.find("QPushButton#scan_btn"):]
    assert "#0366d6" in scan_btn_section
    assert "#2ea44f" not in qss

def test_view_results_btn_qss_is_outline(self) -> None:
    """view_results_btn 应为轮廓样式（白底蓝边），与 scan_btn 主次区分。"""
    qss = Path("src/fuscan/gui/styles.qss").read_text(encoding="utf-8")
    assert "QPushButton#view_results_btn" in qss
    view_results_section = qss[qss.find("QPushButton#view_results_btn"):]
    # 轮廓样式：白底 + 蓝边
    assert "background: #ffffff" in view_results_section[:200]
    assert "border: 1px solid #0366d6" in view_results_section[:200]
```

## 假设与决策

1. **保留 spacer**：`setup_btn_spacer` 仅改变位置（从 view_results_btn 之前移到之后），objectName 不变，避免破坏潜在引用。
2. **view_results_btn 移到左侧**：标准 UX 模式 — 次操作在左，主操作在右。
3. **view_results_btn 改轮廓样式**：避免与 scan_btn 同为蓝色填充导致主次不分。export_btn/rescan_btn 保持蓝色填充不变（结果页的两个按钮都是主操作级别）。
4. **scan_btn 高度 44px**：与扫描中页的 pause_resume_btn/cancel_btn 一致，建立跨阶段按钮高度一致性。
5. **不加水平 padding**：setup_layout 已有 12px 边距，QFrame 再加水平 padding 会导致双边距。

## 验证

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyrefly check
uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96
```

手动验证（可选）：
- 启动 GUI，确认配置页底部有顶部分隔线的操作条
- `scan_btn` 为蓝色填充、44px 高、位于右侧
- `view_results_btn`（有报告时可见）为白底蓝边轮廓样式、位于左侧
- 两个按钮视觉层次清晰：scan_btn 明显更突出
