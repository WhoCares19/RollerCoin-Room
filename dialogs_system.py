import os
import re
import importer
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, 
    QFileDialog, QFormLayout, QLineEdit, QCheckBox, QGroupBox,
    QDoubleSpinBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
from ui_styles import resolve_path
from settings import ROOM_THEME_DATA

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setFixedSize(500, 500)
        self.config = config
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.cb_auto_room = QCheckBox("Auto import room")
        self.cb_auto_inv = QCheckBox("Auto import inventory")
        self.cb_backup_room = QCheckBox("Backup Player Room on every start")
        self.cb_auto_inv_backup = QCheckBox("Backup Player Inventory on every start")
        self.cb_pause_gifs = QCheckBox("Pause .gif animations")
        self.cb_pause_hamsters = QCheckBox("Pause hamster animations")
        self.cb_light_theme = QCheckBox("Light theme")
        self.cb_auto_save = QCheckBox("Auto Save Application")

        self.cb_auto_room.setChecked(self.config.get("auto_import_room", True))
        self.cb_auto_inv.setChecked(self.config.get("auto_import_inv", True))
        self.cb_backup_room.setChecked(self.config.get("backup_room", True))
        self.cb_auto_inv_backup.setChecked(self.config.get("backup_inv", True))
        self.cb_pause_gifs.setChecked(self.config.get("pause_gifs", False))
        self.cb_pause_hamsters.setChecked(self.config.get("pause_hamsters", False))
        self.cb_light_theme.setChecked(self.config.get("light_theme", False))
        self.cb_auto_save.setChecked(self.config.get("auto_save", True))

        layout.addWidget(self.cb_auto_room)
        layout.addWidget(self.cb_auto_inv)
        layout.addWidget(self.cb_backup_room)
        layout.addWidget(self.cb_auto_inv_backup)
        layout.addWidget(self.cb_pause_gifs)
        layout.addWidget(self.cb_pause_hamsters)
        layout.addWidget(self.cb_light_theme)
        layout.addWidget(self.cb_auto_save)

        room_group = QGroupBox("Room Settings")
        room_layout = QFormLayout(room_group)

        self.sb_scale = QDoubleSpinBox()
        self.sb_scale.setRange(0.5, 2.0)
        self.sb_scale.setSingleStep(0.05)
        self.sb_scale.setValue(self.config.get("rack_scale", 1.0))
        room_layout.addRow("Rack Scale:", self.sb_scale)

        # Room Theme Selection
        self.theme_combo = QComboBox()
        theme_items = []
        for folder_name in ROOM_THEME_DATA.keys():
            display_name = folder_name
            if folder_name.lower().startswith("dunno"):
                # Extract digits to maintain the specific number
                num_match = re.search(r'\d+', folder_name)
                num = num_match.group() if num_match else ""
                display_name = f"Some Room {num}".strip()
            
            theme_items.append((display_name, folder_name))
        
        # Sort alphabetically by the display name
        theme_items.sort(key=lambda x: x[0].lower())

        for d_name, f_key in theme_items:
            self.theme_combo.addItem(d_name, f_key)

        # Set current selection based on existing config
        current_bg = self.config.get("room1_bg", "")
        for i in range(self.theme_combo.count()):
            folder_key = self.theme_combo.itemData(i)
            if folder_key in current_bg:
                self.theme_combo.setCurrentIndex(i)
                break

        room_layout.addRow("Room Theme:", self.theme_combo)

        layout.addWidget(room_group)
        layout.addStretch()

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save"); save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_box.addStretch(); btn_box.addWidget(save_btn); btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def get_data(self):
        folder_key = self.theme_combo.currentData()
        files = ROOM_THEME_DATA[folder_key]
        
        # Construct relative paths: assets/rooms/FolderName/FileName
        r1_path = f"assets/rooms/{folder_key}/{files[0]}".replace("\\", "/")
        r_rest_path = f"assets/rooms/{folder_key}/{files[1]}".replace("\\", "/")

        return {
            "auto_import_room": self.cb_auto_room.isChecked(),
            "auto_import_inv": self.cb_auto_inv.isChecked(),
            "backup_room": self.cb_backup_room.isChecked(),
            "backup_inv": self.cb_auto_inv_backup.isChecked(),
            "pause_gifs": self.cb_pause_gifs.isChecked(),
            "pause_hamsters": self.cb_pause_hamsters.isChecked(),
            "light_theme": self.cb_light_theme.isChecked(),
            "auto_save": self.cb_auto_save.isChecked(),
            "rack_scale": self.sb_scale.value(),
            "room1_bg": r1_path,
            "room_rest_bg": r_rest_path
        }

class ImportManagerDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Manager")
        self.setFixedSize(500, 250)
        self.config = config
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        room_box = QVBoxLayout()
        room_box.addWidget(QLabel("<b>1. Current Room File Path</b>"))
        room_path_layout = QHBoxLayout()
        self.room_path_edit = QLineEdit(self.config.get("room_path", ""))
        self.room_path_edit.setReadOnly(True)
        room_browse = QPushButton("Browse")
        room_browse.clicked.connect(self.browse_room)
        room_path_layout.addWidget(self.room_path_edit)
        room_path_layout.addWidget(room_browse)
        room_box.addLayout(room_path_layout)
        layout.addLayout(room_box)
        inv_box = QVBoxLayout()
        inv_box.addWidget(QLabel("<b>2. Current Inventory File Path</b>"))
        inv_path_layout = QHBoxLayout()
        self.inv_path_edit = QLineEdit(self.config.get("inv_path", ""))
        self.inv_path_edit.setReadOnly(True)
        inv_browse = QPushButton("Browse")
        inv_browse.clicked.connect(self.browse_inv)
        inv_path_layout.addWidget(self.inv_path_edit)
        inv_path_layout.addWidget(inv_browse)
        inv_box.addLayout(inv_path_layout)
        layout.addLayout(inv_box)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save && Apply"); save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch(); btn_layout.addWidget(save_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browse_room(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Room JSON", "", "JSON Files (*.json)")
        if path: self.room_path_edit.setText(path)

    def browse_inv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Inventory File", "", "JSON Files (*.json);;All Files (*.*)")
        if path: self.inv_path_edit.setText(path)

    def get_data(self):
        return {"room_path": self.room_path_edit.text(), "inv_path": self.inv_path_edit.text()}

class JsonParserDialog(QDialog):
    def __init__(self, show_api_input=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paste JSON Data / Fetch via ID")
        self.setFixedSize(600, 480)
        self.id_edit = None
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Option 1: Paste .json here:</b>"))
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("Paste .json here...")
        layout.addWidget(self.text_edit)
        
        if show_api_input:
            layout.addSpacing(10)
            layout.addWidget(QLabel("<b>Option 2: Enter User ID to fetch via API:</b>"))
            self.id_edit = QLineEdit()
            self.id_edit.setPlaceholderText("e.g. 646f...")
            layout.addWidget(self.id_edit)
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Okay"); ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_box.addStretch(); btn_box.addWidget(ok_btn); btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def get_text(self):
        return self.text_edit.toPlainText()
        
    def get_user_id(self):
        return self.id_edit.text() if self.id_edit else ""

class ParsingSummaryDialog(QDialog):
    def __init__(self, data_list, miner_name, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(f"Parsed Data: {miner_name}")
        self.resize(900, 400)
        self.setModal(False)
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Miner Name", "Item ID", "Internal Level", "Displayed Level", "Raw Power (GH/s)", "Percent", "Slot Size"
        ])
        self.table.setRowCount(len(data_list))
        for row, d in enumerate(data_list):
            self.table.setItem(row, 0, QTableWidgetItem(str(miner_name)))
            self.table.setItem(row, 1, QTableWidgetItem(str(d['id'])))
            self.table.setItem(row, 2, QTableWidgetItem(str(d['internal_lvl'])))
            self.table.setItem(row, 3, QTableWidgetItem(str(d['displayed_lvl'])))
            self.table.setItem(row, 4, QTableWidgetItem(str(d['power'])))
            self.table.setItem(row, 5, QTableWidgetItem(f"{d['percent']}%"))
            self.table.setItem(row, 6, QTableWidgetItem(str(d['width'])))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)