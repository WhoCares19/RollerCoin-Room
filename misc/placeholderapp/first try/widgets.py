from PySide6.QtWidgets import QGraphicsView, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent, QKeyEvent, QMouseEvent

class ZoomView(QGraphicsView):
    """Custom view with debug logging and zoom limits."""
    def __init__(self, scene):
        super().__init__(scene)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        print("[WIDGETS DEBUG] ZoomView initialized with StrongFocus")
        self.scale_factor = 1.0  # Track current zoom

    def focusInEvent(self, event):
        print("[WIDGETS DEBUG] Viewport gained focus")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        print("[WIDGETS DEBUG] Viewport lost focus")
        super().focusOutEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)

        print(f"[WIDGETS DEBUG] Mouse Click at Scene {scene_pos}")
        if not items:
            print("  -> No items found under cursor.")
        else:
            for i, item in enumerate(items):
                itype = getattr(item, 'item_type', 'Non-Managed Item')
                iz = item.zValue()
                ivis = item.isVisible()
                print(f"  -> Item {i}: Type={itype}, Z={iz}, Visible={ivis}, Rect={item.sceneBoundingRect()}")

        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            new_scale = self.scale_factor * factor
            # Limit zoom to 0.5x - 2x
            if 0.5 <= new_scale <= 2.0:
                self.scale(factor, factor)
                self.scale_factor = new_scale
                print(f"[WIDGETS DEBUG] Zoomed to {self.scale_factor:.2f}x")
            else:
                print(f"[WIDGETS DEBUG] Zoom limit reached: {self.scale_factor:.2f}x")
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Arrow key movement
        if key in [Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down]:
            selected = self.scene().selectedItems()
            print(f"[WIDGETS DEBUG] KeyPress: {event.text()} (Code: {key}) | Selected Count: {len(selected)}")

            if not selected:
                print("  -> No selection to move. Suppressing scroll.")
                event.accept()
                return

            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx, dy = 0, 0
            if key == Qt.Key.Key_Left: dx = -step
            elif key == Qt.Key.Key_Right: dx = step
            elif key == Qt.Key.Key_Up: dy = -step
            elif key == Qt.Key.Key_Down: dy = step

            for item in selected:
                old_pos = item.pos()
                item.moveBy(dx, dy)
                print(f"  -> Moved {getattr(item, 'item_type', 'item')} from {old_pos} to {item.pos()}")

            event.accept()
            return

        print(f"[WIDGETS DEBUG] KeyPress: {key} passed to super")
        super().keyPressEvent(event)
