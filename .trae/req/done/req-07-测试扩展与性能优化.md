# 需求：测试扩展与性能优化

## 核心需求

- [x] 增加更多示例测试，包括不同格式文件对象和不同规则的扫描分析
- [x] 建立基准 benchmark，量化扫描吞吐量（文件/秒、字节/秒）与缓存收益
- [x] 分析并实现提高扫描文件数量每秒的性能优化方法

## 性能优化

- [x] 优化 1：流水线扫描（walk 与 scan 并行，边遍历边 pool.submit，每 500 future 非阻塞 drain）
- [x] 优化 2：缓存模式跳过 filename/path-only 规则的文件 I/O（无 CONTENT 规则时不读文件）
- [x] 优化 3：进度上报减负（无 on_progress 回调时跳过 matched_files 收集）

## Benchmark

- [x] 独立脚本 benchmarks/bench_scan.py（5 场景：单线程/多线程/cpu_count/缓存冷/缓存热）
- [x] table 与 JSON 输出格式
- [x] pytest slow 回归测试（吞吐量 + 缓存命中率阈值）

## 测试覆盖

- [x] 多格式多规则扫描测试（tests/test_multiformat_scan.py，40 个测试）
- [x] 流水线正确性测试（600 文件 drain、无回调 matched_files 空集合）
- [x] 流水线分支覆盖（walk 取消、drain 异常、drain+on_progress、archive+on_progress）
- [x] 覆盖率 ≥ 96% 维持
