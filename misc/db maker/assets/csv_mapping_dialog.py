# csv_mapping_dialog.py
from PyQt5 import QtWidgets, QtCore, QtGui

class CSVMappingDialog(QtWidgets.QDialog):
    """
    A dialog for mapping CSV columns to specific miner attributes.
    Allows entering Excel-style column letters (A, B, C...).
    Ensures that unique positions for Power, Bonus, Slots, and Sets 
    are accurately identified.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure CSV Import Mapping")
        self.setFixedWidth(450)
        self.mapping_data = None
        
        self.init_ui()

    def init_ui(self):
        # Using a main vertical layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Form layout for easy label-input pairing
        form_layout = QtWidgets.QFormLayout()
        
        # Stylesheet for inputs to match the app theme
        input_style = "padding: 3px; border: 1px solid #ccc; border-radius: 3px;"

        # --- General Settings ---
        self.start_row_spin = QtWidgets.QSpinBox()
        self.start_row_spin.setRange(1, 10000)
        self.start_row_spin.setValue(2) # Default to row 5 as per instructions
        self.start_row_spin.setStyleSheet(input_style)
        form_layout.addRow("Data Starting Row:", self.start_row_spin)

        self.name_col_input = QtWidgets.QLineEdit("A")
        self.name_col_input.setStyleSheet(input_style)
        self.name_col_input.setToolTip("Column containing the Miner Name")
        form_layout.addRow("Miner Name Column (Name):", self.name_col_input)

        # --- Power Levels Mapping (Columns B through G) ---
        self.power_inputs = []
        power_defaults = ["B", "C", "D", "E", "F", "G"]
        for i in range(6):
            inp = QtWidgets.QLineEdit(power_defaults[i])
            inp.setStyleSheet(input_style)
            inp.setPlaceholderText(f"L{i+1} Power Column")
            form_layout.addRow(f"Level {i+1} Power Column:", inp)
            self.power_inputs.append(inp)

        # --- Bonus Levels Mapping (Columns H through L, and N for L6) ---
        # Level 6 is explicitly in Column N to avoid collision with M (Slots)
        self.bonus_inputs = []
        bonus_defaults = ["H", "I", "J", "K", "L", "M"]
        for i in range(6):
            inp = QtWidgets.QLineEdit(bonus_defaults[i])
            inp.setStyleSheet(input_style)
            inp.setPlaceholderText(f"L{i+1} Bonus Column")
            form_layout.addRow(f"Level {i+1} Bonus Column:", inp)
            self.bonus_inputs.append(inp)

        # --- Slot and Set Mapping (Columns M and O) ---
        self.slot_col_input = QtWidgets.QLineEdit("N")
        self.slot_col_input.setStyleSheet(input_style)
        self.slot_col_input.setToolTip("Column containing Slot Size (strictly 1 or 2)")
        form_layout.addRow("Slot Size Column (Slots):", self.slot_col_input)

        self.set_col_input = QtWidgets.QLineEdit("O")
        self.set_col_input.setStyleSheet(input_style)
        self.set_col_input.setToolTip("Column containing Set Name (can be empty)")
        form_layout.addRow("Set Name Column (Sets):", self.set_col_input)

        layout.addLayout(form_layout)

        # --- Footer Buttons ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.import_btn = QtWidgets.QPushButton("Start Import")
        self.import_btn.setStyleSheet("""
            background-color: #5DADE2; 
            color: white; 
            font-weight: bold; 
            padding: 10px; 
            border-radius: 5px;
        """)
        self.import_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("padding: 10px;")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch() # Push buttons to the right
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def col_to_idx(self, col_str):
        """
        Technical helper: Converts Excel column letters like 'A' to 0, 
        'B' to 1, 'Z' to 25, 'AA' to 26, etc.
        """
        col_str = col_str.upper().strip()
        if not col_str:
            return -1
        
        idx = 0
        for char in col_str:
            if 'A' <= char <= 'Z':
                # Base-26 calculation for letters
                idx = idx * 26 + (ord(char) - ord('A') + 1)
            else:
                return -1 # Invalid character check
        return idx - 1

    def get_mapping(self):
        """
        Compiles all the UI inputs into a clean mapping dictionary
        of numeric indices to be used by the csv_parser.
        """
        return {
            "start_row": self.start_row_spin.value(),
            "name_idx": self.col_to_idx(self.name_col_input.text()),
            "power_indices": [self.col_to_idx(inp.text()) for inp in self.power_inputs],
            "bonus_indices": [self.col_to_idx(inp.text()) for inp in self.bonus_inputs],
            "slot_idx": self.col_to_idx(self.slot_col_input.text()),
            "set_idx": self.col_to_idx(self.set_col_input.text())
        }
