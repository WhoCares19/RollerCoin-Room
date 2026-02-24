import sqlite3
import os
from settings import UNIT_MULTIPLIERS, LEAGUES, CATALOG_DB_PATH

def parse_hashrate_to_gh(input_val):
    if input_val is None:
        return 0.0
    if isinstance(input_val, (int, float)):
        return float(input_val)
    clean_str = str(input_val).strip()
    if not clean_str:
        return 0.0
    try:
        sorted_units = sorted(UNIT_MULTIPLIERS.keys(), key=len, reverse=True)
        for unit in sorted_units:
            if unit.lower() in clean_str.lower():
                num_part = clean_str.lower().replace(unit.lower(), "").strip()
                return float(num_part) * UNIT_MULTIPLIERS[unit]
        return float(clean_str)
    except:
        return 0.0

def parse_percentage_to_float(input_val):
    if input_val is None:
        return 0.0
    if isinstance(input_val, (int, float)):
        return float(input_val)
    try:
        clean_str = str(input_val).strip().replace("%", "")
        return float(clean_str) if clean_str else 0.0
    except:
        return 0.0

def format_hashrate(gh_s):
    try:
        val = float(gh_s)
    except:
        val = 0.0
    if val == 0:
        return "0.000 Gh/s"
    sorted_units = sorted(UNIT_MULTIPLIERS.items(), key=lambda x: x[1], reverse=True)
    for unit, multiplier in sorted_units:
        if val >= multiplier:
            return f"{val / multiplier:.3f} {unit}"
    return f"{val:.3f} Gh/s"

def get_league_info(total_gh_s):
    val = parse_hashrate_to_gh(total_gh_s)
    for name, min_val, max_val, icon_file in LEAGUES:
        if min_val <= val < max_val:
            return name, icon_file
    return "Unknown", "bronze_1.png"

def get_league_tooltip(total_gh_s):
    name, _ = get_league_info(total_gh_s)
    return f'You are in <span style="color:#992438; font-weight:bold;">{name}</span> League'

def calculate_power_breakdown(rooms_state_dict):
    total_raw_miner_power = 0.0
    total_unique_bonus_pct = 0.0
    total_rack_bonus_power = 0.0
    
    room_base_power = {} 
    room_rack_bonus = {} 
    room_flat_set_power = {} 

    seen_miner_bonus = set()

    for room_id, racks_list in rooms_state_dict.items():
        room_base_power[room_id] = 0.0
        room_rack_bonus[room_id] = 0.0
        room_flat_set_power[room_id] = 0.0
        
        for rack_entry in racks_list:
            rack_data = rack_entry.get('rack_data', {})
            rack_set_id = rack_data.get('set_global_id')
            r_bonus_pct = rack_entry.get('rack_bonus', 0.0)
            
            for row in rack_entry.get('rows', []):
                miners_in_row = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                for miner in miners_in_row:
                    if not isinstance(miner, dict):
                        continue
                    
                    p_val = miner.get('power_val', 0.0)
                    b_val = miner.get('bonus_val', 0.0)
                    
                    total_raw_miner_power += p_val
                    room_base_power[room_id] += p_val

                    miner_name = miner.get('name')
                    lvl = miner.get('lvl')
                    key = (miner_name, lvl)
                    if key not in seen_miner_bonus:
                        total_unique_bonus_pct += b_val
                        seen_miner_bonus.add(key)

                    if r_bonus_pct > 0:
                        rb_val = (p_val * (r_bonus_pct / 100))
                        total_rack_bonus_power += rb_val
                        room_rack_bonus[room_id] += rb_val

    additional_set_bonus_multiplier = 0.0
    additional_set_base_power = 0.0

    if os.path.exists(CATALOG_DB_PATH):
        all_set_miners_per_rack = {} 
        for room_id, racks_list in rooms_state_dict.items():
            for rack_entry in racks_list:
                rack_data = rack_entry.get('rack_data', {})
                rack_set_id = rack_data.get('set_global_id')
                if not rack_set_id: continue
                
                matches = []
                for row in rack_entry.get('rows', []):
                    miners_in_row = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                    for miner in miners_in_row:
                        if isinstance(miner, dict) and miner.get('set_global_id') == rack_set_id:
                            matches.append(miner)
                
                if rack_set_id not in all_set_miners_per_rack:
                    all_set_miners_per_rack[rack_set_id] = []
                all_set_miners_per_rack[rack_set_id].append((room_id, matches))

        conn = sqlite3.connect(CATALOG_DB_PATH)
        cursor = conn.cursor()
        for s_id, list_of_tuples in all_set_miners_per_rack.items():
            best_tuple = max(list_of_tuples, key=lambda x: len(x[1]))
            best_room_id = best_tuple[0]
            count = len(best_tuple[1])
            
            cursor.execute("""
                SELECT COALESCE(slr.bonus_reward, 0), COALESCE(slr.power_reward_ghs, 0)
                FROM set_level_rewards slr
                JOIN set_definitions sd ON slr.set_id = sd.id
                WHERE sd.set_global_id = ? AND CAST(slr.requirement AS INTEGER) <= ?
                ORDER BY CAST(slr.requirement AS INTEGER) ASC
            """, (s_id, count))
            rewards = cursor.fetchall()

            if rewards:
                prize_bonus = sum(float(r[0]) for r in rewards)
                prize_power = sum(float(r[1]) for r in rewards)
                additional_set_bonus_multiplier += prize_bonus
                additional_set_base_power += prize_power
                if best_room_id in room_flat_set_power:
                    room_flat_set_power[best_room_id] += prize_power
        conn.close()

    final_raw_base = total_raw_miner_power + additional_set_base_power
    final_global_bonus_pct = total_unique_bonus_pct + additional_set_bonus_multiplier
    
    bonus_power_hashrate = final_raw_base * (final_global_bonus_pct / 100)
    total_power = final_raw_base + bonus_power_hashrate + total_rack_bonus_power

    room_details = []
    for r_id in room_base_power:
        r_base = room_base_power[r_id] + room_flat_set_power[r_id]
        r_bonus_contrib = r_base * (final_global_bonus_pct / 100)
        r_rack_bonus = room_rack_bonus[r_id]
        r_total = r_base + r_bonus_contrib + r_rack_bonus
        room_details.append({
            "room_id": r_id,
            "total": r_total
        })

    return {
        "miners_base": final_raw_base,
        "bonus_power": bonus_power_hashrate,
        "bonus_percent": final_global_bonus_pct,
        "rack_bonus": total_rack_bonus_power,
        "total": total_power,
        "room_details": room_details
    }

def calculate_single_rack_stats(rack_data, rows_data, global_bonus_pct):
    rack_bonus_pct = rack_data.get('bonus_val', 0.0)
    rack_set_id = rack_data.get('set_global_id')
    
    miner_list = []
    matching_set_miners = []
    rack_total_miner_base = 0.0
    rack_total_miner_unique_bonus = 0.0
    seen_locally = set()

    for r_idx, row in enumerate(rows_data):
        miners_in_row = []
        if isinstance(row, dict):
            miners_in_row = [(0, row)]
        elif isinstance(row, list):
            for s_idx, m in enumerate(row):
                if m: miners_in_row.append((s_idx, m))
                
        for s_idx, miner in miners_in_row:
            p_val = miner.get('power_val', 0.0)
            b_val = miner.get('bonus_val', 0.0)
            img_path = miner.get('image_path', '')
            
            rack_total_miner_base += p_val
            
            miner_name = miner.get('name')
            lvl = miner.get('lvl')
            key = (miner_name, lvl)
            if key not in seen_locally:
                rack_total_miner_unique_bonus += b_val
                seen_locally.add(key)
            
            if rack_set_id and miner.get('set_global_id') == rack_set_id:
                matching_set_miners.append(miner)
            
            miner_list.append({
                'name': miner.get('name'), 
                'lvl': miner.get('lvl'), 
                'power': p_val, 
                'bonus': b_val,
                'image_path': img_path,
                'row': r_idx,
                'slot': s_idx
            })

    additional_set_bonus = 0.0
    additional_set_power = 0.0
    set_name = "Unknown Set"

    if rack_set_id and matching_set_miners and os.path.exists(CATALOG_DB_PATH):
        conn = sqlite3.connect(CATALOG_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(slr.bonus_reward, 0), COALESCE(slr.power_reward_ghs, 0), 
                   CAST(slr.requirement AS INTEGER), sd.name
            FROM set_level_rewards slr
            JOIN set_definitions sd ON slr.set_id = sd.id
            WHERE sd.set_global_id = ? AND CAST(slr.requirement AS INTEGER) <= ?
            ORDER BY CAST(slr.requirement AS INTEGER) ASC
        """, (rack_set_id, len(matching_set_miners)))
        rewards = cursor.fetchall()
        conn.close()

        if rewards:
            set_name = rewards[0][3]
            prize_bonus = sum(float(r[0]) for r in rewards)
            prize_power = sum(float(r[1]) for r in rewards)
            additional_set_bonus = prize_bonus
            additional_set_power = prize_power

    final_base = rack_total_miner_base + additional_set_power
    final_multiplier = rack_total_miner_unique_bonus + additional_set_bonus
    
    bonus_power_val = final_base * (final_multiplier / 100)
    rack_bonus_power = rack_total_miner_base * (rack_bonus_pct / 100)
    
    total = final_base + bonus_power_val + rack_bonus_power

    return {
        "miners": miner_list,
        "base_power": final_base,
        "miner_bonus_pct": rack_total_miner_unique_bonus,
        "miner_bonus_power": final_base * (rack_total_miner_unique_bonus / 100),
        "set_bonus_pct": additional_set_bonus,
        "set_bonus_power": final_base * (additional_set_bonus / 100),
        "set_flat_power": additional_set_power,
        "rack_bonus_pct": rack_bonus_pct,
        "rack_bonus": rack_bonus_power,
        "total_power": total,
        "set_name": set_name,
        "is_set_rack": True if rack_set_id else False
    }