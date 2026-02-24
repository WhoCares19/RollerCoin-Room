import os

# Application Settings
WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 800
APP_ICON_PATH = os.path.join("assets", "Icons", "rcicon.ico")

# Unit Multipliers for Hashrate (Base unit is Gh/s)
UNIT_MULTIPLIERS = {
    "Gh/s": 1,
    "Th/s": 1000,
    "Ph/s": 1000**2,
    "Eh/s": 1000**3,
    "Zh/s": 1000**4
}

# Leagues Configuration (Name, Min GH/s, Max GH/s, Icon Filename)
LEAGUES = [
    ("Bronze I", 0, 5000000, "bronze_1.png"),
    ("Bronze II", 5000000, 30000000, "bronze_2.png"),
    ("Bronze III", 30000000, 100000000, "bronze_3.png"),
    ("Silver I", 100000000, 200000000, "silver_1.png"),
    ("Silver II", 200000000, 500000000, "silver_2.png"),
    ("Silver III", 500000000, 1000000000, "silver_3.png"),
    ("Gold I", 1000000000, 2000000000, "gold_1.png"),
    ("Gold II", 2000000000, 5000000000, "gold_2.png"),
    ("Gold III", 5000000000, 15000000000, "gold_3.png"),
    ("Platinum I", 15000000000, 50000000000, "plat_1.png"),
    ("Platinum II", 50000000000, 100000000000, "plat_2.png"),
    ("Platinum III", 100000000000, 200000000000, "plat_3.png"),
    ("Diamond I", 200000000000, 400000000000, "diamond_1.png"),
    ("Diamond II", 400000000000, 1000000000000, "diamond_2.png"),
    ("Diamond III", 1000000000000, 999999999999999, "diamond_3.png")
]

# Asset File Locations
ASSETS_DIR = "assets"
ICONS_DIR = os.path.join(ASSETS_DIR, "Icons")
LEVELS_DIR = os.path.join(ASSETS_DIR, "Levels")
LEAGUES_DIR = os.path.join(ASSETS_DIR, "Leagues")
CATALOG_DB_PATH = os.path.join(ASSETS_DIR, "miner_catalog.db")
RACK_JSON_PATH = os.path.join(ASSETS_DIR, "Rack_Placeholders.json")
CONFIG_PATH = os.path.join(ASSETS_DIR, "config.json")

SET_ICON = os.path.join(ICONS_DIR, "set.png")
LOCK_ICON = os.path.join(ICONS_DIR, "lock.png")
UNLOCK_ICON = os.path.join(ICONS_DIR, "unlock.png")

# Room Configurations
ROOM_1_RACKS = 12
ROOM_OTHER_RACKS = 18
ROOM_1_COLS = 6
ROOM_OTHER_COLS = 9

# Inventory Layout
INVENTORY_ITEM_WIDTH = 125 
INVENTORY_ITEM_HEIGHT = 150