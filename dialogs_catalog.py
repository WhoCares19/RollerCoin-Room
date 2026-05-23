import os
import json
import urllib.request
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, 
    QFileDialog, QFormLayout, QLineEdit, QComboBox, QFrame,
    QScrollArea, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from ui_styles import resolve_path
from dialogs_system import JsonParserDialog, ParsingSummaryDialog

class EditMinerDialog(QDialog):
    def __init__(self, miner_data, db_handler, parent=None):
        super().__init__(parent)
        self.miner_data = miner_data
        self.db = db_handler
        self.setWindowTitle(f"Edit Miner: {miner_data.get('name')}")
        self.setFixedSize(500, 450)
        self.level_inputs = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel(f"Editing all levels for <b>{self.miner_data.get('name')}</b>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        
        miner_id = self.miner_data.get('id')
        levels = self.db.get_all_miner_levels(miner_id)
        
        for stats_id, lvl_num, power, bonus in levels:
            row_frame = QFrame()
            row_frame.setStyleSheet("background: #1a1a1a; border-radius: 5px; margin: 2px;")
            row_layout = QHBoxLayout(row_frame)
            lvl_lbl = QLabel(f"<b>Lvl {lvl_num}</b>")
            lvl_lbl.setFixedWidth(50)
            p_edit = QLineEdit(str(power))
            b_edit = QLineEdit(f"{bonus}%")
            b_edit.setFixedWidth(80)
            
            row_layout.addWidget(lvl_lbl)
            row_layout.addWidget(QLabel("Power:"))
            row_layout.addWidget(p_edit)
            row_layout.addWidget(QLabel("Bonus:"))
            row_layout.addWidget(b_edit)
            
            self.level_inputs.append((stats_id, p_edit, b_edit))
            c_layout.addWidget(row_frame)
            
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("background-color: #2e7d32; font-weight: bold;")
        save_btn.clicked.connect(self.save_data)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def save_data(self):
        try:
            for stats_id, p_edit, b_edit in self.level_inputs:
                p_val = p_edit.text().strip()
                b_val = b_edit.text().replace('%', '').strip()
                self.db.update_miner_level_stats(stats_id, p_val, b_val)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update miner: {e}")

class AddRackDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Add Catalog Rack")
        self.setFixedSize(450, 500)
        self.result_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        form.addRow("Rack Name:", self.name_edit)
        
        self.id_tag_edit = QLineEdit()
        self.id_tag_edit.setPlaceholderText("rack_id_tag (for JSON imports)")
        form.addRow("Rack ID Tag:", self.id_tag_edit)
        
        self.img_edit = QLineEdit()
        btn_browse_img = QPushButton("Browse")
        btn_browse_img.clicked.connect(lambda: self.browse_file(self.img_edit))
        img_box = QHBoxLayout()
        img_box.addWidget(self.img_edit); img_box.addWidget(btn_browse_img)
        form.addRow("Rack Image:", img_box)
        
        self.bonus_edit = QLineEdit("0.00")
        form.addRow("Bonus %:", self.bonus_edit)
        
        self.set_combo = QComboBox()
        self.set_combo.addItem("None", None)
        self.set_combo.addItem("+ Create New Set", "NEW")
        sets = self.db.get_all_set_definitions()
        for s in sets:
            self.set_combo.addItem(s[1], s[2])
        self.set_combo.currentIndexChanged.connect(self.on_set_changed)
        form.addRow("Set:", self.set_combo)
        
        self.set_icon_edit = QLineEdit()
        btn_browse_icon = QPushButton("Browse")
        btn_browse_icon.clicked.connect(lambda: self.browse_file(self.set_icon_edit))
        icon_box = QHBoxLayout()
        icon_box.addWidget(self.set_icon_edit); icon_box.addWidget(btn_browse_icon)
        form.addRow("Set Sign Icon:", icon_box)
        
        layout.addLayout(form)
        
        self.new_set_group = QFrame()
        self.new_set_group.setStyleSheet("background: #1a1a1a; border-radius: 5px;")
        ns_layout = QFormLayout(self.new_set_group)
        self.ns_name = QLineEdit()
        self.ns_id = QLineEdit()
        ns_layout.addRow("New Set Name:", self.ns_name)
        ns_layout.addRow("New Set Global ID:", self.ns_id)
        layout.addWidget(self.new_set_group)
        self.new_set_group.hide()
        
        layout.addStretch()
        
        btn_box = QHBoxLayout()
        apply_btn = QPushButton("Save to Database")
        apply_btn.clicked.connect(self.do_apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(apply_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def on_set_changed(self, index):
        data = self.set_combo.currentData()
        self.new_set_group.setVisible(data == "NEW")
        if data and data != "NEW":
            self.set_icon_edit.setText(self.db.get_set_icon_lookup(data))
        elif not data:
            self.set_icon_edit.clear()

    def browse_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.gif *.ico)")
        if path:
            target.setText(path)

    def do_apply(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Rack Name is required."); return
        set_global_id = self.set_combo.currentData()
        if set_global_id == "NEW":
            set_global_id = self.ns_id.text().strip()
            self.db.ensure_set_exists(self.ns_name.text(), set_global_id)
        self.result_data = {
            'name': self.name_edit.text(),
            'rack_id_tag': self.id_tag_edit.text().strip(),
            'set_global_id': set_global_id,
            'rack_size': "Big Rack",
            'bonus_percent': self.bonus_edit.text(),
            'image_path': self.img_edit.text(),
            'set_sign_icon_path': self.set_icon_edit.text()
        }
        self.accept()

class AddMinerDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Add Catalog Miner")
        self.setFixedSize(550, 750)
        self.base_result = None
        self.levels_result = []
        self.extracted_filename = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        form.addRow("Miner Name:", self.name_edit)
        
        self.img_edit = QLineEdit()
        btn_browse_img = QPushButton("Browse")
        btn_browse_img.clicked.connect(lambda: self.browse_file(self.img_edit))
        img_box = QHBoxLayout()
        img_box.addWidget(self.img_edit); img_box.addWidget(btn_browse_img)
        form.addRow("Base Image:", img_box)
        
        self.slot_combo = QComboBox()
        self.slot_combo.addItems(["1 slot", "2 slot"])
        form.addRow("Slot Size:", self.slot_combo)
        
        self.set_combo = QComboBox()
        self.set_combo.addItem("None", None)
        self.set_combo.addItem("+ Create New Set", "NEW")
        sets = self.db.get_all_set_definitions()
        for s in sets:
            self.set_combo.addItem(s[1], s[2])
        self.set_combo.currentIndexChanged.connect(self.on_set_changed)
        form.addRow("Set:", self.set_combo)
        
        self.set_icon_edit = QLineEdit()
        btn_browse_icon = QPushButton("Browse")
        btn_browse_icon.clicked.connect(lambda: self.browse_file(self.set_icon_edit))
        icon_box = QHBoxLayout()
        icon_box.addWidget(self.set_icon_edit); icon_box.addWidget(btn_browse_icon)
        form.addRow("Set Sign Icon:", icon_box)
        
        layout.addLayout(form)
        
        self.new_data_btn = QPushButton("New Miner Data")
        self.new_data_btn.setStyleSheet("background-color: #34495e; font-weight: bold; height: 30px;")
        self.new_data_btn.clicked.connect(self.on_new_data_clicked)
        layout.addWidget(self.new_data_btn)
        
        self.new_set_group = QFrame()
        self.new_set_group.setStyleSheet("background: #1a1a1a; border-radius: 5px;")
        ns_layout = QFormLayout(self.new_set_group)
        self.ns_name = QLineEdit()
        self.ns_id = QLineEdit()
        ns_layout.addRow("New Set Name:", self.ns_name)
        ns_layout.addRow("New Set Global ID:", self.ns_id)
        layout.addWidget(self.new_set_group)
        self.new_set_group.hide()
        
        lbl_levels = QLabel("<b>Level Statistics</b> (Empty levels will be skipped)")
        lbl_levels.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_levels)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        self.level_rows = []
        for i in range(1, 7):
            frame = QFrame()
            frame.setStyleSheet("background: #1a1a1a; border-radius: 5px; margin: 2px;")
            r = QVBoxLayout(frame)
            h1 = QHBoxLayout()
            h1.addWidget(QLabel(f"<b>Lvl {i}</b>"))
            p_edit = QLineEdit()
            p_edit.setPlaceholderText("Power (e.g. 150 Gh/s)")
            b_edit = QLineEdit()
            b_edit.setPlaceholderText("Bonus %")
            h1.addWidget(QLabel("Power:")); h1.addWidget(p_edit)
            h1.addWidget(QLabel("Bonus:")); h1.addWidget(b_edit)
            r.addLayout(h1)
            h2 = QHBoxLayout()
            id_edit = QLineEdit()
            id_edit.setPlaceholderText("Level ID Tag (for JSON imports)")
            h2.addWidget(QLabel("ID Tag:")); h2.addWidget(id_edit)
            r.addLayout(h2)
            self.level_rows.append((i, p_edit, b_edit, id_edit))
            c_layout.addWidget(frame)
            
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        btn_box = QHBoxLayout()
        apply_btn = QPushButton("Save All to Database")
        apply_btn.clicked.connect(self.do_apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(apply_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def on_set_changed(self, index):
        data = self.set_combo.currentData()
        self.new_set_group.setVisible(data == "NEW")
        if data and data != "NEW":
            self.set_icon_edit.setText(self.db.get_set_icon_lookup(data))
        elif not data:
            self.set_icon_edit.clear()

    def browse_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.gif)")
        if path:
            target.setText(path)

    def on_new_data_clicked(self):
        dlg = JsonParserDialog(show_api_input=False, parent=self)
        if dlg.exec():
            raw_text = dlg.get_text()
            self.auto_fill_from_json(raw_text)

    def auto_fill_from_json(self, raw_text):
        try:
            data = json.loads(raw_text)
            craftings = data["data"]["craftings"]
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse JSON: {e}")
            return
        
        parsed_items = []
        seen_ids = set()
        miner_name = "Unknown Miner"
        img_folder = os.path.join("assets", "miners")
        if not os.path.exists(img_folder): os.makedirs(img_folder)

        def process_item_data(item_id, item_stats, raw_name_obj=None):
            nonlocal miner_name
            if item_id and (item_id, item_stats.get("level")) not in seen_ids:
                seen_ids.add((item_id, item_stats.get("level")))
                internal_lvl = item_stats.get("level", 0)
                power_gh = item_stats.get("power", 0)
                percent = item_stats.get("percent", 0) / 100
                width = item_stats.get("width", 1)
                filename = item_stats.get("filename")
                if filename:
                    self.extracted_filename = filename
                    target_local = os.path.join(img_folder, f"{filename}.gif").replace("\\", "/")
                    if not os.path.exists(target_local):
                        url = f"https://static.rollercoin.com/static/img/market/miners/{filename}.gif"
                        try:
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req) as response:
                                with open(target_local, 'wb') as out_file: out_file.write(response.read())
                        except: pass
                    if os.path.exists(target_local): self.img_edit.setText(target_local)
                parsed_items.append({'id': item_id, 'internal_lvl': internal_lvl, 'displayed_lvl': internal_lvl+1, 'power': power_gh, 'percent': percent, 'width': width})
                if raw_name_obj:
                    miner_name = raw_name_obj.get("en", next(iter(raw_name_obj.values()))) if isinstance(raw_name_obj, dict) else raw_name_obj

        for craft in craftings:
            process_item_data(craft.get("prev_item_info", {}).get("_id"), craft.get("prev_item_info", {}), craft.get("prev_item_info", {}).get("name"))
            process_item_data(craft.get("result", {}).get("_id"), craft.get("result", {}).get("item_data", {}), craft.get("result", {}).get("item_data", {}).get("name"))

        if parsed_items:
            parsed_items.sort(key=lambda x: x['internal_lvl'])
            self.name_edit.setText(str(miner_name))
            self.slot_combo.setCurrentText(f"{parsed_items[-1]['width']} slot")
            for item in parsed_items:
                idx = item['displayed_lvl'] - 1
                if 0 <= idx < len(self.level_rows):
                    _, p_edit, b_edit, id_edit = self.level_rows[idx]
                    p_edit.setText(f"{item['power']} Gh/s"); b_edit.setText(f"{item['percent']}%"); id_edit.setText(str(item['id']))
            ParsingSummaryDialog(parsed_items, miner_name, self).show()

    def do_apply(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Miner Name is required."); return
        set_global_id = self.set_combo.currentData()
        if set_global_id == "NEW":
            set_global_id = self.ns_id.text().strip()
            self.db.ensure_set_exists(self.ns_name.text(), set_global_id)
        self.base_result = {
            'name': self.name_edit.text(),
            'image_path': self.img_edit.text(),
            'slot_size': 1 if self.slot_combo.currentText() == "1 slot" else 2,
            'set_global_id': set_global_id,
            'set_sign_icon_path': self.set_icon_edit.text(),
            'filename': self.extracted_filename
        }
        for lvl, p_e, b_e, id_e in self.level_rows:
            if p_e.text().strip() or b_e.text().strip() or id_e.text().strip():
                self.levels_result.append({
                    'lvl': lvl,
                    'power': p_e.text().strip() or "0",
                    'bonus': b_e.text().strip() or "0",
                    'level_id_tag': id_e.text().strip()
                })
        if not self.levels_result:
            QMessageBox.warning(self, "Empty", "Add stats for at least one level."); return
        self.accept()