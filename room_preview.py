import os
import ast
import json
import random
from PySide6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, 
                               QLabel, QMenu, QFrame, QSizePolicy, QApplication)
from PySide6.QtCore import Qt, Signal, QRect, QMimeData, QPoint, QSize, QTimer
from PySide6.QtGui import QPixmap, QAction, QImage, QPainter, QDrag, QColor, QMovie, QImageReader
from settings import (ROOM_1_RACKS, ROOM_OTHER_RACKS, ROOM_1_COLS, ROOM_OTHER_COLS, 
                      RACK_JSON_PATH)
from logic_math import format_hashrate
from ui_styles import resolve_path
from hamsters import Hamster

BASE_SLOT_W = 100
BASE_SLOT_H = 140

GLOBAL_PIXMAP_CACHE = {}

def get_cached_pixmap(path, w, h, mode=Qt.AspectRatioMode.KeepAspectRatio):
    cache_key = (path, w, h, mode)
    if cache_key in GLOBAL_PIXMAP_CACHE:
        return GLOBAL_PIXMAP_CACHE[cache_key]
    
    if not os.path.exists(path):
        return QPixmap()

    pix = QPixmap()
    if path.lower().endswith(".gif"):
        reader = QImageReader(path)
        if reader.canRead():
            reader.setScaledSize(QSize(w, h))
            img = reader.read()
            if not img.isNull():
                pix = QPixmap.fromImage(img)
    else:
        raw_pix = QPixmap(path)
        if not raw_pix.isNull():
            pix = raw_pix.scaled(w, h, mode, Qt.TransformationMode.SmoothTransformation)

    if not pix.isNull():
        GLOBAL_PIXMAP_CACHE[cache_key] = pix
    return pix

class MinerInRack(QFrame):
    removed = Signal(int, int)
    edit_requested = Signal(dict)

    def __init__(self, miner_data, rect, row, slot, scale, slot_template=None, animations_enabled=True):
        super().__init__()
        self.data = miner_data
        self.row_idx = row
        self.slot_idx = slot
        self.scale = scale
        self.slot_template = slot_template or {}
        self.drag_start_pos = None
        self.movie = None
        self._animations_active = animations_enabled
        self.img_label = None
        
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents)
        self.setGeometry(rect)
        self.setStyleSheet("background: transparent; border: none;")
        self.update_image()

        icon_path = resolve_path(self.data.get('level_icon_path', ''))
        if icon_path and os.path.exists(icon_path):
            icon_scale = self.data.get('img_scale', 1.0)
            icon_size = int(12 * icon_scale * self.scale)
            pix_icon = get_cached_pixmap(icon_path, icon_size, icon_size)
            
            self.corner_label = QLabel(self)
            self.corner_label.setPixmap(pix_icon)
            self.corner_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            
            if 'set_icon' in self.slot_template:
                icon_tmpl = self.slot_template['set_icon']
                self.corner_label.move(int(icon_tmpl['x'] * self.scale), int(icon_tmpl['y'] * self.scale))
                self.corner_label.setFixedSize(int(icon_tmpl['w'] * self.scale), int(icon_tmpl['h'] * self.scale))
            else:
                self.corner_label.move(2, 2)
                self.corner_label.setFixedSize(icon_size, icon_size)
            self.corner_label.show()
            self.corner_label.raise_()

    def update_image(self):
        if self.img_label:
            self.img_label.deleteLater()
        
        self.img_label = QLabel(self)
        self.img_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        path = resolve_path(self.data.get('image_path', ''))
        img_scale_attr = self.data.get('img_scale', 0.5)
        total_scale = img_scale_attr * self.scale
        rect = self.geometry()

        if not os.path.exists(path):
            return

        reader = QImageReader(path)
        orig_size = reader.size()
        sw, sh = int(orig_size.width() * total_scale), int(orig_size.height() * total_scale)
        is_gif = path.lower().endswith(".gif")
        
        if is_gif and self._animations_active:
            self.movie = QMovie(path)
            self.movie.setScaledSize(QSize(sw, sh))
            self.img_label.setMovie(self.movie)
            dx = (rect.width() - sw) // 2
            dy = (rect.height() - sh) // 2
            self.img_label.setGeometry(dx, dy, sw, sh)
            self.movie.start()
        else:
            if self.movie:
                self.movie.stop()
                self.movie = None
            self.img_label.setPixmap(get_cached_pixmap(path, sw, sh))
            dx = (rect.width() - sw) // 2
            dy = (rect.height() - sh) // 2
            self.img_label.setGeometry(dx, dy, sw, sh)
        
        self.img_label.show()

    def set_animations_enabled(self, active):
        if self._animations_active != active:
            self._animations_active = active
            self.update_image()

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
            menu.addAction(remove_act); menu.addAction(edit_act)
            menu.exec(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        rack = self.parent()
        if rack and hasattr(rack, 'is_locked') and rack.is_locked: return
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None: return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime = QMimeData()
        move_info = {'type': 'miner', 'miner_data': self.data, 'move_meta': {'from_rack_id': id(self.parent()), 'from_row': self.row_idx, 'from_slot': self.slot_idx}}
        mime.setText(str(move_info)); drag.setMimeData(mime); self.drag_start_pos = None; drag.exec(Qt.DropAction.MoveAction)

class RackWidget(QFrame):
    removed = Signal(dict) 
    miner_removed = Signal(dict)
    miner_added = Signal()
    clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    swap_requested = Signal(object, QPoint)

    def __init__(self, rack_data, scale, is_locked=False, animations_enabled=True):
        super().__init__()
        self.data = rack_data
        self.scale = scale
        self.is_locked = is_locked
        self.drag_start_pos = None
        self.is_drag_active = False
        self.drag_miner_size = 1
        self.rack_movie = None
        self.rack_img = None
        self._animations_active = animations_enabled 
        
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents)
        self.setStyleSheet("background: transparent; border: none;")
        template_root = self.load_template_root()
        self.metadata = template_root.get('metadata', {}) if template_root else {}
        racks_list = template_root.get('racks', []) if template_root else []
        self.template = racks_list[0] if racks_list else None
        self.row_count = len(self.template.get('2 slot', [])) if self.template else 0
        self.rows_data = [None] * self.row_count
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setFixedSize(int(BASE_SLOT_W * self.scale), int(BASE_SLOT_H * self.scale))
        self.update_rack_image()

    def load_template_root(self):
        try:
            if not os.path.exists(RACK_JSON_PATH): return None
            with open(RACK_JSON_PATH, 'r') as f: templates = json.load(f)
            size_attr = str(self.data.get('rack_size', '')).lower()
            name_attr = str(self.data.get('name', '')).lower()
            target_key = None
            if "big" in size_attr: target_key = "Big Rack"
            elif "small" in size_attr: target_key = "Small Rack"
            if not target_key:
                if "rack 8" in name_attr: target_key = "Big Rack"
                elif "rack 6" in name_attr: target_key = "Small Rack"
            if not target_key and templates: return list(templates.values())[0]
            return templates.get(target_key)
        except: return None

    def update_rack_image(self):
        if self.rack_img:
            self.rack_img.deleteLater()
            
        if not self.template:
            return

        self.rack_img = QLabel(self)
        self.rack_img.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        path = resolve_path(self.data.get('image_path', ''))
        if not os.path.exists(path):
            return

        img_scale_attr = self.metadata.get('img_scale', 1.0)
        total_scale = img_scale_attr * self.scale
        is_gif = path.lower().endswith(".gif")

        reader = QImageReader(path)
        orig_size = reader.size()
        sw, sh = int(orig_size.width() * total_scale), int(orig_size.height() * total_scale)

        if is_gif and self._animations_active:
            self.rack_movie = QMovie(path)
            self.rack_movie.setScaledSize(QSize(sw, sh))
            self.rack_img.setMovie(self.rack_movie)
            rack_img_offset_y = int(BASE_SLOT_H * self.scale) - sh
            self.rack_img.setGeometry(int(self.template['x'] * self.scale), int(rack_img_offset_y), sw, sh)
            self.rack_movie.start()
        else:
            if self.rack_movie:
                self.rack_movie.stop()
                self.rack_movie = None
            self.rack_img.setPixmap(get_cached_pixmap(path, sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio))
            rack_img_offset_y = int(BASE_SLOT_H * self.scale) - sh
            self.rack_img.setGeometry(int(self.template['x'] * self.scale), int(rack_img_offset_y), sw, sh)
            
        self.rack_img.show()
        self.rack_img.lower()

    def set_animations_enabled(self, active):
        if self._animations_active != active:
            self._animations_active = active
            self.update_rack_image()
            self.refresh_ui()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.is_drag_active or not self.template: return
        painter = QPainter(self); highlight_color = QColor(0, 255, 0, 50); painter.setBrush(highlight_color); painter.setPen(Qt.NoPen)
        rx, ry = int(self.template['x'] * self.scale), 0 
        for r_idx, row_tmpl in enumerate(self.template['2 slot']):
            row_state = self.rows_data[r_idx]
            if self.drag_miner_size == 2:
                if row_state is None: 
                    painter.drawRoundedRect(rx + int(row_tmpl['x'] * self.scale), 
                                          ry + int(row_tmpl['y'] * self.scale), 
                                          int(row_tmpl['w'] * self.scale), 
                                          int(row_tmpl['h'] * self.scale), 3, 3)
            else:
                for s_idx, slot_tmpl in enumerate(row_tmpl['1 slot']):
                    empty = (row_state is None or (isinstance(row_state, list) and row_state[s_idx] is None))
                    if empty: 
                        painter.drawRoundedRect(rx + int(row_tmpl['x'] * self.scale) + int(slot_tmpl['x'] * self.scale), 
                                              ry + int(row_tmpl['y'] * self.scale) + int(slot_tmpl['y'] * self.scale), 
                                              int(slot_tmpl['w'] * self.scale), 
                                              int(slot_tmpl['h'] * self.scale), 2, 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_locked: return
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None: return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime = QMimeData()
        move_info = {'type': 'rack', 'rack_data': self.data, 'rows_data': self.rows_data, 'is_locked': self.is_locked, 'move_meta': {'from_placeholder_idx': self.parent().index if hasattr(self.parent(), 'index') else -1}}
        mime.setText(str(move_info)); drag.setMimeData(mime); self.drag_start_pos = None; drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance(): self.clicked.emit(self.data, self.rows_data)
        self.drag_start_pos = None; super().mouseReleaseEvent(event)

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
            curr = self.rows_data[row]
            if curr is not None:
                if miner_size == 2 or isinstance(curr, dict) or (isinstance(curr, list) and curr[slot] is not None): return False
            if miner_size == 2: self.rows_data[row] = miner_data
            else:
                if self.rows_data[row] is None: self.rows_data[row] = [None] * len(self.template['2 slot'][row]['1 slot'])
                self.rows_data[row][slot] = miner_data
            self.refresh_ui(); self.miner_added.emit(); return True
        return False

    def remove_miner(self, row_idx, slot_idx, silent=False):
        if self.is_locked: return
        for child in self.findChildren(MinerInRack):
            if child.row_idx == row_idx and child.slot_idx == slot_idx:
                child.hide()
        row_state = self.rows_data[row_idx]; miner_to_return = None
        if isinstance(row_state, dict): miner_to_return = row_state; self.rows_data[row_idx] = None
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
        rx, ry = int(self.template['x'] * self.scale), 0 
        for r_idx, row_state in enumerate(self.rows_data):
            if row_state is None: continue
            row_tmpl = self.template['2 slot'][r_idx]
            if isinstance(row_state, dict):
                fx, fy = rx + int(row_tmpl['x'] * self.scale), ry + int(row_tmpl['y'] * self.scale)
                m = MinerInRack(row_state, QRect(fx, fy, int(row_tmpl['w'] * self.scale), int(row_tmpl['h'] * self.scale)), 
                               r_idx, 0, self.scale, slot_template=row_tmpl, animations_enabled=self._animations_active)
                m.setParent(self)
                m.removed.connect(self.remove_miner)
                m.edit_requested.connect(self.miner_edit_requested.emit)
                m.show()
            elif isinstance(row_state, list):
                for s_idx, miner in enumerate(row_state):
                    if isinstance(miner, dict):
                        slot_tmpl = row_tmpl['1 slot'][s_idx]
                        fx, fy = rx + int(row_tmpl['x'] * self.scale) + int(slot_tmpl['x'] * self.scale), \
                                ry + int(row_tmpl['y'] * self.scale) + int(slot_tmpl['y'] * self.scale)
                        m = MinerInRack(miner, QRect(fx, fy, int(slot_tmpl['w'] * self.scale), int(slot_tmpl['h'] * self.scale)), 
                                       r_idx, s_idx, self.scale, slot_template=slot_tmpl, animations_enabled=self._animations_active)
                        m.setParent(self)
                        m.removed.connect(self.remove_miner)
                        m.edit_requested.connect(self.miner_edit_requested.emit)
                        m.show()

    def show_context_menu(self, pos):
        menu = QMenu(self); swap_act = QAction("Swap Rack", self); swap_act.triggered.connect(lambda: self.swap_requested.emit(self, self.mapToGlobal(pos))); swap_act.setEnabled(not self.is_locked); menu.addAction(swap_act); empty_act = QAction("Empty the rack", self); empty_act.triggered.connect(self.clear_miners); empty_act.setEnabled(not self.is_locked); menu.addAction(empty_act); del_act = QAction("Remove Rack", self); del_act.triggered.connect(lambda: self.removed.emit(self.data)); del_act.setEnabled(not self.is_locked); menu.addAction(del_act); menu.exec(self.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        try:
            data = ast.literal_eval(event.mimeData().text()); miner_obj = data.get('miner_data', data) if isinstance(data, dict) else data
            if isinstance(miner_obj, dict) and miner_obj.get('type') == 'miner': self.is_drag_active = True; self.drag_miner_size = int(miner_obj.get('slot_size', 1)); self.update(); event.acceptProposedAction()
            elif "rack" in event.mimeData().text(): event.acceptProposedAction()
        except: pass

    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dragLeaveEvent(self, event): self.is_drag_active = False; self.update(); super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.is_drag_active = False; self.update()
        try:
            data_obj = ast.literal_eval(event.mimeData().text())
            if isinstance(data_obj, dict) and (data_obj.get('type') == 'miner' or 'miner_data' in data_obj):
                is_move = 'move_meta' in data_obj; miner_data = data_obj['miner_data'] if is_move else data_obj
                pos, target_row, target_slot, rx = event.position(), -1, 0, int((self.template['x'] if self.template else 0) * self.scale)
                if self.template and '2 slot' in self.template:
                    for r_idx, row_tmpl in enumerate(self.template['2 slot']):
                        scaled_ry = int(row_tmpl['y'] * self.scale)
                        scaled_rh = int(row_tmpl['h'] * self.scale)
                        if scaled_ry <= pos.y() <= (scaled_ry + scaled_rh):
                            target_row = r_idx
                            if int(miner_data.get('slot_size', 1)) == 1:
                                for s_idx, slot_tmpl in enumerate(row_tmpl['1 slot']):
                                    sx_start = rx + int(row_tmpl['x'] * self.scale) + int(slot_tmpl['x'] * self.scale)
                                    sw = int(slot_tmpl['w'] * self.scale)
                                    if sx_start <= pos.x() <= (sx_start + sw): target_slot = s_idx; break
                            break
                if target_row == -1: target_row, target_slot = self.can_fit(miner_data)
                if target_row != -1 and self.add_miner(miner_data, target_row, target_slot):
                    if is_move:
                        if data_obj['move_meta']['from_rack_id'] == id(self):
                            if not (data_obj['move_meta']['from_row'] == target_row and data_obj['move_meta']['from_slot'] == target_slot): self.remove_miner(data_obj['move_meta']['from_row'], data_obj['move_meta']['from_slot'], silent=True)
                        else:
                            source_rack = next((r.rack for r in self.window().findChildren(RackPlaceholder) if r.rack and id(r.rack) == data_obj['move_meta']['from_rack_id']), None)
                            if source_rack: source_rack.remove_miner(data_obj['move_meta']['from_row'], data_obj['move_meta']['from_slot'], silent=True)
                    elif miner_data.get('source') == 'Personal':
                        parent_view = self.parent().parent()
                        if hasattr(parent_view, 'item_placed'): parent_view.item_placed.emit(miner_data)
        except: pass

class RackPlaceholder(QFrame):
    rack_placed = Signal()
    item_removed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    rack_swap_requested = Signal(object, QPoint)

    def __init__(self, index, scale):
        super().__init__()
        self.index = index
        self.scale = scale
        self.rack = None
        self.setFixedSize(int(BASE_SLOT_W * self.scale), int(BASE_SLOT_H * self.scale))
        self.setAcceptDrops(True)
        self.setStyleSheet("border: 1px dashed #333; background-color: transparent; border-radius: 2px;")
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("Empty"); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #444; font-size: 8px;"); layout.addWidget(self.label)

    def add_rack(self, rack_data, initial_miners=None, is_locked=False):
        if self.rack: return False
        anim_enabled = True
        parent_view = self.parent()
        if isinstance(parent_view, RoomView): anim_enabled = parent_view._animations_enabled
        self.label.hide(); self.rack = RackWidget(rack_data, self.scale, is_locked=is_locked, animations_enabled=anim_enabled)
        self.layout().addWidget(self.rack); self.setStyleSheet("border: none; background: transparent;")
        self.rack.removed.connect(self.remove_rack); self.rack.miner_removed.connect(self.item_removed.emit); self.rack.miner_added.connect(self.rack_placed.emit); self.rack.clicked.connect(self.rack_clicked.emit); self.rack.miner_edit_requested.connect(self.miner_edit_requested.emit); self.rack.swap_requested.connect(self.rack_swap_requested.emit)
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
            self.rack.hide()
            self.rack.clear_miners(silent=silent); data = rack_data if rack_data else self.rack.data
            if not silent: self.item_removed.emit(data)
            self.layout().removeWidget(self.rack); self.rack.deleteLater(); self.rack = None; self.label.show(); self.setStyleSheet("border: 1px dashed #333; background-color: transparent;"); self.rack_placed.emit()

    def set_animations_enabled(self, active):
        if self.rack: self.rack.set_animations_enabled(active)

    def dragEnterEvent(self, event):
        if "rack" in event.mimeData().text(): event.acceptProposedAction()

    def dropEvent(self, event):
        try:
            data_obj = ast.literal_eval(event.mimeData().text())
            if isinstance(data_obj, dict) and data_obj.get('type') == 'rack':
                is_move = 'move_meta' in data_obj; rack_data = data_obj['rack_data'] if is_move else data_obj
                rows_data, is_locked = data_obj.get('rows_data') if is_move else None, data_obj.get('is_locked', False)
                if self.add_rack(rack_data, initial_miners=rows_data, is_locked=is_locked):
                    if is_move:
                        src_idx = data_obj['move_meta']['from_placeholder_idx']
                        if 0 <= src_idx < len(self.parent().placeholders): self.parent().placeholders[src_idx].remove_rack(silent=True)
                    elif rack_data.get('source') == 'Personal': self.parent().item_placed.emit(rack_data)
        except: pass

class RoomView(QWidget):
    stats_changed = Signal()
    item_returned = Signal(dict)
    item_placed = Signal(dict)
    rack_clicked = Signal(dict, list)
    miner_edit_requested = Signal(dict)
    rack_swap_requested = Signal(object, QPoint)

    def __init__(self, room_id, scale, bg_path="", hamsters_paused=False):
        super().__init__()
        self.room_id = room_id
        self.room_uuid = None
        self.scale = scale
        self.placeholders = []
        self._animations_enabled = True
        self.bg_pixmap = QPixmap()
        if bg_path and os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path)
        self.init_ui()
        
        # Instantiate Dusty the Hamster (Scaled to 100x100)
        self.dusty = Hamster(self, display_size=65, paused=hamsters_paused)
        # Place him randomly within Room boundaries
        QTimer.singleShot(100, self.randomize_hamster)

    def randomize_hamster(self):
        max_x = self.width() - self.dusty.width()
        max_y = self.height() - self.dusty.height()
        if max_x > 0 and max_y > 0:
            rx = random.randint(0, max_x)
            ry = random.randint(0, max_y)
            self.dusty.move(rx, ry)
            self.dusty.raise_()

    def init_ui(self):
        self.grid = QGridLayout(self); self.grid.setSpacing(10); self.grid.setContentsMargins(10, 10, 10, 10)
        
        # Room 1 Specific lowering logic
        if self.room_id == 0:
            self.grid.setRowStretch(0, 1)

        count = ROOM_1_RACKS if self.room_id == 0 else ROOM_OTHER_RACKS
        for i in range(count):
            p = RackPlaceholder(i, self.scale)
            p.rack_placed.connect(self.stats_changed.emit); p.item_removed.connect(self.item_returned.emit)
            p.rack_clicked.connect(self.rack_clicked.emit); p.miner_edit_requested.connect(self.miner_edit_requested.emit)
            p.rack_swap_requested.connect(self.rack_swap_requested.emit)
            
            # Manual Alignment logic based on 8-column centering
            if self.room_id == 0:
                if i < 8: row, col = 1, i
                else: row, col = 2, (i - 8) + 2 # Centered Row 2 (4 items)
            else:
                if i < 4: row, col = 0, i + 2    # Centered Row 1 (4 items)
                elif i < 12: row, col = 1, i - 4 # Full Row 2 (8 items)
                else: row, col = 2, (i - 12) + 1 # Centered Row 3 (6 items)
            
            self.grid.addWidget(p, row, col)
            self.placeholders.append(p)

    def update_background(self, bg_path):
        if bg_path and os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path)
        else:
            self.bg_pixmap = QPixmap()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self.bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.bg_pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#121212"))
        super().paintEvent(event)

    def set_animations_enabled(self, active):
        self._animations_enabled = active
        for p in self.placeholders: p.set_animations_enabled(active)

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
        return {'room_uuid': self.room_uuid, 'racks': [{'rack_data': p.rack.data, 'rack_bonus': p.rack.data.get('bonus_val', 0), 'rows': p.rack.rows_data, 'is_locked': p.rack.is_locked} for p in self.placeholders if p.rack]}

    def clear_room(self, only_miners=False, silent=False):
        for p in self.placeholders:
            if p.rack:
                if only_miners: p.rack.clear_miners(silent=silent)
                else: p.remove_rack(silent=silent)
        self.stats_changed.emit()