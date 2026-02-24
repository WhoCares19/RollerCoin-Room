import sys
import json
import time
import copy
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                             QGroupBox, QFormLayout, QFileDialog, QMessageBox, 
                             QScrollArea, QGridLayout, QShortcut, QComboBox)
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QRect, QPoint

# --- Constants ---
COLOR_RACK = QColor(100, 100, 100, 150)
COLOR_RACK_SEL = QColor(150, 150, 150, 200)
COLOR_ROW = QColor(200, 0, 0, 100)
COLOR_ROW_SEL = QColor(255, 0, 0, 180)
COLOR_MINER = QColor(0, 150, 255, 150)
COLOR_MINER_SEL = QColor(0, 200, 255, 220)
COLOR_CANVAS_BG = QColor(30, 30, 30)
CANVAS_SIZE = 550

class RackStructureEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Rack & Child Editor")
        self.setFixedSize(900, 600)

        # Multi-Type Data Structure
        self.current_type = "Big Rack"
        self.all_data = {
            "Big Rack": {"racks": [], "img": QPixmap(), "offset": QPoint(0, 0)},
            "Small Rack": {"racks": [], "img": QPixmap(), "offset": QPoint(0, 0)}
        }
        
        # State
        self.selection = [] 
        self.clipboard = []
        self.current_file_path = None
        
        # View State
        self.zoom_level = 1.0
        self.dragging = False      
        self.dragging_img = False  
        self.panning = False       
        self.last_mouse_pos = QPoint()

        self.init_ui()
        self.setup_shortcuts()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- Sidebar ---
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(280)
        sidebar = QVBoxLayout(sidebar_widget)
        sidebar.setContentsMargins(5, 5, 5, 5)

        sidebar.addWidget(QLabel("Select Rack Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Big Rack", "Small Rack"])
        self.type_combo.currentTextChanged.connect(self.switch_rack_type)
        sidebar.addWidget(self.type_combo)

        btn_img = QPushButton("Import Template Image")
        btn_img.clicked.connect(self.import_template)
        sidebar.addWidget(btn_img)

        btn_rack = QPushButton("Add Rack Placeholder")
        btn_rack.clicked.connect(self.add_rack)
        sidebar.addWidget(btn_rack)

        btn_row = QPushButton("Add Row to Selected Rack")
        btn_row.clicked.connect(self.add_row)
        sidebar.addWidget(btn_row)

        btn_miner = QPushButton("Add Miner to Selected Row")
        btn_miner.clicked.connect(self.add_miner)
        sidebar.addWidget(btn_miner)

        tool_group = QGroupBox("Tools")
        tool_layout = QGridLayout()
        btn_copy = QPushButton("Copy (Ctrl+C)"); btn_copy.clicked.connect(self.copy_selection)
        btn_paste = QPushButton("Paste (Ctrl+V)"); btn_paste.clicked.connect(self.paste_selection)
        btn_delete = QPushButton("Delete (Del)"); btn_delete.clicked.connect(self.delete_selection)
        btn_align_h = QPushButton("Align H"); btn_align_h.clicked.connect(self.align_h)
        btn_align_v = QPushButton("Align V"); btn_align_v.clicked.connect(self.align_v)
        
        tool_layout.addWidget(btn_copy, 0, 0); tool_layout.addWidget(btn_paste, 0, 1)
        tool_layout.addWidget(btn_delete, 1, 0, 1, 2)
        tool_layout.addWidget(btn_align_h, 2, 0); tool_layout.addWidget(btn_align_v, 2, 1)
        tool_group.setLayout(tool_layout)
        sidebar.addWidget(tool_group)

        self.prop_group = QGroupBox("Properties")
        prop_layout = QFormLayout()
        self.spn_x = QSpinBox(); self.spn_x.setRange(-5000, 5000); self.spn_x.valueChanged.connect(self.update_data_from_ui)
        self.spn_y = QSpinBox(); self.spn_y.setRange(-5000, 5000); self.spn_y.valueChanged.connect(self.update_data_from_ui)
        self.spn_w = QSpinBox(); self.spn_w.setRange(1, 5000); self.spn_w.valueChanged.connect(self.update_data_from_ui)
        self.spn_h = QSpinBox(); self.spn_h.setRange(1, 5000); self.spn_h.valueChanged.connect(self.update_data_from_ui)
        prop_layout.addRow("X:", self.spn_x)
        prop_layout.addRow("Y:", self.spn_y)
        prop_layout.addRow("Width:", self.spn_w)
        prop_layout.addRow("Height:", self.spn_h)
        self.prop_group.setLayout(prop_layout)
        sidebar.addWidget(self.prop_group)

        sidebar.addStretch()
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_current_file)
        sidebar.addWidget(btn_save)

        btn_exp = QPushButton("Export JSON")
        btn_exp.setStyleSheet("background: #2e7d32; color: white;")
        btn_exp.clicked.connect(self.export_json)
        sidebar.addWidget(btn_exp)

        main_layout.addWidget(sidebar_widget)

        # --- Canvas Area ---
        self.canvas = QLabel()
        self.canvas.setFixedSize(CANVAS_SIZE, CANVAS_SIZE)
        self.canvas.setStyleSheet("background: #1e1e1e;")
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

        self.update_display()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_selection)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_selection)
        QShortcut(QKeySequence("Delete"), self, self.delete_selection)

    def switch_rack_type(self, new_type):
        self.current_type = new_type
        self.selection = []
        self.update_ui_from_data()
        self.update_display()

    @property
    def racks(self): return self.all_data[self.current_type]["racks"]
    
    @property
    def current_img_offset(self): return self.all_data[self.current_type]["offset"]
    @current_img_offset.setter
    def current_img_offset(self, val): self.all_data[self.current_type]["offset"] = val
    
    @property
    def current_template_image(self): return self.all_data[self.current_type]["img"]

    def add_rack(self):
        new_rack = {"x": 0, "y": 0, "w": 65, "h": 115, "rows": []}
        self.racks.append(new_rack)
        self.selection = [('rack', len(self.racks)-1, -1, -1)]
        self.update_display()

    def add_row(self):
        r_idx = self.get_primary_rack_idx()
        if r_idx == -1: return
        new_row = {"x": 5, "y": 5, "w": 55, "h": 20, "miners": []}
        self.racks[r_idx]["rows"].append(new_row)
        self.selection = [('row', r_idx, len(self.racks[r_idx]["rows"])-1, -1)]
        self.update_display()

    def add_miner(self):
        idx = self.get_primary_selection()
        if not idx or idx[0] != 'row': return
        _, r_idx, row_idx, _ = idx
        new_miner = {"x": 5, "y": 5, "w": 20, "h": 15}
        self.racks[r_idx]["rows"][row_idx]["miners"].append(new_miner)
        self.selection = [('miner', r_idx, row_idx, len(self.racks[r_idx]["rows"][row_idx]["miners"])-1)]
        self.update_display()

    def delete_selection(self):
        if not self.selection: return
        sorted_sel = sorted(self.selection, key=lambda x: (0 if x[0]=='miner' else (1 if x[0]=='row' else 2), -x[1], -x[2], -x[3]))
        for item in sorted_sel:
            t, r_idx, row_idx, m_idx = item
            try:
                if t == 'miner': del self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
                elif t == 'row': del self.racks[r_idx]["rows"][row_idx]
                elif t == 'rack': del self.racks[r_idx]
            except IndexError: continue
        self.selection = []
        self.update_display()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0: self.zoom_level = min(5.0, self.zoom_level + 0.1)
            else: self.zoom_level = max(0.2, self.zoom_level - 0.1)
            self.update_display()

    def keyPressEvent(self, event):
        step = 10 if event.modifiers() == Qt.ShiftModifier else 1
        dx, dy = 0, 0
        if event.key() == Qt.Key_Left: dx = -step
        elif event.key() == Qt.Key_Right: dx = step
        elif event.key() == Qt.Key_Up: dy = -step
        elif event.key() == Qt.Key_Down: dy = step
        if dx != 0 or dy != 0:
            for item in self.selection: self.move_item(item, dx, dy)
            self.update_ui_from_data(); self.update_display()
        else: super().keyPressEvent(event)

    def move_item(self, item, dx, dy):
        obj_type, r_idx, row_idx, m_idx = item
        if obj_type == 'rack':
            self.racks[r_idx]["x"] += dx
            self.racks[r_idx]["y"] += dy
        elif obj_type == 'row':
            r = self.racks[r_idx]; row = r["rows"][row_idx]
            row["x"] = max(0, min(row["x"] + dx, r["w"] - row["w"]))
            row["y"] = max(0, min(row["y"] + dy, r["h"] - row["h"]))
        elif obj_type == 'miner':
            row = self.racks[r_idx]["rows"][row_idx]; m = row["miners"][m_idx]
            m["x"] = max(0, min(m["x"] + dx, row["w"] - m["w"]))
            m["y"] = max(0, min(m["y"] + dy, row["h"] - m["h"]))

    def mousePressEvent(self, event):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self.panning = True; self.last_mouse_pos = event.pos(); return

        spos = self.canvas.mapFromGlobal(event.globalPos())
        lx, ly = spos.x() / self.zoom_level, spos.y() / self.zoom_level
        adj_lx = lx - self.current_img_offset.x()
        adj_ly = ly - self.current_img_offset.y()
        
        if event.button() == Qt.LeftButton:
            item = self.hit_test(adj_lx, adj_ly)
            if item:
                if event.modifiers() == Qt.ShiftModifier:
                    if item in self.selection: self.selection.remove(item)
                    else: self.selection.append(item)
                else:
                    if item not in self.selection: self.selection = [item]
                self.dragging = True
            else:
                self.selection = []
                self.dragging_img = True 
            
            self.last_mouse_pos = QPoint(int(lx), int(ly))
            self.update_ui_from_data(); self.update_display()

    def mouseMoveEvent(self, event):
        if self.panning:
            delta = event.pos() - self.last_mouse_pos
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - delta.y())
            self.last_mouse_pos = event.pos()
            return

        spos = self.canvas.mapFromGlobal(event.globalPos())
        lx, ly = spos.x() / self.zoom_level, spos.y() / self.zoom_level
        dx = int(lx - self.last_mouse_pos.x()); dy = int(ly - self.last_mouse_pos.y())

        if dx != 0 or dy != 0:
            if self.dragging:
                for item in self.selection: self.move_item(item, dx, dy)
            elif self.dragging_img:
                self.current_img_offset += QPoint(dx, dy)
            self.last_mouse_pos = QPoint(int(lx), int(ly))
            self.update_ui_from_data(); self.update_display()

    def mouseReleaseEvent(self, event):
        self.dragging = False; self.dragging_img = False; self.panning = False

    def hit_test(self, lx, ly):
        for r_idx, r in enumerate(self.racks):
            for row_idx, row in enumerate(r["rows"]):
                for m_idx, m in enumerate(row["miners"]):
                    if QRect(r["x"] + row["x"] + m["x"], r["y"] + row["y"] + m["y"], m["w"], m["h"]).contains(int(lx), int(ly)):
                        return ('miner', r_idx, row_idx, m_idx)
                if QRect(r["x"] + row["x"], r["y"] + row["y"], row["w"], row["h"]).contains(int(lx), int(ly)):
                    return ('row', r_idx, row_idx, -1)
            if QRect(r["x"], r["y"], r["w"], r["h"]).contains(int(lx), int(ly)):
                return ('rack', r_idx, -1, -1)
        return None

    def copy_selection(self):
        self.clipboard = []
        for item in self.selection:
            t, r_idx, row_idx, m_idx = item
            if t == 'rack': data = copy.deepcopy(self.racks[r_idx])
            elif t == 'row': data = copy.deepcopy(self.racks[r_idx]["rows"][row_idx])
            else: data = copy.deepcopy(self.racks[r_idx]["rows"][row_idx]["miners"][m_idx])
            self.clipboard.append((t, data))

    def paste_selection(self):
        new_selection = []
        for t, data in self.clipboard:
            if t == 'rack': 
                data["x"] += 20; data["y"] += 20; self.racks.append(data)
                new_selection.append(('rack', len(self.racks)-1, -1, -1))
            elif t == 'row' and self.get_primary_rack_idx() != -1:
                r_idx = self.get_primary_rack_idx()
                data["x"] += 10; data["y"] += 10; self.racks[r_idx]["rows"].append(data)
                new_selection.append(('row', r_idx, len(self.racks[r_idx]["rows"])-1, -1))
        if new_selection: self.selection = new_selection
        self.update_display()

    def align_h(self):
        if len(self.selection) < 2: return
        items = sorted(self.selection, key=lambda x: self.get_obj_coords(x)[0])
        _, first_y, _, _ = self.get_obj_coords(items[0])
        current_x, _, _, _ = self.get_obj_coords(items[0])
        for item in items:
            self.set_obj_pos(item, current_x, first_y)
            current_x += self.get_obj_coords(item)[2] + 5
        self.update_display()

    def align_v(self):
        if len(self.selection) < 2: return
        items = sorted(self.selection, key=lambda x: self.get_obj_coords(x)[1])
        first_x, _, _, _ = self.get_obj_coords(items[0])
        _, current_y, _, _ = self.get_obj_coords(items[0])
        for item in items:
            self.set_obj_pos(item, first_x, current_y)
            current_y += self.get_obj_coords(item)[3] + 5
        self.update_display()

    def get_primary_selection(self): return self.selection[0] if self.selection else None
    def get_primary_rack_idx(self):
        sel = self.get_primary_selection()
        return sel[1] if sel else -1

    def get_obj_coords(self, item):
        t, r_idx, row_idx, m_idx = item
        if t == 'rack': obj = self.racks[r_idx]
        elif t == 'row': obj = self.racks[r_idx]["rows"][row_idx]
        else: obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
        return obj["x"], obj["y"], obj["w"], obj["h"]

    def set_obj_pos(self, item, x, y):
        t, r_idx, row_idx, m_idx = item
        if t == 'rack': self.racks[r_idx]["x"], self.racks[r_idx]["y"] = x, y
        elif t == 'row': self.racks[r_idx]["rows"][row_idx]["x"], self.racks[r_idx]["rows"][row_idx]["y"] = x, y
        elif t == 'miner': self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["x"], self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["y"] = x, y

    def update_ui_from_data(self):
        sel = self.get_primary_selection()
        if not sel: return
        self.spn_x.blockSignals(True); self.spn_y.blockSignals(True); self.spn_w.blockSignals(True); self.spn_h.blockSignals(True)
        x, y, w, h = self.get_obj_coords(sel)
        self.spn_x.setValue(int(x)); self.spn_y.setValue(int(y))
        self.spn_w.setValue(int(w)); self.spn_h.setValue(int(h))
        self.spn_x.blockSignals(False); self.spn_y.blockSignals(False); self.spn_w.blockSignals(False); self.spn_h.blockSignals(False)

    def update_data_from_ui(self):
        sel = self.get_primary_selection()
        if not sel: return
        t, r_idx, row_idx, m_idx = sel
        if t == 'rack': obj = self.racks[r_idx]
        elif t == 'row': obj = self.racks[r_idx]["rows"][row_idx]
        else: obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
        obj["x"], obj["y"], obj["w"], obj["h"] = self.spn_x.value(), self.spn_y.value(), self.spn_w.value(), self.spn_h.value()
        self.update_display()

    def import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg)")
        if path: 
            self.all_data[self.current_type]["img"] = QPixmap(path)
            self.current_img_offset = QPoint((CANVAS_SIZE - self.current_template_image.width()) // 2, 
                                            (CANVAS_SIZE - self.current_template_image.height()) // 2)
            self.update_display()

    def update_display(self):
        pix = QPixmap(self.canvas.size())
        pix.fill(COLOR_CANVAS_BG)
        painter = QPainter(pix)
        painter.scale(self.zoom_level, self.zoom_level)
        
        ox, oy = self.current_img_offset.x(), self.current_img_offset.y()
        if not self.current_template_image.isNull(): 
            painter.drawPixmap(ox, oy, self.current_template_image)
            
        for r_idx, r in enumerate(self.racks):
            sel_r = any(s == ('rack', r_idx, -1, -1) for s in self.selection)
            painter.setBrush(COLOR_RACK_SEL if sel_r else COLOR_RACK)
            painter.setPen(QPen(Qt.white, 2 if sel_r else 1))
            painter.drawRect(ox + r["x"], oy + r["y"], r["w"], r["h"])
            for row_idx, row in enumerate(r["rows"]):
                sel_row = any(s == ('row', r_idx, row_idx, -1) for s in self.selection)
                painter.setBrush(COLOR_ROW_SEL if sel_row else COLOR_ROW)
                painter.setPen(QPen(Qt.white, 2 if sel_row else 1))
                rx, ry = ox + r["x"] + row["x"], oy + r["y"] + row["y"]
                painter.drawRect(rx, ry, row["w"], row["h"])
                for m_idx, m in enumerate(row["miners"]):
                    sel_m = any(s == ('miner', r_idx, row_idx, m_idx) for s in self.selection)
                    painter.setBrush(COLOR_MINER_SEL if sel_m else COLOR_MINER)
                    painter.setPen(QPen(Qt.black, 1))
                    painter.drawRect(rx + m["x"], ry + m["y"], m["w"], m["h"])
        painter.end()
        self.canvas.setPixmap(pix)

    def save_current_file(self):
        if not self.current_file_path: self.export_json()
        else: self._write_to_file(self.current_file_path)

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if path:
            self.current_file_path = path
            self._write_to_file(path)

    def _write_to_file(self, path):
        export_data = {}
        for r_type in self.all_data:
            export_data[r_type] = {
                "racks": self.all_data[r_type]["racks"],
                "offset": [self.all_data[r_type]["offset"].x(), self.all_data[r_type]["offset"].y()]
            }
        with open(path, 'w') as f: json.dump(export_data, f, indent=4)
        QMessageBox.information(self, "Done", f"Saved to {os.path.basename(path)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = RackStructureEditor(); ex.show()
    sys.exit(app.exec_())
