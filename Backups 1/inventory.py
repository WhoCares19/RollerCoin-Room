import os
import json
import sqlite3
import shutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QComboBox, QLineEdit, QLabel, QListView, 
                               QStyledItemDelegate, QStyle, QButtonGroup, QFileDialog, QMessageBox, QMenu)
from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QSize, QRect, Signal, QMimeData
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

def normalize_item(item):
    if not isinstance(item, dict):
        return None
    name = item.get("name", "").strip()
    file_lvl = int(item.get("level", 0))
    qty = int(item.get("quantity", 1))
    return {
        "name": name,
        "level": file_lvl + 1,
        "quantity": qty
    }    

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

    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and event.button() == Qt.MouseButton.LeftButton:
            data = index.data(Qt.ItemDataRole.UserRole)
            self.itemClicked.emit(data)
            
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(data))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
        super().mousePressEvent(event)

class InventorySection(QWidget):
    edit_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.db = DatabaseHandler()
        self.game_data = []
        self.personal_data = []
        self.set_names_map = {} 
        self.item_spacing = 5
        
        self.setMinimumHeight(INVENTORY_ITEM_HEIGHT + 100)
        self.init_ui()
        self.preload_data_from_db()

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

        self.slot_combo = QComboBox()
        self.slot_combo.addItems(["All", "1 slot", "2 slot"])
        self.slot_combo.currentIndexChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.slot_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Power + Bonus", "Bonus + Power", "High Power + High Bonus", "High Bonus + High Power"])
        self.sort_combo.currentTextChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.sort_combo)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.setFixedWidth(150)
        self.search_bar.textChanged.connect(self.trigger_refresh)
        toolbar.addWidget(self.search_bar)

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
        self.view.setViewMode(QListView.ViewMode.IconMode)
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
        if index.isValid():
            data = index.data(Qt.ItemDataRole.UserRole)
            if data.get('type') == 'miner':
                menu = QMenu(self)
                edit_action = QAction("Edit Miner Data", self)
                edit_action.triggered.connect(lambda: self.edit_requested.emit(data))
                menu.addAction(edit_action)
                menu.exec(self.view.mapToGlobal(pos))

    def preload_data_from_db(self):
        self.game_data = []
        if os.path.exists(CATALOG_DB_PATH):
            conn = sqlite3.connect(CATALOG_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT set_global_id, name FROM set_definitions")
            self.set_names_map = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()

        for lvl in range(1, 7):
            raw = self.db.get_catalog_miners(lvl)
            for d in raw:
                self.game_data.append({
                    'id': d[0], 'name': d[1], 'image_path': d[2], 'slot_size': d[3], 
                    'set_global_id': d[4], 'set_sign_icon_path': d[5], 
                    'power_val': parse_hashrate_to_gh(d[6]),
                    'bonus_val': parse_percentage_to_float(d[7]),
                    'level_icon_path': d[8], 'mls_id': d[9],
                    'lvl': lvl, 'type': 'miner', 'source': 'Game'
                })
        raw_r = self.db.get_catalog_racks()
        for d in raw_r:
            self.game_data.append({
                'id': d[0], 'name': d[1], 'rack_id_tag': d[2], 'set_global_id': d[3],
                'rack_size': d[4], 'bonus_val': parse_percentage_to_float(d[5]),
                'image_path': d[6], 'set_sign_icon_path': d[7], 
                'type': 'rack', 'source': 'Game'
            })
        self.trigger_refresh()

    def on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personal Items", "", "Files (*.json *.txt *.csv)")
        if not path:
            return
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        shutil.copy(path, os.path.join(backup_dir, f"backup_{os.path.basename(path)}"))
        imported_list = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if path.endswith('.json'):
                    raw_data = json.loads(content)
                    if isinstance(raw_data, dict) and "items" in raw_data:
                        imported_list = raw_data["items"]
                    elif isinstance(raw_data, dict):
                        imported_list = list(raw_data.values())
                    else:
                        imported_list = raw_data
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse file: {e}")
            return
        missing_items = []
        self.personal_data = []
        for raw_item in imported_list:
            norm = normalize_item(raw_item)
            if not norm:
                continue
            target_name = norm["name"].lower()
            target_lvl = norm["level"]
            qty = norm["quantity"]
            match = None
            for g in self.game_data:
                if g['name'].lower() == target_name and g.get('lvl') == target_lvl:
                    match = g
                    break
            if match:
                personal_item = match.copy()
                personal_item['quantity'] = qty
                personal_item['source'] = 'Personal'
                self.personal_data.append(personal_item)
            else:
                missing_items.append(f"{target_name} (File Lvl {target_lvl-1} → DB Lvl {target_lvl})")
        if missing_items:
            msg = f"The following items were not found in the database:\n\n" + "\n".join(missing_items[:10])
            if len(missing_items) > 10:
                msg += f"\n...and {len(missing_items)-10} more."
            res = QMessageBox.warning(self, "Missing Items", msg + "\n\nWould you like to export this list?", QMessageBox.Yes | QMessageBox.No)
            if res == QMessageBox.Yes:
                exp_path, _ = QFileDialog.getSaveFileName(self, "Export Missing", "missing_items.txt", "Text Files (*.txt)")
                if exp_path:
                    with open(exp_path, 'w', encoding='utf-8') as ef:
                        ef.write("\n".join(missing_items))
        self.trigger_refresh()

    def add_personal_item(self, data):
        """Logic for adding items via the Add Item dialog."""
        # Find item in game_data to get IDs and paths
        match = None
        for g in self.game_data:
            if g['name'].lower() == data.get('name', '').lower() and g.get('lvl') == data.get('lvl'):
                match = g
                break
        
        if match:
            personal_item = match.copy()
            personal_item['source'] = 'Personal'
            personal_item['quantity'] = 1
            
            # Update with custom values if provided
            if 'power' in data:
                personal_item['power_val'] = parse_hashrate_to_gh(data['power'])
            if 'bonus' in data:
                personal_item['bonus_val'] = parse_percentage_to_float(data['bonus'])
            if 'image_path' in data and data['image_path']:
                personal_item['image_path'] = data['image_path']
                
            self.personal_data.append(personal_item)
            self.trigger_refresh()
        else:
            # If no DB match, create a custom entry
            custom_item = {
                'id': -1,
                'name': data.get('name', 'Custom'),
                'image_path': data.get('image_path', ''),
                'slot_size': data.get('slot_size', 1),
                'power_val': parse_hashrate_to_gh(data.get('power', '0')),
                'bonus_val': parse_percentage_to_float(data.get('bonus', '0')),
                'lvl': data.get('lvl', 1),
                'type': data.get('type', 'miner'),
                'source': 'Personal',
                'quantity': 1
            }
            self.personal_data.append(custom_item)
            self.trigger_refresh()

    def adjust_quantity(self, item_id, delta):
        for item in self.personal_data:
            if item['id'] == item_id:
                item['quantity'] = max(0, item['quantity'] + delta)
                self.trigger_refresh()
                return

    def trigger_refresh(self):
        source = self.source_combo.currentText()
        is_personal = (source == "Personal")
        
        if is_personal and not self.personal_data:
            self.import_btn.show()
            self.carousel_widget.hide()
        else:
            self.import_btn.hide()
            self.carousel_widget.show()

        source_list = self.personal_data if is_personal else self.game_data
        itype = "rack" if self.type_combo.currentText() == "Racks" else "miner"
        search = self.search_bar.text().lower().strip()
        lvl = self.level_group.checkedId()
        slots = self.slot_combo.currentText()

        filtered = []
        for item in source_list:
            if is_personal and item.get('quantity', 0) <= 0: continue
            if item['type'] != itype: continue
            
            item_name = item['name'].lower()
            set_id = item.get('set_global_id')
            set_name_str = (self.set_names_map.get(set_id, '')).lower().replace('_', ' ')

            if itype == "miner" and not search and item.get('lvl') != lvl: continue
            if itype == "miner" and slots != "All":
                req = 1 if slots == "1 slot" else 2
                if item.get('slot_size') != req: continue
            
            if search and not (search in item_name or search in set_name_str): continue
            
            filtered.append(item)

        self.model.update_data(filtered)

    def scroll_next(self):
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() + (9 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))

    def scroll_prev(self):
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() - (9 * (INVENTORY_ITEM_WIDTH + self.item_spacing)))