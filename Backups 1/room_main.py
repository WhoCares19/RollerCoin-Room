import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QDialog,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QMessageBox,
    QMenu,
    QScrollArea,
    QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QAction, QPixmap

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    APP_ICON_PATH,
    LEAGUES_DIR
)
from logic_math import (
    format_hashrate,
    get_league_info,
    get_league_tooltip,
    calculate_power_breakdown,
    calculate_single_rack_stats
)
from database import DatabaseHandler
from inventory import InventorySection
from room_preview import RoomView

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #121212;
    color: #e0e0e0;
}
QWidget {
    background-color: #121212;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial;
}
QPushButton {
    background-color: #333333;
    border: 1px solid #555555;
    padding: 5px 15px;
    border-radius: 3px;
    color: white;
}
QPushButton:hover {
    background-color: #444444;
}
QLineEdit, QComboBox {
    background-color: #1e1e1e;
    border: 1px solid #444444;
    color: white;
    padding: 3px;
}
QScrollArea {
    border: none;
    background-color: #121212;
}
QLabel#PowerLabel {
    color: #00ff00;
}
"""

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
            p_edit.setPlaceholderText("Power (e.g. 10.000 Th/s)")
            
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

class RackDetailsDialog(QDialog):
    edit_requested = Signal(dict)

    def __init__(self, stats, rack_name, rack_bonus, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rack Details")
        self.setFixedSize(420, 550)
        layout = QVBoxLayout(self)

        header_text = f"<b>{rack_name}</b> | <span style='color:#5dade2;'>{rack_bonus}% Bonus</span>"
        if stats.get('set_name') and stats.get('set_name') != "Unknown Set":
            header_text = f"<b>{stats['set_name']}</b> | <span style='color:#5dade2;'>{rack_bonus}% Bonus</span>"

        header = QLabel(header_text)
        header.setStyleSheet("font-size: 16px; border-bottom: 1px solid #333; padding-bottom: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for m in stats['miners']:
            m_frame = QFrame()
            m_frame.setObjectName("MinerRow")
            m_frame.setStyleSheet("QFrame#MinerRow { background: #1a1a1a; border-radius: 4px; margin-bottom: 2px; } QFrame#MinerRow:hover { background: #222; }")
            m_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            m_frame.customContextMenuRequested.connect(lambda pos, data=m: self.show_miner_menu(pos, data))
            
            m_layout = QHBoxLayout(m_frame)
            name_lbl = QLabel(f"<b>{m['name']}</b> (Lvl {m['lvl']})")
            p_lbl = QLabel(f"<span style='color:#00ff00;'>{format_hashrate(m['power'])}</span>")
            b_lbl = QLabel(f"<span style='color:#ffcc00;'>{m['bonus']}%</span>")
            
            m_layout.addWidget(name_lbl)
            m_layout.addStretch()
            m_layout.addWidget(p_lbl)
            m_layout.addWidget(b_lbl)
            c_layout.addWidget(m_frame)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        footer = QFrame()
        footer.setStyleSheet("border-top: 1px solid #333; padding-top: 10px;")
        f_layout = QVBoxLayout(footer)
        
        totals_map = [("Base Power:", stats['base_power'], "white")]
        
        if stats.get('miner_bonus_power', 0) > 0 or not stats.get('is_set_rack'):
            totals_map.append(("Miner Bonus's:", stats['miner_bonus_power'], "#ffcc00"))
        
        if stats.get('is_set_rack'):
            if stats.get('set_bonus_power', 0) > 0:
                totals_map.append(("Set Bonus:", stats['set_bonus_power'], "#f1c40f"))
            if stats.get('set_flat_power', 0) > 0:
                totals_map.append(("Set Power:", stats['set_flat_power'], "white"))

        totals_map.append(("Rack Bonus Power:", stats['rack_bonus'], "#5dade2"))
        totals_map.append(("Total Power:", stats['total_power'], "#00ff00"))

        for label, val, color in totals_map:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{label}</b>"))
            row.addStretch()
            
            if label == "Miner Bonus's:":
                display_text = f"{stats.get('miner_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            elif label == "Set Bonus:":
                display_text = f"{stats.get('set_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            elif label == "Rack Bonus Power:":
                display_text = f"{stats.get('rack_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            else:
                display_text = format_hashrate(val)

            v_lbl = QLabel(display_text)
            v_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            row.addWidget(v_lbl)
            f_layout.addLayout(row)

        layout.addWidget(footer)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_miner_menu(self, pos, miner_data):
        menu = QMenu(self)
        edit_act = QAction("Edit Miner Data", self)
        edit_act.triggered.connect(lambda: self.edit_requested.emit(miner_data))
        menu.addAction(edit_act)
        menu.exec(self.sender().mapToGlobal(pos))

class AddItemDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Personal Item")
        self.setFixedSize(450, 520)
        self.result_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        rack_header = QLabel("Add Rack")
        rack_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rack_header.setStyleSheet("font-weight: bold; font-size: 15px; color: #5dade2;")
        layout.addWidget(rack_header)

        r_form = QFormLayout()
        r_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.rack_img = QLineEdit()
        self.rack_img.setPlaceholderText("Path to rack image...")
        r_btn = QPushButton("Browse")
        r_btn.clicked.connect(lambda: self.get_file(self.rack_img))
        
        r_img_box = QHBoxLayout()
        r_img_box.addWidget(self.rack_img)
        r_img_box.addWidget(r_btn)
        r_form.addRow("Image:", r_img_box)

        self.rack_bonus = QLineEdit()
        self.rack_bonus.setPlaceholderText("0.00")
        self.rack_bonus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_form.addRow("Bonus:", self.rack_bonus)
        layout.addLayout(r_form)

        layout.addSpacing(10)
        line = QLabel()
        line.setStyleSheet("background: #333;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        layout.addSpacing(10)

        miner_header = QLabel("Add Miners")
        miner_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        miner_header.setStyleSheet("font-weight: bold; font-size: 15px; color: #58d68d;")
        layout.addWidget(miner_header)

        m_form = QFormLayout()
        m_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.miner_img = QLineEdit()
        self.miner_img.setPlaceholderText("Path to miner image...")
        m_btn = QPushButton("Browse")
        m_btn.clicked.connect(lambda: self.get_file(self.miner_img))
        
        m_img_box = QHBoxLayout()
        m_img_box.addWidget(self.miner_img)
        m_img_box.addWidget(m_btn)
        m_form.addRow("Image:", m_img_box)

        self.miner_power = QLineEdit()
        self.miner_power.setPlaceholderText("0.000 Gh/s")
        self.miner_power.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_form.addRow("Power:", self.miner_power)

        self.miner_bonus = QLineEdit()
        self.miner_bonus.setPlaceholderText("0.00")
        self.miner_bonus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_form.addRow("Bonus:", self.miner_bonus)
        layout.addLayout(m_form)

        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        apply = QPushButton("Apply")
        apply.clicked.connect(self.do_apply)
        
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(apply)
        btn_box.addWidget(cancel)
        layout.addLayout(btn_box)

    def get_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg)")
        if path:
            target.setText(path)

    def do_apply(self):
        if self.miner_power.text().strip():
            self.result_data = {
                'type': 'miner', 
                'name': 'Personal Miner', 
                'image_path': self.miner_img.text(),
                'power': self.miner_power.text(), 
                'bonus': self.miner_bonus.text(), 
                'lvl': 1, 
                'slot_size': 1
            }
        else:
            self.result_data = {
                'type': 'rack', 
                'name': 'Personal Rack 8', 
                'image_path': self.rack_img.text(),
                'bonus_percent': self.rack_bonus.text()
            }
        self.accept()

class PowerBreakdownDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Total Power Breakdown")
        self.setFixedSize(320, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        stats_map = [
            ("miners_base", "Miner:"),
            ("bonus_power", "Bonus Power:"),
            ("rack_bonus", "Rack Bonus:")
        ]

        for key, label in stats_map:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{label}</b>")
            
            if key == "bonus_power":
                bonus_pct = stats.get("bonus_percent", 0.0)
                display_val = f"{bonus_pct:.2f}% | {format_hashrate(stats[key])}"
            else:
                display_val = format_hashrate(stats.get(key, 0))
                
            val = QLabel(display_val)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            layout.addLayout(row)
        
        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mining Room Simulator")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(DARK_STYLESHEET)
        self.room_save_path = None
        
        if os.path.exists(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))
            
        self.db_handler = DatabaseHandler()
        self.room_buttons = []
        self.room_views = []
        self.current_stats = {
            "miners_base": 0, 
            "bonus_power": 0, 
            "bonus_percent": 0, 
            "rack_bonus": 0, 
            "total": 0
        }
        
        self.init_ui()
        self.update_stats()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)

        header = QHBoxLayout()
        self.power_label = QLabel("Total Power: 0.000 Gh/s")
        self.power_label.setObjectName("PowerLabel")
        self.power_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.power_label.mousePressEvent = self.on_power_label_clicked
        
        league_box = QHBoxLayout()
        league_box.addWidget(QLabel("League:"))
        self.league_icon = QLabel()
        self.league_icon.setFixedSize(28, 28)
        league_box.addWidget(self.league_icon)
        
        header.addWidget(self.power_label)
        header.addSpacing(25)
        header.addLayout(league_box)
        header.addStretch()

        for act in ["Add", "Save", "Import", "Export"]:
            btn = QPushButton(act)
            btn.clicked.connect(getattr(self, f"on_{act.lower()}_clicked"))
            header.addWidget(btn)
        self.main_layout.addLayout(header)

        self.room_nav = QHBoxLayout()
        self.room_nav.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for i in range(4):
            self.add_room_button(i)
        
        add_rm = QPushButton("+")
        add_rm.setFixedWidth(30)
        add_rm.clicked.connect(self.on_plus_clicked)
        self.room_nav.addWidget(add_rm)
        self.main_layout.addLayout(self.room_nav)

        self.inventory = InventorySection()
        self.inventory.view.itemClicked.connect(self.on_inventory_item_clicked)
        self.inventory.edit_requested.connect(self.open_miner_editor)

        self.room_stack = QStackedWidget()
        for i in range(4):
            view = RoomView(i)
            self.connect_room_signals(view)
            self.room_views.append(view)
            self.room_stack.addWidget(view)
            
        self.main_layout.addWidget(self.room_stack, stretch=2)
        self.main_layout.addWidget(self.inventory, stretch=1)
        
        self.save_status_label = QLabel("Saved")
        self.save_status_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.save_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.main_layout.addWidget(self.save_status_label)

    def connect_room_signals(self, view):
        view.stats_changed.connect(self.update_stats)
        view.stats_changed.connect(self.auto_save)
        view.item_placed.connect(lambda data: self.inventory.adjust_quantity(data.get('id'), -1))
        view.item_returned.connect(lambda data: self.inventory.adjust_quantity(data.get('id'), 1))
        view.rack_clicked.connect(self.on_rack_clicked)
        view.miner_edit_requested.connect(self.open_miner_editor)

    def open_miner_editor(self, miner_data):
        dlg = EditMinerDialog(miner_data, self.db_handler, self)
        if dlg.exec():
            self.db_handler.preload_data()
            self.inventory.preload_data_from_db()
            self.update_stats()
            for view in self.room_views:
                for p in view.placeholders:
                    if p.rack:
                        p.rack.refresh_ui()

    def on_inventory_item_clicked(self, data):
        curr = self.room_stack.currentWidget()
        if curr:
            curr.handle_item_click(data)

    def on_rack_clicked(self, rack_data, rows_data):
        global_bonus = self.current_stats.get('bonus_percent', 0.0)
        rack_stats = calculate_single_rack_stats(rack_data, rows_data, global_bonus)
        
        dlg = RackDetailsDialog(rack_stats, rack_data.get('name', 'Unknown Rack'), rack_data.get('bonus_val', 0.0), self)
        dlg.edit_requested.connect(self.open_miner_editor)
        dlg.exec()

    def add_room_button(self, idx):
        btn = QPushButton(f"Room {idx + 1}")
        btn.clicked.connect(lambda: self.room_stack.setCurrentIndex(idx))
        self.room_nav.insertWidget(len(self.room_buttons), btn)
        self.room_buttons.append(btn)

    def on_plus_clicked(self):
        idx = len(self.room_buttons)
        view = RoomView(idx)
        self.connect_room_signals(view)
        self.room_views.append(view)
        self.room_stack.addWidget(view)
        self.add_room_button(idx)

    def update_stats(self):
        state = {i: v.get_room_state() for i, v in enumerate(self.room_views)}
        self.current_stats = calculate_power_breakdown(state)
        self.power_label.setText(f"Total Power: {format_hashrate(self.current_stats['total'])}")
        
        name, icon_file = get_league_info(self.current_stats['total'])
        path = os.path.join(LEAGUES_DIR, icon_file)
        if os.path.exists(path):
            self.league_icon.setPixmap(QPixmap(path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        self.league_icon.setToolTip(get_league_tooltip(self.current_stats['total']))

    def on_power_label_clicked(self, ev):
        dlg = PowerBreakdownDialog(self.current_stats, self)
        dlg.exec()

    def on_add_clicked(self):
        dlg = AddItemDialog(self)
        if dlg.exec() and dlg.result_data:
            self.inventory.add_personal_item(dlg.result_data)

    def _save_all_rooms(self, path):
        all_rooms = []
        for room_idx, room_view in enumerate(self.room_views):
            room_state = []
            for p in room_view.placeholders:
                if p.rack:
                    room_state.append({"rack_data": p.rack.data, "rows": p.rack.rows_data})
            if room_state:
                all_rooms.append({"room_index": room_idx, "racks": room_state})
        with open(path, "w") as f:
            json.dump(all_rooms, f, indent=2)

    def auto_save(self):
        if not hasattr(self, "_autosave_path") or not self._autosave_path:
            return 
        self._save_all_rooms(self._autosave_path)
        self.save_status_label.setText("Saved")
        self.save_status_label.setStyleSheet("color: #00ff00; font-size: 10px;")
        QTimer.singleShot(1500, lambda: self.save_status_label.setStyleSheet("color: #888888; font-size: 10px;"))

    def repair_item_data(self, item_dict):
        if not item_dict or "set_global_id" in item_dict:
            return item_dict

        name = item_dict.get('name', '')
        if 'power_val' in item_dict:
            lvl = item_dict.get('lvl', 1)
            for cached in self.db_handler.get_catalog_miners(lvl):
                if cached[1] == name:
                    item_dict['set_global_id'] = cached[4]
                    item_dict['id'] = cached[0]
                    break
        else:
            for cached in self.db_handler.get_catalog_racks():
                if cached[1] == name:
                    item_dict['set_global_id'] = cached[3]
                    item_dict['id'] = cached[0]
                    break
        return item_dict

    def on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Rooms", "", "JSON Files (*.json)")
        if not path:
            return
            
        print(f"Importing rooms from: {path}")
        self.room_save_path = path
        
        with open(path, "r") as f:
            all_rooms = json.load(f)
            
        for room_view in self.room_views:
            for p in room_view.placeholders:
                if p.rack:
                    p.remove_rack()
                    
        for room_data in all_rooms:
            idx = room_data.get("room_index", 0)
            if idx >= len(self.room_views):
                continue
            room_view = self.room_views[idx]
            
            for p_idx, rack_info in enumerate(room_data.get("racks", [])):
                if p_idx >= len(room_view.placeholders):
                    break
                    
                placeholder = room_view.placeholders[p_idx]
                rack_data = self.repair_item_data(rack_info.get("rack_data", rack_info))
                rows = rack_info.get("rows", [])
                
                if placeholder.rack is None:
                    placeholder.add_rack(rack_data)
                    for r_idx, row in enumerate(rows):
                        if isinstance(row, dict):
                            m_data = self.repair_item_data(row)
                            placeholder.rack.add_miner(m_data, r_idx, 0)
                        elif isinstance(row, list):
                            for s_idx, miner in enumerate(row):
                                if miner:
                                    m_data = self.repair_item_data(miner)
                                    placeholder.rack.add_miner(m_data, r_idx, s_idx)
        
        self._autosave_path = path
        self.update_stats()
        print("Import complete.")

    def on_export_clicked(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Rooms", "", "JSON Files (*.json)")
        if not path:
            return
        print(f"Exporting rooms to: {path}")
        self.room_save_path = path
        self._save_all_rooms(path)
        self._autosave_path = path
        print("Export complete.")

    def on_save_clicked(self):
        if not self.room_save_path:
            QMessageBox.warning(self, "No Export Path", "Please export the rooms first.")
            return
        print(f"Saving rooms to: {self.room_save_path}")
        self._save_all_rooms(self.room_save_path)
        print("Save complete.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())