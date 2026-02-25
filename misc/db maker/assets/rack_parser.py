import csv
import os

def parse_rack_csv(file_path):
    """
    Parses a CSV file for rack data using a strict 6-column structure.
    A: Name, B: Percent, C: Set Name, D: Set Global ID, E: Size, F: Individual IDs.
    Starts reading from Row 2. Returns None for empty cells.
    """
    racks_data = []
    
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            for row_idx, row in enumerate(reader):
                # Skip Row 1 (header), processing starts from Row 2
                if row_idx < 1:
                    continue

                # Ensure the row has enough columns for index 5 (Column F)
                if not row or len(row) < 6:
                    continue
                
                # Check if the row is effectively empty
                if not any(cell.strip() for cell in row):
                    continue

                rack_name = row[0].strip()       # Column A
                if not rack_name:
                    continue

                rack_percent = row[1].strip()    # Column B
                rack_sets = row[2].strip()       # Column C
                set_global_id = row[3].strip()   # Column D
                rack_size = row[4].strip()       # Column E
                rack_id = row[5].strip()         # Column F

                racks_data.append({
                    "rack_name": rack_name,
                    "rack_percent": rack_percent if rack_percent else None,
                    "rack_sets": rack_sets if rack_sets else None,
                    "set_global_id": set_global_id if set_global_id else None,
                    "rack_size": rack_size if rack_size else None,
                    "rack_id": rack_id if rack_id else None,
                    "image_path": ""  # Initialized empty
                })

    except Exception as e:
        print(f"DEBUG: Error processing Rack CSV: {e}")
        racks_data = []

    return racks_data
