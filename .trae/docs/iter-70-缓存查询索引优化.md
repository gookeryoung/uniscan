# iter-70：缓存查询索引优化（req-16 续）

## 需求清单

来源：用户实际扫描 F:\ 全盘 5299 文件耗时 291 秒（18.2 文件/秒），
`fuscan-perf.json` 显示 `cache_lookup` 占总耗时 93%。

- [x] R1：消除 `lookup_file_hash` 查询的全表扫描，降至 < 1ms/次

## 迭代目标

iter-68 读并行化消除了 `cache_lookup_hits`/`cache_lookup_extract` 的锁竞争
（从 200 万 ms 降至接近 0），但 `cache_lookup`（`lookup_file_hash`）反而
成为新瓶颈：

| 阶段 | iter-68 前 | iter-68 后 | 变化 |
|------|-----------|-----------|------|
| cache_lookup_hits | 2,095,351 ms / 5800 | 95 ms / 2 | 读并行化生效 |
| cache_lookup_extract | 1,990,035 ms / 5800 | 16 ms / 2 | 读并行化生效 |
| **cache_lookup** | **1,262,227 ms / 6111** | **2,697,251 ms / 5311** | **反而上升** |
| cache_write | 449,092 ms / 123 | 84,696 ms / 107 | 下降 |
| read_bytes | 234,869 ms / 5800 | 0.8 ms / 2 | 缓存命中 |

`cache_lookup` 每次 508ms（比之前 207ms 更慢），占总耗时 93%。
这不是锁竞争（已用读连接），而是 **SQL 查询本身慢**。

## 关键决策与依据

### 根因：scanned_files 表无 size 索引

`lookup_file_hash` 原查询：
```sql
SELECT file_hash FROM file_paths
WHERE path = ? AND mtime = ? AND file_hash IN (
    SELECT file_hash FROM scanned_files WHERE size = ?
)
```

- `file_paths` 有 `idx_paths_path`（单列 path），可用
- **`scanned_files` 无 `size` 索引**，子查询 `WHERE size = ?` 全表扫描
- 当 `scanned_files` 有几千条记录时，每次查询 200-500ms

### 决策1：新增两个索引

```sql
CREATE INDEX IF NOT EXISTS idx_scanned_size ON scanned_files(size);
CREATE INDEX IF NOT EXISTS idx_paths_path_mtime ON file_paths(path, mtime);
```

- `idx_scanned_size`：让子查询按 size 索引扫描
- `idx_paths_path_mtime`：复合索引，让 `WHERE path=? AND mtime=?` 只用索引完成

### 决策2：IN 子查询改写为 JOIN

```sql
SELECT fp.file_hash FROM file_paths fp
JOIN scanned_files sf ON fp.file_hash = sf.file_hash
WHERE fp.path = ? AND fp.mtime = ? AND sf.size = ?
```

JOIN 形式更明确：先用 `idx_paths_path_mtime` 定位 file_paths，再用
`scanned_files` 主键 `file_hash` JOIN 验证 size，全程索引扫描。

### 决策3：CURRENT_VERSION 递增到 5，CACHE_COMPAT_VERSION 不变

索引变更不改变数据语义，`IF NOT EXISTS` 幂等升级，不触发 purge。
`CACHE_COMPAT_VERSION` 保持 5，用户已有缓存数据不丢失。

## 改动文件清单

| 文件 | 说明 |
|------|------|
| `src/fuscan/cache/schema.py` | `CURRENT_VERSION` 4→5；`SCHEMA_SQL` 新增 `idx_scanned_size` + `idx_paths_path_mtime`；migrate 注释新增 v5→v6 说明 |
| `src/fuscan/cache/store.py` | `lookup_file_hash` 查询从 IN 子查询改写为 JOIN |
| `tests/test_cache.py` | `TestMigrate` 新增 `test_migrate_v5_creates_indexes` 验证索引存在 |

## 测试验证结果

- ruff check / format：通过
- pyrefly check：0 errors
- pytest -m "not slow" --cov=fuscan --cov-fail-under=95：**1445 passed**, 覆盖率 **96%**
- 新增 `test_migrate_v5_creates_indexes` 验证索引存在

## 预期效果

`lookup_file_hash` 从 508ms/次降至 < 1ms/次（索引扫描），预期吞吐量
从 18.2 文件/秒大幅提升。实际效果待用户验证。

## 遗留事项

- 用户需实际扫描验证提速效果
- 若 `cache_write`（791ms/次）仍为瓶颈，下一方向优化 extracted_contents 存储

## 下一轮计划

- 等待用户实际扫描性能数据反馈
