import os
import json
import copy
import urllib.request
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
import importer
from settings import CONFIG_PATH

class RoomIOManager:
    def __init__(self, main_window):
        self.main = main_window

    def load_app_config(self):
        """Loads the application configuration from config.json."""
        defaults = {
            "room_path": "", 
            "inv_path": "", 
            "auto_import_room": True, 
            "auto_import_inv": True, 
            "backup_room": True, 
            "backup_inv": True, 
            "pause_gifs": False, 
            "pause_hamsters": False,
            "light_theme": False, 
            "auto_save": True, 
            "rack_scale": 1.0, 
            "room_count": 4, 
            "room1_bg": "", 
            "room_rest_bg": ""
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    defaults.update(json.load(f))
            except:
                pass
        return defaults

    def save_app_config(self):
        """Saves the current configuration to config.json."""
        self.main.config.update({"room_count": len(self.main.room_views)})
        if not os.path.exists(os.path.dirname(CONFIG_PATH)):
            os.makedirs(os.path.dirname(CONFIG_PATH))
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.main.config, f, indent=2)

    def auto_save(self):
        """Serializes current room state to the player_room.json file."""
        p = self.main._autosave_path or self.main.config.get("room_path")
        if self.main.config.get("auto_save", True) and not self.main._is_importing and p:
            data = []
            for i, v in enumerate(self.main.room_views):
                data.append({
                    "room_index": i,
                    "room_uuid": v.room_uuid,
                    "racks": [
                        {
                            "rack_data": p_h.rack.data,
                            "rows": p_h.rack.rows_data,
                            "is_locked": p_h.rack.is_locked
                        } for p_h in v.placeholders if p_h.rack
                    ]
                })
            with open(p, "w") as f:
                json.dump(data, f, indent=2)
            
            self.main.save_status_label.setText("Saved")
            QTimer.singleShot(1500, lambda: self.main.save_status_label.setText(""))

    def fetch_web_data(self, uid):
        """Downloads room configuration from RollerCoin API."""
        try:
            url = f"https://rollercoin.com/api/game/room-config/{uid}"
            with urllib.request.urlopen(url) as r:
                return r.read().decode('utf-8')
        except Exception as e:
            print(f"[IO Manager] Web Fetch Error: {e}")
            return None