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
        """One-time load of all data into memory including the level_id_tag for matching."""
        if not os.path.exists(self.catalog_path):
            return

        self._cache["miners"] = {}
        self._cache["racks"] = []

        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        
        try:
            for lvl in range(1, 7):
                query = """
                    SELECT 
                        md.id, md.name, md.image_path, md.slot_size, md.set_global_id, md.set_sign_icon_path,
                        mls.raw_power, mls.bonus, mls.level_icon_path, mls.id, mls.level_id_tag
                    FROM miner_definitions md
                    JOIN miner_level_stats mls ON md.id = mls.miner_id
                    WHERE mls.level_number = ?
                """
                cursor.execute(query, (lvl,))
                self._cache["miners"][lvl] = cursor.fetchall()

            cursor.execute("""
                SELECT id, name, rack_id_tag, set_global_id, rack_size, bonus_percent, image_path, set_sign_icon_path 
                FROM rack_definitions
            """)
            self._cache["racks"] = cursor.fetchall()

        except sqlite3.Error as e:
            print(f"[Database] SQL Error during preload: {e}")
        finally:
            conn.close()

    def get_all_set_definitions(self):
        """Returns all sets for the UI dropdown: (id, name, set_global_id)"""
        if not os.path.exists(self.catalog_path): return []
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        # Removed set_sign_icon_path to prevent crash
        cursor.execute("SELECT id, name, set_global_id FROM set_definitions")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_set_icon_lookup(self, set_global_id):
        """Looks up an existing set icon path from miners or racks assigned to this set."""
        if not set_global_id or not os.path.exists(self.catalog_path):
            return ""
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        
        icon_path = ""
        # Check miners first
        cursor.execute("SELECT set_sign_icon_path FROM miner_definitions WHERE set_global_id = ? AND set_sign_icon_path != '' LIMIT 1", (set_global_id,))
        row = cursor.fetchone()
        if row:
            icon_path = row[0]
        else:
            # Check racks
            cursor.execute("SELECT set_sign_icon_path FROM rack_definitions WHERE set_global_id = ? AND set_sign_icon_path != '' LIMIT 1", (set_global_id,))
            row = cursor.fetchone()
            if row:
                icon_path = row[0]
                
        conn.close()
        return icon_path

    def ensure_set_exists(self, name, global_id):
        """Checks if a set global_id exists, otherwise creates it with just name and ID."""
        if not global_id: return None
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        cursor.execute("SELECT set_global_id FROM set_definitions WHERE set_global_id = ?", (global_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO set_definitions (name, set_global_id)
                VALUES (?, ?)
            """, (name, global_id))
            conn.commit()
        conn.close()
        return global_id

    def add_custom_miner_full(self, base_data, levels_list):
        """
        base_data: {'name', 'image_path', 'slot_size', 'set_global_id', 'set_sign_icon_path'}
        levels_list: list of {'lvl', 'power', 'bonus', 'level_id_tag'}
        """
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM miner_definitions WHERE name = ?", (base_data['name'],))
            row = cursor.fetchone()
            if row:
                miner_id = row[0]
                cursor.execute("""
                    UPDATE miner_definitions 
                    SET image_path=?, slot_size=?, set_global_id=?, set_sign_icon_path=?
                    WHERE id=?
                """, (base_data['image_path'], base_data['slot_size'], 
                      base_data['set_global_id'], base_data['set_sign_icon_path'], miner_id))
            else:
                cursor.execute("""
                    INSERT INTO miner_definitions (name, image_path, slot_size, set_global_id, set_sign_icon_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (base_data['name'], base_data['image_path'], base_data['slot_size'], 
                      base_data['set_global_id'], base_data['set_sign_icon_path']))
                miner_id = cursor.lastrowid

            for l in levels_list:
                lvl_num = l['lvl']
                icon_path = os.path.join("assets", "Levels", f"lvl{lvl_num}.png").replace("\\", "/")
                
                cursor.execute("SELECT id FROM miner_level_stats WHERE miner_id = ? AND level_number = ?", 
                             (miner_id, lvl_num))
                stat_row = cursor.fetchone()
                if stat_row:
                    cursor.execute("""
                        UPDATE miner_level_stats 
                        SET raw_power=?, bonus=?, level_icon_path=?, level_id_tag=?
                        WHERE id=?
                    """, (l['power'], l['bonus'], icon_path, l['level_id_tag'], stat_row[0]))
                else:
                    cursor.execute("""
                        INSERT INTO miner_level_stats (miner_id, level_number, raw_power, bonus, level_icon_path, level_id_tag)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (miner_id, lvl_num, l['power'], l['bonus'], icon_path, l['level_id_tag']))
            conn.commit()
        finally:
            conn.close()

    def add_custom_rack_full(self, rack_data):
        """rack_data: {'name', 'rack_id_tag', 'set_global_id', 'rack_size', 'bonus_percent', 'image_path', 'set_sign_icon_path'}"""
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM rack_definitions WHERE name = ?", (rack_data['name'],))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE rack_definitions 
                    SET rack_id_tag=?, set_global_id=?, rack_size=?, bonus_percent=?, image_path=?, set_sign_icon_path=?
                    WHERE name=?
                """, (rack_data['rack_id_tag'], rack_data['set_global_id'], rack_data['rack_size'],
                      rack_data['bonus_percent'], rack_data['image_path'], rack_data['set_sign_icon_path'], rack_data['name']))
            else:
                cursor.execute("""
                    INSERT INTO rack_definitions (name, rack_id_tag, set_global_id, rack_size, bonus_percent, image_path, set_sign_icon_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (rack_data['name'], rack_data['rack_id_tag'], rack_data['set_global_id'], 
                      rack_data['rack_size'], rack_data['bonus_percent'], rack_data['image_path'], rack_data['set_sign_icon_path']))
            conn.commit()
        finally:
            conn.close()

    def get_all_miner_levels(self, miner_base_id):
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        query = "SELECT id, level_number, raw_power, bonus FROM miner_level_stats WHERE miner_id = ? ORDER BY level_number ASC"
        cursor.execute(query, (miner_base_id,))
        levels = cursor.fetchall()
        conn.close()
        return levels

    def update_miner_level_stats(self, stats_id, power_str, bonus_str):
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