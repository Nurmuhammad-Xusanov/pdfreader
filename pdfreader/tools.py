"""Shared tool/colour state between the toolbar and the canvas."""


class ToolState:
    HAND = "hand"
    HIGHLIGHT = "highlight"
    PEN = "pen"
    ERASER = "eraser"
    NOTE = "note"

    def __init__(self):
        self.tool = self.HAND
        self.pen_color = (0.05, 0.05, 0.05)
        self.highlight_color = (1.0, 0.90, 0.10)
        self.note_color = (1.0, 0.63, 0.0)
        self.pen_width = 2.5
        self.highlight_width = 16.0
        self.highlight_opacity = 0.38
        self._listeners = []

    def add_listener(self, callback):
        self._listeners.append(callback)

    def _notify(self):
        for cb in self._listeners:
            cb()

    def set_tool(self, tool):
        if tool == self.tool:
            return
        self.tool = tool
        self._notify()

    def current_color(self):
        if self.tool == self.HIGHLIGHT:
            return self.highlight_color
        if self.tool == self.NOTE:
            return self.note_color
        return self.pen_color

    def set_color(self, rgb):
        rgb = tuple(rgb)
        if self.tool == self.HIGHLIGHT:
            self.highlight_color = rgb
        elif self.tool == self.NOTE:
            self.note_color = rgb
        elif self.tool == self.PEN:
            self.pen_color = rgb
        else:
            self.pen_color = rgb
            self.highlight_color = rgb
        self._notify()

    def active_width(self):
        return self.highlight_width if self.tool == self.HIGHLIGHT else self.pen_width

    def nudge_width(self, delta):
        if self.tool == self.HIGHLIGHT:
            self.highlight_width = max(4.0, min(48.0, self.highlight_width + delta))
        else:
            self.pen_width = max(0.5, min(20.0, self.pen_width + delta))
        self._notify()
