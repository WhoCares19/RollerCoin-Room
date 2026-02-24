import os
import json
import re
from PyQt5 import QtWidgets, QtCore, QtGui

from miner_card_widget import MinerCardWidget
from rack_card_widget import RackCardWidget
from csv_parser import parse_miner_csv
from rack_parser import parse_rack_csv
from set_parser import parse_set_csv
import sql_manager

class MinerApp(QtWidgets.QMainWindow):
    """
    Main application class. 
    Handles data for Miners, Racks, and Sets.
    Features integrated 'Export Missing' buttons within import notifications.
    """
    def __init__(self):
        super().__init__()
        
        # Project Root Calculation (Rename-proof)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
        
        self.miners_data = []
        self.racks_data = []
        self.sets_data = []
        
        self.settings = QtCore.QSettings("YourCompany", "MinerApp")
        
        self.setWindowTitle("Miner Data Manager - Pro Edition")
        self.resize(1300, 850)
        
        self.apply_dark_theme()
        self.init_ui()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial; }
            
            #sidebar { 
                background-color: #1E1E1E; 
                border-right: 1px solid #333333; 
                min-width: 220px; 
                max-width: 220px;
            }
            
            .CategoryHeader { 
                color: #5DADE2; 
                font-weight: bold; 
                font-size: 11px; 
                margin-top: 20px; 
                margin-bottom: 5px;
                padding-left: 5px;
                background-color: transparent;
            }

            #sidebar QPushButton {
                background-color: #2D2D2D;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 10px;
                text-align: left;
                margin-bottom: 4px;
            }
            #sidebar QPushButton:hover { background-color: #3D3D3D; border-color: #5DADE2; }
            
            QPushButton#exportBtn { 
                background-color: #1B4F72; 
                color: white; 
                border: 1px solid #21618C; 
                text-align: center;
                margin-top: 10px;
                font-weight: bold;
            }
            QPushButton#exportBtn:hover { background-color: #21618C; }

            QLineEdit {
                background-color: #1E1E1E;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 8px;
                color: #FFFFFF;
            }
            
            QProgressBar {
                border: 1px solid #333333;
                border-radius: 5px;
                text-align: center;
                background-color: #1E1E1E;
                height: 15px;
            }
            QProgressBar::chunk { background-color: #5DADE2; }
            
            QScrollArea { border: none; background-color: #121212; }
            
            #minerNameLabel, #rackNameLabel { color: #FFFFFF; background-color: #1E1E1E; }
            #powerLabel { color: #7DCEA0; }
            #bonusLabel { color: #F1948A; }
            #rackPercentLabel { color: #85C1E9; }
        """)

    def init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- SIDEBAR ---
        sidebar = QtWidgets.QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setAlignment(QtCore.Qt.AlignTop)

        # Miners
        sidebar_layout.addWidget(self._create_sidebar_header("MINERS"))
        btn_miner_csv = self._create_sidebar_btn("Import Miner CSV", self.import_csv)
        btn_miner_img = self._create_sidebar_btn("Import Miner Images", self.import_miner_images)
        btn_lvl_icons = self._create_sidebar_btn("Import Level Icons", self.import_level_icons)
        btn_miner_sets = self._create_sidebar_btn("Import Set Signs", self.import_set_sign_image)
        btn_miner_legacy = self._create_sidebar_btn("Import Legacy Signs", self.import_legacy_sign_image)
        
        for btn in [btn_miner_csv, btn_miner_img, btn_lvl_icons, btn_miner_sets, btn_miner_legacy]:
            sidebar_layout.addWidget(btn)

        # Racks
        sidebar_layout.addWidget(self._create_sidebar_header("RACKS"))
        btn_rack_csv = self._create_sidebar_btn("Import Racks CSV", self.import_rack_csv)
        btn_rack_img = self._create_sidebar_btn("Import Racks Images", self.import_rack_images)
        btn_rack_sets = self._create_sidebar_btn("Import Set Signs", self.import_set_sign_image)
        
        for btn in [btn_rack_csv, btn_rack_img, btn_rack_sets]:
            sidebar_layout.addWidget(btn)

        # Sets
        sidebar_layout.addWidget(self._create_sidebar_header("SETS"))
        btn_import_sets = self._create_sidebar_btn("Import Sets", self.import_sets_csv)
        sidebar_layout.addWidget(btn_import_sets)

        # Export
        sidebar_layout.addWidget(self._create_sidebar_header("EXPORT"))
        btn_export = QtWidgets.QPushButton("Export to SQL")
        btn_export.setObjectName("exportBtn")
        btn_export.clicked.connect(self.export_to_sql_action)
        sidebar_layout.addWidget(btn_export)

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # --- CONTENT AREA ---
        content_area = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(10)

        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search items...")
        self.search_bar.setFixedHeight(40)
        self.search_bar.textChanged.connect(self._filter_cards)
        content_layout.addWidget(self.search_bar)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)
        content_layout.addWidget(self.progress_bar)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.content_widget)
        self.grid_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.grid_layout.setSpacing(20)
        self.scroll_area.setWidget(self.content_widget)
        content_layout.addWidget(self.scroll_area)

        main_layout.addWidget(content_area)
        self._create_menu_bar()

    def _create_sidebar_header(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setProperty("class", "CategoryHeader")
        return lbl

    def _create_sidebar_btn(self, text, slot):
        btn = QtWidgets.QPushButton(text)
        btn.clicked.connect(slot)
        return btn

    def _create_menu_bar(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        load_action = QtWidgets.QAction("Load JSON", self)
        load_action.triggered.connect(self.load_json)
        file_menu.addAction(load_action)
        save_action = QtWidgets.QAction("Save JSON", self)
        save_action.triggered.connect(self.save_json)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _normalize_string(self, text):
        if not text: return ""
        text = str(text)
        text = re.sub(r'\.(exe|png|jpg|jpeg|csv)$', '', text, flags=re.IGNORECASE)
        s = text.lower().replace("-", " ").replace("_", " ").replace("/", " ").replace("\\", " ").replace(".", " ")
        s = re.sub(r'[^a-z0-9\s]', '', s)
        return " ".join(s.split()).strip()

    def _get_rel_path(self, abs_path):
        if not abs_path: return ""
        try:
            return os.path.relpath(abs_path, self.project_root)
        except (ValueError, AttributeError):
            return abs_path

    def _export_list_to_file(self, filename_hint, lines):
        """Helper to let user save a specific list of strings to a text file."""
        if not lines: return
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Missing List", filename_hint, "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Could not save file: {e}")

    def _filter_cards(self):
        search_text = self.search_bar.text().lower().strip()
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                name = ""
                if isinstance(widget, MinerCardWidget):
                    name = widget.miner_data.get("miner_name", "").lower()
                elif isinstance(widget, RackCardWidget):
                    name = widget.rack_data.get("rack_name", "").lower()
                widget.setVisible(search_text in name)

    def display_all_cards(self):
        total = len(self.miners_data) + len(self.racks_data)
        self.content_widget.hide()
        self.content_widget.setUpdatesEnabled(False)
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if total == 0:
            self.content_widget.setUpdatesEnabled(True)
            self.content_widget.show()
            return
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        row, col, max_cols = 0, 0, 4
        curr = 0
        for miner in self.miners_data:
            self.grid_layout.addWidget(MinerCardWidget(miner, self.project_root), row, col)
            col += 1
            if col >= max_cols: col = 0; row += 1
            curr += 1
            if curr % 25 == 0: self.progress_bar.setValue(curr); QtWidgets.QApplication.processEvents()
        if self.miners_data and self.racks_data:
            row += 1; col = 0
        for rack in self.racks_data:
            self.grid_layout.addWidget(RackCardWidget(rack, self.project_root), row, col)
            col += 1
            if col >= max_cols: col = 0; row += 1
            curr += 1
            if curr % 25 == 0: self.progress_bar.setValue(curr); QtWidgets.QApplication.processEvents()
        self.grid_layout.setRowStretch(row + 1, 1)
        self.content_widget.setUpdatesEnabled(True)
        self.content_widget.show()
        QtWidgets.QApplication.processEvents()
        self.content_widget.adjustSize()
        self.grid_layout.activate()
        QtCore.QTimer.singleShot(50, lambda: self.content_widget.adjustSize())
        self.progress_bar.setVisible(False)
        self._filter_cards()

    def import_csv(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Miners CSV", ".", "CSV (*.csv)")
        if not file_path: return
        data = parse_miner_csv(file_path)
        if data:
            self.miners_data = data
            self.display_all_cards()

    def import_rack_csv(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Racks CSV", ".", "CSV (*.csv)")
        if not file_path: return
        data = parse_rack_csv(file_path)
        if data:
            self.racks_data = data
            self.display_all_cards()

    def import_sets_csv(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import Sets CSV", ".", "CSV (*.csv)")
        if not file_path: return
        data = parse_set_csv(file_path)
        if data:
            self.sets_data = data
            QtWidgets.QMessageBox.information(self, "Sets Import", f"Imported {len(data)} sets.")

    def import_miner_images(self):
        if not self.miners_data: return
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Miner Images Folder")
        if not folder: return
        
        files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
        file_map = {self._normalize_string(os.path.splitext(f)[0]): os.path.join(folder, f) for f in files}
        
        found_count = 0
        missing_list = []
        
        for miner in self.miners_data:
            keys = [miner["miner_name"], miner.get("legacy_id", "")]
            for i in range(1, 7):
                if f"level_{i}" in miner: keys.append(miner[f"level_{i}"].get("level_id_tag", ""))
            
            match_found = False
            for key in keys:
                norm = self._normalize_string(key)
                if norm and norm in file_map:
                    miner["image_path"] = self._get_rel_path(file_map[norm])
                    found_count += 1
                    match_found = True
                    break
            
            if not match_found:
                missing_list.append(miner["miner_name"])

        self.display_all_cards()
        
        # CUSTOM NOTIFICATION WITH EXPORT OPTION
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Import Finished")
        msg_box.setText(f"Matched {found_count} of {len(self.miners_data)} miner images.")
        
        ok_btn = msg_box.addButton(QtWidgets.QMessageBox.Ok)
        export_btn = None
        if missing_list:
            export_btn = msg_box.addButton("Export Missing Miners", QtWidgets.QMessageBox.ActionRole)
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == export_btn:
            self._export_list_to_file("missing_miners.txt", missing_list)

    def import_rack_images(self):
        if not self.racks_data: return
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Rack Images Folder")
        if not folder: return
        
        files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
        file_map = {self._normalize_string(os.path.splitext(f)[0]): os.path.join(folder, f) for f in files}
        
        found_count = 0
        missing_list = []
        
        for rack in self.racks_data:
            keys = [rack.get("rack_name", ""), rack.get("rack_id", "")]
            match_found = False
            for key in keys:
                norm = self._normalize_string(key)
                if norm and norm in file_map:
                    rack["image_path"] = self._get_rel_path(file_map[norm])
                    found_count += 1
                    match_found = True
                    break
            if not match_found:
                missing_list.append(rack.get("rack_name", "Unknown Rack"))

        self.display_all_cards()

        # CUSTOM NOTIFICATION WITH EXPORT OPTION
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Import Finished")
        msg_box.setText(f"Matched {found_count} of {len(self.racks_data)} rack images.")
        
        ok_btn = msg_box.addButton(QtWidgets.QMessageBox.Ok)
        export_btn = None
        if missing_list:
            export_btn = msg_box.addButton("Export Missing Racks", QtWidgets.QMessageBox.ActionRole)
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == export_btn:
            self._export_list_to_file("missing_racks.txt", missing_list)

    def import_level_icons(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Level Icons")
        if not folder: return
        icon_map = {}
        for f in os.listdir(folder):
            name = os.path.splitext(f)[0].lower()
            if name.startswith("lvl") and name[3:].isdigit(): icon_map[int(name[3:])] = os.path.join(folder, f)
        for miner in self.miners_data:
            for lvl in range(1, 7):
                key = f"level_{lvl}"
                if key in miner and lvl in icon_map: miner[key]["level_icon"] = self._get_rel_path(icon_map[lvl])
        self.display_all_cards()

    def import_set_sign_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Set Sign", ".", "PNG (*.png)")
        if not path: return
        rel = self._get_rel_path(path)
        for miner in self.miners_data:
            if miner.get("sets") and miner["sets"].lower() != "n/a": miner["set_sign_icon_path"] = rel
        for rack in self.racks_data:
            if rack.get("rack_sets") and rack["rack_sets"].lower() != "n/a": rack["set_sign_icon_path"] = rel
        self.display_all_cards()

    def import_legacy_sign_image(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Legacy Sign", ".", "PNG (*.png)")
        if not path: return
        rel = self._get_rel_path(path)
        for miner in self.miners_data:
            if miner.get("is_legacy", "").lower() == "yes": miner["legacy_sign_icon_path"] = rel
        self.display_all_cards()

    def load_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Data", ".", "JSON (*.json)")
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.miners_data = data.get('miners_data', [])
                self.racks_data = data.get('racks_data', [])
                self.sets_data = data.get('sets_data', [])
            self.display_all_cards()
        except Exception as e: QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def save_json(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Data", "data.json", "JSON (*.json)")
        if not path: return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"miners_data": self.miners_data, "racks_data": self.racks_data, "sets_data": self.sets_data}, f, indent=4)
        except Exception as e: QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def export_to_sql_action(self):
        if not self.miners_data and not self.racks_data and not self.sets_data: return
        success, msg = sql_manager.export_to_sql(self.miners_data, self.racks_data, self.sets_data)
        if success: QtWidgets.QMessageBox.information(self, "Export", msg)
        else: QtWidgets.QMessageBox.critical(self, "Error", msg)
