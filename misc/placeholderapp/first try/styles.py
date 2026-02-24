DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
}
QGroupBox {
    border: 1px solid #555555;
    margin-top: 15px;
    font-weight: bold;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px;
}
QAbstractSpinBox, QComboBox, QLineEdit {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555555;
    padding: 2px;
}
QPushButton {
    background-color: #444444;
    border: 1px solid #555555;
    padding: 6px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #555555;
}
QPushButton:pressed {
    background-color: #111111;
}
QScrollBar:vertical {
    border: none;
    background: #2b2b2b;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
}
QScrollBar:horizontal {
    border: none;
    background: #2b2b2b;
    height: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 20px;
}
"""
