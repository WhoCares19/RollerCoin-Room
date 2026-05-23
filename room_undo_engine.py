import copy

class UndoEngine:
    def __init__(self, max_depth=50):
        self.undo_stack = []
        self.redo_stack = []
        self.max_depth = max_depth

    def record_state(self, room_views, personal_inventory):
        """
        Creates a snapshot of the current application state.
        Returns True if a new state was recorded, False if the state is a duplicate.
        """
        snapshot = {
            "rooms": copy.deepcopy([rv.get_room_state() for rv in room_views]),
            "personal_inventory": copy.deepcopy(personal_inventory)
        }

        # Don't record if the state hasn't changed
        if self.undo_stack and self.undo_stack[-1] == snapshot:
            return False

        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
            
        self.redo_stack.clear()
        return True

    def undo(self):
        """Pops the current state and returns the previous one."""
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            return self.undo_stack[-1]
        return None

    def redo(self):
        """Pops from redo and returns the next state."""
        if self.redo_stack:
            next_state = self.redo_stack.pop()
            self.undo_stack.append(next_state)
            return next_state
        return None