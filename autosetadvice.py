from PySide6.QtWidgets import QApplication

def run_auto_setup(main_window):
    """
    Automated placement logic:
    1. Set Priority: Fill existing set-racks with matching set-miners.
    2. Place Racks: Fill empty spots with highest bonus racks from inventory.
    3. BP Racks: Place highest raw power miners (duplicates allowed) on racks with bonus.
    4. Non-BP Racks: Place highest bonus miners (no duplicates) on racks without bonus.
    """
    inventory = main_window.inventory
    if not inventory.personal_data:
        return

    # Helper to get available items with quantity > 0
    def get_avail(itype):
        return [i for i in inventory.personal_data if i.get('type') == itype and i.get('quantity', 0) > 0]

    # Block signals for performance and to avoid recording every single step in undo/redo
    main_window._is_importing = True
    inventory.block_inventory_signals = True

    try:
        # Phase 0: Priority to Sets (Existing Racks)
        fill_set_racks(main_window, get_avail('miner'))

        # Phase 1: Place Racks from inventory (Descending Bonus)
        place_new_racks(main_window, get_avail('rack'))

        # Phase 2: High Raw Power on BP Racks (Duplicates allowed, respects UI Range)
        fill_bp_racks(main_window, get_avail('miner'))

        # Phase 3: High BP Miners on Non-BP Racks (No duplicates)
        fill_non_bp_racks(main_window, get_avail('miner'))

    finally:
        inventory.block_inventory_signals = False
        main_window._is_importing = False
        main_window.update_stats()
        main_window.record_state()
        inventory.trigger_refresh()

def fill_set_racks(main_window, available_miners):
    for view in main_window.room_views:
        for p in view.placeholders:
            if p.rack and not p.rack.is_locked:
                set_id = p.rack.data.get('set_global_id')
                if not set_id: continue
                # Filter for matching set miners
                matches = [m for m in available_miners if m.get('set_global_id') == set_id]
                matches.sort(key=lambda x: x.get('power_val', 0), reverse=True)
                for m in matches:
                    while m['quantity'] > 0:
                        if p.rack.add_miner(m):
                            main_window.inventory.adjust_quantity(m, -1)
                        else:
                            break # Rack is full

def place_new_racks(main_window, available_racks):
    available_racks.sort(key=lambda x: x.get('bonus_val', 0), reverse=True)
    for view in main_window.room_views:
        for p in view.placeholders:
            if p.rack is None and available_racks:
                # Use the best rack available
                target = next((r for r in available_racks if r['quantity'] > 0), None)
                if target:
                    if p.add_rack(target):
                        main_window.inventory.adjust_quantity(target, -1)
            if not any(r['quantity'] > 0 for r in available_racks): return

def fill_bp_racks(main_window, available_miners):
    # Respect UI Bonus Range
    try: min_b = float(main_window.inventory.bonus_from_edit.text())
    except: min_b = -1.0
    try: max_b = float(main_window.inventory.bonus_to_edit.text())
    except: max_b = 99999.0

    # Filter and sort by Raw Power descending
    pool = [m for m in available_miners if min_b <= m.get('bonus_val', 0) <= max_b]
    pool.sort(key=lambda x: x.get('power_val', 0), reverse=True)

    for view in main_window.room_views:
        for p in view.placeholders:
            if p.rack and not p.rack.is_locked and p.rack.data.get('bonus_val', 0) > 0:
                for m in pool:
                    while m['quantity'] > 0:
                        if p.rack.add_miner(m):
                            main_window.inventory.adjust_quantity(m, -1)
                        else:
                            break

def fill_non_bp_racks(main_window, available_miners):
    # Sort by Bonus descending
    pool = sorted(available_miners, key=lambda x: x.get('bonus_val', 0), reverse=True)
    
    # Track unique miners placed on non-BP racks to prevent duplicates
    placed_uniques = set()

    for view in main_window.room_views:
        for p in view.placeholders:
            if p.rack and not p.rack.is_locked and p.rack.data.get('bonus_val', 0) == 0:
                for m in pool:
                    if m['quantity'] > 0:
                        key = (m.get('name'), m.get('lvl'))
                        if key not in placed_uniques:
                            if p.rack.add_miner(m):
                                main_window.inventory.adjust_quantity(m, -1)
                                placed_uniques.add(key)