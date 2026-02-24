import sys
import os
import json
import copy
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
    QFrame,
    QSplashScreen,
    QProgressBar,
    QComboBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QPoint, QEvent, QRect
from PySide6.QtGui import QIcon, QAction, QPixmap, QColor, QKeySequence, QCursor

from settings import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    APP_ICON_PATH,
    LEAGUES_DIR,
    CONFIG_PATH,
    LOCK_ICON,
    UNLOCK_ICON
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
from room_preview import RoomView, RackPlaceholder

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
QProgressBar {
    border: 1px solid #444;
    border-radius: 5px;
    text-align: center;
    background-color: #1a1a1a;
}
QProgressBar::chunk {
    background-color: #00ff00;
    width: 20px;
}
"""

class HoverMenuButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.menu = QMenu(self)
        self.menu.installEventFilter(self)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.check_hover_and_hide)
        
    def enterEvent(self, event):
        self.hide_timer.stop()
        if not self.menu.isVisible():
            pos = self.mapToGlobal(QPoint(0, self.height()))
            self.menu.popup(pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start(300)
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.menu:
            if event.type() == QEvent.Type.Enter:
                self.hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self.hide_timer.start(300)
        return super().eventFilter(obj, event)

    def check_hover_and_hide(self):
        if not self.menu.isVisible():
            return
        cursor_pos = QCursor.pos()
        btn_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        menu_rect = self.menu.geometry()
        safe_zone = btn_rect.united(menu_rect).adjusted(-10, -10, 10, 10)
        if not safe_zone.contains(cursor_pos):
            self.menu.hide()
        else:
            self.hide_timer.start(300)

class LoadingSplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(400, 200)
        pixmap.fill(QColor("#121212"))
        super().__init__(pixmap)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.label = QLabel("Initializing Mining Room Simulator...")
        self.label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.setLayout(layout)

    def update_progress(self, value, text):
        self.label.setText(text)
        self.progress.setValue(value)
        QApplication.processEvents()

class ImportManagerDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Manager")
        self.setFixedSize(500, 350)
        self.config = config
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        room_group = QVBoxLayout()
        room_label = QLabel("<b>1. Import Player Room</b>")
        room_group.addWidget(room_label)
        room_path_layout = QHBoxLayout()
        self.room_path_edit = QLineEdit(self.config.get("room_path", ""))
        self.room_path_edit.setReadOnly(True)
        room_browse = QPushButton("Browse")
        room_browse.clicked.connect(self.browse_room)
        room_path_layout.addWidget(self.room_path_edit)
        room_path_layout.addWidget(room_browse)
        room_group.addLayout(room_path_layout)
        self.room_auto_cb = QCheckBox("Automatically import on app start")
        self.room_auto_cb.setChecked(self.config.get("room_auto", False))
        room_group.addWidget(self.room_auto_cb)
        layout.addLayout(room_group)
        inv_group = QVBoxLayout()
        inv_label = QLabel("<b>2. Import Player Inventory</b>")
        inv_group.addWidget(inv_label)
        inv_path_layout = QHBoxLayout()
        self.inv_path_edit = QLineEdit(self.config.get("inv_path", ""))
        self.inv_path_edit.setReadOnly(True)
        inv_browse = QPushButton("Browse")
        inv_browse.clicked.connect(self.browse_inv)
        inv_path_layout.addWidget(self.inv_path_edit)
        inv_path_layout.addWidget(inv_browse)
        inv_group.addLayout(inv_path_layout)
        self.inv_auto_cb = QCheckBox("Automatically import on app start")
        self.inv_auto_cb.setChecked(self.config.get("inv_auto", False))
        inv_group.addWidget(self.inv_auto_cb)
        layout.addLayout(inv_group)
        layout.addStretch()
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save && Apply")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def browse_room(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Room JSON", "", "JSON Files (*.json)")
        if path: self.room_path_edit.setText(path)

    def browse_inv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Inventory File", "", "JSON Files (*.json);;All Files (*.*)")
        if path: self.inv_path_edit.setText(path)

    def get_data(self):
        return {"room_path": self.room_path_edit.text(), "room_auto": self.room_auto_cb.isChecked(), "inv_path": self.inv_path_edit.text(), "inv_auto": self.inv_auto_cb.isChecked()}

class EditMinerDialog(QDialog):
    def __init__(self, miner_data, db_handler, parent=None):
        super().__init__(parent)
        self.miner_data = miner_data; self.db = db_handler; self.setWindowTitle(f"Edit Miner: {miner_data.get('name')}"); self.setFixedSize(500, 450); self.level_inputs = []; 
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

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
            lvl_lbl = QLabel(f"<b>Lvl {lvl_num}</b>"); lvl_lbl.setFixedWidth(50)
            p_edit = QLineEdit(str(power)); b_edit = QLineEdit(f"{bonus}%"); b_edit.setFixedWidth(80)
            row_layout.addWidget(lvl_lbl); row_layout.addWidget(QLabel("Power:")); row_layout.addWidget(p_edit); row_layout.addWidget(QLabel("Bonus:")); row_layout.addWidget(b_edit)
            self.level_inputs.append((stats_id, p_edit, b_edit)); c_layout.addWidget(row_frame)
        scroll.setWidget(container); layout.addWidget(scroll)
        btn_box = QHBoxLayout(); save_btn = QPushButton("Save Changes"); save_btn.setStyleSheet("background-color: #2e7d32; font-weight: bold;"); save_btn.clicked.connect(self.save_data)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject); btn_box.addStretch(); btn_box.addWidget(save_btn); btn_box.addWidget(cancel_btn); layout.addLayout(btn_box)

    def save_data(self):
        try:
            for stats_id, p_edit, b_edit in self.level_inputs:
                p_val, b_val = p_edit.text().strip(), b_edit.text().replace('%', '').strip()
                self.db.update_miner_level_stats(stats_id, p_val, b_val)
            self.accept()
        except Exception as e: QMessageBox.critical(self, "Database Error", f"Failed to update miner: {e}")

class RackDetailsDialog(QDialog):
    edit_requested = Signal(dict)
    def __init__(self, stats, rack_widget, parent=None):
        super().__init__(parent)
        self.rack_widget = rack_widget
        self.setWindowTitle("Rack Details")
        self.setFixedSize(450, 580)
        
        main_layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        left_spacer = QWidget(); left_spacer.setFixedWidth(24); header_layout.addWidget(left_spacer)
        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 16px;"); self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.header_label, 1)
        
        self.lock_btn = QPushButton(); self.lock_btn.setFixedSize(24, 24); self.lock_btn.setStyleSheet("background: transparent; border: none;")
        self.update_lock_icon(); self.lock_btn.clicked.connect(self.toggle_lock)
        header_layout.addWidget(self.lock_btn)
        
        header_frame = QFrame(); header_frame.setLayout(header_layout); header_frame.setStyleSheet("border-bottom: 1px solid #333; padding-bottom: 5px;")
        main_layout.addWidget(header_frame)
        
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.miner_container = QWidget()
        self.c_layout = QVBoxLayout(self.miner_container); self.c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.miner_container)
        main_layout.addWidget(self.scroll)
        
        self.footer = QFrame(); self.footer.setStyleSheet("border-top: 1px solid #333; padding-top: 10px;")
        self.f_layout = QVBoxLayout(self.footer)
        main_layout.addWidget(self.footer)
        
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.populate_dialog(stats)

    def populate_dialog(self, stats):
        while self.c_layout.count():
            item = self.c_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        while self.f_layout.count():
            item = self.f_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        rack_name = self.rack_widget.data.get('name', 'Unknown Rack')
        rack_bonus = self.rack_widget.data.get('bonus_val', 0.0)
        header_text = f"<b>{rack_name}</b> | <span style='color:#5dade2;'>{rack_bonus}% Bonus</span>"
        if stats.get('set_name') and stats.get('set_name') != "Unknown Set":
            header_text = f"<b>{stats['set_name']}</b> | <span style='color:#5dade2;'>{rack_bonus}% Bonus</span>"
        self.header_label.setText(header_text)
        
        for m in stats['miners']:
            m_frame = QFrame(); m_frame.setObjectName("MinerRow")
            m_frame.setStyleSheet("QFrame#MinerRow { background: transparent; border-radius: 4px; margin-bottom: 2px; } QFrame#MinerRow:hover { background: #222; } QFrame#MinerRow QLabel { background: transparent; }")
            m_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            m_frame.customContextMenuRequested.connect(lambda pos, data=m, widget=m_frame: self.show_miner_menu(pos, data, widget))
            
            m_layout = QHBoxLayout(m_frame)
            img_lbl = QLabel()
            if os.path.exists(m.get('image_path', '')):
                img_lbl.setPixmap(QPixmap(m['image_path']).scaled(35, 25, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            img_lbl.setFixedWidth(40)
            
            name_lbl = QLabel(f"<b>{m['name']}</b> (Lvl {m['lvl']})")
            p_lbl = QLabel(f"<span style='color:#00ff00;'>{format_hashrate(m['power'])}</span>")
            b_lbl = QLabel(f"<span style='color:#ffcc00;'>{m['bonus']}%</span>")
            
            m_layout.addWidget(img_lbl); m_layout.addWidget(name_lbl); m_layout.addStretch(); m_layout.addWidget(p_lbl); m_layout.addWidget(b_lbl)
            self.c_layout.addWidget(m_frame)
            
        totals_map = [("Base Power:", stats['base_power'], "white"), ("Miner Bonus's:", stats['miner_bonus_power'], "#ffcc00")]
        if stats.get('is_set_rack'):
            if stats.get('set_bonus_power', 0) > 0: totals_map.append(("Set Bonus:", stats['set_bonus_power'], "#f1c40f"))
            if stats.get('set_flat_power', 0) > 0: totals_map.append(("Set Power:", stats['set_flat_power'], "white"))
        totals_map.append(("Rack Bonus Power:", stats['rack_bonus'], "#5dade2"))
        totals_map.append(("Total Power:", stats['total_power'], "#00ff00"))
        
        for label, val, color in totals_map:
            row = QHBoxLayout(); row.addWidget(QLabel(f"<b>{label}</b>")); row.addStretch()
            if label == "Miner Bonus's:": disp = f"{stats.get('miner_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            elif label == "Set Bonus:": disp = f"{stats.get('set_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            elif label == "Rack Bonus Power:": disp = f"{stats.get('rack_bonus_pct', 0.0):.2f}% | {format_hashrate(val)}"
            else: disp = format_hashrate(val)
            v_lbl = QLabel(disp); v_lbl.setStyleSheet(f"color: {color}; font-weight: bold;"); row.addWidget(v_lbl)
            self.f_layout.addLayout(row)

    def toggle_lock(self): 
        self.rack_widget.is_locked = not self.rack_widget.is_locked
        self.update_lock_icon()
        
    def update_lock_icon(self):
        icon_path = LOCK_ICON if self.rack_widget.is_locked else UNLOCK_ICON
        if os.path.exists(icon_path):
            self.lock_btn.setIcon(QIcon(icon_path)); self.lock_btn.setIconSize(QSize(20, 20))
        
    def show_miner_menu(self, pos, miner_data, widget):
        if self.rack_widget.is_locked: return
        menu = QMenu(self)
        edit_act = QAction("Edit Miner Data", self)
        edit_act.triggered.connect(lambda: self.edit_requested.emit(miner_data))
        
        remove_act = QAction("Remove Miner", self)
        remove_act.triggered.connect(lambda: self.do_remove_miner(miner_data))
        
        menu.addAction(edit_act); menu.addAction(remove_act)
        menu.exec(widget.mapToGlobal(pos))

    def do_remove_miner(self, miner_data):
        self.rack_widget.remove_miner(miner_data['row'], miner_data['slot'])
        gb = self.parent().current_stats.get('bonus_percent', 0.0)
        new_stats = calculate_single_rack_stats(self.rack_widget.data, self.rack_widget.rows_data, gb)
        self.populate_dialog(new_stats)

class AddRackDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Add Catalog Rack")
        self.setFixedSize(450, 500)
        self.result_data = None
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

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
        for s in sets: self.set_combo.addItem(s[1], s[2])
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
        self.ns_name = QLineEdit(); self.ns_id = QLineEdit()
        ns_layout.addRow("New Set Name:", self.ns_name); ns_layout.addRow("New Set Global ID:", self.ns_id)
        layout.addWidget(self.new_set_group); self.new_set_group.hide()
        layout.addStretch()
        btn_box = QHBoxLayout()
        apply_btn = QPushButton("Save to Database"); apply_btn.clicked.connect(self.do_apply)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(apply_btn); btn_box.addWidget(cancel_btn); layout.addLayout(btn_box)

    def on_set_changed(self, index):
        data = self.set_combo.currentData()
        self.new_set_group.setVisible(data == "NEW")
        if data and data != "NEW": self.set_icon_edit.setText(self.db.get_set_icon_lookup(data))
        elif not data: self.set_icon_edit.clear()

    def browse_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.ico)")
        if path: target.setText(path)

    def do_apply(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Rack Name is required."); return
        set_global_id = self.set_combo.currentData()
        if set_global_id == "NEW":
            set_global_id = self.ns_id.text().strip()
            self.db.ensure_set_exists(self.ns_name.text(), set_global_id)
        self.result_data = {'name': self.name_edit.text(), 'rack_id_tag': self.id_tag_edit.text().strip(), 'set_global_id': set_global_id, 'rack_size': "Big Rack", 'bonus_percent': self.bonus_edit.text(), 'image_path': self.img_edit.text(), 'set_sign_icon_path': self.set_icon_edit.text()}
        self.accept()

class AddMinerDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db; self.setWindowTitle("Add Catalog Miner"); self.setFixedSize(550, 680); self.base_result = None; self.levels_result = []; 
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self); form = QFormLayout()
        self.name_edit = QLineEdit(); form.addRow("Miner Name:", self.name_edit)
        self.img_edit = QLineEdit()
        btn_browse_img = QPushButton("Browse"); btn_browse_img.clicked.connect(lambda: self.browse_file(self.img_edit))
        img_box = QHBoxLayout(); img_box.addWidget(self.img_edit); img_box.addWidget(btn_browse_img)
        form.addRow("Base Image:", img_box)
        self.slot_combo = QComboBox(); self.slot_combo.addItems(["1 slot", "2 slot"]); form.addRow("Slot Size:", self.slot_combo)
        self.set_combo = QComboBox(); self.set_combo.addItem("None", None); self.set_combo.addItem("+ Create New Set", "NEW")
        sets = self.db.get_all_set_definitions()
        for s in sets: self.set_combo.addItem(s[1], s[2])
        self.set_combo.currentIndexChanged.connect(self.on_set_changed); form.addRow("Set:", self.set_combo)
        self.set_icon_edit = QLineEdit()
        btn_browse_icon = QPushButton("Browse"); btn_browse_icon.clicked.connect(lambda: self.browse_file(self.set_icon_edit))
        icon_box = QHBoxLayout(); icon_box.addWidget(self.set_icon_edit); icon_box.addWidget(btn_browse_icon)
        form.addRow("Set Sign Icon:", icon_box)
        layout.addLayout(form)
        self.new_set_group = QFrame(); self.new_set_group.setStyleSheet("background: #1a1a1a; border-radius: 5px;")
        ns_layout = QFormLayout(self.new_set_group); self.ns_name = QLineEdit(); self.ns_id = QLineEdit()
        ns_layout.addRow("New Set Name:", self.ns_name); ns_layout.addRow("New Set Global ID:", self.ns_id)
        layout.addWidget(self.new_set_group); self.new_set_group.hide()
        lbl_levels = QLabel("<b>Level Statistics</b> (Empty levels will be skipped)"); lbl_levels.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(lbl_levels)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); container = QWidget(); c_layout = QVBoxLayout(container); self.level_rows = []
        for i in range(1, 7):
            frame = QFrame(); frame.setStyleSheet("background: #1a1a1a; border-radius: 5px; margin: 2px;"); r = QVBoxLayout(frame); h1 = QHBoxLayout(); h1.addWidget(QLabel(f"<b>Lvl {i}</b>"))
            p_edit = QLineEdit(); p_edit.setPlaceholderText("Power (e.g. 150 Gh/s)"); b_edit = QLineEdit(); b_edit.setPlaceholderText("Bonus %")
            h1.addWidget(QLabel("Power:")); h1.addWidget(p_edit); h1.addWidget(QLabel("Bonus:")); h1.addWidget(b_edit); r.addLayout(h1); h2 = QHBoxLayout()
            id_edit = QLineEdit(); id_edit.setPlaceholderText("Level ID Tag (for JSON imports)"); h2.addWidget(QLabel("ID Tag:")); h2.addWidget(id_edit); r.addLayout(h2); self.level_rows.append((i, p_edit, b_edit, id_edit)); c_layout.addWidget(frame)
        scroll.setWidget(container); layout.addWidget(scroll)
        btn_box = QHBoxLayout(); apply_btn = QPushButton("Save All to Database"); apply_btn.clicked.connect(self.do_apply)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject); btn_box.addWidget(apply_btn); btn_box.addWidget(cancel_btn); layout.addLayout(btn_box)

    def on_set_changed(self, index):
        data = self.set_combo.currentData()
        self.new_set_group.setVisible(data == "NEW")
        if data and data != "NEW": self.set_icon_edit.setText(self.db.get_set_icon_lookup(data))
        elif not data: self.set_icon_edit.clear()

    def browse_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg)")
        if path: target.setText(path)

    def do_apply(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Miner Name is required."); return
        set_global_id = self.set_combo.currentData()
        if set_global_id == "NEW":
            set_global_id = self.ns_id.text().strip()
            self.db.ensure_set_exists(self.ns_name.text(), set_global_id)
        self.base_result = {'name': self.name_edit.text(), 'image_path': self.img_edit.text(), 'slot_size': 1 if self.slot_combo.currentText() == "1 slot" else 2, 'set_global_id': set_global_id, 'set_sign_icon_path': self.set_icon_edit.text()}
        for lvl, p_e, b_e, id_e in self.level_rows:
            if p_e.text().strip() or b_e.text().strip() or id_e.text().strip():
                self.levels_result.append({'lvl': lvl, 'power': p_e.text().strip() if p_e.text().strip() else "0", 'bonus': b_e.text().strip() if b_e.text().strip() else "0", 'level_id_tag': id_e.text().strip()})
        if not self.levels_result:
            QMessageBox.warning(self, "Empty", "Add stats for at least one level."); return
        self.accept()

class PowerBreakdownDialog(QDialog):
    def __init__(self, stats, baseline_stats=None, parent=None):
        super().__init__(parent); self.setWindowTitle("Total Power Breakdown"); self.setFixedWidth(420)
        room_count = len(stats.get('room_details', [])); self.setFixedHeight(220 + (room_count * 25)); layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 20)
        
        stats_map = [("miners_base", "Miner:"), ("bonus_power", "Bonus Power:"), ("rack_bonus", "Rack Bonus:")]
        for key, label in stats_map:
            row = QHBoxLayout(); lbl = QLabel(f"<b>{label}</b>")
            if key == "bonus_power": disp = f"{stats.get('bonus_percent', 0.0):.2f}% | {format_hashrate(stats[key])}"
            else: disp = format_hashrate(stats.get(key, 0))
            
            val_lbl = QLabel(disp); row.addWidget(lbl); row.addStretch()
            
            if baseline_stats:
                curr_v, base_v = float(stats.get(key, 0)), float(baseline_stats.get(key, 0))
                d_label = self.create_delta_label(curr_v - base_v)
                row.addWidget(d_label)

            row.addWidget(val_lbl); layout.addLayout(row)

        layout.addSpacing(10); separator = QLabel("~~~~~~~~~~~~~~~~ rooms ~~~~~~~~~~~~~~~~"); separator.setAlignment(Qt.AlignmentFlag.AlignCenter); separator.setStyleSheet("color: #555; font-weight: bold;"); layout.addWidget(separator); layout.addSpacing(10)
        
        room_details = sorted(stats.get('room_details', []), key=lambda x: x['room_id'])
        base_rooms = {r['room_id']: r['total'] for r in baseline_stats.get('room_details', [])} if baseline_stats else {}

        for item in room_details:
            row = QHBoxLayout(); room_lbl = QLabel(f"<b>Room {item['room_id'] + 1} Total:</b>")
            room_val = QLabel(format_hashrate(item['total'])); room_val.setStyleSheet("color: #00ff00;"); row.addWidget(room_lbl); row.addStretch()
            
            if item['room_id'] in base_rooms:
                d_label = self.create_delta_label(item['total'] - base_rooms[item['room_id']])
                row.addWidget(d_label)
            
            row.addWidget(room_val); layout.addLayout(row)

        layout.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close); layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def create_delta_label(self, delta):
        lbl = QLabel("")
        if delta > 0.001:
            lbl.setText(f"↑ {format_hashrate(delta)}")
            lbl.setStyleSheet("color: #00ff00; font-size: 10px; font-weight: bold; margin-right: 5px;")
        elif delta < -0.001:
            lbl.setText(f"↓ {format_hashrate(abs(delta))}")
            lbl.setStyleSheet("color: #ff4444; font-size: 10px; font-weight: bold; margin-right: 5px;")
        return lbl

class MainWindow(QMainWindow):
    def __init__(self, splash=None):
        super().__init__(); self.setWindowTitle("Mining Room Simulator"); self.resize(WINDOW_WIDTH, WINDOW_HEIGHT); self.setStyleSheet(DARK_STYLESHEET); self.room_save_path = None; self.splash = splash; self._is_importing = False
        if os.path.exists(APP_ICON_PATH): self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.db_handler = DatabaseHandler(); self.room_buttons, self.room_views = [], []; self.current_stats = None; self.baseline_stats = None; self.undo_stack, self.redo_stack = [], []; self._is_handling_undo_redo = False; 
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui(); self.config = self.load_app_config(); self.perform_auto_imports(); self.update_stats(); self.record_state()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central); self.main_layout = QVBoxLayout(central); header = QHBoxLayout()
        self.power_label = QLabel("Total Power: 0.000 Gh/s"); self.power_label.setObjectName("PowerLabel"); self.power_label.setCursor(Qt.CursorShape.PointingHandCursor); self.power_label.mousePressEvent = self.on_power_label_clicked
        self.power_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.power_label.customContextMenuRequested.connect(self.on_power_label_context_menu)
        self.delta_label = QLabel(""); self.delta_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        league_box = QHBoxLayout(); league_box.addWidget(QLabel("League:")); self.league_icon = QLabel(); self.league_icon.setFixedSize(28, 28); league_box.addWidget(self.league_icon)
        header.addWidget(self.power_label); header.addSpacing(10); header.addWidget(self.delta_label); header.addSpacing(15); header.addLayout(league_box); header.addStretch()
        self.add_btn = HoverMenuButton("Add"); act_add_rack = QAction("Add Rack", self); act_add_rack.triggered.connect(self.on_add_rack_clicked); act_add_miner = QAction("Add Miner", self); act_add_miner.triggered.connect(self.on_add_miner_clicked); self.add_btn.menu.addAction(act_add_rack); self.add_btn.menu.addAction(act_add_miner); header.addWidget(self.add_btn)
        for act in ["Save", "Import", "Export"]:
            btn = QPushButton(act); btn.clicked.connect(getattr(self, f"on_{act.lower()}_clicked")); header.addWidget(btn)
        self.main_layout.addLayout(header); self.room_nav = QHBoxLayout()
        for i in range(4): self.add_room_button(i)
        add_rm = QPushButton("+"); add_rm.setFixedWidth(30); add_rm.clicked.connect(self.on_plus_clicked); self.room_nav.addWidget(add_rm); self.room_nav.addStretch()
        self.clear_btn = HoverMenuButton("Clear"); self.setup_clear_menu(); self.room_nav.addWidget(self.clear_btn); self.main_layout.addLayout(self.room_nav)
        self.inventory = InventorySection(); self.inventory.view.itemClicked.connect(self.on_inventory_item_clicked); self.inventory.edit_requested.connect(self.open_miner_editor); self.inventory.inventory_changed.connect(self.auto_save_inventory)
        self.room_stack = QStackedWidget()
        for i in range(4):
            view = RoomView(i); self.connect_room_signals(view); self.room_views.append(view); self.room_stack.addWidget(view)
        self.main_layout.addWidget(self.room_stack, stretch=2); self.main_layout.addWidget(self.inventory, stretch=1); self.save_status_label = QLabel("Saved"); self.save_status_label.setStyleSheet("color: #888888; font-size: 10px;"); self.save_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); self.main_layout.addWidget(self.save_status_label)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and event.key() == Qt.Key.Key_R: self.redo(); return
            elif event.key() == Qt.Key.Key_Z: self.undo(); return
        super().keyPressEvent(event)

    def record_state(self):
        if self._is_handling_undo_redo or self._is_importing: return
        all_rooms_state = [rv.get_room_state() for rv in self.room_views]
        snapshot = {"rooms": copy.deepcopy(all_rooms_state), "personal_inventory": copy.deepcopy(self.inventory.personal_data)}
        if self.undo_stack and self.undo_stack[-1] == snapshot: return
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 11: self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if len(self.undo_stack) <= 1: return
        self.redo_stack.append(self.undo_stack.pop()); self.apply_state(self.undo_stack[-1])

    def redo(self):
        if not self.redo_stack: return
        next_state = self.redo_stack.pop(); self.undo_stack.append(next_state); self.apply_state(next_state)

    def apply_state(self, state):
        self._is_handling_undo_redo = True; self.inventory.block_inventory_signals = True; self.setUpdatesEnabled(False)
        for rv in self.room_views: rv.blockSignals(True)
        self.inventory.blockSignals(True)
        try:
            for idx, room_view in enumerate(self.room_views):
                target_room_data = state["rooms"][idx] if idx < len(state["rooms"]) else []
                for p_idx, pld in enumerate(room_view.placeholders):
                    target_rack_info = target_room_data[p_idx] if p_idx < len(target_room_data) else None
                    if not target_rack_info:
                        if pld.rack: pld.remove_rack(silent=True)
                        continue
                    trd, trs, tlk = target_rack_info.get("rack_data"), target_rack_info.get("rows", []), target_rack_info.get("is_locked", False)
                    if pld.rack:
                        if pld.rack.data == trd:
                            if pld.rack.rows_data != trs: pld.rack.rows_data = copy.deepcopy(trs); pld.rack.refresh_ui()
                            pld.rack.is_locked = tlk
                        else: pld.remove_rack(silent=True); pld.add_rack(trd, initial_miners=trs, is_locked=tlk)
                    else: pld.add_rack(trd, initial_miners=trs, is_locked=tlk)
            self.inventory.personal_data = copy.deepcopy(state["personal_inventory"]); self.inventory.trigger_refresh(); self.update_stats()
        finally:
            for rv in self.room_views: rv.blockSignals(False)
            self.inventory.blockSignals(False); self.setUpdatesEnabled(True); self.inventory.block_inventory_signals = False; self._is_handling_undo_redo = False

    def setup_clear_menu(self):
        m = self.clear_btn.menu; a1 = QAction("Clear current room", self); a1.triggered.connect(lambda: self.room_stack.currentWidget().clear_room(False))
        a2 = QAction("Clear current room of all miners", self); a2.triggered.connect(lambda: self.room_stack.currentWidget().clear_room(True))
        a3 = QAction("Clear all rooms", self); a3.triggered.connect(self.clear_all_rooms); a4 = QAction("Clear all miners", self); a4.triggered.connect(self.clear_all_miners); m.addActions([a1, a2, a3, a4])

    def clear_all_rooms(self):
        for v in self.room_views: v.clear_room(False)
    def clear_all_miners(self):
        for v in self.room_views: v.clear_room(True)

    def load_app_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f: return json.load(f)
            except: pass
        return {"room_path": "", "room_auto": False, "inv_path": "", "inv_auto": False}

    def save_app_config(self):
        if not os.path.exists(os.path.dirname(CONFIG_PATH)): os.makedirs(os.path.dirname(CONFIG_PATH))
        with open(CONFIG_PATH, "w") as f: json.dump(self.config, f, indent=2)

    def perform_auto_imports(self):
        self._is_importing = True; self.inventory.block_inventory_signals = True
        if self.splash: self.splash.update_progress(25, "Database Initialized.")
        if self.config.get("inv_auto") and self.config.get("inv_path"):
            if self.splash: self.splash.update_progress(50, "Loading Player Inventory..."); self.inventory.load_inventory_file(self.config["inv_path"])
        if self.config.get("room_auto") and self.config.get("room_path"):
            if self.splash: self.splash.update_progress(75, "Loading Player Room..."); self.load_room_file(self.config["room_path"])
        if self.splash: self.splash.update_progress(100, "Reconciling Personal Stock...")
        self.reconcile_personal_inventory(); self.inventory.block_inventory_signals = False; self._is_importing = False
        self.set_baseline() 

    def reconcile_personal_inventory(self):
        for view in self.room_views:
            for p in view.placeholders:
                if p.rack:
                    if p.rack.data.get('source') == 'Personal': self.inventory.adjust_quantity(p.rack.data, -1)
                    for row in p.rack.rows_data:
                        miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                        for m in miners:
                            if isinstance(m, dict) and m.get('source') == 'Personal': self.inventory.adjust_quantity(m, -1)

    def connect_room_signals(self, view):
        view.stats_changed.connect(self.update_stats); view.stats_changed.connect(self.record_state); view.stats_changed.connect(self.auto_save)
        view.item_placed.connect(lambda data: self.inventory.adjust_quantity(data, -1)); view.item_returned.connect(lambda data: self.inventory.adjust_quantity(data, 1))
        view.rack_clicked.connect(self.on_rack_clicked); view.miner_edit_requested.connect(self.open_miner_editor)
        view.rack_swap_requested.connect(self.on_swap_rack_requested)

    def on_swap_rack_requested(self, rack_widget, pos):
        placeholder = next((p for p in self.room_stack.currentWidget().placeholders if p.rack == rack_widget), None)
        if not placeholder: return
        
        available_racks = [item for item in self.inventory.personal_data if item.get('type') == 'rack' and item.get('quantity', 0) > 0]
        if not available_racks:
            QMessageBox.information(self, "No Racks", "You don't have any spare racks in your personal inventory.")
            return
            
        menu = QMenu(self)
        for rack_data in available_racks:
            action_text = f"{rack_data['name']} ({rack_data.get('bonus_val', 0)}%)"
            act = QAction(action_text, self)
            act.triggered.connect(lambda checked=False, rd=rack_data: self.execute_rack_swap(placeholder, rd))
            menu.addAction(act)
        menu.exec(pos)

    def execute_rack_swap(self, placeholder, new_rack_data):
        self.inventory.block_inventory_signals = True
        placeholder.blockSignals(True)
        
        old_rack_data = placeholder.rack.data
        old_miners = []
        for row in placeholder.rack.rows_data:
            if isinstance(row, dict): old_miners.append(row)
            elif isinstance(row, list):
                for m in row:
                    if m: old_miners.append(m)
        
        placeholder.remove_rack(silent=True) 
        self.inventory.adjust_quantity(old_rack_data, 1)
        self.inventory.adjust_quantity(new_rack_data, -1)
        
        placeholder.add_rack(new_rack_data, initial_miners=None, is_locked=False)
        
        for m in old_miners:
            if not placeholder.rack.add_miner(m):
                self.inventory.adjust_quantity(m, 1)
        
        placeholder.blockSignals(False)
        self.inventory.block_inventory_signals = False
        
        self.update_stats()
        self.auto_save()
        self.auto_save_inventory()

    def auto_save_inventory(self):
        if self._is_importing or self.inventory.block_inventory_signals: return
        p = self.config.get("inv_path")
        if p and os.path.exists(p): self.inventory.save_personal_inventory(p)

    def open_miner_editor(self, miner_data):
        dlg = EditMinerDialog(miner_data, self.db_handler, self)
        if dlg.exec(): self.db_handler.preload_data(); self.inventory.preload_data_from_db(); self.sync_room_miners(); self.update_stats()

    def sync_room_miners(self):
        lookup = {(item['name'], item['lvl']): (item['power_val'], item['bonus_val']) for item in self.inventory.game_data if item.get('type') == 'miner'}
        for view in self.room_views:
            for p in view.placeholders:
                if p.rack:
                    upd = False
                    for r_idx, row in enumerate(p.rack.rows_data):
                        miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                        for m in miners:
                            if isinstance(m, dict):
                                key = (m.get('name'), m.get('lvl'))
                                if key in lookup: m['power_val'], m['bonus_val'] = lookup[key]; upd = True
                    if upd: p.rack.refresh_ui()

    def on_inventory_item_clicked(self, data):
        c = self.room_stack.currentWidget()
        if c: c.handle_item_click(data)

    def on_rack_clicked(self, rack_data, rows_data):
        gb = self.current_stats.get('bonus_percent', 0.0)
        s = calculate_single_rack_stats(rack_data, rows_data, gb)
        w = next((p.rack for p in self.room_stack.currentWidget().placeholders if p.rack and p.rack.data == rack_data and p.rack.rows_data == rows_data), None)
        if w:
            dlg = RackDetailsDialog(s, w, self); dlg.edit_requested.connect(self.open_miner_editor); dlg.exec()

    def add_room_button(self, idx):
        btn = QPushButton(f"Room {idx + 1}"); btn.clicked.connect(lambda checked=False, i=idx: self.room_stack.setCurrentIndex(i))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); btn.customContextMenuRequested.connect(lambda pos, i=idx: self.on_room_button_context_menu(pos, i))
        self.room_nav.insertWidget(len(self.room_buttons), btn); self.room_buttons.append(btn)

    def on_room_button_context_menu(self, pos, index):
        menu = QMenu(self); del_action = QAction(f"Delete Room {index + 1}", self); del_action.triggered.connect(lambda: self.delete_room(index)); menu.addAction(del_action); menu.exec(self.room_buttons[index].mapToGlobal(pos))

    def delete_room(self, index):
        if len(self.room_views) <= 1: QMessageBox.warning(self, "Action Denied", "You must have at least one room."); return
        if QMessageBox.question(self, "Delete Room", f"Are you sure you want to delete Room {index + 1}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.room_views[index].clear_room(False); self.room_stack.removeWidget(self.room_views[index]); self.room_nav.removeWidget(self.room_buttons[index])
            btn, view = self.room_buttons.pop(index), self.room_views.pop(index); btn.deleteLater(); view.deleteLater()
            for i, b in enumerate(self.room_buttons):
                b.setText(f"Room {i + 1}"); [b.clicked.disconnect() for _ in range(1) if hasattr(b.clicked, 'disconnect')]; [b.customContextMenuRequested.disconnect() for _ in range(1) if hasattr(b.customContextMenuRequested, 'disconnect')]
                b.clicked.connect(lambda checked=False, idx=i: self.room_stack.setCurrentIndex(idx)); b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); b.customContextMenuRequested.connect(lambda pos, idx=i: self.on_room_button_context_menu(pos, idx))
            for i, v in enumerate(self.room_views): v.room_id = i
            self.update_stats(); self.record_state()

    def on_add_rack_clicked(self):
        dlg = AddRackDialog(self.db_handler, self)
        if dlg.exec() and dlg.result_data: self.db_handler.add_custom_rack_full(dlg.result_data); self.inventory.preload_data_from_db(); self.record_state()

    def on_add_miner_clicked(self):
        dlg = AddMinerDialog(self.db_handler, self)
        if dlg.exec() and dlg.base_result: self.db_handler.add_custom_miner_full(dlg.base_result, dlg.levels_result); self.inventory.preload_data_from_db(); self.record_state()

    def on_plus_clicked(self):
        idx = len(self.room_buttons); view = RoomView(idx); self.connect_room_signals(view); self.room_views.append(view); self.room_stack.addWidget(view); self.add_room_button(idx); self.record_state()

    def update_stats(self):
        placed_ids = set()
        for view in self.room_views:
            for p in view.placeholders:
                if p.rack:
                    for row in p.rack.rows_data:
                        miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                        for m in miners:
                            if isinstance(m, dict):
                                self.repair_item_data(m); tag = m.get('level_id_tag')
                                if tag: placed_ids.add(str(tag).lower())
        self.inventory.set_placed_items(placed_ids); state = {i: v.get_room_state() for i, v in enumerate(self.room_views)}
        
        self.current_stats = calculate_power_breakdown(state)
        self.power_label.setText(f"Total Power: {format_hashrate(self.current_stats['total'])}")
        
        if self.baseline_stats is None:
            self.baseline_stats = copy.deepcopy(self.current_stats)

        delta = float(self.current_stats['total']) - float(self.baseline_stats['total'])
        if delta > 0.001:
            self.delta_label.setText(f"↑ {format_hashrate(delta)}")
            self.delta_label.setStyleSheet("color: #00ff00; font-weight: bold;")
        elif delta < -0.001:
            self.delta_label.setText(f"↓ {format_hashrate(abs(delta))}")
            self.delta_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.delta_label.setText("")

        name, icon_file = get_league_info(self.current_stats['total']); path = os.path.join(LEAGUES_DIR, icon_file)
        if os.path.exists(path): self.league_icon.setPixmap(QPixmap(path).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.league_icon.setToolTip(get_league_tooltip(self.current_stats['total']))

    def set_baseline(self):
        if self.current_stats:
            self.baseline_stats = copy.deepcopy(self.current_stats)
            self.delta_label.setText("")

    def on_power_label_context_menu(self, pos):
        menu = QMenu(self)
        reset_act = QAction("Reset Comparison Baseline", self)
        reset_act.triggered.connect(self.set_baseline)
        menu.addAction(reset_act)
        menu.exec(self.power_label.mapToGlobal(pos))

    def on_power_label_clicked(self, ev):
        PowerBreakdownDialog(self.current_stats, self.baseline_stats, self).exec()

    def _save_all_rooms(self, path):
        all_rooms = [{"room_index": i, "racks": [{"rack_data": p.rack.data, "rows": p.rack.rows_data, "is_locked": p.rack.is_locked} for p in v.placeholders if p.rack]} for i, v in enumerate(self.room_views) if any(p.rack for p in v.placeholders)]
        with open(path, "w") as f: json.dump(all_rooms, f, indent=2)

    def auto_save(self):
        if self._is_importing or not hasattr(self, "_autosave_path") or not self._autosave_path: return 
        self._save_all_rooms(self._autosave_path); self.save_status_label.setText("Saved"); self.save_status_label.setStyleSheet("color: #00ff00; font-size: 10px;"); QTimer.singleShot(1500, lambda: self.save_status_label.setStyleSheet("color: #888888; font-size: 10px;"))

    def repair_item_data(self, item_dict):
        if not item_dict: return item_dict
        name = str(item_dict.get('name', '')).strip()
        if 'power_val' in item_dict:
            lvl = int(item_dict.get('lvl', 1))
            for cached in self.db_handler.get_catalog_miners(lvl):
                if str(cached[1]).strip().lower() == name.lower(): item_dict['set_global_id'], item_dict['id'], item_dict['level_id_tag'] = cached[4], cached[0], str(cached[10]).lower(); break
        else:
            for cached in self.db_handler.get_catalog_racks():
                if str(cached[1]).strip().lower() == name.lower(): item_dict['set_global_id'], item_dict['id'] = cached[3], cached[0]; break
        return item_dict

    def load_room_file(self, path):
        if not os.path.exists(path): return
        self.room_save_path, self._autosave_path = path, path
        with open(path, "r") as f: all_rooms = json.load(f)
        for rv in self.room_views: [p.remove_rack(silent=True) for p in rv.placeholders if p.rack]
        for room_data in all_rooms:
            idx = room_data.get("room_index", 0)
            if idx < len(self.room_views):
                for p_idx, rack_info in enumerate(room_data.get("racks", [])):
                    if p_idx < len(self.room_views[idx].placeholders):
                        rack_data = self.repair_item_data(rack_info.get("rack_data", rack_info)); rows = rack_info.get("rows", []); is_locked = rack_info.get("is_locked", False)
                        repaired_rows = [self.repair_item_data(r) if isinstance(r, dict) else ([self.repair_item_data(m) if isinstance(m, dict) else m for m in r] if isinstance(r, list) else r) for r in rows]
                        self.room_views[idx].placeholders[p_idx].add_rack(rack_data, initial_miners=repaired_rows, is_locked=is_locked)
        self.update_stats()
        self.set_baseline() 

    def on_import_clicked(self):
        dlg = ImportManagerDialog(self.config, self)
        if dlg.exec():
            self._is_importing, self.inventory.block_inventory_signals = True, True; self.config = dlg.get_data(); self.save_app_config()
            if self.config.get("inv_path"): self.inventory.load_inventory_file(self.config["inv_path"])
            if self.config.get("room_path"): self.load_room_file(self.config["room_path"])
            self.reconcile_personal_inventory(); self.inventory.block_inventory_signals, self._is_importing = False, False; self.record_state()
            self.set_baseline() 

    def on_export_clicked(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Rooms", "", "JSON Files (*.json)")
        if path: self.room_save_path, self._autosave_path = path, path; self._save_all_rooms(path)

    def on_save_clicked(self):
        if not self.room_save_path: QMessageBox.warning(self, "No Export Path", "Please export the rooms first."); return
        self._save_all_rooms(self.room_save_path)

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyleSheet(DARK_STYLESHEET); splash = LoadingSplashScreen(); splash.show(); window = MainWindow(splash=splash)
    QTimer.singleShot(500, lambda: (window.show(), splash.finish(window))); sys.exit(app.exec())