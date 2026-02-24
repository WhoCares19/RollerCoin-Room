import sys
import sqlite3
import csv
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget,
    QFileDialog, QProgressBar, QMessageBox
)
from PySide6.QtGui import QKeySequence, QPalette, QColor
from PySide6.QtCore import Qt, QThread, Signal

# Worker thread to scan DB without freezing GUI
class DBScanner(QThread):
    progress = Signal(int)         # percent
    status = Signal(str)           # current name
    result = Signal(list)          # final list of names without images

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, image_path FROM miner_definitions")
            rows = cursor.fetchall()
            total = len(rows)
            missing_names = []

            for i, (name, image) in enumerate(rows, 1):
                self.status.emit(f"Checking: {name}")
                if not image or image.strip() == "":
                    missing_names.append(name)
                percent = int(i / total * 100)
                self.progress.emit(percent)
                self.msleep(10)  # small delay to let GUI update
            self.result.emit(missing_names)
        except Exception as e:
            self.result.emit([])
            print("DB scan error:", e)
        finally:
            if conn:
                conn.close()

class MinerChecker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Miner Image Checker")
        self.setFixedSize(200, 400)

        self.miner_names = []

        layout = QVBoxLayout(self)

        # Buttons
        self.import_btn = QPushButton("Import DB")
        self.import_btn.clicked.connect(self.import_db)
        layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self.export_csv)
        layout.addWidget(self.export_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # List widget for miner names
        self.name_list = QListWidget()
        self.name_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.name_list)

        # Apply dark theme and golden buttons
        self.apply_dark_theme()
        self.apply_golden_buttons()

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
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(80, 80, 150))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        self.setPalette(palette)

    def apply_golden_buttons(self):
        button_style = """
        QPushButton {
            background-color: #c2a349;  /* gold */
            color: white;
            border: 1px solid #B8860B;
            border-radius: 4px;
            padding: 4px;
        }
        QPushButton:hover {
            background-color: #c9a94a;
        }
        QPushButton:pressed {
            background-color: #DAA520;
        }
        """
        self.import_btn.setStyleSheet(button_style)
        self.export_btn.setStyleSheet(button_style)

    def import_db(self):
        db_path, _ = QFileDialog.getOpenFileName(self, "Select SQLite DB", "", "SQLite DB (*.db *.sqlite)")
        if not db_path:
            return

        # Disable buttons while scanning
        self.import_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.name_list.clear()
        self.progress_bar.setValue(0)

        # Start scanning in worker thread
        self.worker = DBScanner(db_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.update_status)
        self.worker.result.connect(self.finish_scan)
        self.worker.start()

    def update_status(self, name):
        self.progress_bar.setFormat(f"{self.progress_bar.value()}% - {name}")

    def finish_scan(self, missing_names):
        self.miner_names = missing_names
        self.name_list.clear()
        self.name_list.addItems(self.miner_names)
        self.progress_bar.setFormat("Done")
        self.progress_bar.setValue(100)

        self.import_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

    def export_csv(self):
        if not self.miner_names:
            QMessageBox.warning(self, "Export CSV", "No names to export")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "miners_missing_images.csv", "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Name"])
                for name in self.miner_names:
                    writer.writerow([name])
            QMessageBox.information(self, "Export CSV", "Export completed successfully")
        except Exception as e:
            QMessageBox.critical(self, "Export CSV", f"Error: {e}")

    # Copy selected items with Ctrl+C
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            selected_items = self.name_list.selectedItems()
            if selected_items:
                clipboard = QApplication.clipboard()
                clipboard.setText("\n".join([item.text() for item in selected_items]))
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MinerChecker()
    window.show()
    sys.exit(app.exec())
