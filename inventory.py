import os
import json
import sqlite3
import shutil
import time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QComboBox, QLineEdit, QLabel, QListView, 
                               QStyledItemDelegate, QStyle, QButtonGroup, QFileDialog, 
                               QMessageBox, QMenu, QApplication, QCheckBox)
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QSize, QRect, Signal, QMimeData, QPoint
from PySide6.QtGui import QPixmap, QColor, QFont, QPen, QPainter, QIcon, QAction, QDrag
from settings import (INVENTORY_ITEM_WIDTH, INVENTORY_ITEM_HEIGHT, LEVELS_DIR, CATALOG_DB_PATH)
from database import DatabaseHandler
from logic_math import format_hashrate, parse_hashrate_to_gh, parse_percentage_to_float

def resolve_path(path):
    if not path:
        return ""
    clean_p = path.replace("\\", "/")
    parts = clean_p.split("/")
    if "assets" in parts:
        return os.path.join(*parts[parts.index("assets"):])
    return path

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
        if not data: 
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(2, 2, -2, -2)
        bg_color = QColor("#1a1a1a")
        border_color = QColor("#333333")
        
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 4, 4)

        img_path = resolve_path(data.get('image_path', ''))
        if img_path and os.path.exists(img_path):
            pix = self.get_cached_pixmap(img_path)
            if not pix.isNull():
                img_h = int(rect.height() * 0.6)
                img_rect = QRect(rect.left() + 5, rect.top() + 5, rect.width() - 10, img_h)
                painter.drawPixmap(img_rect, pix.scaled(img_rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        level_path = resolve_path(data.get('level_icon_path', ''))
        if level_path and os.path.exists(level_path):
            level_pix = self.get_cached_pixmap(level_path)
            icon_size = 20
            painter.drawPixmap(rect.left() + 2, rect.top() + 2, icon_size, icon_size, level_pix)

        if data.get('source') == 'Personal':
            qty = data.get('quantity', 0)
            painter.setPen(QColor("#ffcc00"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(rect.adjusted(0, 5, -8, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, f"x{qty}")

        painter.setPen(QColor("white"))
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        name_y = rect.top() + int(rect.height() * 0.65)
        name_rect = QRect(rect.left() + 5, name_y, rect.width() - 10, 35)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, data.get('name', 'Unknown'))

        painter.setPen(QColor("#00ff00"))
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        
        if data.get('type') == 'miner':
            stat_text = f"{format_hashrate(data.get('power_val', 0))} | {data.get('bonus_val', 0)}%"
        else:
            stat_text = f"Bonus: {data.get('bonus_val', 0)}%"
            
        stat_rect = QRect(rect.left() + 5, rect.bottom() - 20, rect.width() - 10, 15)
        painter.drawText(stat_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, stat_text)
        
        painter.restore()

    def get_cached_pixmap(self, path):
        path = resolve_path(path)
        if path not in self.pixmap_cache: 
            self.pixmap_cache[path] = QPixmap(path)
        return self.pixmap_cache[path]

    def sizeHint(self, option, index):
        return QSize(INVENTORY_ITEM_WIDTH, INVENTORY_ITEM_HEIGHT)

class DraggableListView(QListView):
    itemClicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None:
            return
        
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        index = self.indexAt(self.drag_start_pos)
        if index.isValid():
            data = index.data(Qt.ItemDataRole.UserRole)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(data))
            drag.setMimeData(mime)
            self.drag_start_pos = None
            drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                data = index.data(Qt.ItemDataRole.UserRole)
                self.itemClicked.emit(data)
            self.drag_start_pos = None
        super().mouseReleaseEvent(event)

class InventorySection(QWidget):
    edit_requested = Signal(dict)
    inventory_changed = Signal() 

    def __init__(self):
        super().__init__()
        self.db = DatabaseHandler()
        self.game_data = []
        self.personal_data = []
        self.tag_to_item_map = {}
        self.placed_item_keys = set()
        self.set_names_map = {} 
        self.item_spacing = 5
        self.inventory_is_valid = False 
        self.block_inventory_signals = False 
        
        self.setMinimumHeight(INVENTORY_ITEM_HEIGHT + 100)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.init_ui()
        self.preload_data_from_db()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)

        toolbar = QHBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Miners", "Racks"])
        self.type_combo.currentTextChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.type_combo)

        self.level_group = QButtonGroup(self)
        for i in range(1, 7):
            btn = QPushButton()
            icon_path = resolve_path(os.path.join(LEVELS_DIR, f"lvl{i}.png"))
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(32, 32)
            btn.setCheckable(True)
            btn.setStyleSheet("QPushButton { background-color: #333; border: 1px solid #444; } QPushButton:checked { background-color: #555; border: 1px solid #00ff00; }")
            if i == 1: btn.setChecked(True)
            btn.clicked.connect(self.trigger_refresh)
            self.level_group.addButton(btn, i)
            toolbar.addWidget(btn)
        
        btn_all = QPushButton("")
        btn_all.setFixedSize(32, 32)
        btn_all.setCheckable(True)
        btn_all.setStyleSheet("QPushButton { background-color: #333; border: 1px solid #444; } QPushButton:checked { background-color: #555; border: 1px solid #00ff00; }")
        btn_all.clicked.connect(self.trigger_refresh)
        self.level_group.addButton(btn_all, 0)
        toolbar.addWidget(btn_all)

        self.slot_combo = QComboBox()
        self.slot_combo.addItems(["All", "1 slot", "2 slot"])
        self.slot_combo.currentIndexChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.slot_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Power + Bonus", "Bonus + Power", "Newest First"])
        self.sort_combo.currentTextChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.sort_combo)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedWidth(150)
        self.search_bar.textChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.search_bar)

        toolbar.addWidget(QLabel("Bonus:"))
        self.bonus_from_edit = QLineEdit()
        self.bonus_from_edit.setPlaceholderText("From")
        self.bonus_from_edit.setFixedWidth(40)
        self.bonus_from_edit.textChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.bonus_from_edit)

        self.bonus_to_edit = QLineEdit()
        self.bonus_to_edit.setPlaceholderText("To")
        self.bonus_to_edit.setFixedWidth(40)
        self.bonus_to_edit.textChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.bonus_to_edit)

        self.hide_placed_cb = QCheckBox("Hide Placed Miners")
        self.hide_placed_cb.stateChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.hide_placed_cb)

        toolbar.addStretch()

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Personal", "Game"])
        self.source_combo.setCurrentText("Game")
        self.source_combo.currentTextChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.source_combo)

        layout.addLayout(toolbar)

        self.container_stack = QWidget()
        self.stack_layout = QVBoxLayout(self.container_stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)

        self.carousel_widget = QWidget()
        carousel_layout = QHBoxLayout(self.carousel_widget)
        carousel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedSize(40, INVENTORY_ITEM_HEIGHT)
        self.prev_btn.clicked.connect(self.scroll_prev)
        carousel_layout.addWidget(self.prev_btn)

        locked_width = (9 * INVENTORY_ITEM_WIDTH) + (8 * self.item_spacing) + 12
        self.view = DraggableListView()
        self.view.setFlow(QListView.Flow.LeftToRight)
        self.view.setWrapping(False)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setSpacing(self.item_spacing)
        self.view.setFixedSize(locked_width, INVENTORY_ITEM_HEIGHT + 25)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setStyleSheet("QListView { background: transparent; border: none; padding: 0px; margin: 0px; outline: none; }")
        
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.on_context_menu)

        self.model = InventoryModel()
        self.view.setModel(self.model)
        self.view.setItemDelegate(InventoryDelegate(self.view))
        carousel_layout.addWidget(self.view)

        self.next_btn = QPushButton(">")
        self.next_btn.setFixedSize(40, INVENTORY_ITEM_HEIGHT)
        self.next_btn.clicked.connect(self.scroll_next)
        carousel_layout.addWidget(self.next_btn)
        
        self.stack_layout.addWidget(self.carousel_widget)

        self.import_btn = QPushButton("Import Personal Inventory")
        self.import_btn.setFixedHeight(INVENTORY_ITEM_HEIGHT)
        self.import_btn.setStyleSheet("font-weight: bold; font-size: 16px; border: 2px dashed #444;")
        self.import_btn.clicked.connect(self.on_import_clicked)
        self.import_btn.hide()
        self.stack_layout.addWidget(self.import_btn)

        layout.addWidget(self.container_stack)

    def on_context_menu(self, pos):
        index = self.view.indexAt(pos)
        if not index.isValid():
            return
            
        data = index.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        if data.get('type') == 'miner':
            edit_action = QAction("Edit Miner Data", self)
            edit_action.triggered.connect(lambda: self.edit_requested.emit(data))
            menu.addAction(edit_action)
            
        if data.get('source') == 'Personal':
            del_action = QAction("Delete from inventory", self)
            del_action.triggered.connect(lambda: self.delete_personal_item(data))
            menu.addAction(del_action)
        else:
            copy_action = QAction("Send to personal inventory", self)
            copy_action.triggered.connect(lambda: self.copy_to_personal(data))
            menu.addAction(copy_action)
            
        menu.exec(self.view.mapToGlobal(pos))

    def copy_to_personal(self, data):
        self.adjust_quantity(data, 1)

    def delete_personal_item(self, data):
        target_name = data.get('name')
        target_lvl = data.get('lvl')
        target_type = data.get('type')
        
        self.personal_data = [
            item for item in self.personal_data 
            if not (item.get('name') == target_name and 
                    item.get('lvl') == target_lvl and 
                    item.get('type') == target_type)
        ]
        self.trigger_refresh()
        if not self.block_inventory_signals:
            self.inventory_changed.emit()

    def preload_data_from_db(self):
        self.game_data = []
        self.tag_to_item_map = {}
        if os.path.exists(CATALOG_DB_PATH):
            conn = sqlite3.connect(CATALOG_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT set_global_id, name FROM set_definitions")
            self.set_names_map = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()

        for lvl in range(1, 7):
            raw = self.db.get_catalog_miners(lvl)
            for d in raw:
                item = {
                    'id': d[0], 'name': d[1], 'image_path': d[2], 'slot_size': d[3], 
                    'set_global_id': d[4], 'set_sign_icon_path': d[5], 
                    'power_val': parse_hashrate_to_gh(d[6]),
                    'bonus_val': parse_percentage_to_float(d[7]),
                    'level_icon_path': d[8], 'mls_id': d[9],
                    'level_id_tag': d[10],
                    'lvl': lvl, 'type': 'miner', 'source': 'Game', 'timestamp': 0
                }
                self.game_data.append(item)
                if d[10]: 
                    self.tag_to_item_map[str(d[10]).lower()] = item

        raw_r = self.db.get_catalog_racks()
        for d in raw_r:
            item = {
                'id': d[0], 'name': d[1], 'rack_id_tag': d[2], 'set_global_id': d[3],
                'rack_size': d[4], 'bonus_val': parse_percentage_to_float(d[5]),
                'image_path': d[6], 'set_sign_icon_path': d[7], 
                'type': 'rack', 'source': 'Game', 'timestamp': 0
            }
            self.game_data.append(item)
            if d[2]:
                self.tag_to_item_map[str(d[2]).lower()] = item
        self.trigger_refresh()

    def on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personal Items", "", "Files (*.json *.txt *.csv)")
        if not path:
            return
        self.load_inventory_file(path)

    def load_inventory_file(self, path):
        if not path or not os.path.exists(path):
            self.inventory_is_valid = False
            return
        
        self.inventory_is_valid = False 
        
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        try:
            shutil.copy(path, os.path.join(backup_dir, f"backup_{os.path.basename(path)}"))
        except: pass

        id_quantities = {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                decoder = json.JSONDecoder()
                pos = 0
                while pos < len(content):
                    content = content.lstrip()
                    if not content: break
                    try:
                        obj, index = decoder.raw_decode(content)
                        items_list = []
                        if isinstance(obj, dict) and "data" in obj:
                            inner = obj["data"]
                            if isinstance(inner, dict) and "items" in inner:
                                items_list = inner["items"]
                        elif isinstance(obj, list):
                            items_list = obj
                        elif isinstance(obj, dict) and "items" in obj:
                            items_list = obj["items"]
                            
                        for raw_item in items_list:
                            m_id = raw_item.get("miner_id")
                            qty = int(raw_item.get("quantity", 1))
                            if m_id:
                                m_id = str(m_id).lower()
                                id_quantities[m_id] = id_quantities.get(m_id, 0) + qty
                        content = content[index:].lstrip()
                    except json.JSONDecodeError:
                        break
            
            if not id_quantities:
                raise ValueError("No valid inventory items found in file.")

            self.inventory_is_valid = True
        except Exception as e:
            self.inventory_is_valid = False
            QMessageBox.critical(self, "Import Error", f"Failed to parse file: {e}")
            return

        self.personal_data = []
        for m_id, qty in id_quantities.items():
            if m_id in self.tag_to_item_map:
                personal_item = self.tag_to_item_map[m_id].copy()
                personal_item['quantity'] = qty
                personal_item['source'] = 'Personal'
                personal_item['timestamp'] = 0
                self.personal_data.append(personal_item)

        self.trigger_refresh()

    def save_personal_inventory(self, path):
        if not path or not self.inventory_is_valid:
            return
        
        output_items = []
        for item in self.personal_data:
            tag = None
            if item.get("type") == "miner":
                tag = item.get("level_id_tag")
            elif item.get("type") == "rack":
                tag = item.get("rack_id_tag")

            if tag:
                output_items.append({
                    "name": item.get("name"),
                    "level": item.get("lvl", 1) - 1 if item.get("type") == "miner" else 0, 
                    "miner_id": str(tag).lower(),
                    "quantity": item.get("quantity", 0)
                })
        try:
            final_data = {
                "success": True,
                "data": {"items": output_items},
                "error": ""
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=4)
        except Exception as e:
            print(f"Failed to auto-save inventory: {e}")

    def add_personal_item(self, data):
        match = None
        for g in self.game_data:
            if g['name'].lower() == data.get('name', '').lower():
                if g.get('type') == 'miner' and g.get('lvl') == data.get('lvl'):
                    match = g
                    break
                elif g.get('type') == 'rack':
                    match = g
                    break
        
        if match:
            personal_item = match.copy()
            personal_item['source'] = 'Personal'
            personal_item['quantity'] = 1
            personal_item['timestamp'] = time.time()
            if 'power' in data: personal_item['power_val'] = parse_hashrate_to_gh(data['power'])
            if 'bonus' in data: personal_item['bonus_val'] = parse_percentage_to_float(data['bonus'])
            if 'image_path' in data and data['image_path']: personal_item['image_path'] = data['image_path']
            self.personal_data.append(personal_item)
            self.trigger_refresh()
        else:
            custom_item = {
                'id': -1, 'name': data.get('name', 'Custom'), 'image_path': data.get('image_path', ''),
                'slot_size': data.get('slot_size', 1), 'power_val': parse_hashrate_to_gh(data.get('power', '0')),
                'bonus_val': parse_percentage_to_float(data.get('bonus', '0')), 'lvl': data.get('lvl', 1),
                'type': data.get('type', 'miner'), 'source': 'Personal', 'quantity': 1, 'level_id_tag': None,
                'timestamp': time.time()
            }
            self.personal_data.append(custom_item)
            self.trigger_refresh()
        
        if not self.block_inventory_signals:
            self.inventory_changed.emit()

    def adjust_quantity(self, item_data, delta):
        target_name = item_data.get('name')
        target_lvl = item_data.get('lvl')
        target_type = item_data.get('type')
        found = False
        for item in self.personal_data:
            if (item.get('name') == target_name and item.get('lvl') == target_lvl and item.get('type') == target_type):
                item['quantity'] = max(0, item['quantity'] + delta)
                if delta > 0:
                    item['timestamp'] = time.time()
                found = True
                break
        
        if not found and delta > 0 and self.inventory_is_valid:
            new_item = item_data.copy()
            new_item['source'] = 'Personal'
            new_item['quantity'] = delta
            new_item['timestamp'] = time.time()
            self.personal_data.append(new_item)
        
        self.trigger_refresh()
        if not self.block_inventory_signals:
            self.inventory_changed.emit()

    def set_placed_items(self, ids_set):
        self.placed_item_keys = {id_val.lower() for id_val in ids_set if id_val}
        self.trigger_refresh()

    def trigger_refresh(self):
        source = self.source_combo.currentText()
        is_personal = (source == "Personal")
        if is_personal and not self.personal_data:
            self.import_btn.show(); self.carousel_widget.hide()
        else:
            self.import_btn.hide(); self.carousel_widget.show()

        source_list = self.personal_data if is_personal else self.game_data
        itype = "rack" if self.type_combo.currentText() == "Racks" else "miner"
        search = self.search_bar.text().lower().strip()
        lvl = self.level_group.checkedId()
        slots = self.slot_combo.currentText()
        sort_mode = self.sort_combo.currentText()
        hide_placed = self.hide_placed_cb.isChecked()

        try:
            min_bonus = float(self.bonus_from_edit.text()) if self.bonus_from_edit.text() else -1.0
        except ValueError:
            min_bonus = -1.0
            
        try:
            max_bonus = float(self.bonus_to_edit.text()) if self.bonus_to_edit.text() else 99999.0
        except ValueError:
            max_bonus = 99999.0

        filtered = []
        for item in source_list:
            if is_personal and item.get('quantity', 0) <= 0: continue
            if item['type'] != itype: continue
            
            if is_personal and itype == 'miner' and hide_placed:
                item_tag = item.get('level_id_tag')
                if item_tag and item_tag.lower() in self.placed_item_keys:
                    continue

            if min_bonus != -1.0 and item.get('bonus_val', 0.0) < min_bonus: continue
            if max_bonus != 99999.0 and item.get('bonus_val', 0.0) > max_bonus: continue

            item_name = item['name'].lower()
            set_id = item.get('set_global_id')
            set_name_str = (self.set_names_map.get(set_id, '')).lower().replace('_', ' ')
            if itype == "miner" and not search and lvl != 0 and item.get('lvl') != lvl: continue
            if itype == "miner" and slots != "All":
                req = 1 if slots == "1 slot" else 2
                if int(item.get('slot_size', 1)) != req: continue
            if search and not (search in item_name or search in set_name_str): continue
            filtered.append(item)

        if sort_mode == "Power + Bonus":
            filtered.sort(key=lambda x: (x.get('power_val', 0), x.get('bonus_val', 0)), reverse=True)
        elif sort_mode == "Bonus + Power":
            filtered.sort(key=lambda x: (x.get('bonus_val', 0), x.get('power_val', 0)), reverse=True)
        elif sort_mode == "Newest First":
            filtered.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
        self.model.update_data(filtered)

    def scroll_next(self):
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() + (9 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))

    def scroll_prev(self):
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() - (9 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))