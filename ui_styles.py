import os

DARK_STYLESHEET = """
QMainWindow, QDialog { background-color: #121212; color: #e0e0e0; }
QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Arial; }
QPushButton { background-color: #333333; border: 1px solid #555555; padding: 5px 15px; border-radius: 3px; color: white; }
QPushButton:hover { background-color: #444444; }
QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox { background-color: #1e1e1e; border: 1px solid #444444; color: white; padding: 3px; }
QScrollArea { border: none; background-color: #121212; }
QTableWidget { background-color: #1e1e1e; gridline-color: #333; }
QHeaderView::section { background-color: #2a2a2a; padding: 4px; border: 1px solid #333; }
QLabel#PowerLabel { color: #00ff00; }
QProgressBar { 
    border: 1px solid #444; 
    border-radius: 2px; 
    text-align: center; 
    background-color: #1a1a1a; 
    height: 20px;
}
QProgressBar::chunk { 
    background-color: #00ff00; 
    width: 12px; 
    margin: 1px; 
}
"""

LIGHT_STYLESHEET = """
QMainWindow, QDialog { background-color: #f0f0f0; color: #202020; }
QWidget { background-color: #f0f0f0; color: #202020; font-family: 'Segoe UI', Arial; }
QPushButton { background-color: #e0e0e0; border: 1px solid #bcbcbc; padding: 5px 15px; border-radius: 3px; color: #202020; }
QPushButton:hover { background-color: #d0d0d0; }
QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox { background-color: #ffffff; border: 1px solid #bcbcbc; color: #202020; padding: 3px; }
QScrollArea { border: none; background-color: #f0f0f0; }
QTableWidget { background-color: #ffffff; gridline-color: #bcbcbc; color: #202020; }
QHeaderView::section { background-color: #e0e0e0; padding: 4px; border: 1px solid #bcbcbc; color: #202020; }
QLabel#PowerLabel { color: #008000; }
QProgressBar { 
    border: 1px solid #bcbcbc; 
    border-radius: 2px; 
    text-align: center; 
    background-color: #e0e0e0; 
    height: 20px;
}
QProgressBar::chunk { 
    background-color: #008000; 
    width: 12px; 
    margin: 1px; 
}
"""

def resolve_path(path):
    if not path:
        return ""
    clean_p = path.replace("\\", "/")
    parts = clean_p.split("/")
    if "assets" in parts:
        return os.path.join(*parts[parts.index("assets"):])
    return path