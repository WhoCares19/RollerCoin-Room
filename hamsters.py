import os
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPixmap

class Hamster(QLabel):
    def __init__(self, parent=None, display_size=100, paused=False):
        super().__init__(parent)
        self.sprite_sheet = None
        self.frames = []
        self.current_frame = 0
        self.frame_width = 160  # Source width
        self.frame_height = 160 # Source height
        self.display_size = display_size
        self.paused = paused
        
        # Dragging state
        self.dragging = False
        self.drag_offset = QPoint()
        
        # UI Setup - use scaled display size
        self.setFixedSize(self.display_size, self.display_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Load Sprite Sheet
        sprite_path = os.path.join("assets", "hamsters", "Dusty", "mcuncle_Idle.png")
        if os.path.exists(sprite_path):
            self.sprite_sheet = QPixmap(sprite_path)
            self.load_frames()
            
            # Animation Timer - only start if not paused
            if not self.paused:
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.next_frame)
                self.timer.start(120)  # ~8 FPS
        else:
            self.setText("Missing Sprite")
            self.setStyleSheet("color: red; font-weight: bold;")

    def load_frames(self):
        if not self.sprite_sheet:
            return
        for i in range(6):
            # 1. Slice the 160x160 frame from sheet
            raw_frame = self.sprite_sheet.copy(i * self.frame_width, 0, self.frame_width, self.frame_height)
            # 2. Scale it to display size
            scaled_frame = raw_frame.scaled(self.display_size, self.display_size, 
                                            Qt.AspectRatioMode.KeepAspectRatio, 
                                            Qt.TransformationMode.SmoothTransformation)
            self.frames.append(scaled_frame)
            
        if self.frames:
            self.setPixmap(self.frames[0])

    def next_frame(self):
        if not self.frames or self.paused:
            return
        self.current_frame = (self.current_frame + 1) % len(self.frames)
        self.setPixmap(self.frames[self.current_frame])
        
        if self.dragging:
            self.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.position().toPoint()
            self.raise_()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            parent_rect = self.parent().rect()
            new_pos = self.mapToParent(event.position().toPoint()) - self.drag_offset
            
            # Boundary Clamping using dynamic size
            x = max(0, min(new_pos.x(), parent_rect.width() - self.width()))
            y = max(0, min(new_pos.y(), parent_rect.height() - self.height()))
            
            self.move(x, y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
        super().mouseReleaseEvent(event)