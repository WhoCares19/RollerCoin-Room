import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QStackedWidget
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from ui_components import HoverMenuButton

class RoomUIBuilder:
    def __init__(self, main_window):
        self.main = main_window

    def build_ui(self):
        """Constructs the full layout of the MainWindow."""
        central = QWidget()
        self.main.setCentralWidget(central)
        self.main.main_layout = QVBoxLayout(central)
        self.main.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main.main_layout.setSpacing(0)
        
        # 1. Header Row
        header = QHBoxLayout()
        header.setContentsMargins(10, 5, 10, 5)
        header.setSpacing(10) 
        
        self.main.power_label = QLabel("Total Power: 0.000 Gh/s")
        self.main.power_label.setObjectName("PowerLabel")
        self.main.power_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.main.power_label.mousePressEvent = self.main.on_power_label_clicked
        self.main.power_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.main.power_label.customContextMenuRequested.connect(self.main.on_power_label_context_menu)
        
        self.main.delta_label = QLabel("")
        self.main.delta_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        
        # League Section
        league_box = QHBoxLayout()
        league_box.setSpacing(5)
        
        self.main.league_in_lbl = QLabel("You are in:")
        self.main.league_icon = QLabel()
        self.main.league_icon.setFixedSize(28, 28)
        
        self.main.to_reach_lbl = QLabel("To reach:")
        self.main.next_league_icon = QLabel()
        self.main.next_league_icon.setFixedSize(28, 28)
        self.main.league_needed_lbl = QLabel("")
        
        league_box.addWidget(self.main.league_in_lbl)
        league_box.addWidget(self.main.league_icon)
        league_box.addWidget(self.main.to_reach_lbl)
        league_box.addWidget(self.main.next_league_icon)
        league_box.addWidget(self.main.league_needed_lbl)
        
        header.addWidget(self.main.power_label)
        header.addWidget(self.main.delta_label)
        header.addLayout(league_box)
        header.addStretch()
        
        # Buttons
        self.main.add_btn = HoverMenuButton("Add")
        act_add_rack = QAction("Add Rack", self.main)
        act_add_rack.triggered.connect(self.main.on_add_rack_clicked)
        act_add_miner = QAction("Add Miner", self.main)
        act_add_miner.triggered.connect(self.main.on_add_miner_clicked)
        self.main.add_btn.menu.addAction(act_add_rack)
        self.main.add_btn.menu.addAction(act_add_miner)
        header.addWidget(self.main.add_btn)
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.main.on_save_clicked)
        header.addWidget(btn_save)
        
        self.main.import_btn = HoverMenuButton("Import")
        act_import_room = QAction("Import Player Room", self.main)
        act_import_room.triggered.connect(self.main.on_import_room_clicked)
        act_import_inventory = QAction("Import Personal Inventory", self.main)
        act_import_inventory.triggered.connect(self.main.on_import_inventory_clicked)
        act_import_mgr = QAction("Import Manager", self.main)
        act_import_mgr.triggered.connect(self.main.on_import_clicked)
        self.main.import_btn.menu.addActions([act_import_room, act_import_inventory, act_import_mgr])
        header.addWidget(self.main.import_btn)
        
        self.main.settings_btn = QPushButton("Settings")
        self.main.settings_btn.clicked.connect(self.main.on_settings_clicked)
        header.addWidget(self.main.settings_btn)
        self.main.main_layout.addLayout(header)
        
        # 2. Room Navigation Row
        self.main.room_nav = QHBoxLayout()
        self.main.room_nav.setContentsMargins(10, 0, 10, 5)
        self.main.room_nav.setSpacing(5) 
        
        add_rm = QPushButton("+")
        add_rm.setFixedWidth(30)
        add_rm.clicked.connect(self.main.on_plus_clicked)
        self.main.room_nav.addWidget(add_rm)
        self.main.room_nav.addStretch()
        
        self.main.clear_btn = HoverMenuButton("Clear")
        self.setup_clear_menu()
        self.main.room_nav.addWidget(self.main.clear_btn)
        self.main.main_layout.addLayout(self.main.room_nav)
        
        # 3. Room Stack & Inventory
        self.main.room_stack = QStackedWidget()
        self.main.room_stack.currentChanged.connect(self.main.handle_room_switch)
        
        self.main.main_layout.addWidget(self.main.room_stack, stretch=2)
        self.main.main_layout.addWidget(self.main.inventory, stretch=1)
        
        # 4. Status Bar
        self.main.save_status_label = QLabel("Saved")
        self.main.save_status_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.main.save_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.main.main_layout.addWidget(self.main.save_status_label)

    def setup_clear_menu(self):
        """Builds the options for the Clear dropdown."""
        m = self.main.clear_btn.menu
        m.addAction("Clear current room", lambda: self.main.room_stack.currentWidget().clear_room(False))
        m.addAction("Clear current room of all miners", lambda: self.main.room_stack.currentWidget().clear_room(True))
        m.addAction("Clear all rooms", lambda: self.main.clear_all_rooms(False, True))
        m.addAction("Clear all miners", lambda: self.main.clear_all_rooms(True, True))