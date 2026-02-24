import sqlite3
import os
from settings import CATALOG_DB_PATH

class DatabaseHandler:
    def __init__(self):
        self.catalog_path = CATALOG_DB_PATH
        self._cache = {
            "miners": {}, # level: [data]
            "racks": []
        }
        self.preload_data()

    def preload_data(self):
        """One-time load of all data into memory to prevent redundant disk reads."""
        if not os.path.exists(self.catalog_path):
            return

        self._cache["miners"] = {}
        self._cache["racks"] = []

        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        
        try:
            # Preload all 6 levels of miners fetching set_global_id instead of text sets
            for lvl in range(1, 7):
                query = """
                    SELECT 
                        md.id, md.name, md.image_path, md.slot_size, md.set_global_id, md.set_sign_icon_path,
                        mls.raw_power, mls.bonus, mls.level_icon_path, mls.id
                    FROM miner_definitions md
                    JOIN miner_level_stats mls ON md.id = mls.miner_id
                    WHERE mls.level_number = ?
                """
                cursor.execute(query, (lvl,))
                self._cache["miners"][lvl] = cursor.fetchall()

            # Preload all racks including set_global_id at index 3
            cursor.execute("""
                SELECT id, name, rack_id_tag, set_global_id, rack_size, bonus_percent, image_path, set_sign_icon_path 
                FROM rack_definitions
            """)
            self._cache["racks"] = cursor.fetchall()

        except sqlite3.Error as e:
            print(f"[Database] SQL Error during preload: {e}")
        finally:
            conn.close()

    def get_all_miner_levels(self, miner_base_id):
        """Fetches all 6 level rows for a specific miner from the level stats table."""
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        query = "SELECT id, level_number, raw_power, bonus FROM miner_level_stats WHERE miner_id = ? ORDER BY level_number ASC"
        cursor.execute(query, (miner_base_id,))
        levels = cursor.fetchall()
        conn.close()
        return levels

    def update_miner_level_stats(self, stats_id, power_str, bonus_str):
        """Updates a specific level row with new raw power and bonus values."""
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        query = "UPDATE miner_level_stats SET raw_power = ?, bonus = ? WHERE id = ?"
        cursor.execute(query, (power_str, bonus_str, stats_id))
        conn.commit()
        conn.close()

    def set_db_path(self, path):
        if os.path.exists(path):
            self.catalog_path = path
            self.preload_data()
            return True
        return False

    def get_catalog_miners(self, level=1):
        return self._cache["miners"].get(level, [])

    def get_catalog_racks(self):
        return self._cache["racks"]

    def export_room_data(self, filepath, rooms_data):
        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS room_state (
                            room_id INTEGER,
                            slot_index INTEGER,
                            item_type TEXT,
                            item_id INTEGER,
                            custom_power REAL,
                            custom_bonus REAL,
                            image_path TEXT
                          )''')
        cursor.execute("DELETE FROM room_state")
        for room_id, slots in rooms_data.items():
            for slot_index, item in slots.items():
                cursor.execute('''INSERT INTO room_state 
                                  (room_id, slot_index, item_type, item_id, custom_power, custom_bonus, image_path) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (room_id, slot_index, item['type'], item.get('id'), 
                                item.get('power', 0), item.get('bonus', 0), item.get('image')))
        conn.commit()
        conn.close()

    def import_room_data(self, filepath):
        if not os.path.exists(filepath):
            return None
        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM room_state")
            rows = cursor.fetchall()
            imported_rooms = {}
            for row in rows:
                room_id = row[0]
                if room_id not in imported_rooms:
                    imported_rooms[room_id] = {}
                imported_rooms[room_id][row[1]] = {
                    'type': row[2], 'id': row[3], 'power': row[4],
                    'bonus': row[5], 'image': row[6]
                }
            return imported_rooms
        except sqlite3.Error as e:
            return None
        finally:
            conn.close()