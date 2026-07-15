# iter-39 性能优化策略执行

## 需求清单

- [x] P1：大小文件分流哈希算法（< 8KB SHA-256，≥ 8KB BLAKE2b）
- [x] P2：SQLite 批量写入接口（BatchWriteItem + batch_put_results）
- [x] P3：ArchiveScanner 线程安全修复与流水线并行化（archive 文件级别并行）
- [x] P4：新增 extracted_contents 表缓存提取器结果

## 迭代目标

延续 iter-38 缓存性能优化，针对扫描器写入路径与压缩包扫描并行度进行四项优化，
在不改变公共 API 与扫描结果语义的前提下提升吞吐量，消除已知性能瓶颈。

## 改动文件清单

### `src/fuscan/cache/hashes.py`（P1）

- `hash_bytes(data)` 按数据大小分流：`len(data) < _SIZE_THRESHOLD`（8KB）用
  `hashlib.sha256`，否则用 `hashlib.blake2b(data, digest_size=32)`
- 两种算法输出均为 64 字符 hex，与 `scanned_files.file_hash` 列 schema 兼容
- 小文件避免 BLAKE2b 上下文初始化开销，大文件利用 BLAKE2b 的 GIL 释放与 SIMD 加速
- `CACHE_COMPAT_VERSION` 不递增（输出格式与长度一致，纯算法选型变化）

### `src/fuscan/cache/store.py`（P2 + P4）

- **P2 批量写入**：
  - 新增 `BatchWriteItem` 冻结数据类：`file_hash`/`size`/`path`/`mtime`/`hits`
    （`hits` 为 `tuple[tuple[str, RuleHit | None], ...]`）
  - 新增 `batch_put_results(items)`：单次事务 `executemany` 写入
    `scanned_files`/`file_paths`/`scan_results` 三表，`BEGIN`/`COMMIT`/`ROLLBACK`
    控制，COMMIT 成功后统一 `_hit_cache_invalidate` 每个涉及的 `file_hash`
  - 循环导入打破：`RuleHit` 移入 `TYPE_CHECKING` 块，`get_cached_hits` 内延迟导入
- **P4 提取内容缓存**：
  - 新增 `get_extracted_content(file_hash)`/`put_extracted_content(file_hash, content, ext)`
  - `extracted_contents` 表 schema：`(file_hash TEXT PK, content TEXT, extension TEXT, created_at REAL)`
  - `prune_stale_files` 同步清理 `extracted_contents` 中无对应 `scanned_files` 的孤儿记录

### `src/fuscan/cache/schema.py`（P4）

- `CURRENT_SCHEMA_VERSION` 递增为 `3`（新增 `extracted_contents` 表）
- `CACHE_COMPAT_VERSION` 递增为 `3`（`extracted_contents` 为新缓存数据，旧库无此表）
- `migrate()` 在 v2→v3 迁移时 `CREATE TABLE extracted_contents`
- `_purge_cache_data()` 清空业务表时包含 `extracted_contents`

### `src/fuscan/cache/__init__.py`

- 导出 `BatchWriteItem`

### `src/fuscan/scanner/scanner.py`（P2 + P3）

- **P2 批量写入集成**：
  - 新增模块常量 `_BATCH_THRESHOLD = 50`
  - `Scanner.__init__` 末尾新增 `_pending_batch: list[BatchWriteItem]` 与
    `_batch_lock = threading.Lock()`
  - `_scan_entry_cached` 预筛路径改为累积 `BatchWriteItem(hits=())` 而非直接
    `register_file`/`register_path`
  - `_scan_entry_cached` 常规路径改为累积 `batch_hits` 列表后一次性 `_add_to_batch`
  - 新增 `_add_to_batch`（加锁追加，达阈值自动 flush）、`_flush_batch`、
    `_flush_batch_locked`（调用 `batch_put_results` 并清空缓冲）
  - `scan()` 中新增两处 flush：archive phase 前 + scan() 末尾（保险 flush）
- **P3 archive 文件级别并行**：
  - `_scan_archive_phase` 重写：`max_workers > 1` 时用 `ThreadPoolExecutor` +
    `as_completed`，每个 archive 一个 future；单线程退化保持原有顺序逻辑
  - 取消逻辑：`_check_control()` 时 `cancel()` 未启动的 future，已启动的结果丢弃
  - 提取 `_accumulate_archive_results` 辅助方法，消除单/多线程路径的结果累积重复
  - 用 `is_archive(e.path)` 替代 `get_reader(e.path) is not None` 过滤，避免
    损坏文件在过滤阶段抛异常

### `src/fuscan/archive/scanner.py`（P4）

- `_scan_entry_cached` 接入提取内容缓存：读字节算哈希后先查
  `get_extracted_content`，命中跳过 `extract_content_from_bytes`；
  未命中则提取并 `put_extracted_content`

### `src/fuscan/archive/base.py`

- 新增 `is_archive(path)` 函数：仅按扩展名判断是否为已注册压缩类型，不实例化
  reader。损坏文件仍返回 True，交由 `scan_archive` 捕获返回错误结果

### `src/fuscan/archive/__init__.py`

- 导出 `is_archive`

## 关键决策与依据

### P1 大小文件分流阈值

- 阈值定 8KB：BLAKE2b 在 OpenSSL 后端有上下文初始化开销（约 1-2μs），对 < 8KB
  小文件净收益不显著；≥ 8KB 时 SIMD 加速与 GIL 释放收益超过初始化成本
- 不递增 `CACHE_COMPAT_VERSION`：两种算法输出格式与长度完全一致（64 字符 hex），
  旧缓存可继续使用，纯算法选型不构成数据语义变更

### P2 批量写入阈值与锁

- 阈值 50：单次事务约 200 行写入（50 文件 × 平均 4 行），相比逐条 commit
  减少 99% 提交开销，同时避免单事务过大导致 WAL 页切换
- `_batch_lock` 保护 `_pending_batch` 跨 worker 并发累积与 flush，不阻塞
  CacheStore 内部的 `_conn_lock`（两者锁粒度分离）

### P3 archive 文件级别并行的安全性

- `ArchiveScanner._compiled` 只读（构造后不变），`get_reader` 在 worker 内
  创建独立 reader 实例，无共享状态
- `CacheStore` 内部 `_conn_lock`（RLock）串行化所有 SQLite 操作，跨 archive
  并发写入安全
- 单个 archive 内条目顺序执行：避免同一 reader 的 `list_entries`/`read_entry`
  被多线程并发调用（ZipFile/RarFile 非线程安全）

### P4 提取内容缓存的键设计

- 以 `file_hash` 为主键：同内容不同路径（如重复文件、archive 内同名条目）共享
  一份提取结果，跳过重复 `extract_content_from_bytes` 调用
- `extension` 字段记录提取时的扩展名，便于未来按扩展名统计缓存分布

## 代码实现情况

四项策略全部实现并通过门禁：

- P1：`hash_bytes` 大小分流，5 个相关测试覆盖分流逻辑
- P2：`BatchWriteItem` + `batch_put_results`，15 个新测试（含事务回滚）
- P3：`_scan_archive_phase` 并行化 + `is_archive` 过滤，6 个并行专门测试
- P4：`extracted_contents` 表 + `get/put_extracted_content`，覆盖在 archive 测试

## 整合优化情况

- 提取 `_accumulate_archive_results` 消除 `_scan_archive_phase` 单/多线程路径
  的结果累积重复，同时解决 PLR0912 分支过多告警
- `is_archive` 函数化避免过滤时实例化 reader，消除损坏文件在过滤阶段抛异常的
  风险，同时避免正常文件的重复实例化开销

## 测试验证结果

### 门禁

| 项目 | 结果 |
|------|------|
| ruff check | All checks passed |
| ruff format --check | 75 files already formatted |
| pyrefly check | 0 errors（131 suppressed） |
| pytest -m "not slow" --cov | 1230 passed，覆盖率 96.14% ≥ 95% |
| pytest -m slow tests/test_benchmark.py | 16 passed |

### 新增测试

- `tests/test_cache.py::TestBatchPutResults`：11 个批量写入测试
- `tests/test_scanner.py::TestScannerBatchFlush`：4 个集成测试（含取消后 flush）
- `tests/test_archive.py::TestArchiveParallelScan`：6 个并行扫描测试
  （结果一致性、进度单调、取消、无 archive、单 archive、损坏 archive 错误计数）

### 性能基准对比

| 场景 | iter-38 (files/s) | iter-39 (files/s) | 变化 |
|------|------------------:|------------------:|------|
| S1 单线程无缓存 | 85.4 | 106.0 | +24% |
| S2 4 线程无缓存 | 172.5 | 171.2 | -0.8% |
| S3 24 线程无缓存 | 169.9 | 170.7 | +0.5% |
| S4 4 线程+冷缓存 | 163.9 | 163.9 | 持平 |
| S5 4 线程+热缓存 | 6006.4 | 6369.8 | +6% |

- S1 提升 24%：P2 批量写入对单线程收益最大（消除逐条 commit/fsync）
- S5 小幅提升：P4 提取内容缓存收益在热路径占比已极小
- S2/S3/S4 无回退：P1 大小文件分流对基准测试 4-6KB 文件无显著差异，
  P3 archive 并行化在无压缩包场景下不触发

## 遗留事项

- P3 archive 并行化在基准测试中未触发（测试集无压缩包），实际含大量压缩包
  目录的场景预期有显著收益，待真实场景验证
- P1 大小文件分流阈值 8KB 为经验值，可根据实际文件大小分布进一步调优

## 下一轮计划

iter-39 性能优化策略已全部闭环。后续可考虑：
- 真实压缩包场景的 archive 并行化性能验证
- WAL 模式与 `synchronous` 调优（当前为默认 DELETE 模式）
- 大文件内存映射读取（`mmap`）避免全量 `read_bytes`
