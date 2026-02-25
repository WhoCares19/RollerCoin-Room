import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt

class ImageTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Tool")
        self.setFixedSize(600, 600)  # GUI window size

        self.image_label = QLabel()
        self.image_label.setFixedSize(200, 200)
        self.image_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.image_label.setStyleSheet("background:#222;")

        self.import_btn = QPushButton("Import")
        self.export_btn = QPushButton("Export")
        self.export_btn.setEnabled(False)

        self.import_btn.clicked.connect(self.import_image)
        self.export_btn.clicked.connect(self.export_image)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.export_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        layout.addLayout(btn_layout)

        self.processed_pixmap = None

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Image", "", "Images (*.png)")
        if not path:
            return

        original = QPixmap(path)
        cropped = self.crop_transparent(original)

        # Resize cropped content to 63x(115-63=52?) height remaining for content
        content_height = 115 - 0  # if all height is reserved for image? We'll put content to fit 115 total
        result = QPixmap(63, 115)
        result.fill(Qt.transparent)

        # Scale cropped image to fit width 63, max height 115
        scaled = cropped.scaled(63, 115, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        painter = QPainter(result)
        # draw image at bottom, leaving empty space on top
        painter.drawPixmap(0, 115 - scaled.height(), scaled)
        painter.end()

        self.processed_pixmap = result
        self.image_label.setPixmap(result)
        self.export_btn.setEnabled(True)

    def export_image(self):
        if not self.processed_pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Image", "", "PNG (*.png)")
        if path:
            self.processed_pixmap.save(path, "PNG")

    def crop_transparent(self, pixmap):
        image = pixmap.toImage()
        w, h = image.width(), image.height()

        left, right = w, 0
        top, bottom = h, 0

        for y in range(h):
            for x in range(w):
                if image.pixelColor(x, y).alpha() > 0:
                    left = min(left, x)
                    right = max(right, x)
                    top = min(top, y)
                    bottom = max(bottom, y)

        return pixmap.copy(left, top, right - left + 1, bottom - top + 1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ImageTool()
    w.show()
    sys.exit(app.exec())
