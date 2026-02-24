import sys
import json
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt


DARK_STYLE = """
QWidget {
    background-color: #121212;
    color: #e0e0e0;
    font-size: 14px;
}
QTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #333;
    padding: 6px;
}
QPushButton {
    background-color: #2b2b2b;
    border: 1px solid #444;
    padding: 8px;
}
QPushButton:hover {
    background-color: #3a3a3a;
}
"""


class JsonExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RollerCoin Player Inventory Exporter")
        self.resize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(
            "Paste one or more full JSON blocks here..."
        )

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_json)

        layout.addWidget(self.input_edit)
        layout.addWidget(self.export_button)

        self.setStyleSheet(DARK_STYLE)

    def extract_json_blocks(self, text):
        blocks = []
        depth = 0
        start = None

        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    blocks.append(text[start:i + 1])
                    start = None

        return blocks

    def export_json(self):
        raw_text = self.input_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Error", "No JSON data pasted.")
            return

        json_blocks = self.extract_json_blocks(raw_text)
        if not json_blocks:
            QMessageBox.warning(self, "Error", "No valid JSON blocks found.")
            return

        result_items = []

        for block in json_blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue

            items = data.get("data", {}).get("items", [])

            for item in items:
                if "id" in item and "quantity" in item:
                    result_items.append({
                        "miner_id": item["id"],
                        "quantity": item["quantity"]
                    })

        if not result_items:
            QMessageBox.warning(
                self,
                "Error",
                "No miner_id/quantity pairs found."
            )
            return

        final_json = {
            "items": result_items
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save JSON",
            "output.json",
            "JSON Files (*.json)"
        )

        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(final_json, f, indent=4)

        QMessageBox.information(
            self,
            "Done",
            "JSON exported successfully."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JsonExtractorApp()
    window.show()
    sys.exit(app.exec())
