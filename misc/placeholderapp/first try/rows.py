from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPen

class ManagedItem(QGraphicsRectItem):
    def __init__(self, item_type, color, parent=None):
        super().__init__(parent)
        self.item_type = item_type 
        
        # Transparent Rack (30 alpha), solid Rows/Slots (120 alpha)
        alpha = 30 if item_type == 'rack' else 120
        self.setBrush(QBrush(QColor(color[0], color[1], color[2], alpha)))
        self.setPen(QPen(QColor(color[0], color[1], color[2], 255), 2))
        
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        # Static Z-order to prevent items disappearing behind each other
        z_values = {'rack': 0, 'row': 1, '1-slot': 2}
        z = z_values.get(item_type, 0)
        self.setZValue(z)
        
        print(f"[ROWS DEBUG] Created {item_type} (ID: {id(self)}) | Z: {z} | Parent: {id(parent) if parent else 'None'}")

    def set_rect_centered(self, w, h):
        """Resizes the item while keeping its center fixed, guarding against zero-size and invalid positions."""
        if w < 5 or h < 5:
            print(f"[ROWS DEBUG] REJECTED resize on {self.item_type} (ID: {id(self)}): Requested size {w}x{h} is too small.")
            return

        # Determine anchor point in scene coordinates
        if self.parentItem():
            anchor = self.mapToParent(self.rect().center())
            context = "Parent-Space"
        else:
            anchor = self.scenePos() + self.rect().center()
            context = "Scene-Space"
        
        self.setRect(0, 0, w, h)
        new_offset = self.rect().center()
        new_pos = anchor - new_offset

        # Clamp position to prevent runaway negative coordinates
        if not self.parentItem():
            new_pos.setX(max(0, new_pos.x()))
            new_pos.setY(max(0, new_pos.y()))

        # Check for infinite or NaN positions
        if not (float('-inf') < new_pos.x() < float('inf')) or not (float('-inf') < new_pos.y() < float('inf')):
            print(f"[ROWS DEBUG] ERROR: Calculated invalid position {new_pos} for {self.item_type}. Aborting move.")
            return

        self.setPos(new_pos)
        print(f"[ROWS DEBUG] Resized {self.item_type} (ID: {id(self)}) | Anchor ({context}): {anchor} | New Pos: {new_pos}")

    def itemChange(self, change, value):
        # Restrict 1-slot movement within parent row boundaries
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.parentItem()
            and self.item_type == "1-slot"
        ):
            parent_rect = self.parentItem().rect()
            my_rect = self.rect()

            if parent_rect.width() <= 0 or parent_rect.height() <= 0:
                return value  # Parent not ready

            max_x = parent_rect.width() - my_rect.width()
            max_y = parent_rect.height() - my_rect.height()

            x = max(0.0, min(value.x(), max_x))
            y = max(0.0, min(value.y(), max_y))
            return QPointF(x, y)

        return super().itemChange(change, value)
