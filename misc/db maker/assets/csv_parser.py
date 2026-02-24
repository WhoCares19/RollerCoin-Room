import csv
import os

def parse_miner_csv(file_path, mapping=None):
    """
    Parses a CSV file for miner data using a strict 23-column structure.
    A: Name, B: Slot, C-H: Power L1-6, I-N: Bonus L1-6, O: Set Name, 
    P: Set Global ID, Q-V: Level IDs L1-6, W: Legacy ID.
    Starts reading from Row 2. Returns None for empty cells.
    """
    miners_data = []
    
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_idx, row in enumerate(reader):
                # Skip Row 1 (header), processing starts from Row 2
                if row_idx < 1:
                    continue

                # Ensure the row has enough columns for index 22 (Column W)
                if not row or len(row) < 23:
                    continue
                
                # Check if the row is effectively empty
                if not any(cell.strip() for cell in row):
                    continue

                # 1. Basic Info
                miner_name = row[0].strip()       # Column A
                if not miner_name:
                    continue

                raw_slot = row[1].strip()         # Column B
                slot_size = "".join(filter(str.isdigit, raw_slot))
                if not slot_size or slot_size not in ["1", "2"]:
                    slot_size = "1"

                set_name = row[14].strip()        # Column O
                set_global_id = row[15].strip()   # Column P
                legacy_id = row[22].strip()       # Column W

                miner = {
                    "miner_name": miner_name,
                    "slot_size": slot_size,
                    "sets": set_name if set_name else None,
                    "set_global_id": set_global_id if set_global_id else None,
                    "legacy_id": legacy_id if legacy_id else None,
                    "image_path": "",
                    "legacy_sign_icon_path": ""
                }

                # Helper to clean numeric strings or return None if empty
                def clean_num(val, decimals):
                    if not val or not val.strip(): 
                        return None
                    cleaned = val.strip().replace(",", "").replace("%", "").lower()
                    cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")
                    if not cleaned:
                        return None
                    try:
                        return "{:.{}f}".format(float(cleaned), decimals)
                    except ValueError:
                        return None

                # 2. Level-Specific Data (Power, Bonus, and IDs)
                # Power: C-H (2-7) | Bonus: I-N (8-13) | IDs: Q-V (16-21)
                for i in range(6):
                    p_raw = row[2 + i].strip()
                    b_raw = row[8 + i].strip()
                    l_id  = row[16 + i].strip()
                    
                    # Skip level if both Power and Bonus are empty
                    if not p_raw and not b_raw:
                        continue

                    p_val = clean_num(p_raw, 3)
                    b_val = clean_num(b_raw, 2)

                    miner[f"level_{i+1}"] = {
                        "raw_power": p_val if p_val is not None else "0.000",
                        "bonus": b_val if b_val is not None else "0.00",
                        "level_id_tag": l_id if l_id else None,
                        "level_icon": ""
                    }

                miners_data.append(miner)

    except Exception as e:
        print(f"DEBUG: Error processing Miner CSV: {e}")
        miners_data = []

    return miners_data
