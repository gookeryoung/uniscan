# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'about_dialog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_AboutDialog(object):
    def setupUi(self, AboutDialog):
        if not AboutDialog.objectName():
            AboutDialog.setObjectName(u"AboutDialog")
        AboutDialog.resize(599, 378)
        self.horizontalLayout = QHBoxLayout(AboutDialog)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label = QLabel(AboutDialog)
        self.label.setObjectName(u"label")

        self.horizontalLayout.addWidget(self.label)


        self.retranslateUi(AboutDialog)

        QMetaObject.connectSlotsByName(AboutDialog)
    # setupUi

    def retranslateUi(self, AboutDialog):
        AboutDialog.setWindowTitle(QCoreApplication.translate("AboutDialog", u"\u5173\u4e8e", None))
        self.label.setText(QCoreApplication.translate("AboutDialog", u"TextLabel", None))
    # retranslateUi

