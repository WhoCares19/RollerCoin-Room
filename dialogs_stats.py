import os
import csv
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, 
    QFileDialog, QScrollArea, QFrame, QWidget, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QPixmap, QAction, QIcon
from logic_math import format_hashrate, calculate_single_rack_stats
from settings import LOCK_ICON, UNLOCK_ICON
from ui_styles import resolve_path

class ActualPowerDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("Actual Power Values")
        self.setFixedWidth(450)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        items = [
            ("Base Miner Power:", f"{stats.get('miners_base', 0)} Gh/s"),
            ("Bonus Power Contribution:", f"{stats.get('bonus_power', 0)} Gh/s"),
            ("Rack Bonus Contribution:", f"{stats.get('rack_bonus', 0)} Gh/s"),
            ("Final Total Power:", f"{stats.get('total', 0)} Gh/s")
        ]
        
        for label, val in items:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{label}</b>"))
            row.addStretch()
            v_lbl = QLabel(val)
            v_lbl.setStyleSheet("color: #00ff00; font-family: 'Consolas', monospace;")
            row.addWidget(v_lbl)
            layout.addLayout(row)
            
        btn_box = QHBoxLayout()
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.export_to_csv)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_box.addStretch()
        btn_box.addWidget(download_btn)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def export_to_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Power Breakdown", "player_power.csv", "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Category", "Value (Gh/s)"])
                writer.writerow(["Base Miner Power", self.stats.get('miners_base', 0)])
                writer.writerow(["Bonus Power Contribution", self.stats.get('bonus_power', 0)])
                writer.writerow(["Rack Bonus Contribution", self.stats.get('rack_bonus', 0)])
                writer.writerow(["Final Total Power", self.stats.get('total', 0)])
                room_details = sorted(self.stats.get('room_details', []), key=lambda x: x['room_id'])
                for item in room_details:
                    writer.writerow([f"Room {item['room_id'] + 1} Total", item['total']])
            QMessageBox.information(self, "Success", "Power breakdown exported successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to save CSV: {e}")

class PowerBreakdownDialog(QDialog):
    def __init__(self, stats, baseline_stats=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Total Power Breakdown")
        self.setFixedWidth(420)
        room_count = len(stats.get('room_details', []))
        self.setFixedHeight(250 + (room_count * 25))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        stats_map = [("miners_base", "Miner:"), ("bonus_power", "Bonus Power:"), ("rack_bonus", "Rack Bonus:")]
        for key, label in stats_map:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{label}</b>")
            disp = f"{stats.get('bonus_percent', 0.0):.2f}% | {format_hashrate(stats[key])}" if key == "bonus_power" else format_hashrate(stats.get(key, 0))
            val_lbl = QLabel(disp)
            row.addWidget(lbl); row.addStretch()
            if baseline_stats:
                curr_v, base_v = float(stats.get(key, 0)), float(baseline_stats.get(key, 0))
                row.addWidget(self.create_delta_label(curr_v - base_v))
            row.addWidget(val_lbl); layout.addLayout(row)
        
        layout.addSpacing(10)
        actual_btn = QPushButton("Show Actual Power")
        actual_btn.clicked.connect(lambda: ActualPowerDialog(stats, self).exec())
        layout.addWidget(actual_btn)
        
        layout.addSpacing(10)
        sep = QLabel("~~~~~~~~~~~~~~~~ rooms ~~~~~~~~~~~~~~~~")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter); sep.setStyleSheet("color: #555; font-weight: bold;"); layout.addWidget(sep); layout.addSpacing(10)
        
        room_details = sorted(stats.get('room_details', []), key=lambda x: x['room_id'])
        base_rooms = {r['room_id']: r['total'] for r in baseline_stats.get('room_details', [])} if baseline_stats else {}
        for item in room_details:
            row = QHBoxLayout()
            room_lbl = QLabel(f"<b>Room {item['room_id'] + 1} Total:</b>")
            room_val = QLabel(format_hashrate(item['total'])); room_val.setStyleSheet("color: #00ff00;")
            row.addWidget(room_lbl); row.addStretch()
            if item['room_id'] in base_rooms:
                row.addWidget(self.create_delta_label(item['total'] - base_rooms[item['room_id']]))
            row.addWidget(room_val); layout.addLayout(row)
        layout.addStretch(); close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close); layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def create_delta_label(self, delta):
        lbl = QLabel("")
        if abs(delta) > 0.001:
            lbl.setText(f"{'↑' if delta > 0 else '↓'} {format_hashrate(abs(delta))}")
            lbl.setStyleSheet(f"color: {'#00ff00' if delta > 0 else '#ff4444'}; font-size: 10px; font-weight: bold; margin-right: 5px;")
        return lbl

class RackDetailsDialog(QDialog):
    edit_requested = Signal(dict)
    def __init__(self, rack_widgets, current_index, parent=None):
        super().__init__(parent)
        self.rack_widgets = rack_widgets
        self.current_index = current_index
        self.rack_widget = self.rack_widgets[self.current_index]
        self.setWindowTitle("Rack Details")
        self.setFixedSize(450, 580)
        main_layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        self.prev_btn = QPushButton("<"); self.prev_btn.setFixedSize(24, 24); self.prev_btn.clicked.connect(lambda: self.navigate(-1))
        self.header_label = QLabel(); self.header_label.setStyleSheet("font-size: 16px;"); self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_btn = QPushButton(">"); self.next_btn.setFixedSize(24, 24); self.next_btn.clicked.connect(lambda: self.navigate(1))
        self.lock_btn = QPushButton(); self.lock_btn.setFixedSize(24, 24); self.lock_btn.setStyleSheet("background: transparent; border: none;"); self.lock_btn.clicked.connect(self.toggle_lock)
        
        header_layout.addWidget(self.prev_btn); header_layout.addWidget(self.header_label, 1); header_layout.addWidget(self.next_btn); header_layout.addWidget(self.lock_btn)
        h_frame = QFrame(); h_frame.setLayout(header_layout); h_frame.setStyleSheet("border-bottom: 1px solid #333; padding-bottom: 5px;"); main_layout.addWidget(h_frame)
        
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.miner_container = QWidget(); self.c_layout = QVBoxLayout(self.miner_container); self.c_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.scroll.setWidget(self.miner_container); main_layout.addWidget(self.scroll)
        
        self.footer = QFrame(); self.footer.setStyleSheet("border-top: 1px solid #333; padding-top: 10px;"); self.f_layout = QVBoxLayout(self.footer); main_layout.addWidget(self.footer)
        
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.close); main_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.refresh()

    def navigate(self, delta):
        self.current_index = (self.current_index + delta) % len(self.rack_widgets)
        self.rack_widget = self.rack_widgets[self.current_index]; self.refresh()

    def refresh(self):
        gb = self.parent().current_stats.get('bonus_percent', 0.0) if self.parent().current_stats else 0.0
        stats = calculate_single_rack_stats(self.rack_widget.data, self.rack_widget.rows_data, gb)
        self.update_lock_icon(); self.populate_dialog(stats)

    def populate_dialog(self, stats):
        for layout in [self.c_layout, self.f_layout]:
            while layout.count():
                it = layout.takeAt(0)
                if it.widget(): it.widget().deleteLater()
            
        rb = self.rack_widget.data.get('bonus_val', 0.0)
        self.header_label.setText(f"<b>{stats.get('set_name', self.rack_widget.data.get('name'))}</b> | <span style='color:#5dade2;'>{rb}% Bonus</span>")
        
        for m in stats['miners']:
            frame = QFrame(); frame.setObjectName("MinerRow")
            frame.setStyleSheet("QFrame#MinerRow { background: transparent; border-radius: 4px; margin-bottom: 2px; } QFrame#MinerRow:hover { background: #222; }")
            frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            frame.customContextMenuRequested.connect(lambda pos, d=m, w=frame: self.show_miner_menu(pos, d, w))
            lay = QHBoxLayout(frame); img = QLabel(); ip = resolve_path(m.get('image_path', ''))
            if os.path.exists(ip): img.setPixmap(QPixmap(ip).scaled(35, 25, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            img.setFixedWidth(40); lt = f"Lvl {m['lvl']}" if m['lvl'] > 0 else "Legacy"
            lay.addWidget(img); lay.addWidget(QLabel(f"<b>{m['name']}</b> ({lt})")); lay.addStretch(); lay.addWidget(QLabel(f"<span style='color:#00ff00;'>{format_hashrate(m['power'])}</span>")); lay.addWidget(QLabel(f"<span style='color:#ffcc00;'>{m['bonus']}%</span>"))
            self.c_layout.addWidget(frame)
            
        tm = [("Base Power:", stats['base_power'], "white"), ("Miner Bonus's:", stats['miner_bonus_power'], "#ffcc00")]
        if stats.get('is_set_rack'):
            if stats.get('set_bonus_power', 0) > 0: tm.append(("Set Bonus:", stats['set_bonus_power'], "#f1c40f"))
            if stats.get('set_bonus_pct', 0) > 0: tm.append(("Set Power:", stats['set_flat_power'], "white"))
        tm.extend([("Rack Bonus Power:", stats['rack_bonus'], "#5dade2"), ("Total Power:", stats['total_power'], "#00ff00")])
        for l, v, c in tm:
            row = QHBoxLayout(); row.addWidget(QLabel(f"<b>{l}</b>")); row.addStretch()
            if l == "Miner Bonus's:": d = f"{stats.get('miner_bonus_pct', 0.0):.2f}% | {format_hashrate(v)}"
            elif l == "Set Bonus:": d = f"{stats.get('set_bonus_pct', 0.0):.2f}% | {format_hashrate(v)}"
            elif l == "Rack Bonus Power:": d = f"{stats.get('rack_bonus_pct', 0.0):.2f}% | {format_hashrate(v)}"
            else: d = format_hashrate(v)
            lbl = QLabel(d); lbl.setStyleSheet(f"color: {c}; font-weight: bold;"); row.addWidget(lbl); self.f_layout.addLayout(row)

    def toggle_lock(self): self.rack_widget.is_locked = not self.rack_widget.is_locked; self.update_lock_icon()
    def update_lock_icon(self):
        p = LOCK_ICON if self.rack_widget.is_locked else UNLOCK_ICON
        if os.path.exists(p): self.lock_btn.setIcon(QIcon(p)); self.lock_btn.setIconSize(QSize(20, 20))
        
    def show_miner_menu(self, pos, data, widget):
        if self.rack_widget.is_locked: return
        m = QMenu(self); e = QAction("Edit Miner Data", self); e.triggered.connect(lambda: self.edit_requested.emit(data))
        r = QAction("Remove Miner", self); r.triggered.connect(lambda: (self.rack_widget.remove_miner(data['row'], data['slot']), self.refresh()))
        m.addActions([e, r]); m.exec(widget.mapToGlobal(pos))