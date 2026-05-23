import json
import re
import os
import shutil

PLAYER_INFO_DIR = os.path.join("assets", "player_Info")
BACKUP_DIR = os.path.join(PLAYER_INFO_DIR, "Player Data Backups")
ROOMS_DIR = os.path.join("assets", "rooms")

def ensure_player_info_dir():
    """Ensures the directory for player info exists."""
    if not os.path.exists(PLAYER_INFO_DIR):
        os.makedirs(PLAYER_INFO_DIR)

def ensure_backup_dir():
    """Ensures the backup directory exists."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def ensure_rooms_dir():
    """Ensures the background rooms directory exists."""
    if not os.path.exists(ROOMS_DIR):
        os.makedirs(ROOMS_DIR)

def backup_player_data(filename):
    """
    Copies a file from player_Info to the backup folder.
    Overwrites the previous backup to ensure only the latest version is kept.
    """
    source = os.path.join(PLAYER_INFO_DIR, filename)
    if not os.path.exists(source):
        return False
    
    ensure_backup_dir()
    destination = os.path.join(BACKUP_DIR, filename)
    try:
        shutil.copy2(source, destination)
        return True
    except Exception as e:
        print(f"[Importer] Backup Error for {filename}: {e}")
        return False

def copy_image_to_rooms(source_path):
    """
    Checks if an image is in assets/rooms. If not, copies it there.
    Returns the relative path inside assets/rooms.
    """
    if not source_path or not os.path.exists(source_path):
        return ""

    ensure_rooms_dir()
    
    # Normalize paths for comparison
    abs_source = os.path.abspath(source_path)
    abs_rooms_dir = os.path.abspath(ROOMS_DIR)
    filename = os.path.basename(source_path)
    target_path = os.path.join(ROOMS_DIR, filename)
    abs_target = os.path.abspath(target_path)

    # If it's already in the target folder, just return the relative path
    if os.path.commonpath([abs_source, abs_rooms_dir]) == abs_rooms_dir:
        return os.path.join("assets", "rooms", filename).replace("\\", "/")

    # Copy if source is different from target
    try:
        if abs_source != abs_target:
            shutil.copy2(source_path, target_path)
        return os.path.join("assets", "rooms", filename).replace("\\", "/")
    except Exception as e:
        print(f"[Importer] Error moving background image: {e}")
        return source_path

def extract_json_blocks(text):
    """
    Depth-tracking algorithm to extract valid JSON blocks from a string.
    """
    blocks = []
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(text[start:i + 1])
                start = None
    return blocks

def process_generic_pasted_inventory(raw_text):
    """
    Extracts id and quantity pairs generically. 
    Matches keys like 'id', 'miner_id', or 'rack_id'.
    """
    json_blocks = extract_json_blocks(raw_text)
    if not json_blocks:
        return None

    result_items = []
    for block in json_blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data", {}).get("items", data.get("items", []))

        for item in items:
            found_id = item.get("id") or item.get("miner_id") or item.get("rack_id")
            found_qty = item.get("quantity")

            if found_id is not None and found_qty is not None:
                result_items.append({
                    "miner_id": str(found_id).lower().strip(),
                    "quantity": int(found_qty),
                    "name": item.get("name", "Unknown")
                })
    
    if not result_items:
        return None
        
    return {"items": result_items}

def clean_and_parse_json(file_path_or_text, is_text=False):
    """Cleans trailing commas and returns parsed JSON object."""
    try:
        if is_text:
            raw_data = file_path_or_text
        else:
            if not os.path.exists(file_path_or_text):
                return None
            with open(file_path_or_text, "r", encoding='utf-8') as f:
                raw_data = f.read()
        
        clean_data = re.sub(r",\s*([\]}])", r"\1", raw_data)
        decoder = json.JSONDecoder()
        json_content, _ = decoder.raw_decode(clean_data.strip())
        return json_content
    except Exception as e:
        print(f"[Importer] Error parsing JSON: {e}")
        return None

def parse_personal_inventory(json_content):
    """Extracts tags and quantities from various personal inventory formats."""
    raw_entries = []
    items_list = []
    if isinstance(json_content, dict):
        if "data" in json_content and "items" in json_content["data"]:
            items_list = json_content["data"]["items"]
        elif "items" in json_content:
            items_list = json_content["items"]
    elif isinstance(json_content, list):
        items_list = json_content

    for raw_item in items_list:
        m_id = raw_item.get("miner_id")
        qty = int(raw_item.get("quantity", 1))
        name = raw_item.get("name", "Unknown")
        if m_id:
            m_id = str(m_id).lower().strip()
            raw_entries.append({"miner_id": m_id, "quantity": qty, "name": name})
    return raw_entries

def find_mining_data_block(obj):
    """Recursively searches for the block containing 'rooms' and 'racks' keys."""
    if isinstance(obj, dict):
        if "rooms" in obj and "racks" in obj:
            return obj
        for val in obj.values():
            found = find_mining_data_block(val)
            if found: return found
    return None

def find_item_robust(tag, name, level, tag_map, name_map):
    """Matches an external item to a local database item."""
    tag_str = str(tag).lower().strip()
    item = tag_map.get(tag_str)
    if item:
        source = "Legacy ID" if item.get('is_legacy_item') else "Primary ID"
        return item, source
    
    name_key = str(name).lower().strip()
    if level is not None:
        search_lvl = int(level) + 1 if int(level) != -1 else 0
        match = name_map.get((name_key, search_lvl))
        if match: return match, "Name/Level Fallback"
    else:
        match = name_map.get(name_key)
        if match: return match, "Name Fallback"
    return None, "Not found in local database"

def save_to_player_info(filename, data):
    """Saves data as JSON into the player_Info folder."""
    ensure_player_info_dir()
    path = os.path.join(PLAYER_INFO_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return path

def export_missing_items_report(missing_list, save_path):
    """Writes the list of unknown items (names only) to a text file."""
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            for name in missing_list:
                f.write(f"{name}\n")
        return True
    except Exception as e:
        print(f"[Importer] Export Error: {e}")
        return False