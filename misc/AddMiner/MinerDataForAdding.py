import sys
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel
)
from PySide6.QtCore import Qt


class CraftingViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crafting Data Viewer")
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        self.label = QLabel("Paste JSON data below:")
        layout.addWidget(self.label)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Paste API JSON here…")
        layout.addWidget(self.input_box)

        self.parse_button = QPushButton("Parse Data")
        layout.addWidget(self.parse_button)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Item ID",
            "Internal Level",
            "Displayed Level",
            "Raw Power (GH/s)",
            "Raw Power (PH/s)",
            "Percent"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(self.table)

        self.parse_button.clicked.connect(self.parse_data)
        self.apply_dark_theme()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                font-size: 13px;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #333;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #444;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QTableWidget {
                background-color: #1e1e1e;
                gridline-color: #333;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                padding: 4px;
                border: 1px solid #333;
            }
        """)

    def _add_row(self, item_id, internal_level, displayed_level,
                 raw_power_gh, raw_power_ph, percent_display):

        row = self.table.rowCount()
        self.table.insertRow(row)

        values = [
            item_id,
            str(internal_level),
            str(displayed_level),
            str(raw_power_gh),            # GH/s as plain number
            f"{raw_power_ph:.3f}",        # PH/s as decimal (no commas)
            f"{percent_display:.2f}%"     # Percent
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, col, item)

    def parse_data(self):
        self.table.setRowCount(0)

        try:
            data = json.loads(self.input_box.toPlainText())
            craftings = data["data"]["craftings"]
        except Exception:
            return

        seen_ids = set()  # avoid duplicates

        for craft in craftings:
            # Include prev_item_info if it hasn't been shown yet
            prev = craft.get("prev_item_info", {})
            item_id = prev.get("_id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                internal_level = prev.get("level", 0)
                displayed_level = internal_level + 1
                raw_power_gh = prev.get("power", 0)
                raw_power_ph = raw_power_gh / 1_000_000
                percent_display = prev.get("percent", 0) / 100

                self._add_row(
                    item_id,
                    internal_level,
                    displayed_level,
                    raw_power_gh,
                    raw_power_ph,
                    percent_display
                )

            # Include the result item
            result = craft.get("result", {})
            item_data = result.get("item_data", {})
            item_id = result.get("_id")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                internal_level = item_data.get("level", 0)
                displayed_level = internal_level + 1
                raw_power_gh = item_data.get("power", 0)
                raw_power_ph = raw_power_gh / 1_000_000
                percent_display = item_data.get("percent", 0) / 100

                self._add_row(
                    item_id,
                    internal_level,
                    displayed_level,
                    raw_power_gh,
                    raw_power_ph,
                    percent_display
                )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CraftingViewer()
    window.show()
    sys.exit(app.exec())
