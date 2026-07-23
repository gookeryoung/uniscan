try:
    from PySide2.QtWidgets import QDialog
except ImportError:
    from PySide6.QtWidgets import QDialog


from fuscan import __author__, __description__, __license__, __version__

from .about_dialog_ui import Ui_AboutDialog


class AboutDialog(QDialog, Ui_AboutDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.setWindowTitle("关于 fuscan")
        self.label.setText(
            f"<h3>fuscan {__version__}</h3>"
            f"<p>{__description__}</p>"
            f"<p>基于 YAML 规则对多种格式文件进行内容匹配，"
            f"快速发现敏感信息、合规风险与代码安全问题；"
            f"支持压缩文件扫描与缓存加速。</p>"
            f"<p><b>技术栈</b>: Python + PySide</p>"
            f"<p><b>作者</b>: {__author__}<br>"
            f"<b>许可证</b>: {__license__}</p>"
        )
        self.adjustSize()
