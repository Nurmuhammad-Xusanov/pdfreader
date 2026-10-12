"""In-memory annotation model.

Coordinates are stored in PDF points, relative to the top-left of the page
(same convention as PyMuPDF).  Screen/pixel conversion happens in the canvas.
"""


class Stroke:
    """Freehand ink stroke (pen or a free-form highlighter)."""

    kind = "stroke"

    def __init__(self, page, color, width, points, opacity=0.95):
        self.page = page
        self.color = tuple(color)
        self.width = float(width)
        self.points = list(points)  # list of (x, y, pressure)
        self.opacity = float(opacity)
        self.persisted = False
        self.pdf_annot = None
        self.pdf_page = None


class Highlight:
    """Text highlighter snapped to text-line bounding boxes."""

    kind = "highlight"

    def __init__(self, page, color, opacity, quads):
        self.page = page
        self.color = tuple(color)
        self.opacity = float(opacity)
        self.quads = list(quads)  # list of (x0, y0, x1, y1) in PDF points
        self.persisted = False
        self.pdf_annot = None
        self.pdf_page = None


class Note:
    """Sticky note placed anywhere on a page."""

    kind = "note"

    def __init__(self, page, color, pos, text="", size=(52.0, 40.0)):
        self.page = page
        self.color = tuple(color)
        self.pos = (float(pos[0]), float(pos[1]))
        self.text = text
        self.size = (float(size[0]), float(size[1]))
        self.persisted = False
        self.pdf_annot = None
        self.pdf_page = None
