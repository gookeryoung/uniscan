# 需求：完善 lint、typecheck、测试以及文档

## 背景

项目当前状态：
- ruff check：通过
- pyrefly check：719 个错误（398 个来自自动生成的 _ui.py，321 个来自手写代码/测试）
- pytest 覆盖率：95.60%，1 个 skipped
- 文档：.trae/docs/ 和 .trae/req/ 目录为空，部分公共 API 缺少 docstring

## 需求清单

- [x] 1. pyrefly 配置排除自动生成的 _ui.py 文件
- [x] 2. 修复手写代码（main_window/settings_dialog/tray/worker 等）的 pyrefly 类型错误
- [x] 3. 修复测试文件（test_gui/test_extractors 等）的类型注解错误
- [x] 4. 修复 1 个 skipped 测试
- [x] 5. 补充未覆盖分支测试，覆盖率 ≥ 96%
- [x] 6. 补全公共 API 的中文 docstring
- [x] 7. 更新 README 用户文档
- [x] 8. 创建 .trae/docs/iter-01 迭代记录

## 验收标准

- `uv run ruff check src tests` 通过
- `uv run ruff format --check src tests` 通过
- `uv run pyrefly check` 0 错误（排除 _ui.py 后）
- `uv run pytest -m "not slow" --cov=fuscan --cov-fail-under=96` 通过
- 无 skipped 测试
- 公共 API 均有中文 docstring
- README 包含安装、使用、配置说明

## 特殊约束

- 不修改 .trae/rules/ 下文件
- _ui.py 为自动生成文件，仅通过配置排除，不手动修复
- PySide2 stub 问题用 `# type: ignore[规则码]` 处理，禁用裸 `# type: ignore`
