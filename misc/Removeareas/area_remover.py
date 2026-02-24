import sys
import os
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QVBoxLayout, QWidget, QLabel
from PySide6.QtGui import QImage, QPalette, QColor, Qt, qAlpha
from PySide6.QtCore import QRect

def trim_transparent_area(image: QImage) -> QImage:
    """Trim transparent borders from a QImage using reliable alpha detection."""
    if image.format() != QImage.Format_ARGB32:
        image = image.convertToFormat(QImage.Format_ARGB32)

    width = image.width()
    height = image.height()

    top, left = height, width
    bottom, right = 0, 0

    for y in range(height):
        for x in range(width):
            alpha = qAlpha(image.pixel(x, y))
            if alpha != 0:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y

    # Fully transparent image
    if left > right or top > bottom:
        return QImage(1, 1, QImage.Format_ARGB32)

    return image.copy(QRect(left, top, right - left + 1, bottom - top + 1))

def batch_process(folder_path: str):
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.png', '.tif', '.tiff')):
            full_path = os.path.join(folder_path, filename)
            image = QImage(full_path)
            if image.isNull():
                continue
            trimmed = trim_transparent_area(image)
            trimmed.save(full_path)  # overwrite original

class ImageTrimmerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Batch Transparent Trimmer")
        layout = QVBoxLayout()

        self.label = QLabel("Select a folder to trim all transparent areas:")
        layout.addWidget(self.label)

        self.button = QPushButton("Select Folder")
        self.button.clicked.connect(self.select_folder)
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.apply_dark_theme()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            batch_process(folder)
            self.label.setText(f"Processed all images in:\n{folder}")

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(60, 60, 60))
        palette.setColor(QPalette.ButtonText, Qt.black)  # as requested
        palette.setColor(QPalette.Highlight, QColor(80, 80, 80))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        self.setPalette(palette)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageTrimmerApp()
    window.resize(400, 120)
    window.show()
    sys.exit(app.exec())
