import sys
import os
import copy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, 
    QMenu, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QIcon, QPixmap, QGuiApplication, QAction

from settings import WINDOW_WIDTH, WINDOW_HEIGHT, APP_ICON_PATH, LEAGUES_DIR, LEAGUES
from logic_math import format_hashrate, get_league_info, get_league_tooltip, calculate_power_breakdown
from database import DatabaseHandler
from inventory import InventorySection
from room_preview import RoomView
import importer
import missing_miner_export

# Modular Imports
from ui_styles import DARK_STYLESHEET, LIGHT_STYLESHEET, resolve_path
from ui_components import LoadingSplashScreen, ImportProgressDialog
from dialogs_system import SettingsDialog, ImportManagerDialog, JsonParserDialog
from dialogs_catalog import EditMinerDialog, AddRackDialog, AddMinerDialog
from dialogs_stats import RackDetailsDialog, PowerBreakdownDialog

# New Component Imports
from room_undo_engine import UndoEngine
from room_io_manager import RoomIOManager
from room_ui_builder import RoomUIBuilder

# Automation Logic
from autosetadvice import run_auto_setup
from mineradvice import show_merge_advice

class MainWindow(QMainWindow):
    def __init__(self, splash=None):
        super().__init__()
        self.setWindowTitle("Mining Room Simulator")
        self.room_save_path = None
        self.splash = splash
        self._is_importing = False
        self._is_handling_undo_redo = False
        
        if os.path.exists(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))
            
        # Core Components
        self.db_handler = DatabaseHandler()
        self.undo_engine = UndoEngine()
        self.io_manager = RoomIOManager(self)
        self.ui_builder = RoomUIBuilder(self)
        
        self.room_buttons = []
        self.room_views = []
        self.current_stats = None
        self.baseline_stats = None
        
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.config = self.io_manager.load_app_config()
        
        importer.ensure_player_info_dir()
        if not self.config.get("room_path"):
            self.config["room_path"] = os.path.join(importer.PLAYER_INFO_DIR, "player_room.json").replace("\\", "/")
        if not self.config.get("inv_path"):
            self.config["inv_path"] = os.path.join(importer.PLAYER_INFO_DIR, "player_inventory.json").replace("\\", "/")
            
        self._autosave_path = self.config.get("room_path")
        self.room_save_path = self._autosave_path
        
        # Initialize UI parts
        self.inventory = InventorySection()
        self.inventory.view.itemClicked.connect(self.on_inventory_item_clicked)
        self.inventory.edit_requested.connect(self.open_miner_editor)
        self.inventory.inventory_changed.connect(self.auto_save_inventory)
        self.inventory.missing_items_found.connect(lambda names: self.prompt_missing_items_export(names, "missing_inventory_items.txt"))
        self.inventory.auto_requested.connect(lambda: run_auto_setup(self))
        self.inventory.advice_requested.connect(lambda: show_merge_advice(self))

        # Construct layout
        self.ui_builder.build_ui()
        
        # Initialize Rooms
        h_paused = self.config.get("pause_hamsters", False)
        for i in range(self.config.get("room_count", 4)):
            bg = self.config.get("room1_bg", "") if i == 0 else self.config.get("room_rest_bg", "")
            view = RoomView(i, self.config.get("rack_scale", 1.0), bg, hamsters_paused=h_paused)
            view.parent_window = self 
            self.connect_room_signals(view)
            self.room_views.append(view)
            self.room_stack.addWidget(view)
            self.add_room_button(i)

        self.apply_theme()
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def initial_load(self, splash):
        self._is_importing, self.inventory.block_inventory_signals = True, True
        if self.config.get("auto_import_inv") and os.path.exists(self.config.get("inv_path", "")):
            self.inventory.load_inventory_file(self.config["inv_path"], splash=splash)
        if self.config.get("auto_import_room") and os.path.exists(self.config.get("room_path", "")):
            if splash: splash.update_progress(40, "Loading Player Rooms...")
            self.load_room_file(self.config["room_path"], splash=splash)
        self.reconcile_personal_inventory()
        self.inventory.block_inventory_signals, self._is_importing = False, False
        self.set_baseline()
        if splash: splash.update_progress(90, "Calculating Stats...")
        self.update_stats()
        self.record_state()
        if splash: splash.update_progress(100, "Ready.")

    def prompt_missing_items_export(self, missing_names, default_filename="missing_items.txt"):
        if not missing_names:
            return
        missing_miner_export.show_import_summary(self, missing_names, [], [], default_filename)

    def center_on_screen(self):
        frame_geo = self.frameGeometry()
        screen_center = QGuiApplication.primaryScreen().availableGeometry().center()
        frame_geo.moveCenter(screen_center)
        self.move(frame_geo.topLeft())

    def apply_theme(self):
        self.setStyleSheet(LIGHT_STYLESHEET if self.config.get("light_theme", False) else DARK_STYLESHEET)

    def closeEvent(self, event):
        self.io_manager.auto_save()
        self.auto_save_inventory()
        self.io_manager.save_app_config()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def on_settings_clicked(self):
        old_scale = self.config.get("rack_scale", 1.0)
        old_pause_h = self.config.get("pause_hamsters", False)
        old_pause_gifs = self.config.get("pause_gifs", False)
        
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            new_data = dlg.get_data()
            self.config.update(new_data)
            self.io_manager.save_app_config()
            self.apply_theme()
            
            if old_scale != self.config.get("rack_scale", 1.0):
                self.rebuild_rooms_with_scale(self.config.get("rack_scale", 1.0))
            else:
                for i, view in enumerate(self.room_views):
                    view.update_background(self.config.get("room1_bg", "") if i == 0 else self.config.get("room_rest_bg", ""))
            
            new_pause_gifs = self.config.get("pause_gifs", False)
            if old_pause_gifs != new_pause_gifs:
                self.handle_room_switch(self.room_stack.currentIndex())

            new_pause_h = self.config.get("pause_hamsters", False)
            if old_pause_h != new_pause_h:
                for view in self.room_views:
                    if hasattr(view, 'dusty'):
                        view.dusty.paused = new_pause_h
                        if new_pause_h:
                            if hasattr(view.dusty, 'timer'): view.dusty.timer.stop()
                            if view.dusty.frames: view.dusty.setPixmap(view.dusty.frames[0])
                        else:
                            if hasattr(view.dusty, 'timer'):
                                view.dusty.timer.start(120)
                            else:
                                view.dusty.timer = QTimer(view.dusty)
                                view.dusty.timer.timeout.connect(view.dusty.next_frame)
                                view.dusty.timer.start(120)

            self.handle_room_switch(self.room_stack.currentIndex())

    def rebuild_rooms_with_scale(self, new_scale):
        self._is_importing = True 
        snapshot = [rv.get_room_state() for rv in self.room_views]
        progress_dlg = ImportProgressDialog("Adjusting Room Scale", self)
        progress_dlg.show()
        while self.room_stack.count():
            self.room_stack.removeWidget(self.room_stack.widget(0))
        self.room_views.clear()
        h_paused = self.config.get("pause_hamsters", False)
        for i in range(len(snapshot)):
            view = RoomView(i, new_scale, self.config.get("room1_bg", "") if i == 0 else self.config.get("room_rest_bg", ""), hamsters_paused=h_paused)
            view.parent_window = self
            self.connect_room_signals(view)
            self.room_views.append(view)
            self.room_stack.addWidget(view)
            room_data = snapshot[i]
            view.room_uuid = room_data.get('room_uuid')
            for p_idx, rack_info in enumerate(room_data.get('racks', [])):
                if p_idx < len(view.placeholders):
                    view.placeholders[p_idx].add_rack(rack_info['rack_data'], initial_miners=rack_info['rows'], is_locked=rack_info.get('is_locked', False))
        progress_dlg.close()
        self._is_importing = False
        self.update_stats()

    def handle_room_switch(self, index):
        pause = self.config.get("pause_gifs", False)
        for i, view in enumerate(self.room_views):
            view.set_animations_enabled(False if pause else (i == index))

    def record_state(self):
        if self._is_handling_undo_redo or self._is_importing: return
        self.undo_engine.record_state(self.room_views, self.inventory.personal_data)

    def undo(self):
        state = self.undo_engine.undo()
        if state: self.apply_state(state)

    def redo(self):
        state = self.undo_engine.redo()
        if state: self.apply_state(state)

    def apply_state(self, state):
        self._is_handling_undo_redo = True
        self.inventory.block_inventory_signals = True
        self.setUpdatesEnabled(False)
        for rv in self.room_views: rv.blockSignals(True)
        try:
            for idx, room_view in enumerate(self.room_views):
                target_room_data = state["rooms"][idx] if idx < len(state["rooms"]) else {}
                room_view.room_uuid = target_room_data.get('room_uuid')
                target_racks = target_room_data.get('racks', [])
                for p_idx, pld in enumerate(room_view.placeholders):
                    target_rack_info = target_racks[p_idx] if p_idx < len(target_racks) else None
                    if not target_rack_info:
                        if pld.rack: pld.remove_rack(silent=True)
                        continue
                    pld.add_rack(target_rack_info.get("rack_data"), initial_miners=target_rack_info.get("rows", []), is_locked=target_rack_info.get("is_locked", False))
            self.inventory.personal_data = copy.deepcopy(state["personal_inventory"])
            self.inventory.trigger_refresh()
            self.update_stats()
        finally:
            for rv in self.room_views: rv.blockSignals(False)
            self.setUpdatesEnabled(True)
            self.inventory.block_inventory_signals = False
            self._is_handling_undo_redo = False

    def update_stats(self):
        placed_ids = set()
        for view in self.room_views:
            for rack_info in view.get_room_state().get('racks', []):
                for row in rack_info.get('rows', []):
                    miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                    for m in miners:
                        if isinstance(m, dict):
                            self.repair_item_data(m)
                            tag = m.get('level_id_tag')
                            if tag: placed_ids.add(str(tag).lower().strip())
        self.inventory.set_placed_items(placed_ids)
        state = {i: v.get_room_state() for i, v in enumerate(self.room_views)}
        self.current_stats = calculate_power_breakdown(state)
        self.power_label.setText(f"Total Power: {format_hashrate(self.current_stats['total'])}")
        
        total_p = self.current_stats['total']
        current_idx = -1
        for i, (name, min_v, max_v, icon) in enumerate(LEAGUES):
            if min_v <= total_p < max_v:
                current_idx = i
                break
        
        if current_idx != -1:
            curr_name, _, _, curr_icon_file = LEAGUES[current_idx]
            p_curr = os.path.join(LEAGUES_DIR, curr_icon_file)
            if os.path.exists(p_curr):
                self.league_icon.setPixmap(QPixmap(p_curr).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.league_icon.setToolTip(get_league_tooltip(total_p))
            
            if current_idx + 1 < len(LEAGUES):
                next_name = LEAGUES[current_idx + 1][0]
                next_min = LEAGUES[current_idx + 1][1]
                p_next = os.path.join(LEAGUES_DIR, LEAGUES[current_idx + 1][3])
                if os.path.exists(p_next):
                    self.next_league_icon.setPixmap(QPixmap(p_next).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.next_league_icon.setToolTip(next_name)
                needed_val = next_min - total_p
                self.league_needed_lbl.setText(f"you need {format_hashrate(needed_val)}")
                self.to_reach_lbl.show(); self.next_league_icon.show(); self.league_needed_lbl.show()
            else:
                self.to_reach_lbl.hide(); self.next_league_icon.hide(); self.league_needed_lbl.hide()

        if self._is_importing:
            self.delta_label.setText("")
            return
        if self.baseline_stats is None:
            self.baseline_stats = copy.deepcopy(self.current_stats)
            return
        delta = float(self.current_stats['total']) - float(self.baseline_stats['total'])
        self.delta_label.setText(f"{'↑' if delta > 0.001 else '↓'} {format_hashrate(abs(delta))}" if abs(delta) > 0.001 else "")
        self.delta_label.setStyleSheet(f"color: {'#00ff00' if delta > 0 else '#ff4444'}; font-weight: bold;")

    def repair_item_data(self, item_dict):
        if not item_dict: return item_dict
        nk, lookup_name_map, lookup_tag_map = str(item_dict.get('name', '')).lower().strip(), self.inventory.name_to_item_map, self.inventory.tag_to_item_map
        if 'power_val' in item_dict or 'lvl' in item_dict:
            lvl = item_dict.get('lvl', 1)
            match = lookup_name_map.get((nk, lvl)) or lookup_tag_map.get(str(item_dict.get('level_id_tag', '')).lower().strip())
            if match: item_dict.update({'id': match['id'], 'set_global_id': match.get('set_global_id'), 'level_id_tag': match.get('level_id_tag'), 'power_val': match['power_val'], 'bonus_val': match['bonus_val'], 'name': match['name']})
        else:
            match = lookup_name_map.get(nk) or lookup_tag_map.get(str(item_dict.get('rack_id_tag', '')).lower().strip())
            if match: item_dict.update({'id': match['id'], 'set_global_id': match.get('set_global_id'), 'name': match['name']})
        return item_dict

    def load_room_file(self, path, splash=None):
        if not os.path.exists(path): return
        jc = importer.clean_and_parse_json(path)
        if not jc: return
        m_names, f_racks, f_miners = [], [], []
        all_indices = [0]
        if isinstance(jc, list): all_indices.extend([r.get("room_index", 0) for r in jc])
        data_block = importer.find_mining_data_block(jc)
        if data_block: all_indices.extend([r.get("room_info", {}).get("level", 0) for r in data_block.get("rooms", [])])
        while len(self.room_views) <= max(all_indices): self.on_plus_clicked(auto_save=False)
        
        if data_block: 
            m_names, f_racks, f_miners = self._import_player_json(data_block, splash=splash)
        elif isinstance(jc, list):
            jc.sort(key=lambda x: x.get("room_index", 0))
            miner_pass_queue = []
            for rd in jc:
                idx = rd.get("room_index", 0)
                if idx < len(self.room_views):
                    view = self.room_views[idx]
                    view.room_uuid = rd.get("room_uuid")
                    if splash: splash.update_progress(40, f"Placing Racks in Room {idx + 1}")
                    for p_idx, ri in enumerate(rd.get("racks", [])):
                        if p_idx < len(view.placeholders):
                            rdt = self.repair_item_data(ri.get("rack_data", ri))
                            view.placeholders[p_idx].add_rack(rdt, is_locked=ri.get("is_locked", False))
                            miner_pass_queue.append((idx, p_idx, rdt.get("name", "Unknown"), ri.get("rows", [])))
                    QApplication.processEvents()
            for i, (rm_idx, p_idx, r_name, rows) in enumerate(miner_pass_queue):
                if splash:
                    prog = 60 + int((i/max(1, len(miner_pass_queue))) * 30)
                    splash.update_progress(prog, f"Placing Miners on {r_name} in Room {rm_idx + 1}")
                r_widget = self.room_views[rm_idx].placeholders[p_idx].rack
                if r_widget:
                    rrs = [self.repair_item_data(r) if isinstance(r, dict) else ([self.repair_item_data(m) if isinstance(m, dict) else m for m in r] if isinstance(r, list) else r) for r in rows]
                    for r_row_idx, row_val in enumerate(rrs):
                        if isinstance(row_val, dict): r_widget.add_miner(row_val, r_row_idx, 0)
                        elif isinstance(row_val, list):
                            for s_idx, m_val in enumerate(row_val):
                                if m_val: r_widget.add_miner(m_val, r_row_idx, s_idx)
                QApplication.processEvents()
        
        if m_names or f_racks or f_miners:
            missing_miner_export.show_import_summary(self, m_names, f_racks, f_miners)

    def _import_player_json(self, data, splash=None):
        missing_in_db, failed_racks, failed_miners = [], [], []
        rm_meta = {r["_id"]: r["room_info"] for r in data.get("rooms", [])}
        for u, i in rm_meta.items(): 
            lvl = i.get("level", 0)
            if lvl < len(self.room_views): self.room_views[lvl].room_uuid = u
            
        id_map, racks_by_u = {}, {}
        for r in data.get("racks", []): racks_by_u.setdefault(r.get("placement", {}).get("user_room_id"), []).append(r)
        sorted_room_uuids = sorted(rm_meta.keys(), key=lambda k: rm_meta[k].get("level", 0))
        
        for u in sorted_room_uuids:
            view = next((v for v in self.room_views if v.room_uuid == u), None)
            if not view: continue
            lvl = rm_meta[u].get("level", 0)
            if splash: splash.update_progress(40, f"Placing Racks in Room {lvl + 1}")
            rl = racks_by_u.get(u, [])
            rl.sort(key=lambda r: (r['placement'].get('y', 0) * rm_meta.get(u, {}).get("cols", 8)) + r['placement'].get('x', 0))
            
            for i, rj in enumerate(rl):
                if i >= len(view.placeholders):
                    failed_racks.append(f"{rj.get('name', 'Unknown')} (Room {lvl+1} Full)")
                    continue
                db_item, _ = importer.find_item_robust(rj.get("rack_id"), rj.get("name"), None, self.inventory.tag_to_item_map, self.inventory.name_to_item_map)
                if db_item:
                    if view.placeholders[i].add_rack(copy.deepcopy(db_item)):
                        self.inventory.adjust_quantity(db_item, -1)
                        id_map[rj["_id"]] = (view.placeholders[i].rack, rj.get("name", "Unknown"), lvl + 1)
                else:
                    missing_in_db.append(f"{rj.get('name', 'Unknown Rack')} (Tag: {rj.get('rack_id')})")
            QApplication.processEvents()
            
        miners = data.get("miners", [])
        for i, mj in enumerate(miners):
            rack_id = mj.get("placement", {}).get("user_rack_id")
            if rack_id in id_map:
                tr, rack_name, room_num = id_map[rack_id]
                if splash:
                    prog = 60 + int((i/max(1, len(miners))) * 30)
                    splash.update_progress(prog, f"Placing Miners on {rack_name} in Room {room_num}")
                db_item, _ = importer.find_item_robust(mj.get("miner_id"), mj.get("name"), mj.get("level"), self.inventory.tag_to_item_map, self.inventory.name_to_item_map)
                if db_item:
                    placed = tr.add_miner(copy.deepcopy(db_item), row=mj["placement"].get("y", 0), slot=mj["placement"].get("x", 0))
                    if not placed: placed = tr.add_miner(copy.deepcopy(db_item))
                    if placed: self.inventory.adjust_quantity(db_item, -1)
                    else: failed_miners.append(f"{mj.get('name')} (Rack {rack_name} Full)")
                else:
                    missing_in_db.append(f"{mj.get('name', 'Unknown Miner')} (Tag: {mj.get('miner_id')})")
            if i % 5 == 0: QApplication.processEvents()
        return missing_in_db, failed_racks, failed_miners

    def clear_all_rooms(self, only_miners=False, show_progress=True):
        progress = ImportProgressDialog("Clearing", self) if show_progress else None
        if progress: 
            progress.show()
            progress.update_status(0, "Clearing rooms...")
        for i, v in enumerate(self.room_views):
            v.clear_room(only_miners)
            if progress: progress.update_status(int(((i+1)/len(self.room_views))*100), "Clearing rooms...")
            QApplication.processEvents()
        if progress: progress.close()

    def reconcile_personal_inventory(self):
        for view in self.room_views:
            for rack_info in view.get_room_state().get('racks', []):
                if rack_info['rack_data'].get('source') == 'Personal': self.inventory.adjust_quantity(rack_info['rack_data'], -1)
                for row in rack_info.get('rows', []):
                    miners = [row] if isinstance(row, dict) else (row if isinstance(row, list) else [])
                    for m in miners:
                        if isinstance(m, dict) and m.get('source') == 'Personal': self.inventory.adjust_quantity(m, -1)

    def connect_room_signals(self, view):
        view.stats_changed.connect(self.update_stats); view.stats_changed.connect(self.record_state); view.stats_changed.connect(self.io_manager.auto_save)
        view.item_placed.connect(lambda data: self.inventory.adjust_quantity(data, -1))
        view.item_returned.connect(lambda data: self.inventory.adjust_quantity(data, 1) if not self._is_importing else None)
        view.rack_clicked.connect(self.on_rack_clicked); view.miner_edit_requested.connect(self.open_miner_editor); view.rack_swap_requested.connect(self.on_swap_rack_requested)

    def on_swap_rack_requested(self, rw, pos):
        placeholder = next((p for p in self.room_stack.currentWidget().placeholders if p.rack == rw), None)
        available = [item for item in self.inventory.personal_data if item.get('type') == 'rack' and item.get('quantity', 0) > 0]
        if not available: return
        menu = QMenu(self)
        for rd in available:
            act = QAction(f"{rd['name']} ({rd.get('bonus_val', 0)}%)", self)
            act.triggered.connect(lambda chk=False, r=rd: self.execute_rack_swap(placeholder, r))
            menu.addAction(act)
        menu.exec(pos)

    def execute_rack_swap(self, pld, nrd):
        self.inventory.block_inventory_signals = True
        pld.blockSignals(True)
        ord_data, om = pld.rack.data, []
        for r in pld.rack.rows_data:
            if isinstance(r, dict): om.append(r)
            elif isinstance(r, list):
                for m in r:
                    if m: om.append(m)
        pld.remove_rack(silent=True); self.inventory.adjust_quantity(ord_data, 1); self.inventory.adjust_quantity(nrd, -1); pld.add_rack(nrd)
        for m in om:
            if not pld.rack.add_miner(m): self.inventory.adjust_quantity(m, 1)
        pld.blockSignals(False); self.inventory.block_inventory_signals = False; self.update_stats(); self.io_manager.auto_save()

    def auto_save_inventory(self):
        if self.config.get("auto_save", True) and not self._is_importing and not self.inventory.block_inventory_signals:
            self.inventory.save_personal_inventory(self.config["inv_path"])

    def open_miner_editor(self, data):
        if EditMinerDialog(data, self.db_handler, self).exec():
            self.db_handler.preload_data(); self.inventory.preload_data_from_db(); self.sync_room_miners(); self.update_stats()

    def sync_room_miners(self):
        lookup = {(i['name'], i['lvl']): (i['power_val'], i['bonus_val']) for i in self.inventory.game_data if i.get('type') == 'miner'}
        for v in self.room_views:
            for p in v.placeholders:
                if p.rack:
                    u = False
                    for r in p.rack.rows_data:
                        ms = [r] if isinstance(r, dict) else (r if isinstance(r, list) else [])
                        for m in ms:
                            if isinstance(m, dict) and (m['name'], m['lvl']) in lookup:
                                m['power_val'], m['bonus_val'] = lookup[(m['name'], m['lvl'])]; u = True
                    if u: p.rack.refresh_ui()

    def on_inventory_item_clicked(self, d): self.room_stack.currentWidget().handle_item_click(d)
    
    def on_rack_clicked(self, rd, rs):
        racks = [p.rack for p in self.room_stack.currentWidget().placeholders if p.rack]
        try:
            idx = next(i for i, rw in enumerate(racks) if rw.data == rd and rw.rows_data == rs)
            RackDetailsDialog(racks, idx, self).exec()
        except StopIteration: pass

    def add_room_button(self, idx):
        btn = QPushButton(f"Room {idx + 1}"); btn.clicked.connect(lambda c=False, i=idx: self.room_stack.setCurrentIndex(i))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); btn.customContextMenuRequested.connect(lambda p, i=idx: self.on_room_button_context_menu(p, i))
        self.room_nav.insertWidget(len(self.room_buttons), btn); self.room_buttons.append(btn)

    def on_room_button_context_menu(self, pos, idx):
        menu = QMenu(self); menu.addAction(f"Delete Room {idx + 1}", lambda: self.delete_room(idx)); menu.exec(self.room_buttons[idx].mapToGlobal(pos))

    def delete_room(self, idx):
        if len(self.room_views) <= 1: return
        if QMessageBox.question(self, "Delete", f"Delete Room {idx+1}?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.room_views[idx].clear_room(False); self.room_stack.removeWidget(self.room_views[idx]); self.room_nav.removeWidget(self.room_buttons[idx])
            self.room_buttons.pop(idx).deleteLater(); self.room_views.pop(idx).deleteLater()
            for i, b in enumerate(self.room_buttons):
                b.setText(f"Room {i + 1}"); b.clicked.disconnect(); b.clicked.connect(lambda c=False, x=i: self.room_stack.setCurrentIndex(x))
                b.customContextMenuRequested.disconnect(); b.customContextMenuRequested.connect(lambda p, x=i: self.on_room_button_context_menu(p, x))
            for i, v in enumerate(self.room_views): v.room_id = i
            self.io_manager.save_app_config(); self.update_stats(); self.record_state(); self.io_manager.auto_save()

    def on_add_rack_clicked(self):
        dlg = AddRackDialog(self.db_handler, self)
        if dlg.exec(): 
            self.db_handler.add_custom_rack_full(dlg.result_data)
            self.db_handler.preload_data()
            self.inventory.preload_data_from_db()

    def on_add_miner_clicked(self):
        dlg = AddMinerDialog(self.db_handler, self)
        if dlg.exec(): 
            self.db_handler.add_custom_miner_full(dlg.base_result, dlg.levels_result)
            self.db_handler.preload_data()
            self.inventory.preload_data_from_db()

    def on_plus_clicked(self, auto_save=True):
        idx = len(self.room_buttons); h_paused = self.config.get("pause_hamsters", False)
        view = RoomView(idx, self.config.get("rack_scale", 1.0), self.config.get("room1_bg", "") if idx == 0 else self.config.get("room_rest_bg", ""), hamsters_paused=h_paused)
        view.parent_window = self
        self.connect_room_signals(view); self.room_views.append(view); self.room_stack.addWidget(view); self.add_room_button(idx)
        self.io_manager.save_app_config()
        if auto_save: self.io_manager.auto_save()

    def set_baseline(self): 
        if self.current_stats: self.baseline_stats = copy.deepcopy(self.current_stats); self.delta_label.setText("")

    def on_power_label_context_menu(self, p):
        m = QMenu(self); m.addAction("Reset Comparison", self.set_baseline); m.exec(self.power_label.mapToGlobal(p))

    def on_power_label_clicked(self, e): PowerBreakdownDialog(self.current_stats, self.baseline_stats, self).exec()

    def on_import_room_clicked(self):
        dlg = JsonParserDialog(parent=self)
        if dlg.exec():
            raw, uid = dlg.get_text().strip(), dlg.get_user_id().strip()
            progress = ImportProgressDialog("Importing Room", self); progress.show()
            self.power_label.setText("Total Power: 0.000 Gh/s"); self.delta_label.setText("")
            QApplication.processEvents()
            if uid:
                progress.update_status(0, "Fetching data...")
                raw = self.io_manager.fetch_web_data(uid)
                if not raw: progress.close(); return
            else: progress.update_status(0, "Processing Pasted Data...")
            self._is_importing = True; self.baseline_stats = None
            try:
                self.clear_all_rooms(show_progress=True)
                obj = importer.clean_and_parse_json(raw, is_text=True)
                if obj:
                    saved_path = importer.save_to_player_info("player_room.json", obj)
                    self.load_room_file(saved_path, splash=progress)
                self.update_stats(); self.set_baseline(); self.record_state(); self.io_manager.auto_save()
            finally: self._is_importing = False; progress.close()

    def on_import_inventory_clicked(self):
        dlg = JsonParserDialog(show_api_input=False, parent=self)
        if dlg.exec():
            res = importer.process_generic_pasted_inventory(dlg.get_text())
            if res: self.inventory.add_items_by_tags(res['items']); self.inventory.save_personal_inventory(self.config["inv_path"])

    def on_import_clicked(self):
        dlg = ImportManagerDialog(self.config, self)
        if dlg.exec():
            self.config.update(dlg.get_data()); self.io_manager.save_app_config()
            self.inventory.load_inventory_file(self.config["inv_path"])
            self.load_room_file(self.config["room_path"])

    def on_save_clicked(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save", "", "JSON (*.json)")
        if p: self.room_save_path = p; self.io_manager.auto_save()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = LoadingSplashScreen(); splash.show(); app.processEvents()
    window = MainWindow(splash=splash); window.initial_load(splash); window.center_on_screen()
    splash.finish(window); window.show(); window.raise_(); window.activateWindow(); app.processEvents()
    QTimer.singleShot(100, lambda: (window.repaint(), window.center_on_screen(), app.processEvents()))
    sys.exit(app.exec())