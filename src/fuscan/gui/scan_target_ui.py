# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'scan_target.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(781, 112)
        self.horizontalLayout = QHBoxLayout(Form)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.target_group = QGroupBox(Form)
        self.target_group.setObjectName(u"target_group")
        self.target_group_layout = QVBoxLayout(self.target_group)
        self.target_group_layout.setSpacing(8)
        self.target_group_layout.setObjectName(u"target_group_layout")
        self.target_group_layout.setContentsMargins(12, 16, 12, 12)
        self.scan_mode_layout = QHBoxLayout()
        self.scan_mode_layout.setSpacing(8)
        self.scan_mode_layout.setObjectName(u"scan_mode_layout")
        self.scan_mode_combo = QComboBox(self.target_group)
        self.scan_mode_combo.addItem("")
        self.scan_mode_combo.addItem("")
        self.scan_mode_combo.addItem("")
        self.scan_mode_combo.setObjectName(u"scan_mode_combo")
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.scan_mode_combo.sizePolicy().hasHeightForWidth())
        self.scan_mode_combo.setSizePolicy(sizePolicy)
        self.scan_mode_combo.setMinimumSize(QSize(0, 40))

        self.scan_mode_layout.addWidget(self.scan_mode_combo)

        self.target_stack = QStackedWidget(self.target_group)
        self.target_stack.setObjectName(u"target_stack")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.target_stack.sizePolicy().hasHeightForWidth())
        self.target_stack.setSizePolicy(sizePolicy1)
        self.full_scan_page = QWidget()
        self.full_scan_page.setObjectName(u"full_scan_page")
        self.full_scan_layout = QHBoxLayout(self.full_scan_page)
        self.full_scan_layout.setObjectName(u"full_scan_layout")
        self.full_scan_layout.setContentsMargins(0, 0, 0, 0)
        self.full_scan_label = QLabel(self.full_scan_page)
        self.full_scan_label.setObjectName(u"full_scan_label")

        self.full_scan_layout.addWidget(self.full_scan_label)

        self.target_stack.addWidget(self.full_scan_page)
        self.drive_select_page = QWidget()
        self.drive_select_page.setObjectName(u"drive_select_page")
        self.drive_buttons_layout = QHBoxLayout(self.drive_select_page)
        self.drive_buttons_layout.setSpacing(4)
        self.drive_buttons_layout.setObjectName(u"drive_buttons_layout")
        self.drive_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.target_stack.addWidget(self.drive_select_page)
        self.folder_select_page = QWidget()
        self.folder_select_page.setObjectName(u"folder_select_page")
        self.folder_select_layout = QHBoxLayout(self.folder_select_page)
        self.folder_select_layout.setSpacing(4)
        self.folder_select_layout.setObjectName(u"folder_select_layout")
        self.folder_select_layout.setContentsMargins(0, 0, 0, 0)
        self.path_combo = QComboBox(self.folder_select_page)
        self.path_combo.setObjectName(u"path_combo")
        sizePolicy1.setHeightForWidth(self.path_combo.sizePolicy().hasHeightForWidth())
        self.path_combo.setSizePolicy(sizePolicy1)
        self.path_combo.setMinimumSize(QSize(0, 40))

        self.folder_select_layout.addWidget(self.path_combo)

        self.select_path_btn = QPushButton(self.folder_select_page)
        self.select_path_btn.setObjectName(u"select_path_btn")
        self.select_path_btn.setMinimumSize(QSize(0, 40))

        self.folder_select_layout.addWidget(self.select_path_btn)

        self.target_stack.addWidget(self.folder_select_page)

        self.scan_mode_layout.addWidget(self.target_stack)


        self.target_group_layout.addLayout(self.scan_mode_layout)


        self.horizontalLayout.addWidget(self.target_group)


        self.retranslateUi(Form)

        self.target_stack.setCurrentIndex(2)


        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.target_group.setTitle(QCoreApplication.translate("Form", u"\u626b\u63cf\u76ee\u6807", None))
        self.scan_mode_combo.setItemText(0, QCoreApplication.translate("Form", u"\u5168\u76d8\u626b\u63cf", None))
        self.scan_mode_combo.setItemText(1, QCoreApplication.translate("Form", u"\u9009\u62e9\u76d8\u7b26", None))
        self.scan_mode_combo.setItemText(2, QCoreApplication.translate("Form", u"\u9009\u62e9\u6587\u4ef6\u5939", None))

#if QT_CONFIG(tooltip)
        self.scan_mode_combo.setToolTip(QCoreApplication.translate("Form", u"\u9009\u62e9\u626b\u63cf\u6a21\u5f0f", None))
#endif // QT_CONFIG(tooltip)
        self.full_scan_label.setText(QCoreApplication.translate("Form", u"\u5c06\u626b\u63cf\u6240\u6709\u76d8\u7b26", None))
#if QT_CONFIG(tooltip)
        self.path_combo.setToolTip(QCoreApplication.translate("Form", u"\u626b\u63cf\u8def\u5f84\uff08\u53ef\u4ece\u5386\u53f2\u8bb0\u5f55\u4e2d\u9009\u62e9\uff09", None))
#endif // QT_CONFIG(tooltip)
        self.select_path_btn.setText(QCoreApplication.translate("Form", u"\u9009\u62e9...", None))
    # retranslateUi

