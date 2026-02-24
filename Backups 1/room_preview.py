import os
import ast
import json
from PySide6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, 
                               QLabel, QMenu, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QAction, QImage, QPainter
from settings import (ROOM_1_RACKS, ROOM_OTHER_RACKS, ROOM_1_COLS, ROOM_OTHER_COLS, 
                      RACK_JSON_PATH)
from logic_math import format_hashrate

SLOT_W = 100
SLOT_H = 140

def resolve_path(path):
    if not path: return ""
    clean_p = path.replace("\\", "/")
    parts = clean_p.split("/")
    if "assets" in parts:
        return os.path.join(*parts[parts.index("assets"):])
    return path

class MinerInRack(QFrame):
    removed = Signal(int, int)
    edit_requested = Signal(dict)

    def __init__(self, miner_data, rect, row, slot, slot_template=None):
        super().__init__()
        self.data = miner_data
        self.row_idx = row
        self.slot_idx = slot
        self.slot_template = slot_template or {}
        self.setGeometry(rect)
        self.setStyleSheet("background: transparent; border: none;")

        path = resolve_path(self.data.get('image_path', ''))
        scale = self.data.get('img_scale', 0.5)

        if os.path.exists(path):
            pix = QPixmap(path)
            sw, sh = int(pix.width() * scale), int(pix.height() * scale)
            self.img_label = QLabel(self)
            self.img_label.setPixmap(pix.scaled(sw, sh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            dx = (rect.width() - sw) // 2
            dy = (rect.height() - sh) // 2
            self.img_label.setGeometry(dx, dy, sw, sh)

        icon_path = resolve_path(self.data.get('level_icon_path', ''))
        if icon_path and os.path.exists(icon_path):
            icon_scale = self.data.get('img_scale', 1.0)
            icon_size = int(12 * icon_scale)
            pix_icon = QPixmap(icon_path).scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.corner_label = QLabel(self)
            self.corner_label.setPixmap(pix_icon)
            if 'set_icon' in self.slot_template:
                icon_tmpl = self.slot_template['set_icon']
                self.corner_label.move(icon_tmpl['x'], icon_tmpl['y'])
                self.corner_label.setFixedSize(icon_tmpl['w'], icon_tmpl['h'])
            else:
                self.corner_label.move(2, 2)
                self.corner_label.setFixedSize(icon_size, icon_size)
            self.corner_label.show()
            self.corner_label.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            remove_act = QAction("Remove Miner", self)
            remove_act.triggered.connect(lambda: self.removed.emit(self.row_idx, self.slot_idx))
            
            edit_act = QAction("Edit Miner Data", self)
            edit_act.triggered.connect(lambda: self.edit_requested.emit(self.data))
            
            menu.addAction(remove_act)
            menu.addAction(edit_act)
            menu.exec(event.globalPosition().toPoint())
        else:
            event.ignore()

class RackWidget(QFrame):
    removed = Signal(dict) 
    miner_removed = Signal(dict)
    miner_added = Signal()
    clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)

    def __init__(self, rack_data):
        super().__init__()
        self.data = rack_data
        self.setStyleSheet("background: transparent; border: none;")
        template_root = self.load_template_root()
        self.metadata = template_root.get('metadata', {}) if template_root else {}
        racks_list = template_root.get('racks', []) if template_root else []
        self.template = racks_list[0] if racks_list else None
        self.row_count = len(self.template.get('2 slot', [])) if self.template else 0
        self.rows_data = [None] * self.row_count
        self.rack_img_offset_y = 0
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.init_ui()

    def load_template_root(self):
        try:
            if not os.path.exists(RACK_JSON_PATH): return None
            with open(RACK_JSON_PATH, 'r') as f:
                templates = json.load(f)
            size_attr = str(self.data.get('rack_size', '')).lower()
            name_attr = str(self.data.get('name', '')).lower()
            target_key = None
            if "big" in size_attr: target_key = "Big Rack"
            elif "small" in size_attr: target_key = "Small Rack"
            if not target_key:
                if "rack 8" in name_attr: target_key = "Big Rack"
                elif "rack 6" in name_attr: target_key = "Small Rack"
            if not target_key and templates:
                return list(templates.values())[0]
            return templates.get(target_key)
        except: return None

    def init_ui(self):
        self.setFixedSize(SLOT_W, SLOT_H)
        if self.template:
            self.rack_img = QLabel(self)
            self.rack_img.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            path = resolve_path(self.data.get('image_path', ''))
            if os.path.exists(path):
                full_pix = QPixmap(path)
                if not full_pix.isNull():
                    img_scale = self.metadata.get('img_scale', 1.0)
                    sw, sh = int(full_pix.width() * img_scale), int(full_pix.height() * img_scale)
                    self.rack_img_offset_y = SLOT_H - sh
                    self.rack_img.setPixmap(full_pix.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    self.rack_img.setGeometry(int(self.template['x']), int(self.rack_img_offset_y), sw, sh)
                    self.rack_img.show()
                    self.rack_img.lower()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data, self.rows_data)
        super().mousePressEvent(event)

    def can_fit(self, miner_data):
        if not self.template: return -1, -1
        size = int(miner_data.get('slot_size', 1))
        if size == 1:
            for r, row in enumerate(self.rows_data):
                if isinstance(row, list):
                    for s_idx in range(len(self.template['2 slot'][r]['1 slot'])):
                        if row[s_idx] is None: return r, s_idx
                elif row is None: return r, 0
        else:
            for r, row in enumerate(self.rows_data):
                if row is None: return r, 0
        return -1, -1

    def add_miner(self, miner_data, row=None, slot=None):
        if row is None: row, slot = self.can_fit(miner_data)
        if row != -1:
            if int(miner_data.get('slot_size', 1)) == 2:
                self.rows_data[row] = miner_data
            else:
                if self.rows_data[row] is None:
                    self.rows_data[row] = [None] * len(self.template['2 slot'][row]['1 slot'])
                self.rows_data[row][slot] = miner_data
            self.refresh_ui(); self.miner_added.emit()
            return True
        return False

    def remove_miner(self, row_idx, slot_idx):
        row_state = self.rows_data[row_idx]
        miner_to_return = None
        if isinstance(row_state, dict):
            miner_to_return = row_state
            self.rows_data[row_idx] = None
        elif isinstance(row_state, list):
            miner_to_return = row_state[slot_idx]
            row_state[slot_idx] = None
            if all(m is None for m in row_state): self.rows_data[row_idx] = None
        if miner_to_return:
            self.miner_removed.emit(miner_to_return)
        self.refresh_ui(); self.miner_added.emit()

    def refresh_ui(self):
        for child in self.findChildren(MinerInRack):
            child.deleteLater()
        if not self.template: return
        rx = self.template['x']
        ry = 0 
        for r_idx, row_state in enumerate(self.rows_data):
            if row_state is None: continue
            row_tmpl = self.template['2 slot'][r_idx]
            if isinstance(row_state, dict):
                fx, fy = rx + row_tmpl['x'], ry + row_tmpl['y']
                m = MinerInRack(row_state, QRect(fx, fy, row_tmpl['w'], row_tmpl['h']), r_idx, 0, slot_template=row_tmpl)
                m.setParent(self)
                m.removed.connect(self.remove_miner)
                m.edit_requested.connect(self.miner_edit_requested.emit)
                m.show()
            elif isinstance(row_state, list):
                for s_idx, miner in enumerate(row_state):
                    if isinstance(miner, dict):
                        slot_tmpl = row_tmpl['1 slot'][s_idx]
                        fx = rx + row_tmpl['x'] + slot_tmpl['x']
                        fy = ry + row_tmpl['y'] + slot_tmpl['y']
                        m = MinerInRack(miner, QRect(fx, fy, slot_tmpl['w'], slot_tmpl['h']), r_idx, s_idx, slot_template=slot_tmpl)
                        m.setParent(self)
                        m.removed.connect(self.remove_miner)
                        m.edit_requested.connect(self.miner_edit_requested.emit)
                        m.show()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        del_act = QAction("Remove Rack", self)
        del_act.triggered.connect(lambda: self.removed.emit(self.data))
        menu.addAction(del_act); menu.exec(self.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if "type': 'miner'" in event.mimeData().text(): event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            miner_data = ast.literal_eval(event.mimeData().text())
            if self.add_miner(miner_data):
                if miner_data.get('source') == 'Personal':
                    parent_view = self.parent().parent()
                    if hasattr(parent_view, 'item_placed'):
                        parent_view.item_placed.emit(miner_data)
        except: pass

class RackPlaceholder(QFrame):
    rack_placed = Signal()
    item_removed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)

    def __init__(self, index):
        super().__init__()
        self.index = index
        self.rack = None
        self.setFixedSize(SLOT_W, SLOT_H)
        self.setAcceptDrops(True)
        self.setStyleSheet("border: 1px dashed #333; background-color: #151515; border-radius: 2px;")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("Empty"); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #444; font-size: 8px;"); layout.addWidget(self.label)

    def add_rack(self, rack_data):
        if self.rack: return False
        self.label.hide(); self.rack = RackWidget(rack_data)
        self.layout().addWidget(self.rack); self.setStyleSheet("border: none; background: transparent;")
        self.rack.removed.connect(self.remove_rack)
        self.rack.miner_removed.connect(self.item_removed.emit)
        self.rack.miner_added.connect(self.rack_placed.emit)
        self.rack.clicked.connect(self.rack_clicked.emit)
        self.rack.miner_edit_requested.connect(self.miner_edit_requested.emit)
        self.rack_placed.emit(); return True

    def remove_rack(self, rack_data=None):
        if self.rack:
            data = rack_data if rack_data else self.rack.data
            self.item_removed.emit(data)
            self.layout().removeWidget(self.rack); self.rack.deleteLater()
            self.rack = None; self.label.show(); self.setStyleSheet("border: 1px dashed #333; background-color: #151515;")
            self.rack_placed.emit()

    def dragEnterEvent(self, event):
        if "type': 'rack'" in event.mimeData().text(): event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            rack_data = ast.literal_eval(event.mimeData().text())
            if self.add_rack(rack_data):
                if rack_data.get('source') == 'Personal':
                    self.parent().item_placed.emit(rack_data)
        except: pass

class RoomView(QWidget):
    stats_changed = Signal()
    item_returned = Signal(dict)
    item_placed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)

    def __init__(self, room_id):
        super().__init__()
        self.room_id = room_id
        self.placeholders = []
        self.init_ui()

    def init_ui(self):
        self.grid = QGridLayout(self); self.grid.setSpacing(10); self.grid.setContentsMargins(10, 10, 10, 10)
        count = ROOM_1_RACKS if self.room_id == 0 else ROOM_OTHER_RACKS
        cols = ROOM_1_COLS if self.room_id == 0 else ROOM_OTHER_COLS
        for i in range(count):
            row, col = divmod(i, cols)
            p = RackPlaceholder(i)
            p.rack_placed.connect(self.stats_changed.emit)
            p.item_removed.connect(self.item_returned.emit)
            p.rack_clicked.connect(self.rack_clicked.emit)
            p.miner_edit_requested.connect(self.miner_edit_requested.emit)
            self.grid.addWidget(p, row, col); self.placeholders.append(p)

    def handle_item_click(self, item_data):
        success = False
        if item_data['type'] == 'rack':
            for p in self.placeholders:
                if p.rack is None: 
                    if p.add_rack(item_data):
                        success = True; break
        else:
            for p in self.placeholders:
                if p.rack and p.rack.add_miner(item_data): 
                    success = True; break
        if success and item_data.get('source') == 'Personal':
            self.item_placed.emit(item_data)

    def get_room_state(self):
        return [{
            'rack_data': p.rack.data,
            'rack_bonus': p.rack.data.get('bonus_val', 0), 
            'rows': p.rack.rows_data
        } for p in self.placeholders if p.rack]