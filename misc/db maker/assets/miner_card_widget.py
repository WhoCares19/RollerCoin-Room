import os
from PyQt5 import QtWidgets, QtGui, QtCore

class MinerCardWidget(QtWidgets.QWidget):
    """
    A custom widget to display individual miner information with a dark theme.
    Unified level structure: Handles level_0 (Legacy) through level_6.
    """
    def __init__(self, miner_data, project_root, parent=None):
        super().__init__(parent)
        self.miner_data = miner_data
        self.project_root = project_root
        self.current_level_index = 0 
        self.power_bonus_border_thickness = 1 
        self.init_ui()

    def _resolve_path(self, path):
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.project_root, path))

    def init_ui(self):
        self.setFixedWidth(200)
        self.setFixedHeight(300)
        self.setStyleSheet("border: 1px solid #444444; background-color: #252525; border-radius: 5px;")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        main_layout.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)

        # --- Image Container ---
        self.image_container = QtWidgets.QWidget()
        self.image_container.setFixedSize(180, 150)
        self.image_container.setStyleSheet("border: 1px solid #333333; background-color: transparent;") 
        
        image_container_layout = QtWidgets.QHBoxLayout(self.image_container)
        image_container_layout.setContentsMargins(0, 0, 0, 0)
        image_container_layout.setSpacing(0)

        self.miner_image_label = QtWidgets.QLabel()
        self.miner_image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.miner_image_label.setStyleSheet("background-color: transparent; border: none;")
        image_container_layout.addWidget(self.miner_image_label, 1)

        raw_img_path = self.miner_data.get("image_path")
        miner_image_path = self._resolve_path(raw_img_path)

        if miner_image_path and os.path.exists(miner_image_path):
            pixmap = QtGui.QPixmap(miner_image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.image_container.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.miner_image_label.setPixmap(scaled_pixmap)
            else:
                self.miner_image_label.setText("Load Error")
        else:
            self.miner_image_label.setText("No Image")
        
        # Icon Overlay: Set Sign (Top Left)
        self.set_sign_label = QtWidgets.QLabel(self.image_container)
        self.set_sign_label.setFixedSize(30, 30)
        self.set_sign_label.setAlignment(QtCore.Qt.AlignCenter)
        self.set_sign_label.move(5, 5) 
        self.set_sign_label.setStyleSheet("background-color: transparent; border: none;")
        self.set_sign_label.hide()

        # Icon Overlay: Level Indicator (Top Right)
        self.level_indicator_label = QtWidgets.QLabel(self.image_container)
        self.level_indicator_label.setFixedSize(40, 40)
        self.level_indicator_label.setAlignment(QtCore.Qt.AlignCenter)
        self.level_indicator_label.move(self.image_container.width() - 45, 5) 
        self.level_indicator_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.level_indicator_label.mousePressEvent = self._cycle_level
        self.level_indicator_label.setStyleSheet("background-color: rgba(0, 0, 0, 100); border: 0; border-radius: 5px;") 
        
        main_layout.addWidget(self.image_container)

        # Miner Name
        name_text = self.miner_data.get("miner_name") or "Unknown Miner"
        self.name_label = QtWidgets.QLabel(name_text)
        self.name_label.setObjectName("minerNameLabel")
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.name_label.setFixedWidth(180) 
        self.name_label.setStyleSheet("border: 1px solid #444444; color: #FFFFFF; background-color: #1E1E1E; padding: 2px;")
        main_layout.addWidget(self.name_label)

        # Power/Bonus Container
        self.power_bonus_container = QtWidgets.QWidget()
        self.power_bonus_container.setStyleSheet(f"border: {self.power_bonus_border_thickness}px solid #444444; background-color: #1E1E1E; border-radius: 3px;") 
        self.power_bonus_container.setFixedWidth(160) 
        
        power_bonus_layout = QtWidgets.QHBoxLayout(self.power_bonus_container)
        power_bonus_layout.setContentsMargins(2, 2, 2, 2)
        power_bonus_layout.setSpacing(0) 

        self.power_label = QtWidgets.QLabel("N/A")
        self.power_label.setObjectName("powerLabel")
        self.power_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter) 
        self.power_label.setStyleSheet("padding-left: 2px; border: none; color: #7DCEA0; font-weight: bold;") 
        power_bonus_layout.addWidget(self.power_label, 1)

        self.separator_label = QtWidgets.QLabel("") 
        self.separator_label.setObjectName("separatorLabel") 
        self.separator_label.setFixedWidth(1)
        self.separator_label.setStyleSheet("background-color: #444444; border: none;") 
        power_bonus_layout.addWidget(self.separator_label)

        self.bonus_label = QtWidgets.QLabel("N/A")
        self.bonus_label.setObjectName("bonusLabel")
        self.bonus_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter) 
        self.bonus_label.setStyleSheet("padding-right: 2px; border: none; color: #F1948A; font-weight: bold;") 
        power_bonus_layout.addWidget(self.bonus_label, 1)

        center_hbox = QtWidgets.QHBoxLayout()
        center_hbox.addStretch(1)
        center_hbox.addWidget(self.power_bonus_container)
        center_hbox.addStretch(1)
        main_layout.addLayout(center_hbox)

        main_layout.addStretch(1)
        self._update_display()

    def _get_available_level_keys(self):
        """Returns keys level_0 through level_6 if they exist in the data."""
        keys = []
        for i in range(0, 7):
            if f"level_{i}" in self.miner_data:
                keys.append(f"level_{i}")
        return keys

    def _cycle_level(self, event):
        keys = self._get_available_level_keys()
        if len(keys) > 1:
            self.current_level_index = (self.current_level_index + 1) % len(keys)
            self._update_display()

    def _update_display(self):
        keys = self._get_available_level_keys()
        if not keys:
            self.power_label.setText("N/A")
            self.bonus_label.setText("N/A")
            return

        if self.current_level_index >= len(keys):
            self.current_level_index = 0
            
        active_key = keys[self.current_level_index]
        level_data = self.miner_data.get(active_key)

        if level_data:
            p_val = level_data.get('raw_power') or "0.000"
            b_val = level_data.get('bonus') or "0.00"
            self.power_label.setText(f"{p_val}")
            self.bonus_label.setText(f"{b_val}%")
            
            raw_level_path = level_data.get("level_icon")
            level_img_path = self._resolve_path(raw_level_path)
            if level_img_path and os.path.exists(level_img_path):
                pixmap = QtGui.QPixmap(level_img_path)
                scaled = pixmap.scaled(self.level_indicator_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.level_indicator_label.setPixmap(scaled)
            else:
                self.level_indicator_label.setPixmap(QtGui.QPixmap())
                if active_key == "level_0":
                    self.level_indicator_label.setText("LEG")
                else:
                    self.level_indicator_label.setText(active_key.split('_')[1])
        else:
            self.power_label.setText("N/A")
            self.bonus_label.setText("N/A")

        # Set Sign Logic (Top Left)
        miner_sets_data = (self.miner_data.get("sets") or "").strip()
        raw_set_sign_path = self.miner_data.get("set_sign_icon_path") or "" 
        set_sign_icon_path = self._resolve_path(raw_set_sign_path)
        
        if miner_sets_data and miner_sets_data.lower() != "n/a" and set_sign_icon_path and os.path.exists(set_sign_icon_path):
            pixmap = QtGui.QPixmap(set_sign_icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.set_sign_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.set_sign_label.setPixmap(scaled_pixmap)
                self.set_sign_label.show()
            else:
                self.set_sign_label.hide()
        else:
            self.set_sign_label.hide()
