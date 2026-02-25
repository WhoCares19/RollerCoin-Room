import csv
import os

def parse_set_csv(file_path):
    """
    Parses a CSV file for Set data using a strict 22-column structure.
    A: Name, B-F: Reqs, G-K: Power Rewards, L-P: Bonus Rewards, Q-U: Level IDs, V: Global ID.
    Starts reading from Row 2. Returns None for empty cells.
    """
    sets_data = []
    
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_idx, row in enumerate(reader):
                # Skip Row 1 (header), processing starts from Row 2
                if row_idx < 1:
                    continue

                # Ensure the row has enough columns for index 21 (Column V)
                if not row or len(row) < 22:
                    continue
                
                # Check if the row is effectively empty
                if not any(cell.strip() for cell in row):
                    continue

                set_name = row[0].strip()       # Column A
                if not set_name:
                    continue

                set_global_id = row[21].strip() # Column V

                # Helper to clean numeric strings or return None if empty
                def clean_num(val, decimals):
                    if not val or not val.strip(): 
                        return None
                    
                    cleaned = val.strip().replace(",", "").replace("%", "").lower().replace("gh/s", "")
                    cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")
                    
                    if not cleaned:
                        return None
                        
                    try:
                        return "{:.{}f}".format(float(cleaned), decimals)
                    except ValueError:
                        return None

                set_entry = {
                    "set_name": set_name,
                    "set_global_id": set_global_id if set_global_id else None,
                    "levels": []
                }

                # Process 5 levels of rewards
                # Reqs: B-F (1-5) | Power: G-K (6-10) | Bonus: L-P (11-15) | IDs: Q-U (16-20)
                for i in range(5):
                    req_text = row[1 + i].strip()
                    p_val = clean_num(row[6 + i], 3)
                    b_val = clean_num(row[11 + i], 2)
                    l_id = row[16 + i].strip()

                    # Skip level if all fields are empty
                    if not req_text and p_val is None and b_val is None and not l_id:
                        continue

                    set_entry["levels"].append({
                        "level_number": i + 1,
                        "requirement": req_text if req_text else None,
                        "power_reward": p_val,
                        "bonus_reward": b_val,
                        "reward_id_tag": l_id if l_id else None
                    })

                sets_data.append(set_entry)

    except Exception as e:
        print(f"DEBUG: Error processing Sets CSV: {e}")
        sets_data = []

    return sets_data
