# pyfilescan 开发技能文档

归档自 iter-01 至 iter-05 的可复用模式、踩坑总结与设计决策。

## 项目架构

```
src/pyfilescan/
├── rules/          # YAML 规则解析与匹配模型
│   ├── model.py    # 不可变 dataclass（Rule/RuleSet/MatchSpec）
│   ├── parser.py   # YAML → 数据结构
│   └── errors.py   # 异常家族
├── scanner/        # 扫描引擎
│   ├── walker.py   # 文件遍历（ignore_dirs/extensions 过滤）
│   ├── context.py  # 扫描上下文（FileEntry/MatchContext）
│   ├── matchers.py # 匹配器（AND/OR/NOT 组合）
│   ├── result.py   # ScanResult/ScanReport/ScanStats
│   └── scanner.py  # Scanner 主类
├── extractors/     # 多格式提取器
│   ├── base.py     # Extractor ABC + ExtractorError
│   ├── registry.py # ExtractorRegistry 注册机制
│   ├── text.py     # 纯文本（charset-normalizer）
│   ├── pdf.py      # PDF（pypdf）
│   ├── office.py   # DOCX/PPTX（python-docx/python-pptx）
│   ├── spreadsheet.py  # XLSX/ODS（openpyxl/odfpy）
│   ├── odf.py      # ODT（odfpy）
│   └── wps.py      # WPS（OOXML 检测 + 复用 Office 库）
├── archive/        # 压缩文件扫描
│   ├── base.py     # ArchiveReader ABC + ArchiveEntry
│   ├── zip_reader.py   # ZIP（zipfile）
│   ├── rar_reader.py   # RAR（rarfile，惰性导入）
│   └── scanner.py  # ArchiveScanner（临时文件提取）
├── gui/            # PySide2 GUI
│   ├── main_window.py  # MainWindow（菜单/工具栏/结果树）
│   ├── worker.py       # ScanWorker(QThread)
│   └── app.py          # launch() 入口
├── watcher/        # 托盘驻守与文件监控
│   ├── monitor.py      # FileMonitor（watchdog）
│   ├── incremental.py  # IncrementalScanner（mtime 跟踪）
│   ├── ignore_dirs.py  # 平台默认忽略目录
│   ├── tray.py         # TrayApp(QSystemTrayIcon)
│   └── __init__.py     # TrayApp 惰性导入
└── cli.py          # CLI 入口（scan/rules/gui/tray/version）
```

## 可复用模式

### 1. 惰性导入打破循环依赖

scanner.py 与 archive/__init__.py 存在循环：scanner 导入 archive，archive 导入 scanner.scanner。
解法：scanner.py 用 `TYPE_CHECKING` 守卫类型导入，运行时在方法内惰性导入。

```python
if TYPE_CHECKING:
    from pyfilescan.archive import ArchiveScanner

class Scanner:
    def scan(self, ...):
        if self._scan_archives:
            from pyfilescan.archive import ArchiveScanner  # 惰性导入
            self._archive_scanner = ArchiveScanner(...)
```

### 2. 包级 __getattr__ 惰性导出

watcher/__init__.py 用 `__getattr__` 延迟导入 TrayApp，使无 PySide2 环境也能 import watcher 子包。

```python
def __getattr__(name):
    if name == "TrayApp":
        from pyfilescan.watcher.tray import TrayApp
        return TrayApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### 3. 提取器注册机制

ExtractorRegistry 按扩展名注册提取器实例，支持大小写不敏感查询。
第三方库在 extract() 方法内 try/except ImportError，未安装时抛 ExtractorError。

### 4. OOXML 格式检测与扩展名绕过

WPS 文件通过 ZIP 魔数（PK\x03\x04）判断是否为 OOXML 兼容格式。
提取时复制到临时文件并改扩展名（.wps→.docx），绕过 python-docx 的扩展名检查。
临时文件用 _safe_unlink 删除，处理 Windows 文件锁定。

### 5. QThread 信号测试模式

QThread 信号在无事件循环时无法传递到主线程。
用 QEventLoop + QTimer.singleShot 超时退出模式等待信号：

```python
loop = QEventLoop()
worker.finished_report.connect(loop.quit)
QTimer.singleShot(5000, loop.quit)  # 超时保护
worker.start()
loop.exec_()
```

### 6. 增量扫描的 mtime 比较

用 `abs(entry.mtime - stored_mtime) < 0.001` 而非 `==`，
避免文件系统 mtime 精度差异导致误判。状态以 path_str→mtime 持久化为 JSON。

### 7. 文件监控事件去抖

watchdog 短时间内可能触发多次事件。FileMonitor 用 Dict[Path, float] 记录
最后事件时间，dedup_interval 内同路径事件被丢弃。
TrayApp 用 QTimer singleShot + 2 秒间隔批量处理文件事件。

## 踩坑总结

### 1. charset-normalizer 短文本误判

GBK 编码的短文本（如"密码"）可能被 charset-normalizer 误判为韩文。
解法：测试中使用足够长的 GBK 文本（至少 20 字符）。

### 2. odfpy H 元素必填属性

odfpy 的 `H`（标题）元素需要 `outlinelevel` 属性，否则抛 AttributeError。
创建测试 ODT 时需：`H(outlinelevel="1", text="标题")`。

### 3. Windows chmod 限制

Windows 上 `chmod(0o000)` 不阻止文件所有者读取，无法用于测试权限错误。
解法：用不存在的文件路径测试 OSError 分支。

### 4. QThread 测试崩溃

TrayApp._full_scan 创建真实 ScanWorker(QThread) 在测试中导致
Windows STATUS_STACK_BUFFER_OVERRUN 崩溃。
解法：用 monkeypatch 替换 ScanWorker 为 FakeWorker（带 finished_report
信号的 connect 方法）。

### 5. PySide2 Python 版本限制

PySide2 仅支持 Python 3.8-3.10，Python 3.13 无法安装。
解法：创建 conda 环境 `pyfilescan`（Python 3.10.20）。

### 6. QApplication 跨测试污染

QApplication 是单例，多个测试模块创建 QApplication 会冲突。
解法：用 `QApplication.instance() or QApplication([])` 模式，
并设置 `QT_QPA_PLATFORM=offscreen` 支持无显示器环境。

### 7. ZIP 压缩包内未知扩展名处理

ArchiveScanner 对压缩包内未知扩展名的文件，原逻辑调用 extract_content
返回空字符串（不抛异常），导致回退到 _decode_bytes 的分支永远不执行。
解法：先检查 _has_extractor(extension)，未知扩展名直接走 _decode_bytes。

## 设计决策

### 1. 零运行时依赖原则 vs 实际需求

项目规范要求零运行时依赖，但文件扫描器需要 pypdf、python-docx、openpyxl 等
第三方库。用户确认"放宽规范，自由选型"后，引入按需的第三方依赖，但在
extract() 方法内惰性导入，未安装时优雅降级。

### 2. PySide2 vs PySide6

用户明确要求 PySide2（尽管 PySide6 是推荐选择）。PySide2 仅支持 Python 3.8-3.10，
需创建专用 conda 环境。

### 3. watchdog 文件监控

选择 watchdog 库进行文件系统监控，跨平台支持、API 简洁。
Observer 异步监控不阻塞主线程，适合托盘驻守场景。

### 4. 托盘应用的批量扫描策略

文件监控触发后不立即扫描，而是加入 pending_paths 队列，由 QTimer 2 秒后
批量扫描。避免解压大量文件时逐个扫描的开销。

### 5. 状态持久化位置

IncrementalScanner 的状态文件应保存在扫描目录外，避免被当作新文件扫描。
测试中用 `tmp_path.parent / f"state_{tmp_path.name}.json"`。
