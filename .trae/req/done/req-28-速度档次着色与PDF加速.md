# req-28 速度档次着色与 PDF 加速

## 需求

- [x] 为 5 档速度配置对应的标签颜色，从绿（T1 极速）到红（T5 极慢）
- [x] GUI 勾选树子项按速度档次着色显示
- [x] 评估 PDF 解析能否通过 PyO3（Rust 绑定）显著提速
- [x] 评估 ZIP/压缩包解析能否通过 PyO3 显著提速

## 验收标准

- `SpeedTier.color` 属性返回十六进制色值（绿→青→琥珀→橙→红）
- GUI 勾选树子项 `ForegroundRole` 按 `speed_tier.color` 着色
- PDF 提取器优先使用 `pdf_oxide`（Rust + PyO3），回退到 `pypdf`
- `speed_tier` 根据可用后端动态返回：`pdf_oxide` 可用 → T2 快速，否则 T5 极慢
- 全套门禁通过：ruff/format/pyrefly/pytest（覆盖率不低于 95%）

## ZIP/压缩包 PyO3 评估结论

压缩包扫描的瓶颈不在解压本身（Python `zipfile` 已包装 C 实现的 `zlib`），
而在逐条目读取 + 内容提取的循环。PyO3 对 ZIP 解压无明显收益：

1. `zipfile.ZipFile` 底层调用 `zlib`（C 库），解压阶段已释放 GIL
2. 真正耗时的是逐条目调用提取器链（如压缩包内含 PDF/DOCX）
3. PDF 条目已由 `pdf_oxide` 加速；其他条目走既有提取器

结论：压缩包分类维持 T5 极慢（条目数决定总耗时），不引入额外 Rust 依赖。
