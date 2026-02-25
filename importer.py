import json
import re
import os

def clean_and_parse_json(file_path):
    """Reads a file, cleans trailing commas, and returns the parsed JSON object."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            raw_data = f.read()
            # Remove trailing commas that break standard JSON parsers
            clean_data = re.sub(r",\s*([\]}])", r"\1", raw_data)
            decoder = json.JSONDecoder()
            # Extract the first valid JSON object found
            json_content, _ = decoder.raw_decode(clean_data.strip())
            return json_content
    except Exception as e:
        print(f"[Import] Error parsing JSON: {e}")
        return None

def parse_personal_inventory(json_content):
    """
    Extracts miner/rack tags and quantities from various personal inventory formats.
    Returns a dictionary of {tag: quantity}.
    """
    id_quantities = {}
    
    # Handle list of objects or the "data": {"items": []} structure
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
        if m_id:
            m_id = str(m_id).lower().strip()
            id_quantities[m_id] = id_quantities.get(m_id, 0) + qty
            
    return id_quantities

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
    """
    Matches an external item (by tag or name+level) to a database item.
    Returns (db_item, source_string) or (None, error_string).
    """
    tag_str = str(tag).lower().strip()
    
    # 1. Try Primary ID (covers primary level_id_tags and Legacy IDs)
    item = tag_map.get(tag_str)
    if item:
        source = "Legacy ID" if item.get('is_legacy_item') else "Primary ID"
        return item, source
    
    # 2. Try Name/Level Fallback
    name_key = str(name).lower().strip()
    if level is not None:
        # Map game data: -1 is Legacy (0), 0 is Level 1 (1), etc.
        search_lvl = int(level) + 1 if int(level) != -1 else 0
        match = name_map.get((name_key, search_lvl))
        if match: return match, "Name/Level Fallback"
    else:
        # Check if it's a rack (no level)
        match = name_map.get(name_key)
        if match: return match, "Name Fallback"
        
    return None, "Not found in local database"