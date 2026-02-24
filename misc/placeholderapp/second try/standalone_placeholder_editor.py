import sys
import json
import copy
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QSpinBox, 
                             QGroupBox, QFormLayout, QFileDialog, QMessageBox, 
                             QScrollArea, QGridLayout, QShortcut, QComboBox,
                             QDoubleSpinBox)
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QRect, QPoint

# Workspace Synchronization
TARGET_BOX_W = 100
TARGET_BOX_H = 140
BASE_CANVAS_W = 100
BASE_CANVAS_H = 140

COLOR_RACK = QColor(100, 100, 100, 150)
COLOR_RACK_SEL = QColor(150, 150, 150, 200)
COLOR_ROW = QColor(200, 0, 0, 100)
COLOR_ROW_SEL = QColor(255, 0, 0, 180)
COLOR_MINER = QColor(0, 150, 255, 150)
COLOR_MINER_SEL = QColor(0, 200, 255, 220)
COLOR_ICON = QColor(255, 255, 0, 180)
COLOR_ICON_SEL = QColor(255, 255, 255, 220)
COLOR_CANVAS_BG = QColor(30, 30, 30)

class ExterminatedScrollArea(QScrollArea):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setAlignment(Qt.AlignCenter)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: #121212; }")

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            mouse_pos = self.widget().mapFromGlobal(event.globalPos())
            focal_x = mouse_pos.x() / self.editor.zoom_level
            focal_y = mouse_pos.y() / self.editor.zoom_level

            delta = event.angleDelta().y()
            old_zoom = self.editor.zoom_level
            if delta > 0:
                self.editor.zoom_level = min(20.0, self.editor.zoom_level + 0.1)
            else:
                self.editor.zoom_level = max(1.0, self.editor.zoom_level - 0.1)

            if old_zoom != self.editor.zoom_level:
                self.editor.update_display()
                new_mouse_x = focal_x * self.editor.zoom_level
                new_mouse_y = focal_y * self.editor.zoom_level
                viewport_pos = self.viewport().mapFromGlobal(event.globalPos())
                self.horizontalScrollBar().setValue(int(new_mouse_x - viewport_pos.x()))
                self.verticalScrollBar().setValue(int(new_mouse_y - viewport_pos.y()))
            event.accept()
        else:
            event.accept()

class RackStructureEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Boundary Editor (Universal Icon Support)")
        self.resize(1100, 750)
        self.zoom_level = 1.0
        self.current_type = "Big Rack"
        self.all_data = {
            "Big Rack": {"racks": [], "img": QPixmap(), "offset": QPoint(0, 0), "img_scale": 1.0},
            "Small Rack": {"racks": [], "img": QPixmap(), "offset": QPoint(0, 0), "img_scale": 1.0}
        }
        self.selection = [] 
        self.clipboard = []
        self.current_file_path = None
        self.dragging = False      
        self.dragging_img = False  
        self.last_mouse_pos = QPoint()
        self.init_ui()
        self.setup_shortcuts()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(280)
        sidebar = QVBoxLayout(sidebar_widget)

        sidebar.addWidget(QLabel("<b>1. Mode & Graphics</b>"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Big Rack", "Small Rack"])
        self.type_combo.currentTextChanged.connect(self.switch_rack_type)
        sidebar.addWidget(self.type_combo)

        btn_img = QPushButton("Import Template Image"); btn_img.clicked.connect(self.import_template)
        sidebar.addWidget(btn_img)

        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Image Scale:"))
        self.spn_img_scale = QDoubleSpinBox()
        self.spn_img_scale.setRange(0.01, 10.0); self.spn_img_scale.setSingleStep(0.05); self.spn_img_scale.setValue(1.0)
        self.spn_img_scale.valueChanged.connect(self.update_image_scale); scale_layout.addWidget(self.spn_img_scale)
        sidebar.addLayout(scale_layout)

        sidebar.addWidget(QLabel("<b>2. Components</b>"))
        btn_rack = QPushButton("Add Rack Container"); btn_rack.clicked.connect(self.add_rack); sidebar.addWidget(btn_rack)
        btn_row = QPushButton("Add Row (2 Slot)"); btn_row.clicked.connect(self.add_row); sidebar.addWidget(btn_row)
        btn_miner = QPushButton("Add Slot (1 Slot)"); btn_miner.clicked.connect(self.add_miner); sidebar.addWidget(btn_miner)
        btn_icon = QPushButton("Add Set Icon (To Selected)"); btn_icon.setStyleSheet("color: black;")
        btn_icon.clicked.connect(self.add_set_icon); sidebar.addWidget(btn_icon)

        tool_group = QGroupBox("Tools")
        tool_layout = QGridLayout()
        btn_copy = QPushButton("Copy"); btn_copy.clicked.connect(self.copy_selection)
        btn_paste = QPushButton("Paste"); btn_paste.clicked.connect(self.paste_selection)
        btn_delete = QPushButton("Delete"); btn_delete.clicked.connect(self.delete_selection)
        tool_layout.addWidget(btn_copy, 0, 0); tool_layout.addWidget(btn_paste, 0, 1)
        tool_layout.addWidget(btn_delete, 1, 0, 1, 2)
        tool_group.setLayout(tool_layout); sidebar.addWidget(tool_group)

        self.prop_group = QGroupBox("Properties")
        prop_layout = QFormLayout()
        self.spn_x = QSpinBox(); self.spn_x.setRange(-5000, 5000); self.spn_x.valueChanged.connect(self.update_data_from_ui)
        self.spn_y = QSpinBox(); self.spn_y.setRange(-5000, 5000); self.spn_y.valueChanged.connect(self.update_data_from_ui)
        self.spn_w = QSpinBox(); self.spn_w.setRange(1, 5000); self.spn_w.valueChanged.connect(self.update_data_from_ui)
        self.spn_h = QSpinBox(); self.spn_h.setRange(1, 5000); self.spn_h.valueChanged.connect(self.update_data_from_ui)
        prop_layout.addRow("X:", self.spn_x); prop_layout.addRow("Y:", self.spn_y)
        prop_layout.addRow("Width:", self.spn_w); prop_layout.addRow("Height:", self.spn_h)
        self.prop_group.setLayout(prop_layout); sidebar.addWidget(self.prop_group)

        sidebar.addStretch()
        btn_save = QPushButton("Save Config"); btn_save.clicked.connect(self.save_current_file); sidebar.addWidget(btn_save)
        btn_exp = QPushButton("Export Master JSON"); btn_exp.setStyleSheet("background: #1a73e8; color: white; font-weight: bold;")
        btn_exp.clicked.connect(self.export_json); sidebar.addWidget(btn_exp)

        main_layout.addWidget(sidebar_widget)

        self.scroll_area = ExterminatedScrollArea(self)
        self.canvas = QLabel(); self.canvas.setStyleSheet("background: #1e1e1e; border: none;")
        self.scroll_area.setWidget(self.canvas); main_layout.addWidget(self.scroll_area)
        self.update_display()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_selection)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_selection)
        QShortcut(QKeySequence("Delete"), self, self.delete_selection)

    def switch_rack_type(self, new_type):
        self.current_type = new_type; self.selection = []
        self.spn_img_scale.blockSignals(True); self.spn_img_scale.setValue(self.all_data[self.current_type]["img_scale"])
        self.spn_img_scale.blockSignals(False); self.update_ui_from_data(); self.update_display()

    def update_image_scale(self, val):
        self.all_data[self.current_type]["img_scale"] = val; self.update_display()

    @property
    def racks(self): return self.all_data[self.current_type]["racks"]
    @property
    def current_img_offset(self): return self.all_data[self.current_type]["offset"]
    @current_img_offset.setter
    def current_img_offset(self, val): self.all_data[self.current_type]["offset"] = val
    @property
    def current_template_image(self): return self.all_data[self.current_type]["img"]

    def update_display(self):
        self.canvas.setFixedSize(int(BASE_CANVAS_W * self.zoom_level), int(BASE_CANVAS_H * self.zoom_level))
        pix = QPixmap(self.canvas.size()); pix.fill(COLOR_CANVAS_BG)
        painter = QPainter(pix)
        try:
            painter.scale(self.zoom_level, self.zoom_level)
            ox, oy = self.current_img_offset.x(), self.current_img_offset.y()
            img_scale = self.all_data[self.current_type]["img_scale"]
            if not self.current_template_image.isNull():
                sw = int(self.current_template_image.width() * img_scale)
                sh = int(self.current_template_image.height() * img_scale)
                painter.drawPixmap(ox, oy, self.current_template_image.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            painter.setBrush(Qt.NoBrush); painter.setPen(QPen(QColor(0, 120, 255), 2, Qt.DashLine))
            painter.drawRect(0, 0, TARGET_BOX_W, TARGET_BOX_H)

            for r_idx, r in enumerate(self.racks):
                painter.setBrush(COLOR_RACK_SEL if any(s == ('rack', r_idx, -1, -1) for s in self.selection) else COLOR_RACK)
                painter.setPen(QPen(Qt.white, 1)); painter.drawRect(r["x"], r["y"], r["w"], r["h"])
                for row_idx, row in enumerate(r["rows"]):
                    rx, ry = r["x"] + row["x"], r["y"] + row["y"]
                    painter.setBrush(COLOR_ROW_SEL if any(s == ('row', r_idx, row_idx, -1) for s in self.selection) else COLOR_ROW)
                    painter.setPen(QPen(Qt.white, 1)); painter.drawRect(rx, ry, row["w"], row["h"])
                    
                    if "set_icon" in row:
                        ico = row["set_icon"]
                        painter.setBrush(COLOR_ICON_SEL if any(s == ('icon', r_idx, row_idx, -1) for s in self.selection) else COLOR_ICON)
                        painter.setPen(QPen(Qt.black, 1)); painter.drawRect(rx + ico["x"], ry + ico["y"], ico["w"], ico["h"])

                    for m_idx, m in enumerate(row["miners"]):
                        mx, my = rx + m["x"], ry + m["y"]
                        painter.setBrush(COLOR_MINER_SEL if any(s == ('miner', r_idx, row_idx, m_idx) for s in self.selection) else COLOR_MINER)
                        painter.setPen(QPen(Qt.black, 1)); painter.drawRect(mx, my, m["w"], m["h"])
                        if "set_icon" in m:
                            ico = m["set_icon"]
                            painter.setBrush(COLOR_ICON_SEL if any(s == ('icon', r_idx, row_idx, m_idx) for s in self.selection) else COLOR_ICON)
                            painter.setPen(QPen(Qt.black, 1))
                            painter.drawRect(mx + ico["x"], my + ico["y"], ico["w"], ico["h"])
        finally: painter.end()
        self.canvas.setPixmap(pix)

    def mousePressEvent(self, event):
        spos = self.canvas.mapFrom(self, event.pos())
        lx, ly = spos.x() / self.zoom_level, spos.y() / self.zoom_level
        if event.button() == Qt.LeftButton:
            item = self.hit_test(lx, ly)
            if item:
                self.selection = [item] if event.modifiers() != Qt.ShiftModifier else (self.selection + [item] if item not in self.selection else [s for s in self.selection if s != item])
                self.dragging = True
            else: self.selection = []; self.dragging_img = True 
            self.last_mouse_pos = QPoint(int(lx), int(ly)); self.update_ui_from_data(); self.update_display()

    def mouseMoveEvent(self, event):
        spos = self.canvas.mapFrom(self, event.pos())
        lx, ly = spos.x() / self.zoom_level, spos.y() / self.zoom_level
        dx, dy = int(lx - self.last_mouse_pos.x()), int(ly - self.last_mouse_pos.y())
        if dx != 0 or dy != 0:
            if self.dragging:
                for item in self.selection: self.move_item(item, dx, dy)
            elif self.dragging_img: self.current_img_offset += QPoint(dx, dy)
            self.last_mouse_pos = QPoint(int(lx), int(ly)); self.update_ui_from_data(); self.update_display()

    def mouseReleaseEvent(self, event):
        self.dragging = False; self.dragging_img = False

    def hit_test(self, lx, ly):
        for r_idx, r in reversed(list(enumerate(self.racks))):
            for row_idx, row in reversed(list(enumerate(r["rows"]))):
                rx, ry = r["x"] + row["x"], r["y"] + row["y"]
                # 1. Check Miner Icons
                for m_idx, m in reversed(list(enumerate(row["miners"]))):
                    if "set_icon" in m:
                        ico = m["set_icon"]
                        if QRect(rx + m["x"] + ico["x"], ry + m["y"] + ico["y"], ico["w"], ico["h"]).contains(int(lx), int(ly)):
                            return ('icon', r_idx, row_idx, m_idx)
                # 2. Check Row Icon
                if "set_icon" in row:
                    ico = row["set_icon"]
                    if QRect(rx + ico["x"], ry + ico["y"], ico["w"], ico["h"]).contains(int(lx), int(ly)):
                        return ('icon', r_idx, row_idx, -1)
                # 3. Check Miners
                for m_idx, m in reversed(list(enumerate(row["miners"]))):
                    if QRect(rx + m["x"], ry + m["y"], m["w"], m["h"]).contains(int(lx), int(ly)):
                        return ('miner', r_idx, row_idx, m_idx)
                # 4. Check Row
                if QRect(rx, ry, row["w"], row["h"]).contains(int(lx), int(ly)):
                    return ('row', r_idx, row_idx, -1)
            # 5. Check Rack
            if QRect(r["x"], r["y"], r["w"], r["h"]).contains(int(lx), int(ly)):
                return ('rack', r_idx, -1, -1)
        return None

    def add_rack(self):
        self.racks.append({"x": 0, "y": 0, "w": 65, "h": 115, "rows": []})
        self.selection = [('rack', len(self.racks)-1, -1, -1)]; self.update_display()

    def add_row(self):
        r_idx = self.get_primary_rack_idx()
        if r_idx != -1:
            self.racks[r_idx]["rows"].append({"x": 5, "y": 5, "w": 55, "h": 20, "miners": []})
            self.selection = [('row', r_idx, len(self.racks[r_idx]["rows"])-1, -1)]; self.update_display()

    def add_miner(self):
        sel = self.get_primary_selection()
        if sel and sel[0] == 'row':
            _, r_idx, row_idx, _ = sel
            self.racks[r_idx]["rows"][row_idx]["miners"].append({"x": 5, "y": 5, "w": 20, "h": 15})
            self.selection = [('miner', r_idx, row_idx, len(self.racks[r_idx]["rows"][row_idx]["miners"])-1)]; self.update_display()

    def add_set_icon(self):
        sel = self.get_primary_selection()
        if not sel: return
        t, r_idx, row_idx, m_idx = sel
        if t == 'row':
            self.racks[r_idx]["rows"][row_idx]["set_icon"] = {"x": 2, "y": 2, "w": 8, "h": 8}
            self.selection = [('icon', r_idx, row_idx, -1)]
        elif t == 'miner':
            self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"] = {"x": 2, "y": 2, "w": 8, "h": 8}
            self.selection = [('icon', r_idx, row_idx, m_idx)]
        self.update_display()

    def delete_selection(self):
        if not self.selection: return
        for t, r_idx, row_idx, m_idx in self.selection:
            try:
                if t == 'icon':
                    if m_idx == -1: del self.racks[r_idx]["rows"][row_idx]["set_icon"]
                    else: del self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"]
                elif t == 'miner': del self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
                elif t == 'row': del self.racks[r_idx]["rows"][row_idx]
                elif t == 'rack': del self.racks[r_idx]
            except: continue
        self.selection = []; self.update_display()

    def copy_selection(self):
        self.clipboard = []
        for t, r_idx, row_idx, m_idx in self.selection:
            if t == 'rack': d = copy.deepcopy(self.racks[r_idx])
            elif t == 'row': d = copy.deepcopy(self.racks[r_idx]["rows"][row_idx])
            elif t == 'miner': d = copy.deepcopy(self.racks[r_idx]["rows"][row_idx]["miners"][m_idx])
            else:
                if m_idx == -1: d = copy.deepcopy(self.racks[r_idx]["rows"][row_idx]["set_icon"])
                else: d = copy.deepcopy(self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"])
            self.clipboard.append((t, d))

    def paste_selection(self):
        for t, data in self.clipboard:
            if t == 'rack': data["x"] += 10; data["y"] += 10; self.racks.append(data)
            elif t == 'row' and self.get_primary_rack_idx() != -1: self.racks[self.get_primary_rack_idx()]["rows"].append(data)
        self.update_display()

    def get_primary_selection(self): return self.selection[0] if self.selection else None
    def get_primary_rack_idx(self): return self.get_primary_selection()[1] if self.get_primary_selection() else -1

    def update_ui_from_data(self):
        sel = self.get_primary_selection()
        if not sel: return
        self.spn_x.blockSignals(True); self.spn_y.blockSignals(True); self.spn_w.blockSignals(True); self.spn_h.blockSignals(True)
        x, y, w, h = self.get_obj_coords(sel)
        self.spn_x.setValue(int(x)); self.spn_y.setValue(int(y)); self.spn_w.setValue(int(w)); self.spn_h.setValue(int(h))
        self.spn_x.blockSignals(False); self.spn_y.blockSignals(False); self.spn_w.blockSignals(False); self.spn_h.blockSignals(False)

    def get_obj_coords(self, item):
        t, r_idx, row_idx, m_idx = item
        if t == 'rack': obj = self.racks[r_idx]
        elif t == 'row': obj = self.racks[r_idx]["rows"][row_idx]
        elif t == 'miner': obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
        else:
            if m_idx == -1: obj = self.racks[r_idx]["rows"][row_idx]["set_icon"]
            else: obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"]
        return obj["x"], obj["y"], obj["w"], obj["h"]

    def update_data_from_ui(self):
        sel = self.get_primary_selection()
        if not sel: return
        t, r_idx, row_idx, m_idx = sel
        if t == 'rack': obj = self.racks[r_idx]
        elif t == 'row': obj = self.racks[r_idx]["rows"][row_idx]
        elif t == 'miner': obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]
        else:
            if m_idx == -1: obj = self.racks[r_idx]["rows"][row_idx]["set_icon"]
            else: obj = self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"]
        obj["x"], obj["y"], obj["w"], obj["h"] = self.spn_x.value(), self.spn_y.value(), self.spn_w.value(), self.spn_h.value()
        self.update_display()

    def move_item(self, item, dx, dy):
        t, r_idx, row_idx, m_idx = item
        if t == 'rack': self.racks[r_idx]["x"] += dx; self.racks[r_idx]["y"] += dy
        elif t == 'row': self.racks[r_idx]["rows"][row_idx]["x"] += dx; self.racks[r_idx]["rows"][row_idx]["y"] += dy
        elif t == 'miner': self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["x"] += dx; self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["y"] += dy
        else:
            if m_idx == -1:
                self.racks[r_idx]["rows"][row_idx]["set_icon"]["x"] += dx; self.racks[r_idx]["rows"][row_idx]["set_icon"]["y"] += dy
            else:
                self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"]["x"] += dx; self.racks[r_idx]["rows"][row_idx]["miners"][m_idx]["set_icon"]["y"] += dy

    def import_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg)")
        if path: self.all_data[self.current_type]["img"] = QPixmap(path); self.update_display()

    def save_current_file(self):
        if not self.current_file_path: self.export_json()
        else: self._write_to_file(self.current_file_path)

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "", "JSON Files (*.json)")
        if path: self.current_file_path = path; self._write_to_file(path)

    def _write_to_file(self, path):
        export_data = {}
        for r_type in self.all_data:
            scale = self.all_data[r_type]["img_scale"]; off_img = self.all_data[r_type]["offset"]
            racks = []
            for r in self.all_data[r_type]["racks"]:
                rows_list = []
                for rw in r["rows"]:
                    miners_list = []
                    for m in rw["miners"]:
                        m_entry = {"x": m["x"], "y": m["y"], "w": m["w"], "h": m["h"]}
                        if "set_icon" in m: m_entry["set_icon"] = m["set_icon"]
                        miners_list.append(m_entry)
                    rw_entry = {"x": rw["x"], "y": rw["y"], "w": rw["w"], "h": rw["h"], "1 slot": miners_list}
                    if "set_icon" in rw: rw_entry["set_icon"] = rw["set_icon"]
                    rows_list.append(rw_entry)
                racks.append({"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"], "2 slot": rows_list})
            export_data[r_type] = {"metadata": {"img_scale": scale, "boundary": [TARGET_BOX_W, TARGET_BOX_H]}, "racks": racks}
        with open(path, 'w') as f: json.dump(export_data, f, indent=4)
        QMessageBox.information(self, "Done", f"JSON saved to {os.path.basename(path)}")

if __name__ == "__main__":
    app = QApplication(sys.argv); ex = RackStructureEditor(); ex.show(); sys.exit(app.exec())
