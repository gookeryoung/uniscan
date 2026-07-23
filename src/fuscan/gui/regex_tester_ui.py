# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'regex_tester.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_RegexTesterDialog(object):
    def setupUi(self, RegexTesterDialog):
        if not RegexTesterDialog.objectName():
            RegexTesterDialog.setObjectName(u"RegexTesterDialog")
        RegexTesterDialog.resize(720, 680)
        RegexTesterDialog.setMinimumSize(QSize(720, 680))
        self.main_layout = QVBoxLayout(RegexTesterDialog)
        self.main_layout.setObjectName(u"main_layout")
        self.regex_input_layout = QHBoxLayout()
        self.regex_input_layout.setObjectName(u"regex_input_layout")
        self.regex_pattern_label = QLabel(RegexTesterDialog)
        self.regex_pattern_label.setObjectName(u"regex_pattern_label")

        self.regex_input_layout.addWidget(self.regex_pattern_label)

        self.regex_pattern_edit = QLineEdit(RegexTesterDialog)
        self.regex_pattern_edit.setObjectName(u"regex_pattern_edit")
        self.regex_pattern_edit.setClearButtonEnabled(True)

        self.regex_input_layout.addWidget(self.regex_pattern_edit)

        self.regex_case_sensitive_check = QCheckBox(RegexTesterDialog)
        self.regex_case_sensitive_check.setObjectName(u"regex_case_sensitive_check")

        self.regex_input_layout.addWidget(self.regex_case_sensitive_check)


        self.main_layout.addLayout(self.regex_input_layout)

        self.regex_io_layout = QHBoxLayout()
        self.regex_io_layout.setObjectName(u"regex_io_layout")
        self.test_text_col = QVBoxLayout()
        self.test_text_col.setObjectName(u"test_text_col")
        self.test_text_label = QLabel(RegexTesterDialog)
        self.test_text_label.setObjectName(u"test_text_label")

        self.test_text_col.addWidget(self.test_text_label)

        self.regex_test_text_edit = QPlainTextEdit(RegexTesterDialog)
        self.regex_test_text_edit.setObjectName(u"regex_test_text_edit")

        self.test_text_col.addWidget(self.regex_test_text_edit)


        self.regex_io_layout.addLayout(self.test_text_col)

        self.regex_result_col = QVBoxLayout()
        self.regex_result_col.setObjectName(u"regex_result_col")
        self.regex_result_label = QLabel(RegexTesterDialog)
        self.regex_result_label.setObjectName(u"regex_result_label")

        self.regex_result_col.addWidget(self.regex_result_label)

        self.regex_result_view = QTextEdit(RegexTesterDialog)
        self.regex_result_view.setObjectName(u"regex_result_view")
        self.regex_result_view.setReadOnly(True)

        self.regex_result_col.addWidget(self.regex_result_view)


        self.regex_io_layout.addLayout(self.regex_result_col)


        self.main_layout.addLayout(self.regex_io_layout)

        self.regex_cheatsheet_label = QLabel(RegexTesterDialog)
        self.regex_cheatsheet_label.setObjectName(u"regex_cheatsheet_label")

        self.main_layout.addWidget(self.regex_cheatsheet_label)

        self.regex_cheatsheet_view = QTextEdit(RegexTesterDialog)
        self.regex_cheatsheet_view.setObjectName(u"regex_cheatsheet_view")
        self.regex_cheatsheet_view.setReadOnly(True)

        self.main_layout.addWidget(self.regex_cheatsheet_view)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.close_btn = QPushButton(RegexTesterDialog)
        self.close_btn.setObjectName(u"close_btn")

        self.horizontalLayout.addWidget(self.close_btn)


        self.main_layout.addLayout(self.horizontalLayout)


        self.retranslateUi(RegexTesterDialog)
        self.close_btn.clicked.connect(RegexTesterDialog.accept)

        QMetaObject.connectSlotsByName(RegexTesterDialog)
    # setupUi

    def retranslateUi(self, RegexTesterDialog):
        RegexTesterDialog.setWindowTitle(QCoreApplication.translate("RegexTesterDialog", u"\u6b63\u5219\u8868\u8fbe\u5f0f\u6d4b\u8bd5\u5de5\u5177", None))
        self.regex_pattern_label.setText(QCoreApplication.translate("RegexTesterDialog", u"\u6b63\u5219:", None))
#if QT_CONFIG(tooltip)
        self.regex_pattern_edit.setToolTip(QCoreApplication.translate("RegexTesterDialog", u"\u8f93\u5165\u6b63\u5219\u8868\u8fbe\u5f0f\uff0c\u5982 \\d{4}-\\d{2}-\\d{2}", None))
#endif // QT_CONFIG(tooltip)
        self.regex_pattern_edit.setPlaceholderText(QCoreApplication.translate("RegexTesterDialog", u"\u8f93\u5165\u6b63\u5219\u8868\u8fbe\u5f0f\uff0c\u5982 \\d{4}-\\d{2}-\\d{2}", None))
        self.regex_pattern_edit.setProperty("fontFamily", QCoreApplication.translate("RegexTesterDialog", u"Consolas", None))
#if QT_CONFIG(tooltip)
        self.regex_case_sensitive_check.setToolTip(QCoreApplication.translate("RegexTesterDialog", u"\u52fe\u9009\u540e\u533a\u5206\u5927\u5c0f\u5199\uff08\u9ed8\u8ba4\u5ffd\u7565\u5927\u5c0f\u5199\uff0c\u4e0e\u89c4\u5219\u9ed8\u8ba4\u884c\u4e3a\u4e00\u81f4\uff09", None))
#endif // QT_CONFIG(tooltip)
        self.regex_case_sensitive_check.setText(QCoreApplication.translate("RegexTesterDialog", u"\u533a\u5206\u5927\u5c0f\u5199", None))
        self.test_text_label.setText(QCoreApplication.translate("RegexTesterDialog", u"\u6d4b\u8bd5\u6587\u672c:", None))
#if QT_CONFIG(tooltip)
        self.regex_test_text_edit.setToolTip(QCoreApplication.translate("RegexTesterDialog", u"\u652f\u6301\u591a\u884c\u6587\u672c\uff1b\u6bcf\u884c\u72ec\u7acb\u5339\u914d\uff0c\u8de8\u884c\u4e0d\u8fde\u63a5", None))
#endif // QT_CONFIG(tooltip)
        self.regex_test_text_edit.setPlaceholderText(QCoreApplication.translate("RegexTesterDialog", u"\u8f93\u5165\u6d4b\u8bd5\u6587\u672c...", None))
        self.regex_result_label.setText(QCoreApplication.translate("RegexTesterDialog", u"\u547d\u4e2d\u7ed3\u679c:", None))
#if QT_CONFIG(tooltip)
        self.regex_result_view.setToolTip(QCoreApplication.translate("RegexTesterDialog", u"\u663e\u793a\u6bcf\u4e2a\u547d\u4e2d\u7684\u4f4d\u7f6e\u3001\u6587\u672c\u4e0e\u6355\u83b7\u7ec4", None))
#endif // QT_CONFIG(tooltip)
        self.regex_result_view.setPlaceholderText(QCoreApplication.translate("RegexTesterDialog", u"\u70b9\u51fb\u300c\u6d4b\u8bd5\u300d\u67e5\u770b\u547d\u4e2d\u7ed3\u679c...", None))
        self.regex_result_view.setProperty("fontFamily", QCoreApplication.translate("RegexTesterDialog", u"Consolas", None))
#if QT_CONFIG(tooltip)
        self.regex_cheatsheet_label.setToolTip(QCoreApplication.translate("RegexTesterDialog", u"Python re \u6a21\u5757\u652f\u6301\u7684\u5e38\u7528\u6b63\u5219\u8bed\u6cd5", None))
#endif // QT_CONFIG(tooltip)
        self.regex_cheatsheet_label.setText(QCoreApplication.translate("RegexTesterDialog", u"\u8bed\u6cd5\u901f\u67e5:", None))
        self.regex_cheatsheet_view.setProperty("fontFamily", QCoreApplication.translate("RegexTesterDialog", u"Consolas", None))
        self.close_btn.setText(QCoreApplication.translate("RegexTesterDialog", u"\u5173\u95ed", None))
    # retranslateUi

