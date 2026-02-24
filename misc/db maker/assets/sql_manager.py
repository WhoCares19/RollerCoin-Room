import sqlite3
import os
import re

DB_NAME = "miner_catalog.db"

def _clean_value(value):
    """
    Helper function to convert strings into floats if needed.
    Returns None if value is empty or invalid.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    
    cleaned = re.sub(r'[^\d.]', '', str(value).replace(',', ''))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None

def _init_db(cursor):
    """
    Creates the relational schema for the Master Catalog.
    Includes Miners, Racks, and Sets with support for multiple ID layers.
    """
    # Table for global miner properties
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS miner_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            set_global_id TEXT,
            legacy_id TEXT,
            is_legacy TEXT,
            image_path TEXT,
            slot_size TEXT,
            sets TEXT,
            set_sign_icon_path TEXT,
            legacy_sign_icon_path TEXT
        )
    ''')

    # Table for level-specific stats (Miners)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS miner_level_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id INTEGER,
            level_number INTEGER,
            level_id_tag TEXT,
            raw_power TEXT, 
            bonus TEXT,
            level_icon_path TEXT,
            FOREIGN KEY (miner_id) REFERENCES miner_definitions (id) ON DELETE CASCADE
        )
    ''')

    # Table for racks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rack_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            rack_id_tag TEXT,
            set_global_id TEXT,
            rack_size TEXT,
            bonus_percent TEXT,
            image_path TEXT,
            rack_sets TEXT,
            set_sign_icon_path TEXT
        )
    ''')

    # Tables for Sets Rewards Info
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS set_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            set_global_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS set_level_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER,
            level_number INTEGER,
            requirement TEXT,
            reward_id_tag TEXT,
            power_reward_ghs TEXT,
            bonus_reward TEXT,
            FOREIGN KEY (set_id) REFERENCES set_definitions (id) ON DELETE CASCADE
        )
    ''')

def export_to_sql(miners_data, racks_data, sets_data):
    """
    Performs an Upsert operation. 
    Synchronizes the advanced ID structures for Miners, Racks, and Sets.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION")
        _init_db(cursor)

        # --- Export Miners ---
        for miner in miners_data:
            m_name = miner.get("miner_name")
            if not m_name: continue

            cursor.execute("SELECT id FROM miner_definitions WHERE name = ?", (m_name,))
            row = cursor.fetchone()
            
            # Data Mapping
            set_global_id = miner.get("set_global_id") or None
            legacy_id = miner.get("legacy_id") or None
            is_legacy = miner.get("is_legacy") or None
            image_path = miner.get("image_path") or None
            slot_size = miner.get("slot_size") or None
            sets = miner.get("sets") or None
            set_sign = miner.get("set_sign_icon_path") or None
            legacy_sign = miner.get("legacy_sign_icon_path") or None

            if row:
                miner_id = row[0]
                cursor.execute('''
                    UPDATE miner_definitions 
                    SET set_global_id = ?, legacy_id = ?, is_legacy = ?, image_path = ?, 
                        slot_size = ?, sets = ?, set_sign_icon_path = ?, legacy_sign_icon_path = ?
                    WHERE id = ?
                ''', (set_global_id, legacy_id, is_legacy, image_path, slot_size, 
                      sets, set_sign, legacy_sign, miner_id))
                cursor.execute("DELETE FROM miner_level_stats WHERE miner_id = ?", (miner_id,))
            else:
                cursor.execute('''
                    INSERT INTO miner_definitions (name, set_global_id, legacy_id, is_legacy, image_path, 
                                                   slot_size, sets, set_sign_icon_path, legacy_sign_icon_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (m_name, set_global_id, legacy_id, is_legacy, image_path, 
                      slot_size, sets, set_sign, legacy_sign))
                miner_id = cursor.lastrowid

            for i in range(1, 7):
                level_key = f"level_{i}"
                level_data = miner.get(level_key)
                if level_data:
                    cursor.execute('''
                        INSERT INTO miner_level_stats (miner_id, level_number, level_id_tag, raw_power, bonus, level_icon_path)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (miner_id, i, level_data.get("level_id_tag") or None, 
                          level_data.get("raw_power"), level_data.get("bonus"), 
                          level_data.get("level_icon") or None))

        # --- Export Racks ---
        for rack in racks_data:
            r_name = rack.get("rack_name")
            if not r_name: continue

            raw_pct = rack.get("rack_percent")
            cleaned_pct = None
            if raw_pct and str(raw_pct).strip():
                val = str(raw_pct).replace("%", "").replace(",", "").strip()
                try:
                    cleaned_pct = "{:.3f}".format(float(val))
                except ValueError:
                    cleaned_pct = None

            cursor.execute('''
                INSERT INTO rack_definitions (name, rack_id_tag, set_global_id, rack_size, bonus_percent, image_path, rack_sets, set_sign_icon_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    rack_id_tag = excluded.rack_id_tag,
                    set_global_id = excluded.set_global_id,
                    rack_size = excluded.rack_size,
                    bonus_percent = excluded.bonus_percent,
                    image_path = excluded.image_path,
                    rack_sets = excluded.rack_sets,
                    set_sign_icon_path = excluded.set_sign_icon_path
            ''', (r_name, rack.get("rack_id") or None, rack.get("set_global_id") or None, 
                  rack.get("rack_size") or None, cleaned_pct, rack.get("image_path") or None, 
                  rack.get("rack_sets") or None, rack.get("set_sign_icon_path") or None))

        # --- Export Sets ---
        for s_entry in sets_data:
            s_name = s_entry.get("set_name")
            if not s_name: continue

            cursor.execute("SELECT id FROM set_definitions WHERE name = ?", (s_name,))
            row = cursor.fetchone()
            
            s_global_id = s_entry.get("set_global_id") or None
            
            if row:
                set_id = row[0]
                cursor.execute("UPDATE set_definitions SET set_global_id = ? WHERE id = ?", (s_global_id, set_id))
                cursor.execute("DELETE FROM set_level_rewards WHERE set_id = ?", (set_id,))
            else:
                cursor.execute("INSERT INTO set_definitions (name, set_global_id) VALUES (?, ?)", (s_name, s_global_id))
                set_id = cursor.lastrowid

            for level in s_entry.get("levels", []):
                cursor.execute('''
                    INSERT INTO set_level_rewards (set_id, level_number, requirement, reward_id_tag, power_reward_ghs, bonus_reward)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (set_id, level["level_number"], level["requirement"], 
                      level.get("reward_id_tag"), level["power_reward"], level["bonus_reward"]))

        conn.commit()
        return True, "Catalog synced successfully with all ID layers."

    except sqlite3.Error as e:
        conn.rollback()
        return False, f"SQL Database Error: {e}"
    
    finally:
        conn.close()
