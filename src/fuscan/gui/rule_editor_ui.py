# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rule_editor.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_RuleEditorDialog(object):
    def setupUi(self, RuleEditorDialog):
        if not RuleEditorDialog.objectName():
            RuleEditorDialog.setObjectName(u"RuleEditorDialog")
        RuleEditorDialog.resize(760, 780)
        RuleEditorDialog.setMinimumSize(QSize(760, 780))
        self.main_layout = QVBoxLayout(RuleEditorDialog)
        self.main_layout.setObjectName(u"main_layout")
        self.file_layout = QHBoxLayout()
        self.file_layout.setObjectName(u"file_layout")
        self.file_label = QLabel(RuleEditorDialog)
        self.file_label.setObjectName(u"file_label")

        self.file_layout.addWidget(self.file_label)

        self.file_combo = QComboBox(RuleEditorDialog)
        self.file_combo.setObjectName(u"file_combo")

        self.file_layout.addWidget(self.file_combo)


        self.main_layout.addLayout(self.file_layout)

        self.empty_label = QLabel(RuleEditorDialog)
        self.empty_label.setObjectName(u"empty_label")
        self.empty_label.setVisible(False)

        self.main_layout.addWidget(self.empty_label)

        self.rule_editor = QTextEdit(RuleEditorDialog)
        self.rule_editor.setObjectName(u"rule_editor")

        self.main_layout.addWidget(self.rule_editor)

        self.regex_test_group = QGroupBox(RuleEditorDialog)
        self.regex_test_group.setObjectName(u"regex_test_group")
        self.regex_test_layout = QVBoxLayout(self.regex_test_group)
        self.regex_test_layout.setSpacing(6)
        self.regex_test_layout.setObjectName(u"regex_test_layout")
        self.regex_test_layout.setContentsMargins(8, 8, 8, 8)
        self.regex_input_layout = QHBoxLayout()
        self.regex_input_layout.setObjectName(u"regex_input_layout")
        self.regex_pattern_label = QLabel(self.regex_test_group)
        self.regex_pattern_label.setObjectName(u"regex_pattern_label")

        self.regex_input_layout.addWidget(self.regex_pattern_label)

        self.regex_pattern_edit = QLineEdit(self.regex_test_group)
        self.regex_pattern_edit.setObjectName(u"regex_pattern_edit")
        self.regex_pattern_edit.setClearButtonEnabled(True)

        self.regex_input_layout.addWidget(self.regex_pattern_edit)

        self.regex_case_sensitive_check = QCheckBox(self.regex_test_group)
        self.regex_case_sensitive_check.setObjectName(u"regex_case_sensitive_check")

        self.regex_input_layout.addWidget(self.regex_case_sensitive_check)

        self.regex_test_btn = QPushButton(self.regex_test_group)
        self.regex_test_btn.setObjectName(u"regex_test_btn")

        self.regex_input_layout.addWidget(self.regex_test_btn)


        self.regex_test_layout.addLayout(self.regex_input_layout)

        self.regex_io_layout = QHBoxLayout()
        self.regex_io_layout.setObjectName(u"regex_io_layout")
        self.test_text_col = QVBoxLayout()
        self.test_text_col.setObjectName(u"test_text_col")
        self.test_text_label = QLabel(self.regex_test_group)
        self.test_text_label.setObjectName(u"test_text_label")

        self.test_text_col.addWidget(self.test_text_label)

        self.regex_test_text_edit = QPlainTextEdit(self.regex_test_group)
        self.regex_test_text_edit.setObjectName(u"regex_test_text_edit")

        self.test_text_col.addWidget(self.regex_test_text_edit)


        self.regex_io_layout.addLayout(self.test_text_col)

        self.regex_result_col = QVBoxLayout()
        self.regex_result_col.setObjectName(u"regex_result_col")
        self.regex_result_label = QLabel(self.regex_test_group)
        self.regex_result_label.setObjectName(u"regex_result_label")

        self.regex_result_col.addWidget(self.regex_result_label)

        self.regex_result_view = QTextEdit(self.regex_test_group)
        self.regex_result_view.setObjectName(u"regex_result_view")
        self.regex_result_view.setReadOnly(True)

        self.regex_result_col.addWidget(self.regex_result_view)


        self.regex_io_layout.addLayout(self.regex_result_col)


        self.regex_test_layout.addLayout(self.regex_io_layout)

        self.regex_cheatsheet_label = QLabel(self.regex_test_group)
        self.regex_cheatsheet_label.setObjectName(u"regex_cheatsheet_label")

        self.regex_test_layout.addWidget(self.regex_cheatsheet_label)

        self.regex_cheatsheet_view = QTextEdit(self.regex_test_group)
        self.regex_cheatsheet_view.setObjectName(u"regex_cheatsheet_view")
        self.regex_cheatsheet_view.setReadOnly(True)

        self.regex_test_layout.addWidget(self.regex_cheatsheet_view)


        self.main_layout.addWidget(self.regex_test_group)

        self.btn_layout = QHBoxLayout()
        self.btn_layout.setObjectName(u"btn_layout")
        self.reload_btn = QPushButton(RuleEditorDialog)
        self.reload_btn.setObjectName(u"reload_btn")

        self.btn_layout.addWidget(self.reload_btn)

        self.btn_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.btn_layout.addItem(self.btn_spacer)

        self.save_btn = QPushButton(RuleEditorDialog)
        self.save_btn.setObjectName(u"save_btn")

        self.btn_layout.addWidget(self.save_btn)

        self.close_btn = QPushButton(RuleEditorDialog)
        self.close_btn.setObjectName(u"close_btn")

        self.btn_layout.addWidget(self.close_btn)


        self.main_layout.addLayout(self.btn_layout)


        self.retranslateUi(RuleEditorDialog)
        self.close_btn.clicked.connect(RuleEditorDialog.accept)

        self.regex_test_btn.setDefault(True)


        QMetaObject.connectSlotsByName(RuleEditorDialog)
    # setupUi

    def retranslateUi(self, RuleEditorDialog):
        RuleEditorDialog.setWindowTitle(QCoreApplication.translate("RuleEditorDialog", u"\u89c4\u5219\u7f16\u8f91\u5668", None))
        self.file_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\u89c4\u5219\u6587\u4ef6:", None))
        self.empty_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\uff08\u672a\u52a0\u8f7d\u4efb\u4f55\u89c4\u5219\u6587\u4ef6\uff09", None))
        self.rule_editor.setProperty("fontFamily", QCoreApplication.translate("RuleEditorDialog", u"Consolas", None))
        self.regex_test_group.setTitle(QCoreApplication.translate("RuleEditorDialog", u"\u6b63\u5219\u8868\u8fbe\u5f0f\u9a8c\u8bc1", None))
#if QT_CONFIG(tooltip)
        self.regex_test_group.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u6d4b\u8bd5\u6b63\u5219\u8868\u8fbe\u5f0f\u662f\u5426\u7b26\u5408\u9884\u671f\uff0c\u4e0e\u626b\u63cf\u5f15\u64ce finditer \u884c\u4e3a\u4e00\u81f4", None))
#endif // QT_CONFIG(tooltip)
        self.regex_pattern_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\u6b63\u5219:", None))
#if QT_CONFIG(tooltip)
        self.regex_pattern_edit.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u8f93\u5165\u6b63\u5219\u8868\u8fbe\u5f0f\uff0c\u5982 \\d{4}-\\d{2}-\\d{2}", None))
#endif // QT_CONFIG(tooltip)
        self.regex_pattern_edit.setPlaceholderText(QCoreApplication.translate("RuleEditorDialog", u"\u8f93\u5165\u6b63\u5219\u8868\u8fbe\u5f0f\uff0c\u5982 \\d{4}-\\d{2}-\\d{2}", None))
        self.regex_pattern_edit.setProperty("fontFamily", QCoreApplication.translate("RuleEditorDialog", u"Consolas", None))
#if QT_CONFIG(tooltip)
        self.regex_case_sensitive_check.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u52fe\u9009\u540e\u533a\u5206\u5927\u5c0f\u5199\uff08\u9ed8\u8ba4\u5ffd\u7565\u5927\u5c0f\u5199\uff0c\u4e0e\u89c4\u5219\u9ed8\u8ba4\u884c\u4e3a\u4e00\u81f4\uff09", None))
#endif // QT_CONFIG(tooltip)
        self.regex_case_sensitive_check.setText(QCoreApplication.translate("RuleEditorDialog", u"\u533a\u5206\u5927\u5c0f\u5199", None))
#if QT_CONFIG(tooltip)
        self.regex_test_btn.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u5bf9\u6d4b\u8bd5\u6587\u672c\u6267\u884c\u6b63\u5219\u5339\u914d\u5e76\u663e\u793a\u547d\u4e2d\u7ed3\u679c", None))
#endif // QT_CONFIG(tooltip)
        self.regex_test_btn.setText(QCoreApplication.translate("RuleEditorDialog", u"\u6d4b\u8bd5", None))
        self.test_text_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\u6d4b\u8bd5\u6587\u672c:", None))
#if QT_CONFIG(tooltip)
        self.regex_test_text_edit.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u652f\u6301\u591a\u884c\u6587\u672c\uff1b\u6bcf\u884c\u72ec\u7acb\u5339\u914d\uff0c\u8de8\u884c\u4e0d\u8fde\u63a5", None))
#endif // QT_CONFIG(tooltip)
        self.regex_test_text_edit.setPlaceholderText(QCoreApplication.translate("RuleEditorDialog", u"\u8f93\u5165\u6d4b\u8bd5\u6587\u672c...", None))
        self.regex_result_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\u547d\u4e2d\u7ed3\u679c:", None))
#if QT_CONFIG(tooltip)
        self.regex_result_view.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u663e\u793a\u6bcf\u4e2a\u547d\u4e2d\u7684\u4f4d\u7f6e\u3001\u6587\u672c\u4e0e\u6355\u83b7\u7ec4", None))
#endif // QT_CONFIG(tooltip)
        self.regex_result_view.setProperty("fontFamily", QCoreApplication.translate("RuleEditorDialog", u"Consolas", None))
        self.regex_result_view.setPlaceholderText(QCoreApplication.translate("RuleEditorDialog", u"\u70b9\u51fb\u300c\u6d4b\u8bd5\u300d\u67e5\u770b\u547d\u4e2d\u7ed3\u679c...", None))
        self.regex_cheatsheet_label.setText(QCoreApplication.translate("RuleEditorDialog", u"\u901f\u67e5\u624b\u518c\uff08\u5e38\u7528\u8bed\u6cd5\uff09:", None))
#if QT_CONFIG(tooltip)
        self.regex_cheatsheet_label.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"Python re \u6a21\u5757\u652f\u6301\u7684\u5e38\u7528\u6b63\u5219\u8bed\u6cd5", None))
#endif // QT_CONFIG(tooltip)
        self.regex_cheatsheet_view.setProperty("fontFamily", QCoreApplication.translate("RuleEditorDialog", u"Consolas", None))
#if QT_CONFIG(tooltip)
        self.reload_btn.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u653e\u5f03\u4fee\u6539\uff0c\u4ece\u6587\u4ef6\u91cd\u65b0\u52a0\u8f7d\u5185\u5bb9", None))
#endif // QT_CONFIG(tooltip)
        self.reload_btn.setText(QCoreApplication.translate("RuleEditorDialog", u"\u91cd\u65b0\u52a0\u8f7d", None))
#if QT_CONFIG(tooltip)
        self.save_btn.setToolTip(QCoreApplication.translate("RuleEditorDialog", u"\u4fdd\u5b58\u6587\u4ef6\u5e76\u91cd\u65b0\u52a0\u8f7d\u89c4\u5219\u96c6", None))
#endif // QT_CONFIG(tooltip)
        self.save_btn.setText(QCoreApplication.translate("RuleEditorDialog", u"\u4fdd\u5b58\u5e76\u5e94\u7528", None))
        self.close_btn.setText(QCoreApplication.translate("RuleEditorDialog", u"\u5173\u95ed", None))
    # retranslateUi

