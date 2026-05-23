import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QScrollArea, QWidget, QFrame, QLineEdit, QGridLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QMovie
from ui_styles import resolve_path
from logic_math import format_hashrate

class ImagePopupDialog(QDialog):
    def __init__(self, image_path, miner_name, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background-color: rgba(18, 18, 18, 230); border: 2px solid #444; border-radius: 10px;")
        
        if image_path.lower().endswith(".gif"):
            self.movie = QMovie(image_path)
            self.img_label.setMovie(self.movie)
            self.movie.start()
        else:
            pix = QPixmap(image_path)
            if not pix.isNull():
                self.img_label.setPixmap(pix.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        layout.addWidget(self.img_label)
        
        self.name_label = QLabel(miner_name, self.img_label)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180); 
            color: white; 
            font-weight: bold; 
            font-size: 16px; 
            padding: 10px;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        """)
        
        layout.addWidget(self.name_label)
        
    def mousePressEvent(self, event):
        self.accept()

class ClickableImageLabel(QLabel):
    clicked = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

class MergeAdviceDialog(QDialog):
    def __init__(self, advice_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge Advice")
        self.setFixedSize(1150, 690)
        self.setStyleSheet("QDialog { background-color: #121212; }")
        
        self.full_advice_data = advice_data
        self.filtered_data = []
        self.batch_size = 36
        self.loaded_count = 0
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search miners...")
        self.search_bar.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: 14px;
            }
        """)
        self.search_bar.textChanged.connect(self.reset_and_filter)
        self.main_layout.addWidget(self.search_bar)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        # Connect scrollbar signal for lazy loading
        self.scroll.verticalScrollBar().valueChanged.connect(self.check_scroll)
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)
        
        self.reset_and_filter()
        self.setFocus()

    def reset_and_filter(self):
        # Clear existing cards
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Apply search filter
        search_text = self.search_bar.text().lower().strip()
        self.filtered_data = [item for item in self.full_advice_data if search_text in item['name'].lower()]
        
        self.loaded_count = 0
        self.load_next_batch()

    def check_scroll(self, value):
        # Trigger next batch when user scrolls to 90% of the maximum
        max_scroll = self.scroll.verticalScrollBar().maximum()
        if max_scroll > 0 and value > max_scroll * 0.9:
            self.load_next_batch()

    def load_next_batch(self):
        if self.loaded_count >= len(self.filtered_data):
            return

        end_idx = min(self.loaded_count + self.batch_size, len(self.filtered_data))
        batch = self.filtered_data[self.loaded_count:end_idx]
        
        for i, item in enumerate(batch):
            idx = self.loaded_count + i
            row = idx // 6
            col = idx % 6
            card = self.create_advice_card(item)
            self.grid_layout.addWidget(card, row, col)
            
        self.loaded_count = end_idx

    def create_advice_card(self, item):
        card = QFrame()
        card.setFixedSize(175, 200)
        card.setStyleSheet("background-color: #161616; border-radius: 10px; border: 1px solid #333;")
        
        vlay = QVBoxLayout(card)
        vlay.setContentsMargins(0, 5, 0, 0)
        vlay.setSpacing(0)
        vlay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. Top - Image
        img_label = ClickableImageLabel()
        img_path = resolve_path(item['base_image'])
        if os.path.exists(img_path):
            pix = QPixmap(img_path).scaled(110, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pix)
        img_label.clicked.connect(lambda p=img_path, n=item['name']: self.open_popup(p, n))
        img_label.setStyleSheet("border: none; background: transparent;")
        vlay.addWidget(img_label, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Middle - Miner Name
        name_lbl = QLabel(item['name'])
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #e0e0e0; border: none; background: transparent;")
        name_lbl.setFixedHeight(35)
        vlay.addWidget(name_lbl)

        # 3. Bottom - Stats row
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(0)
        stats_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Previous Level
        prev_col = self.create_compact_stat_col(item['curr_icon'], item['curr_power'], item['curr_bonus'])
        stats_row.addLayout(prev_col)

        # Arrow
        arrow_lbl = QLabel("→")
        arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_lbl.setStyleSheet("font-size: 16px; color: #555; border: none; background: transparent; padding-bottom: 25px;")
        stats_row.addWidget(arrow_lbl)

        # Next Level
        next_col = self.create_compact_stat_col(item['next_icon'], item['next_power'], item['next_bonus'])
        stats_row.addLayout(next_col)

        vlay.addLayout(stats_row)
        return card

    def create_compact_stat_col(self, icon_path, power, bonus):
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        if os.path.exists(icon_path):
            icon_lbl.setPixmap(QPixmap(icon_path).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio))
        col.addWidget(icon_lbl)
        
        stat_text = f"<span style='color:#00ff00;'>{format_hashrate(power)}</span><br/><span style='color:#ffcc00;'>{bonus}%</span>"
        stat_lbl = QLabel(stat_text)
        stat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stat_lbl.setStyleSheet("font-size: 9px; border: none; background: transparent;")
        col.addWidget(stat_lbl)
        
        return col

    def open_popup(self, path, name):
        pop = ImagePopupDialog(path, name, self)
        pop.exec()

def show_merge_advice(main_window):
    inventory = main_window.inventory
    tally = {}

    for view in main_window.room_views:
        for p in view.placeholders:
            if p.rack:
                for row in p.rack.rows_data:
                    miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                    for m in miners:
                        if isinstance(m, dict) and m.get('type') == 'miner':
                            key = (m['name'], m.get('lvl', 1))
                            tally[key] = tally.get(key, 0) + 1

    for item in inventory.personal_data:
        if item.get('type') == 'miner':
            key = (item['name'], item.get('lvl', 1))
            tally[key] = tally.get(key, 0) + item.get('quantity', 0)

    advice_list = []
    for (name, lvl), qty in tally.items():
        if qty >= 2 and lvl < 6:
            next_lvl_data = inventory.name_to_item_map.get((name.lower().strip(), lvl + 1))
            curr_lvl_data = inventory.name_to_item_map.get((name.lower().strip(), lvl))
            
            if next_lvl_data and curr_lvl_data:
                advice_list.append({
                    "name": name,
                    "base_image": curr_lvl_data.get('image_path', ''),
                    "curr_icon": resolve_path(curr_lvl_data.get('level_icon_path', '')),
                    "curr_power": curr_lvl_data.get('power_val', 0),
                    "curr_bonus": curr_lvl_data.get('bonus_val', 0),
                    "next_icon": resolve_path(next_lvl_data.get('level_icon_path', '')),
                    "next_power": next_lvl_data.get('power_val', 0),
                    "next_bonus": next_lvl_data.get('bonus_val', 0)
                })

    dialog = MergeAdviceDialog(advice_list, main_window)
    dialog.exec()