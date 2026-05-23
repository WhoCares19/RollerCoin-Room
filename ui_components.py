from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMenu,
    QProgressBar, QSplashScreen, QApplication, QDialog
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QSize, QEvent
from PySide6.QtGui import QPixmap, QColor, QCursor, QIcon
from ui_styles import DARK_STYLESHEET

class ImportProgressDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 120)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        layout = QVBoxLayout(self)
        self.label = QLabel("Initializing...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.setStyleSheet(parent.styleSheet() if parent else DARK_STYLESHEET)

    def update_status(self, value, text):
        self.label.setText(text)
        self.progress.setValue(value)
        QApplication.processEvents()

    def update_progress(self, value, text):
        """Alias for update_status to maintain compatibility with splash screen calls."""
        self.update_status(value, text)

class HoverMenuButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.menu = QMenu(self)
        self.menu.installEventFilter(self)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.check_hover_and_hide)
        
    def enterEvent(self, event):
        self.hide_timer.stop()
        if not self.menu.isVisible():
            pos = self.mapToGlobal(QPoint(0, self.height()))
            self.menu.popup(pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start(300)
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.menu:
            if event.type() == QEvent.Type.Enter:
                self.hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self.hide_timer.start(300)
        return super().eventFilter(obj, event)

    def check_hover_and_hide(self):
        if not self.menu.isVisible():
            return
        cursor_pos = QCursor.pos()
        btn_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        menu_rect = self.menu.geometry()
        safe_zone = btn_rect.united(menu_rect).adjusted(-10, -10, 10, 10)
        if not safe_zone.contains(cursor_pos):
            self.menu.hide()
        else:
            self.hide_timer.start(300)

class LoadingSplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(400, 200)
        pixmap.fill(QColor("#121212"))
        super().__init__(pixmap)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.label = QLabel("Initializing Mining Room Simulator...")
        self.label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress.setFormat("%p%")
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                background-color: #1a1a1a;
                color: #ffffff;
                height: 30px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #00ff00;
                width: 1px;
            }
        """)
        
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.setLayout(layout)

    def update_progress(self, value, text):
        self.label.setText(text)
        self.progress.setValue(value)
        QApplication.processEvents()