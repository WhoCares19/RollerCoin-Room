import sqlite3
import os
from decimal import Decimal, ROUND_HALF_UP
from settings import UNIT_MULTIPLIERS, LEAGUES, CATALOG_DB_PATH, LEAGUES_DIR

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
        val = Decimal(str(gh_s))
    except:
        val = Decimal("0.000")
    
    if val == 0:
        return "0.000 Gh/s"
        
    sorted_units = sorted(UNIT_MULTIPLIERS.items(), key=lambda x: x[1], reverse=True)
    
    for unit, multiplier in sorted_units:
        if val >= multiplier:
            converted = val / Decimal(str(multiplier))
            rounded = converted.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            return f"{rounded:.3f} {unit}"
            
    rounded_gh = val.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{rounded_gh:.3f} Gh/s"

def get_league_info(total_gh_s):
    val = parse_hashrate_to_gh(total_gh_s)
    for name, min_val, max_val, icon_file in LEAGUES:
        if min_val <= val < max_val:
            return name, icon_file
    return "Unknown", "bronze_1.png"

def get_league_tooltip(total_gh_s):
    name, _ = get_league_info(total_gh_s)
    return name

def _get_set_rewards_for_count(cursor, set_global_id, count):
    cursor.execute("""
        SELECT COALESCE(slr.bonus_reward, 0), COALESCE(slr.power_reward_ghs, 0)
        FROM set_level_rewards slr
        JOIN set_definitions sd ON slr.set_id = sd.id
        WHERE sd.set_global_id = ? AND CAST(slr.requirement AS INTEGER) <= ?
        ORDER BY CAST(slr.requirement AS INTEGER) ASC
    """, (set_global_id, count))
    rows = cursor.fetchall()
    if not rows:
        return Decimal("0"), Decimal("0")
    bonus = sum(Decimal(str(r[0])) for r in rows)
    power = sum(Decimal(str(r[1])) for r in rows)
    return bonus, power

def calculate_power_breakdown(rooms_state_dict):
    total_raw_miner_power = Decimal("0.0")
    total_unique_bonus_pct = Decimal("0.0")
    total_rack_bonus_power = Decimal("0.0")

    room_base_power = {}
    room_rack_bonus = {}
    room_flat_set_power = {}

    seen_miner_bonus = set()

    print("\n" + "="*60)
    print("DEBUG: calculate_power_breakdown START")
    print("="*60)

    # ── Pass 1: raw miner power, miner bonuses, rack bonuses ──────────────────
    for room_id, room_data in rooms_state_dict.items():
        room_base_power[room_id] = Decimal("0.0")
        room_rack_bonus[room_id] = Decimal("0.0")
        room_flat_set_power[room_id] = Decimal("0.0")

        racks_list = room_data.get('racks', []) if isinstance(room_data, dict) else room_data

        for rack_entry in racks_list:
            rack_name = rack_entry.get('rack_data', {}).get('name', 'unknown')
            r_bonus_pct = Decimal(str(rack_entry.get('rack_bonus', 0.0)))
            rack_miner_base = Decimal("0.0")

            print(f"\n  [RACK] Room={room_id} | '{rack_name}' | rack_bonus_pct={r_bonus_pct}%")

            for row in rack_entry.get('rows', []):
                miners_in_row = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                for miner in miners_in_row:
                    if not isinstance(miner, dict):
                        continue
                    p_val = Decimal(str(miner.get('power_val', 0.0)))
                    b_val = Decimal(str(miner.get('bonus_val', 0.0)))
                    key = (miner.get('name'), miner.get('lvl'))
                    is_new_bonus = key not in seen_miner_bonus

                    print(f"    [MINER] {miner.get('name')} lvl={miner.get('lvl')} | "
                          f"power={p_val} | bonus={b_val}% | "
                          f"bonus_counted={'YES' if is_new_bonus else 'SKIP(dup)'}")

                    total_raw_miner_power += p_val
                    room_base_power[room_id] += p_val
                    rack_miner_base += p_val

                    if is_new_bonus:
                        total_unique_bonus_pct += b_val
                        seen_miner_bonus.add(key)

            if r_bonus_pct > 0:
                rb_exact = rack_miner_base * (r_bonus_pct / Decimal("100"))
                rb_rounded = rb_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                total_rack_bonus_power += rb_rounded
                room_rack_bonus[room_id] += rb_rounded
                print(f"    [RACK BONUS] base={rack_miner_base} * {r_bonus_pct}% = {rb_exact} -> rounded={rb_rounded}")
            else:
                print(f"    [RACK BONUS] no rack bonus (pct=0)")

    print(f"\n[PASS1 TOTALS]")
    print(f"  total_raw_miner_power  = {total_raw_miner_power}")
    print(f"  total_unique_bonus_pct = {total_unique_bonus_pct}%")
    print(f"  total_rack_bonus_power = {total_rack_bonus_power}")

    # ── Pass 2: set bonuses ────────────────────────────────────────────────────
    additional_set_bonus_multiplier = Decimal("0.0")
    additional_set_base_power = Decimal("0.0")

    print(f"\n[PASS2 SET BONUSES]")

    if os.path.exists(CATALOG_DB_PATH):
        conn = sqlite3.connect(CATALOG_DB_PATH)
        cursor = conn.cursor()

        best_per_set = {}  # set_global_id -> (room_id, count, rack_name)

        for room_id, room_data in rooms_state_dict.items():
            racks_list = room_data.get('racks', []) if isinstance(room_data, dict) else room_data

            for rack_entry in racks_list:
                rack_data = rack_entry.get('rack_data', {})
                rack_set_id = rack_data.get('set_global_id')
                rack_name = rack_data.get('name', 'unknown')
                if not rack_set_id:
                    continue

                count = 0
                for row in rack_entry.get('rows', []):
                    miners_in_row = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                    for miner in miners_in_row:
                        if isinstance(miner, dict) and miner.get('set_global_id') == rack_set_id:
                            count += 1

                print(f"  [SET SCAN] Room={room_id} | '{rack_name}' | set_id={rack_set_id} | matching_miners={count}")

                if count == 0:
                    continue

                existing = best_per_set.get(rack_set_id)
                if existing is None or count > existing[1]:
                    best_per_set[rack_set_id] = (room_id, count, rack_name)
                    print(f"    -> NEW BEST for set '{rack_set_id}'")
                else:
                    print(f"    -> ignored (existing best has {existing[1]} miners)")

        print(f"\n  [SET WINNERS]")
        for rack_set_id, (room_id, count, rack_name) in best_per_set.items():
            prize_bonus, prize_power = _get_set_rewards_for_count(cursor, rack_set_id, count)
            additional_set_bonus_multiplier += prize_bonus
            additional_set_base_power += prize_power
            room_flat_set_power[room_id] += prize_power
            print(f"  set_id={rack_set_id} | rack='{rack_name}' | room={room_id} | "
                  f"count={count} | prize_bonus={prize_bonus}% | prize_power={prize_power} Gh/s")

        conn.close()
    else:
        print("  [SET] CATALOG_DB not found, skipping set bonuses")

    print(f"\n  additional_set_bonus_multiplier = {additional_set_bonus_multiplier}%")
    print(f"  additional_set_base_power       = {additional_set_base_power} Gh/s")

    # ── Final totals ───────────────────────────────────────────────────────────
    final_raw_base = total_raw_miner_power + additional_set_base_power
    final_global_bonus_pct = total_unique_bonus_pct + additional_set_bonus_multiplier

    bonus_power_hashrate = final_raw_base * (final_global_bonus_pct / Decimal("100"))
    total_power = final_raw_base + bonus_power_hashrate + total_rack_bonus_power

    print(f"\n[FINAL CALCULATION]")
    print(f"  final_raw_base         = {total_raw_miner_power} + {additional_set_base_power} = {final_raw_base}")
    print(f"  final_global_bonus_pct = {total_unique_bonus_pct} + {additional_set_bonus_multiplier} = {final_global_bonus_pct}%")
    print(f"  bonus_power_hashrate   = {final_raw_base} * {final_global_bonus_pct}% = {bonus_power_hashrate}")
    print(f"  total_rack_bonus_power = {total_rack_bonus_power}")
    print(f"  total_power (raw)      = {final_raw_base} + {bonus_power_hashrate} + {total_rack_bonus_power} = {total_power}")
    print(f"  total_power (rounded)  = {total_power.quantize(Decimal('1'), rounding=ROUND_HALF_UP)}")
    print("="*60 + "\n")

    room_details = []
    for r_id in room_base_power:
        r_base = room_base_power[r_id] + room_flat_set_power[r_id]
        r_bonus_contrib = r_base * (final_global_bonus_pct / Decimal("100"))
        r_rack_bonus = room_rack_bonus[r_id]
        r_total = r_base + r_bonus_contrib + r_rack_bonus
        room_details.append({
            "room_id": r_id,
            "total": float(r_total)
        })

    return {
        "miners_base": float(total_raw_miner_power),
        "bonus_power": float(bonus_power_hashrate),
        "bonus_percent": float(final_global_bonus_pct),
        "rack_bonus": int(total_rack_bonus_power),
        "total": float(total_power.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "room_details": room_details
    }

def calculate_single_rack_stats(rack_data, rows_data, global_bonus_pct):
    rack_bonus_pct = Decimal(str(rack_data.get('bonus_val', 0.0)))
    rack_set_id = rack_data.get('set_global_id')

    miner_list = []
    matching_set_miners = []
    rack_total_miner_base = Decimal("0.0")
    rack_total_miner_unique_bonus = Decimal("0.0")
    seen_locally = set()

    for r_idx, row in enumerate(rows_data):
        miners_in_row = []
        if isinstance(row, dict):
            miners_in_row = [(0, row)]
        elif isinstance(row, list):
            for s_idx, m in enumerate(row):
                if m: miners_in_row.append((s_idx, m))

        for s_idx, miner in miners_in_row:
            p_val = Decimal(str(miner.get('power_val', 0.0)))
            b_val = Decimal(str(miner.get('bonus_val', 0.0)))
            img_path = miner.get('image_path', '')

            rack_total_miner_base += p_val

            key = (miner.get('name'), miner.get('lvl'))
            if key not in seen_locally:
                rack_total_miner_unique_bonus += b_val
                seen_locally.add(key)

            if rack_set_id and miner.get('set_global_id') == rack_set_id:
                matching_set_miners.append(miner)

            miner_list.append({
                'id': miner.get('id'),
                'name': miner.get('name'),
                'lvl': miner.get('lvl'),
                'power': float(p_val),
                'bonus': float(b_val),
                'image_path': img_path,
                'row': r_idx,
                'slot': s_idx
            })

    additional_set_bonus = Decimal("0.0")
    additional_set_power = Decimal("0.0")
    set_name = "Unknown Set"

    if rack_set_id and matching_set_miners and os.path.exists(CATALOG_DB_PATH):
        conn = sqlite3.connect(CATALOG_DB_PATH)
        cursor = conn.cursor()
        prize_bonus, prize_power = _get_set_rewards_for_count(
            cursor, rack_set_id, len(matching_set_miners)
        )
        cursor.execute(
            "SELECT name FROM set_definitions WHERE set_global_id = ? LIMIT 1",
            (rack_set_id,)
        )
        row = cursor.fetchone()
        if row:
            set_name = row[0]
        conn.close()
        additional_set_bonus = prize_bonus
        additional_set_power = prize_power

    final_base = rack_total_miner_base + additional_set_power
    final_multiplier = rack_total_miner_unique_bonus + additional_set_bonus

    bonus_power_val = final_base * (final_multiplier / Decimal("100"))
    rack_bonus_power = rack_total_miner_base * (rack_bonus_pct / Decimal("100"))

    total = final_base + bonus_power_val + rack_bonus_power

    return {
        "miners": miner_list,
        "base_power": float(final_base),
        "miner_bonus_pct": float(rack_total_miner_unique_bonus),
        "miner_bonus_power": float(final_base * (rack_total_miner_unique_bonus / Decimal("100"))),
        "set_bonus_pct": float(additional_set_bonus),
        "set_bonus_power": float(final_base * (additional_set_bonus / Decimal("100"))),
        "set_flat_power": float(additional_set_power),
        "rack_bonus_pct": float(rack_bonus_pct),
        "rack_bonus": float(rack_bonus_power),
        "total_power": float(total),
        "is_set_rack": True if rack_set_id else False,
        "set_name": set_name
    }