# iter-61 需求清单

## 需求1：移除 HitDetailDialog 对话框设计

- [x] 删除 detail_dialog.py / detail_dialog_ui.py / detail_dialog.ui 三个对话框相关文件
- [x] 移除 main_window.py 中 HitDetailDialog 导入与相关方法（_on_result_activated、_on_open_in_window_requested、"在新窗口打开"菜单项）
- [x] 移除 detail_panel.py 中 open_in_window_requested 信号与 open_in_window 方法
- [x] 移除 result_tree.py 中 result_activated 信号、doubleClicked 连接与 _handle_double_clicked 方法
- [x] 移除 styles.qss 中 HitDetailDialog 样式块（#hit_info_label/#hit_preview/#hit_hits_table）
- [x] 更新 preview_utils.py 模块文档（detail_dialog.py → detail_panel.py）
- [x] 更新 SKILL.md GUI 模块清单（detail_dialog.py → detail_panel.py）

## 需求2：测试整合与门禁通过

- [x] 移除 test_gui.py 中 HitDetailDialog 相关测试（TestHitDetailDialog / TestHitDetailDialogNavigation / test_double_click_grouped_child_opens_dialog / test_detail_open_in_window_*）
- [x] 重命名 TestHitDetailDialogHelpers → TestPreviewHelpers（公共辅助函数测试保留）
- [x] 迁移 TestMatchTextHighlighting 中 4 个 test_dialog_positions_* 测试改用 DetailPanel（重命名 test_panel_positions_*）
- [x] 适配 test_result_tree_context_menu_actions 断言（3 → 2 个动作）
- [x] ruff check / ruff format / pyrefly / pytest --cov 通过
