# iter-89 压缩包内部条目展示

## 需求清单

- [x] 压缩包内容匹配项需在结果树显示命中的具体文件，区分"压缩包根"与"内部条目路径"（req-26）

## 迭代目标

让压缩包内部条目的命中结果在 GUI/CLI/导出端均可识别并清晰展示"压缩包根路径 + 内部条目路径"，
避免内容预览触发解压耗时，同时让用户一眼看出命中的是压缩包内哪个文件。

此前压缩包内部条目 `ScanResult.path` 形如 `archive.zip!dir/file.txt`，
GUI 结果树第 0 列只取 `path.name`（即 `file.txt`），用户无法区分这是普通文件还是压缩包条目；
详情区对压缩包内部条目调用 `path.stat()` 必然失败，且内容预览会触发解压，导致明显卡顿。

## 关键决策与依据

1. **新增 `archive_path` 字段而非新 dataclass**：在 `ScanResult` 上新增 `archive_path: Path | None` 字段
   标识压缩包内部条目，相比新建 `ArchiveScanResult` 子类更轻量——所有展示/导出/筛选逻辑
   只需 `if sr.is_archive_entry:` 单点判断，无需重写整个 dataclass 层级。
2. **`inner_path` 统一为正斜杠**：ZIP/RAR/7Z 规范要求内部条目路径使用 `/` 分隔符，
   但 Windows 上 `Path(entry.display_path)` 构造时会把 `!` 后部分的 `/` 转成 `\`，
   导致跨平台展示不一致。`inner_path` 在返回前 `replace("\\", "/")` 还原。
3. **结果树第 0 列展示 `a.zip » dir/file.txt` 格式**：原本仅展示 `file.txt`（path.name），
   用户无法区分压缩包条目；新格式 `f"{archive_path.name} » {inner_path}"` 一眼看出命中来源。
   tooltip 仍展示完整 `path`（含 `!` 分隔），便于复制/调试。
4. **详情区跳过 stat 与内容预览**：压缩包内部条目在文件系统不存在，`stat` 必失败；
   内容预览需读字节解压，明显卡顿。改为展示"压缩包路径 / 内部条目路径"双字段，
   内容预览改为提示文案 `压缩包内部条目：未解压预览内容（避免解压耗时）`。
5. **CSV 列扩展而非新格式**：在现有 CSV 表头插入 `archive_path`/`inner_path` 两列，
   普通文件这两列为空字符串，保持向后兼容（旧脚本读 CSV 时新列被忽略）。
6. **JSON 字段 `archive_path` 为字符串或 null**：非压缩包条目序列化为 `null`，
   压缩包条目序列化为压缩根路径字符串，便于下游消费方统一处理。
7. **文本报告附加标注**：`to_text` 在压缩包条目行尾追加 `[压缩包: archive.zip » dir/file.txt]`，
   让纯文本输出也能识别压缩包来源。

## 改动文件清单

修改（源码）：
- `src/fuscan/scanner/result.py`：
  - `ScanResult` 新增 `archive_path: Path | None` 字段与 `is_archive_entry`/`inner_path` 属性
  - `file_info_html` 对压缩包条目跳过 stat，显示"压缩包路径 / 内部条目路径"双字段
  - `to_json` 新增 `archive_path`/`inner_path` 字段
  - `to_csv` 表头新增 `archive_path`/`inner_path` 两列
  - `to_text` 压缩包条目行尾追加 `[压缩包: ...]` 标注
  - `filter` 重建 `ScanResult` 时保留 `archive_path`
- `src/fuscan/archive/scanner.py`：
  - `_scan_entry_uncached`/`_scan_entry_cached` 构造 `ScanResult` 时填充 `archive_path=archive_path`
- `src/fuscan/gui/result_tree.py`：
  - 新增模块级 `_display_name(sr)` 辅助函数
  - `_populate_flat`/`_populate_grouped_by_rule`/`_populate_grouped_by_severity` 第 0 列使用 `_display_name(sr)`
    对压缩包条目展示 `archive.zip » dir/file.txt` 格式
- `src/fuscan/gui/detail_panel.py`：
  - `_populate_preview` 对压缩包条目跳过内容提取，展示提示文案并禁用命中导航

修改（测试）：
- `tests/test_archive.py`：
  - 新增 `TestArchiveEntryResultFields` 测试类，5 个测试覆盖：
    - 命中条目 archive_path 填充
    - 未命中条目 archive_path 也填充
    - 缓存模式下 archive_path 填充
    - 错误结果（压缩根打开失败）archive_path 为 None
    - 普通文件 inner_path 返回空字符串
- `tests/test_gui.py`：
  - 新增 `_build_archive_entry_report` 辅助函数构造含压缩包条目的 ScanReport
  - 新增 `TestArchiveEntryDisplay` 测试类，5 个测试覆盖：
    - 结果树第 0 列 `archive.zip » dir/secret.txt` 格式
    - tooltip 显示完整 `!` 路径
    - 详情区文件信息双字段（压缩包路径 / 内部条目路径）
    - 详情区内容预览跳过解压显示提示文案
    - 按规则分组模式下子项同样展示压缩包格式
- `tests/test_scanner.py`：更新 4 个 CSV 相关测试的表头断言（新增 archive_path/inner_path 列）
- `tests/test_cli.py`：更新 CSV 输出测试表头断言
- `tests/test_export.py`：更新 CSV 保存测试前缀断言

修改（文档）：
- `.trae/req/req-26-压缩包内部条目展示.md`：新建需求清单
- `.trae/docs/iter-89-压缩包内部条目展示.md`：新建迭代记录

## 代码实现情况

### ScanResult 新字段与属性

```python
@dataclass(frozen=True)
class ScanResult:
    path: Path
    size: int
    hits: tuple[RuleHit, ...] = field(default_factory=tuple)
    errors: int = 0
    user_skipped: bool = False
    # 压缩包根路径（iter-89）：非 None 时标识本结果为压缩包内部条目
    archive_path: Path | None = None

    @property
    def is_archive_entry(self) -> bool:
        """是否为压缩包内部条目（archive_path 非 None）。"""
        return self.archive_path is not None

    @property
    def inner_path(self) -> str:
        """压缩包内部条目路径（``!`` 后部分），统一正斜杠分隔。"""
        if self.archive_path is None:
            return ""
        path_str = str(self.path)
        sep_idx = path_str.find("!")
        if sep_idx < 0:
            return ""
        return path_str[sep_idx + 1 :].replace("\\", "/")
```

### ArchiveScanner 填充 archive_path

`_scan_entry_uncached`/`_scan_entry_cached` 在 `ScanResult(...)` 构造时新增 `archive_path=archive_path`。
错误结果（压缩根打开失败/列出条目失败）的 `ScanResult` 不填充 `archive_path`，保留为 None，
因为这些结果代表压缩根本身而非内部条目。

### 结果树第 0 列展示格式

```python
def _display_name(sr: ScanResult) -> str:
    """普通文件展示 path.name；压缩包条目展示 archive.zip » dir/file.txt。"""
    if sr.is_archive_entry and sr.archive_path is not None:
        return f"{sr.archive_path.name} » {sr.inner_path}"
    return sr.path.name
```

### 详情区压缩包条目跳过预览

```python
def _populate_preview(self, result: ScanResult) -> None:
    if result.is_archive_entry:
        self._c.preview.setPlainText(
            "压缩包内部条目：未解压预览内容（避免解压耗时）。\n"
            "命中信息见上方命中表与详情列；压缩包路径与内部条目路径见上方文件信息。"
        )
        self._hit_positions = []
        self._current_hit_index = -1
        self._plain_text = ""
        self._update_nav_label()
        return
    # ... 原有内容预览逻辑
```

### CSV/JSON/Text 导出扩展

- CSV 表头：`path,archive_path,inner_path,size,severity,rule,description,match_count,detail`
  普通文件 archive_path/inner_path 列为空字符串
- JSON：`hits[].archive_path` 为字符串或 null，`hits[].inner_path` 为字符串或 null
- Text：压缩包条目行尾追加 `[压缩包: archive.zip » dir/file.txt]`

## 整合优化情况

- 复用 `ScanResult.is_archive_entry` 单点判断，避免在 result_tree/detail_panel/导出端
  分别判断 `archive_path is not None`
- `inner_path` 属性统一处理路径分隔符，避免每个调用方各自 `replace("\\", "/")`
- `_display_name` 提取为模块级纯函数，三处填充逻辑共用，无重复实现

## 测试验证结果

- `uv run ruff check src tests`：通过
- `uv run ruff format --check src tests`：通过
- `uv run pyrefly check`：0 errors
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=95`：
  - 1585 passed, 16 deselected
  - 覆盖率 95.11%（>= 95% 门禁）

新增测试覆盖：
- `TestArchiveEntryResultFields`（5 个）：ArchiveScanner 填充 archive_path 各场景
- `TestArchiveEntryDisplay`（5 个）：GUI 结果树/详情区/分组模式下压缩包条目展示

## 遗留事项

- 无

## 下一轮计划

- 无（需求已闭环）
