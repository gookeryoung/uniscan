# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'rule_panel.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

import resources_rc

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(722, 458)
        self.horizontalLayout = QHBoxLayout(Form)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.rules_group = QGroupBox(Form)
        self.rules_group.setObjectName(u"rules_group")
        self.rules_group_layout = QVBoxLayout(self.rules_group)
        self.rules_group_layout.setSpacing(6)
        self.rules_group_layout.setObjectName(u"rules_group_layout")
        self.rules_group_layout.setContentsMargins(12, 16, 12, 12)
        self.rules_btn_row = QHBoxLayout()
        self.rules_btn_row.setSpacing(8)
        self.rules_btn_row.setObjectName(u"rules_btn_row")
        self.load_rules_btn = QPushButton(self.rules_group)
        self.load_rules_btn.setObjectName(u"load_rules_btn")
        self.load_rules_btn.setMinimumSize(QSize(150, 40))
        icon = QIcon()
        icon.addFile(u":/assets/icons/load_list.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.load_rules_btn.setIcon(icon)

        self.rules_btn_row.addWidget(self.load_rules_btn)

        self.edit_rule_btn = QPushButton(self.rules_group)
        self.edit_rule_btn.setObjectName(u"edit_rule_btn")
        self.edit_rule_btn.setMinimumSize(QSize(0, 40))
        icon1 = QIcon()
        icon1.addFile(u":/assets/icons/edit.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.edit_rule_btn.setIcon(icon1)

        self.rules_btn_row.addWidget(self.edit_rule_btn)

        self.rules_btn_spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.rules_btn_row.addItem(self.rules_btn_spacer)


        self.rules_group_layout.addLayout(self.rules_btn_row)

        self.rules_file_label = QLabel(self.rules_group)
        self.rules_file_label.setObjectName(u"rules_file_label")

        self.rules_group_layout.addWidget(self.rules_file_label)

        self.rules_file_list = QListWidget(self.rules_group)
        self.rules_file_list.setObjectName(u"rules_file_list")
        self.rules_file_list.setMaximumSize(QSize(16777215, 120))

        self.rules_group_layout.addWidget(self.rules_file_list)

        self.rules_tree = QTreeWidget(self.rules_group)
        self.rules_tree.setObjectName(u"rules_tree")
        self.rules_tree.setRootIsDecorated(False)

        self.rules_group_layout.addWidget(self.rules_tree)


        self.horizontalLayout.addWidget(self.rules_group)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.rules_group.setTitle(QCoreApplication.translate("Form", u"\u89c4\u5219\u914d\u7f6e", None))
        self.load_rules_btn.setText(QCoreApplication.translate("Form", u"\u52a0\u8f7d\u89c4\u5219...", None))
#if QT_CONFIG(tooltip)
        self.edit_rule_btn.setToolTip(QCoreApplication.translate("Form", u"\u7f16\u8f91\u9009\u4e2d\u7684\u89c4\u5219\u6587\u4ef6", None))
#endif // QT_CONFIG(tooltip)
        self.edit_rule_btn.setText(QCoreApplication.translate("Form", u"\u7f16\u8f91", None))
        self.rules_file_label.setText(QCoreApplication.translate("Form", u"\u89c4\u5219\u6587\u4ef6\uff08\u987a\u5e8f\u4ece\u4e0a\u5230\u4e0b\uff0c\u540e\u8005\u8986\u76d6\u524d\u8005\uff09", None))
#if QT_CONFIG(tooltip)
        self.rules_file_list.setToolTip(QCoreApplication.translate("Form", u"\u5df2\u52a0\u8f7d\u7684\u89c4\u5219\u6587\u4ef6\uff0c\u5217\u8868\u987a\u5e8f\u4ee3\u8868\u4f18\u5148\u7ea7\uff08\u4ece\u4f4e\u5230\u9ad8\uff09", None))
#endif // QT_CONFIG(tooltip)
        ___qtreewidgetitem = self.rules_tree.headerItem()
        ___qtreewidgetitem.setText(2, QCoreApplication.translate("Form", u"\u6269\u5c55\u540d", None));
        ___qtreewidgetitem.setText(1, QCoreApplication.translate("Form", u"\u4e25\u91cd\u7b49\u7ea7", None));
        ___qtreewidgetitem.setText(0, QCoreApplication.translate("Form", u"\u89c4\u5219\u540d", None));
    # retranslateUi

