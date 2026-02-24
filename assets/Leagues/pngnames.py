import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QFileDialog
)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QKeySequence, QClipboard

class PngImporter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PNG Importer")
        self.setFixedSize(200, 200)
        self.setAcceptDrops(True)  # Enable drag-and-drop

        layout = QVBoxLayout(self)

        # Button to import files via dialog
        self.import_btn = QPushButton("Import PNGs")
        self.import_btn.clicked.connect(self.import_pngs)
        layout.addWidget(self.import_btn)

        # List widget to display filenames
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.file_list)

    def import_pngs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PNG files",
            "",
            "PNG Files (*.png)"
        )
        if files:
            self.add_files(files)

    def add_files(self, files):
        for f in files:
            filename = f.split("/")[-1]
            if not self.is_in_list(filename):
                self.file_list.addItem(filename)

    def is_in_list(self, filename):
        for index in range(self.file_list.count()):
            if self.file_list.item(index).text() == filename:
                return True
        return False

    # Handle drag-and-drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(".png")]
        self.add_files(files)

    # Override key press for copying selected items
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            selected_items = self.file_list.selectedItems()
            if selected_items:
                clipboard = QApplication.clipboard()
                filenames = "\n".join([item.text() for item in selected_items])
                clipboard.setText(filenames)
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PngImporter()
    window.show()
    sys.exit(app.exec())
