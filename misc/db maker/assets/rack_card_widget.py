import os
from PyQt5 import QtWidgets, QtGui, QtCore

class RackCardWidget(QtWidgets.QWidget):
    """
    A custom widget to display individual rack information with a dark theme.
    Uses the project root to resolve relative image paths correctly.
    Handles 'None' values from the parser to prevent crashes.
    """
    def __init__(self, rack_data, project_root, parent=None):
        super().__init__(parent)
        self.rack_data = rack_data
        self.project_root = project_root
        self.init_ui()

    def _resolve_path(self, path):
        """Resolves stored path relative to the defined project root."""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self.project_root, path))

    def init_ui(self):
        self.setFixedWidth(200) 
        self.setFixedHeight(280) 
        # Apply Dark Theme styles to the card
        self.setStyleSheet("border: 1px solid #444444; background-color: #252525; border-radius: 5px;")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        main_layout.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)

        # --- Image Area ---
        self.rack_image_container = QtWidgets.QWidget()
        self.rack_image_container.setFixedSize(180, 150)
        self.rack_image_container.setStyleSheet("border: 1px solid #333333; background-color: transparent;") 
        
        rack_image_container_layout = QtWidgets.QHBoxLayout(self.rack_image_container)
        rack_image_container_layout.setContentsMargins(0, 0, 0, 0)
        rack_image_container_layout.setSpacing(0)

        self.rack_image_label = QtWidgets.QLabel()
        self.rack_image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.rack_image_label.setStyleSheet("background-color: transparent; border: none;")
        rack_image_container_layout.addWidget(self.rack_image_label, 1)

        raw_img_path = self.rack_data.get("image_path")
        rack_image_path = self._resolve_path(raw_img_path)

        if rack_image_path and os.path.exists(rack_image_path):
            pixmap = QtGui.QPixmap(rack_image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.rack_image_container.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.rack_image_label.setPixmap(scaled_pixmap)
            else:
                self.rack_image_label.setText("Image Error")
        else:
            self.rack_image_label.setText("No Image")
        
        # Set Sign Overlay
        self.rack_set_sign_label = QtWidgets.QLabel(self.rack_image_container)
        self.rack_set_sign_label.setFixedSize(30, 30)
        self.rack_set_sign_label.setAlignment(QtCore.Qt.AlignCenter)
        self.rack_set_sign_label.move(5, 5)
        self.rack_set_sign_label.setStyleSheet("background-color: transparent; border: none;")
        self.rack_set_sign_label.hide()
        
        main_layout.addWidget(self.rack_image_container)

        # --- Rack Name ---
        rack_name_text = self.rack_data.get("rack_name") or "Unknown Rack"
        self.rack_name_label = QtWidgets.QLabel(rack_name_text)
        self.rack_name_label.setObjectName("rackNameLabel")
        self.rack_name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.rack_name_label.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.rack_name_label.setWordWrap(True)
        self.rack_name_label.setFixedWidth(180)
        self.rack_name_label.setStyleSheet("border: 1px solid #444444; color: #FFFFFF; background-color: #1E1E1E; padding: 2px;")
        main_layout.addWidget(self.rack_name_label)

        # --- Rack ID and Size Info ---
        r_id = self.rack_data.get("rack_id") or "N/A"
        r_size = self.rack_data.get("rack_size") or "N/A"
        info_text = f"ID: {r_id} | {r_size}"
        
        self.rack_info_label = QtWidgets.QLabel(info_text)
        self.rack_info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.rack_info_label.setStyleSheet("color: #AAAAAA; font-size: 10px; border: none;")
        main_layout.addWidget(self.rack_info_label)

        # --- Percent Display ---
        display_percent = (self.rack_data.get("rack_percent") or "N/A").strip()
        if display_percent != "N/A" and not display_percent.endswith("%"):
            display_percent += "%"

        self.rack_percent_label = QtWidgets.QLabel(display_percent)
        self.rack_percent_label.setObjectName("rackPercentLabel")
        self.rack_percent_label.setAlignment(QtCore.Qt.AlignCenter)
        self.rack_percent_label.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        self.rack_percent_label.setStyleSheet("color: #85C1E9; border: 1px solid #333333; background-color: #1E1E1E; padding: 2px; border-radius: 3px;")
        self.rack_percent_label.setFixedWidth(150)
        
        percent_center_hbox = QtWidgets.QHBoxLayout()
        percent_center_hbox.addStretch(1)
        percent_center_hbox.addWidget(self.rack_percent_label)
        percent_center_hbox.addStretch(1)
        main_layout.addLayout(percent_center_hbox)

        main_layout.addStretch(1)
        self._update_display()

    def _update_display(self):
        rack_sets_data = (self.rack_data.get("rack_sets") or "").strip()
        raw_set_path = self.rack_data.get("set_sign_icon_path") or ""
        set_sign_icon_path = self._resolve_path(raw_set_path)
        
        if rack_sets_data and rack_sets_data.lower() != "n/a" and set_sign_icon_path and os.path.exists(set_sign_icon_path):
            pixmap = QtGui.QPixmap(set_sign_icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.rack_set_sign_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                self.rack_set_sign_label.setPixmap(scaled_pixmap)
                self.rack_set_sign_label.show()
            else:
                self.rack_set_sign_label.hide()
        else:
            self.rack_set_sign_label.hide()
