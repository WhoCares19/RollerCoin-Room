import sys
import os
from PyQt5 import QtWidgets, QtCore

# Ensure the directory containing this script is in the search path
# This helps resolve imports when files are moved into subfolders like 'assets'
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from miner_app import MinerApp
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import MinerApp from miner_app.py.")
    print(f"Error details: {e}")
    sys.exit(1)

if __name__ == "__main__":
    print("DEBUG: Starting application from script directory.")
    app = QtWidgets.QApplication(sys.argv)
    
    # Initialize the main application window
    # The MinerApp class internally calculates the project root
    window = MinerApp()

    # Center the window on the available screen geometry
    screen_geometry = app.desktop().availableGeometry()
    window.setGeometry(
        QtWidgets.QStyle.alignedRect(
            QtCore.Qt.LeftToRight,
            QtCore.Qt.AlignCenter,
            window.size(),
            screen_geometry
        )
    )
    
    print("DEBUG: Application window initialized and centered.")
    window.show()
    sys.exit(app.exec_())
