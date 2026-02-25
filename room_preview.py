import os
import ast
import json
from PySide6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, 
                               QLabel, QMenu, QFrame, QSizePolicy, QApplication)
from PySide6.QtCore import Qt, Signal, QRect, QMimeData, QPoint
from PySide6.QtGui import QPixmap, QAction, QImage, QPainter, QDrag, QColor
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
        self.drag_start_pos = None
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
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            rack = self.parent()
            if rack and hasattr(rack, 'is_locked') and rack.is_locked:
                event.ignore()
                return

            menu = QMenu(self)
            remove_act = QAction("Remove Miner", self)
            remove_act.triggered.connect(lambda: self.removed.emit(self.row_idx, self.slot_idx))
            edit_act = QAction("Edit Miner Data", self)
            edit_act.triggered.connect(lambda: self.edit_requested.emit(self.data))
            menu.addAction(remove_act)
            menu.addAction(edit_act)
            menu.exec(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        rack = self.parent()
        if rack and hasattr(rack, 'is_locked') and rack.is_locked:
            return

        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None:
            return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        move_info = {
            'type': 'miner',
            'miner_data': self.data,
            'move_meta': {
                'from_rack_id': id(self.parent()),
                'from_row': self.row_idx,
                'from_slot': self.slot_idx
            }
        }
        mime.setText(str(move_info))
        drag.setMimeData(mime)
        self.drag_start_pos = None
        drag.exec(Qt.DropAction.MoveAction)

class RackWidget(QFrame):
    removed = Signal(dict) 
    miner_removed = Signal(dict)
    miner_added = Signal()
    clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    swap_requested = Signal(object, QPoint)

    def __init__(self, rack_data, is_locked=False):
        super().__init__()
        self.data = rack_data
        self.is_locked = is_locked
        self.drag_start_pos = None
        self.is_drag_active = False
        self.drag_miner_size = 1
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.is_drag_active or not self.template:
            return
        painter = QPainter(self)
        highlight_color = QColor(0, 255, 0, 50)
        painter.setBrush(highlight_color)
        painter.setPen(Qt.NoPen)
        rx = self.template['x']
        ry = 0 
        for r_idx, row_tmpl in enumerate(self.template['2 slot']):
            row_state = self.rows_data[r_idx]
            if self.drag_miner_size == 2:
                if row_state is None:
                    painter.drawRoundedRect(rx + row_tmpl['x'], ry + row_tmpl['y'], row_tmpl['w'], row_tmpl['h'], 3, 3)
            else:
                for s_idx, slot_tmpl in enumerate(row_tmpl['1 slot']):
                    empty = False
                    if row_state is None: empty = True
                    elif isinstance(row_state, list) and row_state[s_idx] is None: empty = True
                    if empty:
                        fx = rx + row_tmpl['x'] + slot_tmpl['x']
                        fy = ry + row_tmpl['y'] + slot_tmpl['y']
                        painter.drawRoundedRect(fx, fy, slot_tmpl['w'], slot_tmpl['h'], 2, 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_locked:
            return
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None:
            return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        move_info = {
            'type': 'rack',
            'rack_data': self.data,
            'rows_data': self.rows_data,
            'is_locked': self.is_locked,
            'move_meta': {
                'from_placeholder_idx': self.parent().index if hasattr(self.parent(), 'index') else -1
            }
        }
        mime.setText(str(move_info))
        drag.setMimeData(mime)
        self.drag_start_pos = None
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
                self.clicked.emit(self.data, self.rows_data)
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

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
        miner_size = int(miner_data.get('slot_size', 1))
        if row is None: row, slot = self.can_fit(miner_data)
        if row != -1:
            current_row_state = self.rows_data[row]
            if current_row_state is not None:
                if miner_size == 2: return False 
                if isinstance(current_row_state, list) and current_row_state[slot] is not None: return False 
                if isinstance(current_row_state, dict): return False 
            if miner_size == 2: self.rows_data[row] = miner_data
            else:
                if self.rows_data[row] is None: self.rows_data[row] = [None] * len(self.template['2 slot'][row]['1 slot'])
                self.rows_data[row][slot] = miner_data
            self.refresh_ui(); self.miner_added.emit(); return True
        return False

    def remove_miner(self, row_idx, slot_idx, silent=False):
        if self.is_locked: return
        row_state = self.rows_data[row_idx]
        miner_to_return = None
        if isinstance(row_state, dict):
            miner_to_return = row_state; self.rows_data[row_idx] = None
        elif isinstance(row_state, list):
            miner_to_return = row_state[slot_idx]; row_state[slot_idx] = None
            if all(m is None for m in row_state): self.rows_data[row_idx] = None
        if miner_to_return and not silent: self.miner_removed.emit(miner_to_return)
        self.refresh_ui(); self.miner_added.emit()

    def clear_miners(self, silent=False):
        if self.is_locked: return
        for r_idx in range(len(self.rows_data)):
            row_state = self.rows_data[r_idx]
            if isinstance(row_state, dict): self.remove_miner(r_idx, 0, silent=silent)
            elif isinstance(row_state, list):
                for s_idx in range(len(row_state)):
                    if row_state[s_idx] is not None: self.remove_miner(r_idx, s_idx, silent=silent)

    def refresh_ui(self):
        for child in self.findChildren(MinerInRack): child.deleteLater()
        if not self.template: return
        rx, ry = self.template['x'], 0 
        for r_idx, row_state in enumerate(self.rows_data):
            if row_state is None: continue
            row_tmpl = self.template['2 slot'][r_idx]
            if isinstance(row_state, dict):
                fx, fy = rx + row_tmpl['x'], ry + row_tmpl['y']
                m = MinerInRack(row_state, QRect(fx, fy, row_tmpl['w'], row_tmpl['h']), r_idx, 0, slot_template=row_tmpl)
                m.setParent(self); m.removed.connect(self.remove_miner); m.edit_requested.connect(self.miner_edit_requested.emit); m.show()
            elif isinstance(row_state, list):
                for s_idx, miner in enumerate(row_state):
                    if isinstance(miner, dict):
                        slot_tmpl = row_tmpl['1 slot'][s_idx]
                        fx, fy = rx + row_tmpl['x'] + slot_tmpl['x'], ry + row_tmpl['y'] + slot_tmpl['y']
                        m = MinerInRack(miner, QRect(fx, fy, slot_tmpl['w'], slot_tmpl['h']), r_idx, s_idx, slot_template=slot_tmpl)
                        m.setParent(self); m.removed.connect(self.remove_miner); m.edit_requested.connect(self.miner_edit_requested.emit); m.show()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        swap_act = QAction("Swap Rack", self)
        swap_act.triggered.connect(lambda: self.swap_requested.emit(self, self.mapToGlobal(pos)))
        swap_act.setEnabled(not self.is_locked)
        menu.addAction(swap_act)
        
        empty_act = QAction("Empty the rack", self)
        empty_act.triggered.connect(self.clear_miners)
        empty_act.setEnabled(not self.is_locked)
        menu.addAction(empty_act)
        
        del_act = QAction("Remove Rack", self)
        del_act.triggered.connect(lambda: self.removed.emit(self.data))
        del_act.setEnabled(not self.is_locked)
        menu.addAction(del_act)
        menu.exec(self.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        try:
            data = ast.literal_eval(event.mimeData().text())
            miner_obj = data.get('miner_data', data) if isinstance(data, dict) else data
            if isinstance(miner_obj, dict) and miner_obj.get('type') == 'miner':
                self.is_drag_active = True; self.drag_miner_size = int(miner_obj.get('slot_size', 1)); self.update(); event.acceptProposedAction()
            elif "rack" in event.mimeData().text(): event.acceptProposedAction()
        except: pass

    def dragMoveEvent(self, event): event.acceptProposedAction()

    def dragLeaveEvent(self, event): self.is_drag_active = False; self.update(); super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.is_drag_active = False; self.update()
        try:
            data_obj = ast.literal_eval(event.mimeData().text())
            if isinstance(data_obj, dict) and (data_obj.get('type') == 'miner' or 'miner_data' in data_obj):
                is_move = 'move_meta' in data_obj
                miner_data = data_obj['miner_data'] if is_move else data_obj
                pos, target_row, target_slot, rx = event.position(), -1, 0, (self.template['x'] if self.template else 0)
                if self.template and '2 slot' in self.template:
                    for r_idx, row_tmpl in enumerate(self.template['2 slot']):
                        if row_tmpl['y'] <= pos.y() <= (row_tmpl['y'] + row_tmpl['h']):
                            target_row = r_idx
                            if int(miner_data.get('slot_size', 1)) == 1:
                                for s_idx, slot_tmpl in enumerate(row_tmpl['1 slot']):
                                    sx_start = rx + row_tmpl['x'] + slot_tmpl['x']; sx_end = sx_start + slot_tmpl['w']
                                    if sx_start <= pos.x() <= sx_end: target_slot = s_idx; break
                            break
                if target_row == -1: target_row, target_slot = self.can_fit(miner_data)
                if target_row != -1:
                    if self.add_miner(miner_data, target_row, target_slot):
                        if is_move:
                            if data_obj['move_meta']['from_rack_id'] == id(self):
                                if not (data_obj['move_meta']['from_row'] == target_row and data_obj['move_meta']['from_slot'] == target_slot):
                                    self.remove_miner(data_obj['move_meta']['from_row'], data_obj['move_meta']['from_slot'], silent=True)
                            else:
                                source_rack = next((r.rack for r in self.window().findChildren(RackPlaceholder) if r.rack and id(r.rack) == data_obj['move_meta']['from_rack_id']), None)
                                if source_rack: source_rack.remove_miner(data_obj['move_meta']['from_row'], data_obj['move_meta']['from_slot'], silent=True)
                        else:
                            if miner_data.get('source') == 'Personal':
                                parent_view = self.parent().parent()
                                if hasattr(parent_view, 'item_placed'): parent_view.item_placed.emit(miner_data)
        except: pass

class RackPlaceholder(QFrame):
    rack_placed = Signal()
    item_removed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    rack_swap_requested = Signal(object, QPoint)

    def __init__(self, index):
        super().__init__()
        self.index = index; self.rack = None; self.setFixedSize(SLOT_W, SLOT_H); self.setAcceptDrops(True); self.setStyleSheet("border: 1px dashed #333; background-color: #151515; border-radius: 2px;")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); self.label = QLabel("Empty"); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.label.setStyleSheet("color: #444; font-size: 8px;"); layout.addWidget(self.label)

    def add_rack(self, rack_data, initial_miners=None, is_locked=False):
        if self.rack: return False
        self.label.hide(); self.rack = RackWidget(rack_data, is_locked=is_locked)
        self.layout().addWidget(self.rack); self.setStyleSheet("border: none; background: transparent;")
        self.rack.removed.connect(self.remove_rack); self.rack.miner_removed.connect(self.item_removed.emit); self.rack.miner_added.connect(self.rack_placed.emit); self.rack.clicked.connect(self.rack_clicked.emit); self.rack.miner_edit_requested.connect(self.miner_edit_requested.emit)
        self.rack.swap_requested.connect(self.rack_swap_requested.emit)
        if initial_miners:
            for r_idx, row in enumerate(initial_miners):
                if isinstance(row, dict): self.rack.add_miner(row, r_idx, 0)
                elif isinstance(row, list):
                    for s_idx, miner in enumerate(row):
                        if miner: self.rack.add_miner(miner, r_idx, s_idx)
        self.rack_placed.emit(); return True

    def remove_rack(self, rack_data=None, silent=False):
        if self.rack:
            if self.rack.is_locked: return
            self.rack.clear_miners(silent=silent)
            data = rack_data if rack_data else self.rack.data
            if not silent: self.item_removed.emit(data)
            self.layout().removeWidget(self.rack); self.rack.deleteLater(); self.rack = None; self.label.show(); self.setStyleSheet("border: 1px dashed #333; background-color: #151515;"); self.rack_placed.emit()

    def dragEnterEvent(self, event):
        if "rack" in event.mimeData().text(): event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            data_obj = ast.literal_eval(event.mimeData().text())
            if isinstance(data_obj, dict) and data_obj.get('type') == 'rack':
                is_move = 'move_meta' in data_obj
                rack_data = data_obj['rack_data'] if is_move else data_obj
                rows_data, is_locked = data_obj.get('rows_data') if is_move else None, data_obj.get('is_locked', False)
                if self.add_rack(rack_data, initial_miners=rows_data, is_locked=is_locked):
                    if is_move:
                        parent_view = self.parent()
                        if parent_view and hasattr(parent_view, 'placeholders'):
                            src_idx = data_obj['move_meta']['from_placeholder_idx']
                            if 0 <= src_idx < len(parent_view.placeholders): parent_view.placeholders[src_idx].remove_rack(silent=True)
                    else:
                        if rack_data.get('source') == 'Personal': self.parent().item_placed.emit(rack_data)
        except: pass

class RoomView(QWidget):
    stats_changed = Signal()
    item_returned = Signal(dict)
    item_placed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    rack_swap_requested = Signal(object, QPoint)

    def __init__(self, room_id):
        super().__init__()
        self.room_id = room_id
        self.room_uuid = None
        self.placeholders = []
        self.init_ui()

    def init_ui(self):
        self.grid = QGridLayout(self); self.grid.setSpacing(10); self.grid.setContentsMargins(10, 10, 10, 10)
        count = ROOM_1_RACKS if self.room_id == 0 else ROOM_OTHER_RACKS
        cols = ROOM_1_COLS if self.room_id == 0 else ROOM_OTHER_COLS
        for i in range(count):
            row, col = divmod(i, cols); p = RackPlaceholder(i); p.rack_placed.connect(self.stats_changed.emit); p.item_removed.connect(self.item_returned.emit); p.rack_clicked.connect(self.rack_clicked.emit); p.miner_edit_requested.connect(self.miner_edit_requested.emit)
            p.rack_swap_requested.connect(self.rack_swap_requested.emit)
            self.grid.addWidget(p, row, col); self.placeholders.append(p)

    def handle_item_click(self, item_data):
        success = False
        if item_data['type'] == 'rack':
            for p in self.placeholders:
                if p.rack is None: 
                    if p.add_rack(item_data): success = True; break
        else:
            for p in self.placeholders:
                if p.rack and p.rack.add_miner(item_data): success = True; break
        if success and item_data.get('source') == 'Personal': self.item_placed.emit(item_data)

    def get_room_state(self):
        return {
            'room_uuid': self.room_uuid,
            'racks': [{
                'rack_data': p.rack.data,
                'rack_bonus': p.rack.data.get('bonus_val', 0), 
                'rows': p.rack.rows_data,
                'is_locked': p.rack.is_locked
            } for p in self.placeholders if p.rack]
        }

    def clear_room(self, only_miners=False):
        for p in self.placeholders:
            if p.rack:
                if only_miners: p.rack.clear_miners()
                else: p.remove_rack()
        self.stats_changed.emit()