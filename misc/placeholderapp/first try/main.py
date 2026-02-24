import sys
import json
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QComboBox, QDoubleSpinBox, 
                             QGraphicsScene, QGraphicsPixmapItem, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter

# Custom Module Imports
from widgets import ZoomView
from styles import DARK_STYLESHEET
from rows import ManagedItem

class RackApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rack Placeholder Designer")
        self.resize(1400, 900)
        
        QApplication.setStyle("Fusion")
        self.setStyleSheet(DARK_STYLESHEET)

        self.json_path = None
        self.last_dir = ""
        self.clipboard = [] 
        self.current_rack_key = "Rack 8"
        
        # Scene with fixed size
        self.scene = QGraphicsScene(0, 0, 1200, 900)  # FIXED SIZE
        self.scene.selectionChanged.connect(self.sync_controls_to_selection)
        
        self.view = ZoomView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(Qt.GlobalColor.black)

        self.background_item = None
        self.rack_item = None

        # Storage
        self.racks_storage = {
            "Rack 8": {"rack_pos": [100, 100], "rack_size": [400, 600], "items": []},
            "Rack 6": {"rack_pos": [100, 100], "rack_size": [400, 450], "items": []}
        }

        self.init_ui()
        self.setup_initial_rack()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        controls = QVBoxLayout()

        rack_group = QGroupBox("Rack Configuration")
        rack_layout = QFormLayout()
        self.rack_selector = QComboBox()
        self.rack_selector.addItems(["Rack 8", "Rack 6"])
        self.rack_selector.currentTextChanged.connect(self.switch_rack)
        
        self.rack_w_spin = QDoubleSpinBox(); self.rack_w_spin.setRange(10, 5000)
        self.rack_w_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.rack_h_spin = QDoubleSpinBox(); self.rack_h_spin.setRange(10, 5000)
        self.rack_h_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        self.rack_w_spin.valueChanged.connect(self.update_rack_dims)
        self.rack_h_spin.valueChanged.connect(self.update_rack_dims)
        
        rack_layout.addRow("Active Rack:", self.rack_selector)
        rack_layout.addRow("Width:", self.rack_w_spin)
        rack_layout.addRow("Height:", self.rack_h_spin)
        rack_group.setLayout(rack_layout)
        controls.addWidget(rack_group)

        row_group = QGroupBox("Row Category")
        row_layout = QVBoxLayout()
        btn_add_row = QPushButton("Add Row (2-Slot)")
        btn_add_row.clicked.connect(self.add_row_item)
        btn_add_slot = QPushButton("Add 1 Slot")
        btn_add_slot.clicked.connect(self.add_slot_item)

        self.sel_w_spin = QDoubleSpinBox(); self.sel_w_spin.setRange(1, 5000)
        self.sel_w_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.sel_h_spin = QDoubleSpinBox(); self.sel_h_spin.setRange(1, 5000)
        self.sel_h_spin.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        self.sel_w_spin.valueChanged.connect(self.apply_dims_to_selection)
        self.sel_h_spin.valueChanged.connect(self.apply_dims_to_selection)

        btn_align_w = QPushButton("Align Width (X)")
        btn_align_w.clicked.connect(self.align_rows_x)
        btn_align_h = QPushButton("Align Height (Y)")
        btn_align_h.clicked.connect(self.align_rows_y)

        row_layout.addWidget(btn_add_row); row_layout.addWidget(btn_add_slot)
        dim_form = QFormLayout()
        dim_form.addRow("Sel. Width:", self.sel_w_spin)
        dim_form.addRow("Sel. Height:", self.sel_h_spin)
        row_layout.addLayout(dim_form)
        row_layout.addWidget(btn_align_w); row_layout.addWidget(btn_align_h)
        row_group.setLayout(row_layout)
        controls.addWidget(row_group)

        asset_group = QGroupBox("Import Assets")
        asset_layout = QVBoxLayout()
        btn_rack_img = QPushButton("Import Rack Image")
        btn_rack_img.clicked.connect(self.import_rack_bg)
        btn_2s_img = QPushButton("Import 2 slot miner")
        btn_2s_img.clicked.connect(self.import_miner_ref)
        btn_1s_img = QPushButton("Import 1 slot miner")
        btn_1s_img.clicked.connect(self.import_miner_ref)
        asset_layout.addWidget(btn_rack_img); asset_layout.addWidget(btn_2s_img); asset_layout.addWidget(btn_1s_img)
        asset_group.setLayout(asset_layout)
        controls.addWidget(asset_group)

        btn_export = QPushButton("Export JSON (Set File)")
        btn_export.clicked.connect(self.export_json_dialog)
        self.btn_save = QPushButton("Save"); self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_all_to_file)
        controls.addWidget(btn_export); controls.addWidget(self.btn_save)

        controls.addStretch()
        layout.addLayout(controls, 1)
        layout.addWidget(self.view, 4)

    def setup_initial_rack(self):
        self.rack_item = ManagedItem("rack", (100, 100, 255))
        self.scene.addItem(self.rack_item)
        data = self.racks_storage[self.current_rack_key]
        self.rack_w_spin.setValue(data["rack_size"][0])
        self.rack_h_spin.setValue(data["rack_size"][1])
        self.rack_item.setPos(*data["rack_pos"])
        self.view.centerOn(self.rack_item)

    def update_rack_dims(self):
        if self.rack_item:
            self.rack_item.set_rect_centered(self.rack_w_spin.value(), self.rack_h_spin.value())

    # --- Rows / Slots ---
    def add_row_item(self):
        center = self.view.mapToScene(self.view.viewport().rect().center())
        row = ManagedItem("row", (70, 180, 70))
        row.setRect(0, 0, 300, 80)
        row.setPos(center.x() - 150, center.y() - 40)
        self.scene.addItem(row)
        self.scene.clearSelection(); row.setSelected(True)

    def add_slot_item(self):
        selected = self.scene.selectedItems()
        parent = next((i for i in selected if isinstance(i, ManagedItem) and i.item_type == "row"), None)
        w, h = (parent.rect().width()/2, parent.rect().height()) if parent else (100, 50)
        slot = ManagedItem("1-slot", (200, 70, 70), parent)
        slot.setRect(0, 0, w, h)
        if not parent:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            slot.setPos(center.x() - w/2, center.y() - h/2)
            self.scene.addItem(slot)
        else:
            slot.setPos(0, 0)
        self.scene.clearSelection(); slot.setSelected(True)

    def sync_controls_to_selection(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], ManagedItem):
            item = selected[0]
            self.sel_w_spin.blockSignals(True)
            self.sel_h_spin.blockSignals(True)
            self.sel_w_spin.setValue(item.rect().width())
            self.sel_h_spin.setValue(item.rect().height())
            self.sel_w_spin.blockSignals(False)
            self.sel_h_spin.blockSignals(False)

    def apply_dims_to_selection(self):
        selected = self.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], ManagedItem):
            selected[0].set_rect_centered(self.sel_w_spin.value(), self.sel_h_spin.value())

    # --- Alignment ---
    def align_rows_x(self):
        selected = [i for i in self.scene.selectedItems() if isinstance(i, ManagedItem)]
        if len(selected) < 2: return
        tx = selected[0].x()
        for i in selected[1:]: i.setX(tx)

    def align_rows_y(self):
        selected = [i for i in self.scene.selectedItems() if isinstance(i, ManagedItem)]
        if len(selected) < 2: return
        ty = selected[0].y()
        for i in selected[1:]: i.setY(ty)

    # --- Import / Export ---
    def import_rack_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Rack Image", self.last_dir, "Images (*.png *.jpg *.jpeg)")
        if path:
            self.last_dir = os.path.dirname(path)
            if self.background_item: self.scene.removeItem(self.background_item)
            pix = QPixmap(path); self.background_item = QGraphicsPixmapItem(pix)
            self.background_item.setFlags(self.background_item.GraphicsItemFlag.ItemIsMovable | self.background_item.GraphicsItemFlag.ItemIsSelectable)
            self.background_item.setZValue(-10)
            center = self.view.mapToScene(self.view.viewport().rect().center())
            self.background_item.setPos(center.x() - pix.width()/2, center.y() - pix.height()/2)
            self.scene.addItem(self.background_item)

    def import_miner_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Miner Image", self.last_dir, "Images (*.png *.jpg *.jpeg)")
        if path:
            self.last_dir = os.path.dirname(path)
            pix = QPixmap(path)
            item = QGraphicsPixmapItem(pix)
            item.setFlags(item.GraphicsItemFlag.ItemIsMovable | item.GraphicsItemFlag.ItemIsSelectable)
            item.setOpacity(0.7)
            item.setZValue(5)
            center = self.view.mapToScene(self.view.viewport().rect().center())
            item.setPos(center.x() - pix.width()/2, center.y() - pix.height()/2)
            self.scene.addItem(item)

    # --- Rack Switching / Saving ---
    def switch_rack(self, new_key):
        self.save_to_memory()
        self.current_rack_key = new_key
        for item in list(self.scene.items()):
            if isinstance(item, ManagedItem) and item.item_type != 'rack':
                self.scene.removeItem(item)
        data = self.racks_storage[new_key]
        self.rack_w_spin.setValue(data["rack_size"][0])
        self.rack_h_spin.setValue(data["rack_size"][1])
        self.rack_item.setPos(data["rack_pos"][0], data["rack_pos"][1])
        for idata in data["items"]:
            color = (70, 180, 70) if idata["type"] == "row" else (200, 70, 70)
            item = ManagedItem(idata["type"], color)
            item.setRect(0, 0, idata["size"][0], idata["size"][1])
            item.setPos(idata["pos"][0], idata["pos"][1])
            self.scene.addItem(item)
            for sdata in idata.get("slots", []):
                slot = ManagedItem("1-slot", (200, 70, 70), item)
                slot.setRect(0, 0, sdata["size"][0], sdata["size"][1])
                slot.setPos(sdata["pos"][0], sdata["pos"][1])

    def save_to_memory(self):
        items_data = []
        for item in self.scene.items():
            if isinstance(item, ManagedItem) and item.item_type == 'row' and not item.parentItem():
                row_data = {"type": "row", "pos": [item.x(), item.y()], "size": [item.rect().width(), item.rect().height()], "slots": []}
                for child in item.childItems():
                    if isinstance(child, ManagedItem):
                        row_data["slots"].append({"type": child.item_type, "pos": [child.x(), child.y()], "size": [child.rect().width(), child.rect().height()]})
                items_data.append(row_data)
        self.racks_storage[self.current_rack_key] = {
            "rack_pos": [self.rack_item.x(), self.rack_item.y()],
            "rack_size": [self.rack_item.rect().width(), self.rack_item.rect().height()],
            "items": items_data
        }

    def export_json_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", self.last_dir, "JSON Files (*.json)")
        if path:
            self.last_dir = os.path.dirname(path)
            self.json_path = path
            self.btn_save.setEnabled(True)
            self.save_all_to_file()

    def save_all_to_file(self):
        if not self.json_path: return
        self.save_to_memory()
        with open(self.json_path, 'w') as f:
            json.dump(self.racks_storage, f, indent=4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RackApp()
    window.show()
    sys.exit(app.exec())
