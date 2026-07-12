# 需求 05：详情界面命中定位修复与测试丰富

## 背景

用户报告：数据库连接串密码与 Bearer 令牌命中后，详情界面无法定位（显示"无命中"或未高亮）。

## 根因

`matchers.py._apply_leaf` 使用 `repr(m.group(0))` 将匹配文本序列化进 `detail`，
`detail_dialog.py._extract_keywords` 与 `main_window.py._extract_keywords` 再用
正则 `'([^']+)'` 从 detail 反解析关键词。该链路在以下场景失真：

- [x] 反斜杠：`repr` 将 `\` 转义为 `\\`，关键词与原文不匹配
- [x] 单引号：`repr` 切换为双引号包裹，单引号正则提取失败
- [x] 换行符：`repr` 将 `\r\n` 转义为字面字符；且 `QTextDocument.find` 不跨段落查找

## 需求

- [x] 1. 修复详情界面命中定位：数据库连接串密码、Bearer 令牌以及含特殊字符（反斜杠/单引号/换行）的命中均能正确定位与高亮
- [x] 2. 为修复制定测试代码：覆盖 matchers → scanner → GUI 详情区的全链路
- [x] 3. 丰富测试示例：覆盖更多典型格式（txt/yaml/json/docx/xlsx/odt/zip/二进制等），测试需具有典型性

## 验收标准

- [x] `MatchResult` 与 `RuleHit` 新增 `match_text` 字段，直接存储原始匹配文本
- [x] `_extract_keywords` 改为读取 `match_text`，不再依赖 `repr` 反解析
- [x] 详情对话框（HitDetailDialog）与主窗口详情区均能正确定位含特殊字符的命中
- [x] 新增测试覆盖：反斜杠、单引号、换行符、跨行 Bearer、大小写、多命中并存等场景
- [x] 全套门禁通过：ruff check/format、pyrefly、pytest --cov ≥ 95%
