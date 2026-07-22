# iter-68：缓存读并行化（req-16）

## 需求清单

来源：用户实际扫描 F:\ 全盘 6099 文件耗时 720 秒（8.5 文件/秒，基线 171 文件/秒，
慢 20 倍），`fuscan-perf.json` 显示 cache_* 系列操作占总耗时 85%+。

- [x] R1：消除 SQLite 读查询的 RLock 锁竞争，读操作并行执行

## 迭代目标

iter-66 性能统计增强后，用户实际扫描 F:\ 全盘收集到 `fuscan-perf.json`，
数据显示瓶颈全在 cache_* 系列（累积 5797 秒 / 4 线程，实际墙钟 720 秒）：

| 阶段 | 总耗时 | 次数 | 平均/次 | 最大 |
|------|--------|------|---------|------|
| cache_lookup_hits | 2095s | 5800 | 361ms | 7993ms |
| cache_lookup_extract | 1990s | 5800 | 343ms | 7946ms |
| cache_lookup | 1262s | 6111 | 207ms | 3680ms |
| cache_write | 449s | 123 | 3651ms | 8088ms |

SQLite 查询本应 < 1ms，200-360ms/次说明 4 线程在 RLock 上严重等待。
根因：所有读写操作共享一个 SQLite 连接 + 一把 RLock，WAL 模式的并发读
优势完全被锁抵消。

本迭代实施读写连接分离：读操作使用线程本地只读连接并行执行，写操作
仍用主连接 + RLock 串行化。

## 关键决策与依据

### 决策1：读写连接分离，读操作不加 _lock

WAL 模式下 SQLite 读不阻塞写，但原实现所有操作持同一 RLock，读操作
被写操作串行化。改为：

- **读操作**（`get_cached_hits`/`lookup_file_hash`/`get_extracted_content`/
  `get_rule_hashes`/`schema_version`）：使用线程本地只读连接，无锁并行
- **写操作**（`put_result`/`register_file`/`register_path`/`batch_put_results`/
  `register_ruleset`/`prune_*`）：仍用主连接 + RLock 串行化
- **`stats`**：诊断方法不在热路径，保持主连接 + RLock

### 决策2：线程本地连接 + query_only 保护

`threading.local()` 为每个线程惰性创建独立只读连接，配置：
- `PRAGMA journal_mode = WAL`：与主连接一致
- `PRAGMA query_only = ON`：防止读连接误写
- `isolation_level=None`：自动提交，WAL 下每次查询读最新快照

连接登记到 `_read_conns` 列表，`close()` 时统一关闭。

### 决策3：LRU 独立锁 _lru_lock

`_hit_cache`（OrderedDict）从 `_lock` 保护改为独立的 `_lru_lock`。
LRU 操作（get/put/invalidate/clear）极快（微秒级），独立锁不阻塞 DB 读。

锁顺序约定：`_lock` → `_lru_lock`（写操作先持 `_lock` 再持 `_lru_lock`），
读操作只持 `_lru_lock`，不会死锁。

### 决策4：stats() 保持主连接持锁

`stats()` 不在扫描热路径（仅在扫描结束后或 GUI 中调用），且测试
`test_stats_db_missing_returns_zero_bytes` 依赖修改 `_db_path` 后主连接
仍连接原始数据库。保持 `stats()` 用主连接 + `_lock` 最安全。

## 改动文件清单

| 文件 | 说明 |
|------|------|
| `src/fuscan/cache/store.py` | 模块 docstring 更新；`__init__` 新增 `_lru_lock`/`_read_local`/`_read_conns`；新增 `_get_read_conn()`；读方法改用读连接无锁；LRU 操作改用 `_lru_lock`；`close` 关闭所有读连接 |
| `tests/test_cache.py` | `TestCacheStoreConcurrency` 新增 2 个测试（线程本地只读连接验证 / 并发读不阻塞写验证） |

## 代码实现情况

### _get_read_conn() 线程本地只读连接

```python
def _get_read_conn(self) -> sqlite3.Connection:
    conn = getattr(self._read_local, "conn", None)
    if conn is not None:
        return conn
    conn = sqlite3.connect(str(self._db_path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA query_only = ON")  # 只读保护
    self._read_local.conn = conn
    with self._lru_lock:
        self._read_conns.append(conn)
    return conn
```

### get_cached_hits 读 + LRU 分离

```python
# LRU 查询用 _lru_lock（细粒度）
with self._lru_lock:
    cached = self._hit_cache_get(file_hash, rule_hashes)
if cached is not None:
    return cached
# SQLite 查询用线程本地读连接（无锁并行）
rows = self._get_read_conn().execute(...).fetchall()
# LRU 写回用 _lru_lock
with self._lru_lock:
    self._hit_cache_put(file_hash, rule_hashes, result)
```

### 写操作 LRU 失效用 _lru_lock

```python
def put_result(self, ...):
    with self._lock:  # 写串行化
        self._conn.execute(...)
        with self._lru_lock:  # LRU 失效（锁顺序 _lock → _lru_lock）
            self._hit_cache_invalidate(file_hash)
```

## 整合优化情况

- 读操作完全并行：4 线程各自有读连接，无 RLock 等待
- LRU 细粒度锁：LRU 操作微秒级，不阻塞 DB 读也不被写操作阻塞
- 写操作不变：仍用主连接 + RLock 串行化，保证一致性
- WAL 一致性：读连接自动提交模式下每次查询读最新快照
- query_only 保护：读连接误写会抛 OperationalError

## 测试验证结果

- ruff check / format：通过（93 files already formatted）
- pyrefly check：0 errors
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1439 passed**, 覆盖率 **96%**
- cache/store.py 并发测试全部通过（5/5）：
  - `test_concurrent_writes`：多线程并发写不冲突
  - `test_concurrent_read_write`：读+写并发不抛异常
  - `test_concurrent_same_file_hash`：同 file_hash 并发写最后一个胜出
  - `test_read_connections_are_thread_local_and_query_only`（新增）：读连接线程本地 + query_only
  - `test_concurrent_reads_do_not_block_writes`（新增）：4 线程并发读不阻塞写

## 遗留事项

- 用户需在实际 F:\ 全盘扫描中验证提速效果，预期从 8.5 文件/秒提升至接近
  基线 171 文件/秒（消除 RLock 等待后，瓶颈回到 read_bytes 41ms/次）
- 若仍慢，下一方向：`cache_write` 的 3.65 秒/次（extracted_contents 大文本写入），
  可考虑分表或压缩存储

## 下一轮计划

- 等待用户实际扫描性能数据反馈
- 若 cache_write 仍为瓶颈，优化 extracted_contents 存储
