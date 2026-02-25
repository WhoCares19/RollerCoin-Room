import csv
import os

def parse_miner_csv(file_path, mapping=None):
    """
    Parses a CSV file for miner data using a 25-column structure.
    A: Name, B: Slot, C-H: Power L1-6, I: Legacy Power, J-O: Bonus L1-6, 
    P: Legacy Bonus, Q: Set Name, R: Set Global ID, S-X: Level IDs L1-6, Y: Legacy ID.
    Legacy data is stored as 'level_0'.
    """
    miners_data = []
    
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_idx, row in enumerate(reader):
                if row_idx < 1:
                    continue

                if not row or len(row) < 25:
                    continue
                
                if not any(cell.strip() for cell in row):
                    continue

                # 1. Basic Info
                miner_name = row[0].strip()
                if not miner_name:
                    continue

                raw_slot = row[1].strip()
                slot_size = "".join(filter(str.isdigit, raw_slot))
                if not slot_size or slot_size not in ["1", "2"]:
                    slot_size = "1"

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

                # Legacy Fields extraction
                legacy_p = clean_num(row[8].strip(), 3)
                legacy_b = clean_num(row[15].strip(), 2)
                
                set_name = row[16].strip()
                set_global_id = row[17].strip()
                legacy_id = row[24].strip()

                miner = {
                    "miner_name": miner_name,
                    "slot_size": slot_size,
                    "sets": set_name if set_name else None,
                    "set_global_id": set_global_id if set_global_id else None,
                    "legacy_id": legacy_id if legacy_id else None,
                    "is_legacy": "yes" if (legacy_p or legacy_b) else "no",
                    "image_path": "",
                    "set_sign_icon_path": ""
                }

                # Store Legacy data as Level 0
                if miner["is_legacy"] == "yes":
                    miner["level_0"] = {
                        "raw_power": legacy_p if legacy_p is not None else "0.000",
                        "bonus": legacy_b if legacy_b is not None else "0.00",
                        "level_id_tag": legacy_id if legacy_id else None,
                        "level_icon": ""
                    }

                # 2. Level-Specific Data (Power, Bonus, and IDs)
                # Power: C-H (2-7) | Bonus: J-O (9-14) | IDs: S-X (18-23)
                for i in range(6):
                    p_raw = row[2 + i].strip()
                    b_raw = row[9 + i].strip()
                    l_id  = row[18 + i].strip()
                    
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
