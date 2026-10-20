"""Document wrapper: rendering, text geometry, annotation persistence."""

import os
import tempfile

import pymupdf as fitz

from .annotations import Highlight, Note, Stroke


class Document:
    def __init__(self, path):
        self.path = path
        self.doc = fitz.open(path)
        self.page_count = self.doc.page_count
        self._sizes = [
            (self.doc[i].rect.width, self.doc[i].rect.height)
            for i in range(self.page_count)
        ]
        self._lines = {}
        self._words = {}
        self._dirty = False

    # ---- geometry -------------------------------------------------------
    def page_size(self, index):
        return self._sizes[index]

    def text_lines(self, index):
        """Return cached text-line bboxes [(x0,y0,x1,y1), ...] for a page.

        Watermark / background text is filtered out so the highlighter snaps
        to real body text instead of a full-page diagonal stamp.
        """
        if index not in self._lines:
            page = self.doc[index]
            W, H = self._sizes[index]
            raw = []
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type", 0) != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    size = max((s.get("size", 0.0) for s in spans), default=0.0)
                    d = line.get("dir", (1.0, 0.0))
                    raw.append((tuple(line["bbox"]), size, d))
            sizes = [s for _, s, _ in raw if s > 0]
            median = sorted(sizes)[len(sizes) // 2] if sizes else 0.0
            lines = []
            for bbox, size, d in raw:
                x0, y0, x1, y1 = bbox
                w, h = x1 - x0, y1 - y0
                if abs(d[1]) > 0.1:
                    continue                       # rotated stamp
                if W and H and w > 0.8 * W and h > 0.6 * H:
                    continue                       # full-page block
                if len(sizes) >= 4 and median > 0 and size > 3.0 * median:
                    continue                       # oversized display text
                lines.append((x0, y0, x1, y1))
            self._lines[index] = lines
        return self._lines[index]

    def text_words(self, index):
        """Return cached word bboxes [(x0,y0,x1,y1), ...] for a page."""
        if index not in self._words:
            page = self.doc[index]
            W, H = self._sizes[index]
            boxes = []
            try:
                words = page.get_text("words")
                if words:
                    from collections import defaultdict

                    by_line = defaultdict(list)
                    for w in words:
                        by_line[(w[5], w[6])].append(w)
                    for lst in by_line.values():
                        lst.sort(key=lambda x: x[0])
                        for w in lst:
                            boxes.append((w[0], w[1], w[2], w[3]))
            except Exception:
                boxes = []

            if len(boxes) < 5:
                boxes = list(self.text_lines(index))

            # filter out very large blocks
            boxes_f = []
            for b in boxes:
                x0, y0, x1, y1 = b
                w, h = x1 - x0, y1 - y0
                if W and H and w > 0.9 * W and h > 0.7 * H:
                    continue
                boxes_f.append(b)
            if boxes_f:
                boxes = boxes_f

            self._words[index] = boxes
        return self._words[index]

    # ---- rendering ------------------------------------------------------
    def render(self, index, zoom, scale=1.0, invert=False):
        page = self.doc[index]
        matrix = fitz.Matrix(zoom * scale, zoom * scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False, annots=False)
        if invert:
            pix.invert_irect()
        return pix

    # ---- annotations ----------------------------------------------------
    def load_annotations(self):
        result = []
        for i in range(self.page_count):
            page = self.doc[i]
            before = len(result)
            for annot in page.annots():
                kind = annot.type[1]
                try:
                    if kind == "Ink":
                        result.extend(self._read_ink(i, annot))
                    elif kind == "Highlight":
                        self._read_highlight(i, annot, result)
                    elif kind == "Text":
                        result.append(self._read_note(i, annot))
                except Exception:
                    continue
            for ann in result[before:]:
                ann.pdf_page = page
        return result

    @staticmethod
    def _read_ink(page_index, annot):
        color = tuple(annot.colors.get("stroke") or (0, 0, 0))
        opacity = annot.opacity if annot.opacity and annot.opacity >= 0 else 1.0
        try:
            width = annot.border.get("width") or 1.5
        except Exception:
            width = 1.5
        out = []
        for raw in annot.vertices:
            points = [(float(x), float(y), 1.0) for x, y in raw]
            if len(points) >= 1:
                out.append(Stroke(page_index, color, width, points, opacity=opacity))
                out[-1].persisted = True
                out[-1].pdf_annot = annot
        return out

    @staticmethod
    def _read_highlight(page_index, annot, result):
        color = tuple(annot.colors.get("stroke") or (1, 1, 0))
        opacity = annot.opacity if annot.opacity and annot.opacity >= 0 else 0.4
        verts = annot.vertices
        quads = []
        for j in range(0, len(verts), 4):
            quad = verts[j:j + 4]
            if len(quad) == 4:
                xs = [p[0] for p in quad]
                ys = [p[1] for p in quad]
                quads.append((min(xs), min(ys), max(xs), max(ys)))
        if quads:
            ann = Highlight(page_index, color, opacity, quads)
            ann.persisted = True
            ann.pdf_annot = annot
            result.append(ann)

    @staticmethod
    def _note_size_tag(size):
        return f"pdfreader-size:{size[0]:.1f}x{size[1]:.1f}"

    @staticmethod
    def _parse_note_size(subject):
        if subject and subject.startswith("pdfreader-size:"):
            try:
                w, h = subject.split(":", 1)[1].split("x")
                return (max(20.0, float(w)), max(20.0, float(h)))
            except Exception:
                return None
        return None

    @staticmethod
    def _read_note(page_index, annot):
        color = tuple(annot.colors.get("stroke") or (1, 0.6, 0))
        rect = annot.rect
        info = annot.info or {}
        text = info.get("content", "") or ""
        size = Document._parse_note_size(info.get("subject"))
        if size is None:
            size = (max(20.0, rect.width), max(20.0, rect.height))
        ann = Note(page_index, color, (rect.x0, rect.y0), text, size=size)
        ann.persisted = True
        ann.pdf_annot = annot
        return ann

    def write_annot(self, annot):
        page = self.doc[annot.page]
        if annot.kind == "stroke":
            strokes = [[(x, y) for x, y, _p in annot.points]]
            pa = page.add_ink_annot(strokes)
            pa.set_colors(stroke=annot.color)
            pa.set_opacity(annot.opacity)
            try:
                pa.set_border(width=annot.width)
            except Exception:
                pass
        elif annot.kind == "highlight":
            quads = [fitz.Rect(q) for q in annot.quads]
            pa = page.add_highlight_annot(quads=quads)
            pa.set_colors(stroke=annot.color)
            pa.set_opacity(annot.opacity)
        elif annot.kind == "note":
            pa = page.add_text_annot(fitz.Point(*annot.pos), annot.text, icon="Note")
            pa.set_colors(stroke=annot.color)
            try:
                pa.set_info(content=annot.text,
                            subject=self._note_size_tag(annot.size))
            except Exception:
                pass
            try:
                pa.set_rect(fitz.Rect(annot.pos[0], annot.pos[1],
                                      annot.pos[0] + annot.size[0],
                                      annot.pos[1] + annot.size[1]))
            except Exception:
                pass
        else:
            return None
        annot.pdf_annot = pa
        annot.pdf_page = page
        annot.persisted = True
        self._dirty = True
        return pa

    def delete_annot(self, annot):
        if annot.pdf_annot is not None:
            try:
                self.doc[annot.page].delete_annot(annot.pdf_annot)
                self._dirty = True
            except Exception:
                pass
        annot.pdf_annot = None

    def update_note_text(self, annot):
        if annot.pdf_annot is not None:
            try:
                annot.pdf_annot.set_info(content=annot.text)
                self._dirty = True
            except Exception:
                pass

    def update_note_geometry(self, annot):
        if annot.pdf_annot is not None:
            try:
                annot.pdf_annot.set_info(subject=self._note_size_tag(annot.size))
                annot.pdf_annot.set_rect(fitz.Rect(
                    annot.pos[0], annot.pos[1],
                    annot.pos[0] + annot.size[0], annot.pos[1] + annot.size[1]))
                self._dirty = True
            except Exception:
                pass

    def update_note(self, annot):
        self.update_note_text(annot)
        self.update_note_geometry(annot)

    def save(self):
        if not self._dirty:
            return False
        try:
            self.doc.saveIncr()
        except Exception:
            self._full_save()
        self._dirty = False
        return True

    def _full_save(self):
        """Rewrite the whole file (for repaired/encrypted PDFs where
        incremental saving is unsupported)."""
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=directory)
        os.close(fd)
        try:
            self.doc.save(tmp, garbage=3, deflate=True)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def save_as(self, path):
        """Full save to a new path (bakes in all pending annot changes)."""
        self.doc.save(path, garbage=3, deflate=True)
        self.path = path
        self._dirty = False
        return True

    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass
