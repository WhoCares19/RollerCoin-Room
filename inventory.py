import os
import json
import sqlite3
import shutil
import time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QComboBox, QLineEdit, QLabel, QListView, 
                               QStyledItemDelegate, QButtonGroup, QFileDialog, 
                               QMessageBox, QMenu, QApplication, QCheckBox, 
                               QFrame, QSizePolicy)
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QSize, QRect, Signal, QMimeData
from PySide6.QtGui import QPixmap, QColor, QFont, QPen, QPainter, QIcon, QAction, QDrag
from settings import (INVENTORY_ITEM_WIDTH, INVENTORY_ITEM_HEIGHT, LEVELS_DIR, CATALOG_DB_PATH)
from database import DatabaseHandler
from logic_math import format_hashrate, parse_hashrate_to_gh, parse_percentage_to_float
from importer import clean_and_parse_json, parse_personal_inventory
from ui_styles import resolve_path

class InventoryModel(QAbstractListModel):
    def __init__(self, data=None):
        super().__init__()
        self._items = data or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        if role == Qt.ItemDataRole.UserRole:
            return self._items[index.row()]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        self._items = new_data
        self.endResetModel()

class InventoryDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap_cache = {}

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole)
        if not data: return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(2, 2, -2, -2)
        
        painter.setBrush(QColor("#1a1a1a"))
        painter.setPen(QPen(QColor("#333333"), 1))
        painter.drawRoundedRect(rect, 4, 4)

        img_path = resolve_path(data.get('image_path', ''))
        if img_path and os.path.exists(img_path):
            pix = self.get_cached_pixmap(img_path)
            if not pix.isNull():
                target_w, target_h = rect.width() - 10, int(rect.height() * 0.6)
                target_rect = QRect(rect.left() + 5, rect.top() + 5, target_w, target_h)
                scaled_pix = pix.scaled(target_rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                x_off = (target_rect.width() - scaled_pix.width()) // 2
                y_off = (target_rect.height() - scaled_pix.height()) // 2
                painter.drawPixmap(target_rect.left() + x_off, target_rect.top() + y_off, scaled_pix)

        level_path = resolve_path(data.get('level_icon_path', ''))
        if level_path and os.path.exists(level_path):
            painter.drawPixmap(rect.left() + 2, rect.top() + 2, 20, 20, self.get_cached_pixmap(level_path))

        if data.get('source') == 'Personal':
            painter.setPen(QColor("#ffcc00"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(rect.adjusted(0, 5, -8, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, f"x{data.get('quantity', 0)}")

        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        name_rect = QRect(rect.left() + 5, rect.top() + int(rect.height() * 0.65), rect.width() - 10, 35)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, data.get('name', 'Unknown'))

        painter.setPen(QColor("#00ff00"))
        painter.setFont(QFont("Segoe UI", 8))
        stat_text = f"{format_hashrate(data.get('power_val', 0))} | {data.get('bonus_val', 0)}%" if data.get('type') == 'miner' else f"Bonus: {data.get('bonus_val', 0)}%"
        painter.drawText(QRect(rect.left() + 5, rect.bottom() - 20, rect.width() - 10, 15), Qt.AlignmentFlag.AlignCenter, stat_text)
        painter.restore()

    def get_cached_pixmap(self, path):
        p = resolve_path(path)
        if p not in self.pixmap_cache: self.pixmap_cache[p] = QPixmap(p)
        return self.pixmap_cache[p]

    def sizeHint(self, option, index): return QSize(INVENTORY_ITEM_WIDTH, INVENTORY_ITEM_HEIGHT)

class DraggableListView(QListView):
    itemClicked = Signal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None: return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance(): return
        index = self.indexAt(self.drag_start_pos)
        if index.isValid():
            drag = QDrag(self); mime = QMimeData(); mime.setText(str(index.data(Qt.ItemDataRole.UserRole)))
            drag.setMimeData(mime); self.drag_start_pos = None; drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            idx = self.indexAt(event.position().toPoint())
            if idx.isValid(): self.itemClicked.emit(idx.data(Qt.ItemDataRole.UserRole))
        self.drag_start_pos = None; super().mouseReleaseEvent(event)

class InventorySection(QWidget):
    edit_requested = Signal(dict)
    inventory_changed = Signal() 
    missing_items_found = Signal(list)
    auto_requested = Signal()
    advice_requested = Signal()

    def __init__(self):
        super().__init__()
        self.db = DatabaseHandler(); self.game_data, self.personal_data, self.tag_to_item_map, self.name_to_item_map = [], [], {}, {}
        self.placed_item_keys, self.set_names_map, self.item_spacing, self.inventory_is_valid, self.block_inventory_signals = set(), {}, 5, False, False
        self.setMinimumHeight(INVENTORY_ITEM_HEIGHT + 60); self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui(); self.preload_data_from_db()

    def mousePressEvent(self, event): self.setFocus(); super().mousePressEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        toolbar = QHBoxLayout(); toolbar.setContentsMargins(5, 5, 5, 0); toolbar.setSpacing(6)
        
        self.type_combo = QComboBox(); self.type_combo.addItems(["Miners", "Racks"]); self.type_combo.currentTextChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.type_combo)

        self.level_group = QButtonGroup(self)
        for i in range(1, 7):
            btn = QPushButton(); icon_path = resolve_path(os.path.join(LEVELS_DIR, f"lvl{i}.png"))
            if os.path.exists(icon_path): btn.setIcon(QIcon(icon_path)); btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(32, 32); btn.setCheckable(True)
            btn.setStyleSheet("QPushButton { background-color: #333; border: 1px solid #444; } QPushButton:checked { background-color: #555; border: 1px solid #00ff00; }")
            if i == 1: btn.setChecked(True)
            btn.clicked.connect(self.trigger_refresh); self.level_group.addButton(btn, i); toolbar.addWidget(btn)
        
        btn_all = QPushButton(""); btn_all.setFixedSize(32, 32); btn_all.setCheckable(True)
        btn_all.setStyleSheet("QPushButton { background-color: #333; border: 1px solid #444; } QPushButton:checked { background-color: #555; border: 1px solid #00ff00; }")
        btn_all.clicked.connect(self.trigger_refresh); self.level_group.addButton(btn_all, 0); toolbar.addWidget(btn_all)

        self.slot_combo = QComboBox(); self.slot_combo.addItems(["All", "1 slot", "2 slot"]); self.slot_combo.currentIndexChanged.connect(self.trigger_refresh); toolbar.addWidget(self.slot_combo)
        self.sort_combo = QComboBox(); self.sort_combo.addItems(["Power + Bonus", "Bonus + Power", "Newest First"]); self.sort_combo.currentTextChanged.connect(self.trigger_refresh); toolbar.addWidget(self.sort_combo)
        self.search_bar = QLineEdit(); self.search_bar.setPlaceholderText("Search..."); self.search_bar.setFixedWidth(150); self.search_bar.textChanged.connect(self.trigger_refresh); toolbar.addWidget(self.search_bar)
        toolbar.addWidget(QLabel("Bonus:")); self.bonus_from_edit = QLineEdit(); self.bonus_from_edit.setPlaceholderText("From"); self.bonus_from_edit.setFixedWidth(40); self.bonus_from_edit.textChanged.connect(self.trigger_refresh); toolbar.addWidget(self.bonus_from_edit)
        self.bonus_to_edit = QLineEdit(); self.bonus_to_edit.setPlaceholderText("To"); self.bonus_to_edit.setFixedWidth(40); self.bonus_to_edit.textChanged.connect(self.trigger_refresh); toolbar.addWidget(self.bonus_to_edit)
        self.hide_placed_cb = QCheckBox("Hide Placed Miners"); self.hide_placed_cb.stateChanged.connect(self.trigger_refresh); toolbar.addWidget(self.hide_placed_cb)
        
        self.auto_btn = QPushButton("Auto")
        self.auto_btn.clicked.connect(lambda: self.auto_requested.emit())
        toolbar.addWidget(self.auto_btn)

        self.advice_btn = QPushButton("Advice")
        self.advice_btn.clicked.connect(lambda: self.advice_requested.emit())
        toolbar.addWidget(self.advice_btn)
        
        toolbar.addStretch()
        self.source_combo = QComboBox(); self.source_combo.addItems(["Personal", "Game"]); self.source_combo.setCurrentText("Personal"); self.source_combo.currentTextChanged.connect(self.trigger_refresh); toolbar.addWidget(self.source_combo)
        layout.addLayout(toolbar)

        self.container_stack = QWidget(); self.stack_layout = QVBoxLayout(self.container_stack); self.stack_layout.setContentsMargins(0, 0, 0, 0); self.stack_layout.setSpacing(0)
        
        self.carousel_widget = QWidget(); carousel_layout = QHBoxLayout(self.carousel_widget); carousel_layout.setContentsMargins(5, 0, 5, 0); carousel_layout.setSpacing(10) 
        
        self.prev_btn = QPushButton("<"); self.prev_btn.setFixedSize(40, INVENTORY_ITEM_HEIGHT + 25); self.prev_btn.clicked.connect(self.scroll_prev); carousel_layout.addWidget(self.prev_btn)

        locked_width = (6 * INVENTORY_ITEM_WIDTH) + (5 * self.item_spacing) + 170
        self.view = DraggableListView(); self.view.setFlow(QListView.Flow.LeftToRight); self.view.setWrapping(False); self.view.setMovement(QListView.Movement.Static); self.view.setSpacing(self.item_spacing)
        self.view.setMinimumWidth(locked_width); self.view.setFixedHeight(INVENTORY_ITEM_HEIGHT + 25); self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.view.setStyleSheet("QListView { background: transparent; border: none; padding: 0px; margin: 0px; outline: none; }")
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.view.customContextMenuRequested.connect(self.on_context_menu)

        self.model = InventoryModel(); self.view.setModel(self.model); self.view.setItemDelegate(InventoryDelegate(self.view)); carousel_layout.addWidget(self.view)
        
        self.next_btn = QPushButton(">"); self.next_btn.setFixedSize(40, INVENTORY_ITEM_HEIGHT + 25); self.next_btn.clicked.connect(self.scroll_next); carousel_layout.addWidget(self.next_btn)
        
        self.stack_layout.addWidget(self.carousel_widget)

        self.import_btn = QPushButton("Import Personal Inventory"); self.import_btn.setFixedHeight(INVENTORY_ITEM_HEIGHT); self.import_btn.setStyleSheet("font-weight: bold; font-size: 16px; border: 2px dashed #444;"); self.import_btn.clicked.connect(self.on_import_clicked); self.import_btn.hide()
        self.stack_layout.addWidget(self.import_btn); layout.addWidget(self.container_stack)

    def on_context_menu(self, pos):
        idx = self.view.indexAt(pos)
        if not idx.isValid(): return
        data = idx.data(Qt.ItemDataRole.UserRole); menu = QMenu(self)
        if data.get('type') == 'miner':
            e_act = QAction("Edit Miner Data", self); e_act.triggered.connect(lambda: self.edit_requested.emit(data)); menu.addAction(e_act)
        if data.get('source') == 'Personal':
            d_act = QAction("Delete from inventory", self); d_act.triggered.connect(lambda: self.delete_personal_item(data)); menu.addAction(d_act)
        else:
            c_act = QAction("Send to personal inventory", self); c_act.triggered.connect(lambda: self.copy_to_personal(data)); menu.addAction(c_act)
        menu.exec(self.view.mapToGlobal(pos))

    def copy_to_personal(self, data): self.adjust_quantity(data, 1)

    def delete_personal_item(self, data):
        tn, tl, tt = data.get('name'), data.get('lvl'), data.get('type')
        self.personal_data = [i for i in self.personal_data if not (i.get('name') == tn and i.get('lvl') == tl and i.get('type') == tt)]
        self.trigger_refresh()
        if not self.block_inventory_signals: self.inventory_changed.emit()

    def preload_data_from_db(self):
        self.game_data, self.tag_to_item_map, self.name_to_item_map = [], {}, {}
        if os.path.exists(CATALOG_DB_PATH):
            conn = sqlite3.connect(CATALOG_DB_PATH); cursor = conn.cursor(); cursor.execute("SELECT set_global_id, name FROM set_definitions")
            self.set_names_map = {row[0]: row[1] for row in cursor.fetchall()}; conn.close()
        for lvl in range(0, 7):
            for d in self.db.get_catalog_miners(lvl):
                item = {'id': d[0], 'name': d[1], 'image_path': d[2], 'slot_size': d[3], 'set_global_id': d[4], 'set_sign_icon_path': d[5], 'power_val': parse_hashrate_to_gh(d[6]), 'bonus_val': parse_percentage_to_float(d[7]), 'level_icon_path': d[8], 'mls_id': d[9], 'level_id_tag': d[10], 'lvl': lvl, 'type': 'miner', 'source': 'Game', 'timestamp': 0, 'is_legacy_item': (lvl == 0)}
                self.game_data.append(item)
                if d[10]: self.tag_to_item_map[str(d[10]).lower().strip()] = item
                self.name_to_item_map[(str(d[1]).lower().strip(), lvl)] = item
        for d in self.db.get_catalog_racks():
            item = {'id': d[0], 'name': d[1], 'rack_id_tag': d[2], 'set_global_id': d[3], 'rack_size': d[4], 'bonus_val': parse_percentage_to_float(d[5]), 'image_path': d[6], 'set_sign_icon_path': d[7], 'type': 'rack', 'source': 'Game', 'timestamp': 0}
            self.game_data.append(item)
            if d[2]: self.tag_to_item_map[str(d[2]).lower().strip()] = item
            self.name_to_item_map[str(d[1]).lower().strip()] = item
        self.trigger_refresh()

    def on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personal Items", "", "JSON Files (*.json)")
        if path: self.load_inventory_file(path)

    def load_inventory_file(self, path, splash=None):
        if not path or not os.path.exists(path): return
        jc = clean_and_parse_json(path)
        if jc:
            raw = parse_personal_inventory(jc)
            if raw: self.add_items_by_tags(raw, splash=splash)

    def add_items_by_tags(self, items_list, splash=None):
        self.inventory_is_valid = True; self.personal_data, missing = [], []
        total = len(items_list)
        for i, entry in enumerate(items_list):
            if splash:
                # Inventory contributes up to 40% of the bar during initial load
                progress = int((i / max(1, total)) * 40)
                splash.update_progress(progress, f"Parsing Inventory: {entry.get('name', 'Miner')}")
            
            mid = str(entry['miner_id']).lower().strip(); qty = entry['quantity']
            if mid in self.tag_to_item_map:
                base = self.tag_to_item_map[mid]; found = False
                for pi in self.personal_data:
                    ptag = pi.get('level_id_tag') if pi.get('type') == 'miner' else pi.get('rack_id_tag')
                    if ptag and str(ptag).lower().strip() == mid:
                        pi['quantity'] += qty; found = True; break
                if not found:
                    ni = base.copy(); ni.update({'quantity': qty, 'source': 'Personal', 'timestamp': time.time()}); self.personal_data.append(ni)
            else: missing.append(str(entry.get('name', mid)))
        if missing: self.missing_items_found.emit(missing)
        self.trigger_refresh()
        if not self.block_inventory_signals: self.inventory_changed.emit()
        return missing

    def save_personal_inventory(self, path):
        if not path: return
        out = []
        for i in self.personal_data:
            tag = i.get("level_id_tag") if i.get("type") == "miner" else i.get("rack_id_tag")
            if tag:
                lvl = 0 if i.get("is_legacy_item") else (i.get("lvl", 1) - 1)
                out.append({"name": i.get("name"), "level": lvl, "miner_id": str(tag).lower(), "quantity": i.get("quantity", 0)})
        try:
            with open(path, 'w', encoding='utf-8') as f: json.dump({"success": True, "data": {"items": out}, "error": ""}, f, indent=4)
        except: pass

    def adjust_quantity(self, data, delta):
        tn, tl, tt, found = data.get('name'), data.get('lvl'), data.get('type'), False
        for i in self.personal_data:
            if (i.get('name') == tn and i.get('lvl') == tl and i.get('type') == tt):
                i['quantity'] = max(0, i['quantity'] + delta); i['timestamp'] = time.time() if delta > 0 else i['timestamp']; found = True; break
        if not found and delta > 0 and self.inventory_is_valid:
            ni = data.copy(); ni.update({'source': 'Personal', 'quantity': delta, 'timestamp': time.time()}); self.personal_data.append(ni)
        self.trigger_refresh()
        if not self.block_inventory_signals: self.inventory_changed.emit()

    def set_placed_items(self, ids_set): self.placed_item_keys = {idv.lower().strip() for idv in ids_set if idv}; self.trigger_refresh()

    def trigger_refresh(self):
        src = self.source_combo.currentText(); is_p = (src == "Personal")
        self.import_btn.setVisible(is_p and not self.personal_data); self.carousel_widget.setVisible(not (is_p and not self.personal_data))
        itype = "rack" if self.type_combo.currentText() == "Racks" else "miner"
        q, lvl, slots, smode = self.search_bar.text().lower().strip(), self.level_group.checkedId(), self.slot_combo.currentText(), self.sort_combo.currentText()
        try: mn_b = float(self.bonus_from_edit.text()) if self.bonus_from_edit.text() else -1.0
        except: mn_b = -1.0
        try: mx_b = float(self.bonus_to_edit.text()) if self.bonus_to_edit.text() else 99999.0
        except: mx_b = 99999.0
        filtered = []
        for i in (self.personal_data if is_p else self.game_data):
            if (is_p and i.get('quantity', 0) <= 0) or i['type'] != itype: continue
            if is_p and itype == 'miner' and self.hide_placed_cb.isChecked() and (i.get('level_id_tag') or '').lower() in self.placed_item_keys: continue
            if mn_b != -1.0 and i.get('bonus_val', 0.0) < mn_b: continue
            if mx_b != 99999.0 and i.get('bonus_val', 0.0) > mx_b: continue
            sn = self.set_names_map.get(i.get('set_global_id'), '').lower().replace('_', ' ')
            if itype == "miner" and not q and lvl != 0 and i.get('lvl') != lvl: continue
            if itype == "miner" and slots != "All" and int(i.get('slot_size', 1)) != (1 if slots == "1 slot" else 2): continue
            if q and not (q in i['name'].lower() or q in sn): continue
            filtered.append(i)
        if smode == "Power + Bonus": filtered.sort(key=lambda x: (x.get('power_val', 0), x.get('bonus_val', 0)), reverse=True)
        elif smode == "Bonus + Power": filtered.sort(key=lambda x: (x.get('bonus_val', 0), x.get('power_val', 0)), reverse=True)
        elif smode == "Newest First": filtered.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        self.model.update_data(filtered)

    def scroll_next(self): self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() + (6 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))
    def scroll_prev(self): self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - (6 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))