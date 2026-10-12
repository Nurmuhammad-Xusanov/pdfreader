"""The document view: renders visible pages, draws annotation overlays and
handles mouse / touch / stylus input."""

import bisect
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gtk

from .annotations import Highlight, Note, Stroke
from .tools import ToolState

MARGIN = 18
SPACING = 18
ZOOM_MIN = 0.15
ZOOM_MAX = 6.0
NOTE_MIN_SIZE = 24.0
HANDLE = 14.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _invert(rgb):
    return (1.0 - rgb[0], 1.0 - rgb[1], 1.0 - rgb[2])


class Canvas(Gtk.Widget):
    __gtype_name__ = "PdfCanvas"

    def __init__(self, tool_state: ToolState):
        super().__init__()
        self.doc = None
        self.tool_state = tool_state
        self.zoom = 1.0
        self.invert = False
        self.layout = []
        self.annots = []

        self._textures = {}
        self._width = 0
        self._height = 0
        self._requested = (0, 0)

        self._scrolled = None
        self._vadj = None
        self._hadj = None
        self._pending = None

        # interaction
        self._active = None
        self._pan = None
        self._note_gesture = None
        self.selected = None
        self._zoom0 = 1.0

        # undo / redo
        self._undo = []
        self._redo = []
        self.on_history_changed = None
        self.on_changed = None

        self.set_focusable(True)
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self._install_controllers()

        self.tool_state.add_listener(self.queue_draw)

    # ------------------------------------------------------------------ UI
    def _install_controllers(self):
        self.stylus = Gtk.GestureStylus()
        self.stylus.set_stylus_only(False)
        self.stylus.connect("down", self._on_stylus_down)
        self.stylus.connect("motion", self._on_stylus_motion)
        self.stylus.connect("up", self._on_stylus_up)
        self.add_controller(self.stylus)

        self.zoom_gesture = Gtk.GestureZoom()
        self.zoom_gesture.connect("begin", self._on_zoom_begin)
        self.zoom_gesture.connect("update", self._on_zoom_update)
        self.zoom_gesture.connect("end", self._on_zoom_end)
        self.add_controller(self.zoom_gesture)

        Gtk.Gesture.group(self.stylus, self.zoom_gesture)

        self.scroll_ctrl = Gtk.EventControllerScroll()
        self.scroll_ctrl.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        self.scroll_ctrl.connect("scroll", self._on_scroll_ctrl)
        self.add_controller(self.scroll_ctrl)

    def _on_scroll_ctrl(self, controller, dx, dy):
        state = controller.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            factor = 1.0 + _clamp(-dy, -1.0, 1.0) * 0.25
            self.zoom_by(factor)
            return True
        return False

    def attach(self, scrolled: Gtk.ScrolledWindow):
        self._scrolled = scrolled
        self._vadj = scrolled.get_vadjustment()
        self._hadj = scrolled.get_hadjustment()
        self._hadj.connect("notify::upper", self._on_adj_upper)
        self._vadj.connect("notify::upper", self._on_adj_upper)
        self._hadj.connect("notify::page-size", self._on_viewport_change)
        self._vadj.connect("notify::page-size", self._on_viewport_change)
        self._vadj.connect("value-changed", lambda *_: self.queue_draw())
        self._hadj.connect("value-changed", lambda *_: self.queue_draw())

    def _on_viewport_change(self, *_args):
        self.recompute_layout()
        self.queue_draw()

    def _on_adj_upper(self, *_args):
        self._apply_pending()

    # -------------------------------------------------------------- layout
    def set_document(self, doc):
        self.doc = doc
        self.annots = doc.load_annotations() if doc else []
        self._textures.clear()
        self.zoom = 1.0
        self._pending = None
        self.selected = None
        self._undo.clear()
        self._redo.clear()
        self._notify_history()
        self.recompute_layout()
        self.queue_draw()
        if self._vadj:
            self._hadj.set_value(0)
            self._vadj.set_value(0)

    def recompute_layout(self):
        self.layout = []
        if not self.doc:
            if self._requested != (0, 0):
                self.set_size_request(0, 0)
                self._requested = (0, 0)
            self._width = self._height = 0
            return
        vw = self._hadj.get_page_size() if self._hadj else 0
        maxw = 0.0
        y = MARGIN
        items = []
        for i in range(self.doc.page_count):
            pw, ph = self.doc.page_size(i)
            w = pw * self.zoom
            h = ph * self.zoom
            maxw = max(maxw, w)
            items.append((i, y, w, h))
            y += h + SPACING
        content_w = max(maxw + 2 * MARGIN, float(vw))
        content_h = y - SPACING + MARGIN
        for i, yy, w, h in items:
            self.layout.append(
                {"index": i, "x": (content_w - w) / 2, "y": yy, "w": w, "h": h}
            )
        self._width = content_w
        self._height = content_h
        req = (int(content_w), int(content_h))
        if req != self._requested:
            self.set_size_request(*req)
            self._requested = req

    def current_page(self):
        if not self.layout:
            return 0
        v = self._vadj.get_value() + (self._vadj.get_page_size() or 0) / 2
        ys = [lay["y"] for lay in self.layout]
        return _clamp(bisect.bisect_right(ys, v) - 1, 0, len(self.layout) - 1)

    def _page_at(self, cx, cy):
        for lay in self.layout:
            if (lay["x"] <= cx <= lay["x"] + lay["w"]
                    and lay["y"] <= cy <= lay["y"] + lay["h"]):
                return lay["index"]
        return None

    def _to_pdf(self, page, cx, cy):
        lay = self.layout[page]
        return (cx - lay["x"]) / self.zoom, (cy - lay["y"]) / self.zoom

    # ------------------------------------------------------------- texture
    def _texture_for(self, index):
        scale = self.get_scale_factor()
        cached = self._textures.get(index)
        if cached and cached[1] == self.zoom and cached[2] == scale \
                and cached[3] == self.invert:
            return cached[0]
        pix = self.doc.render(index, self.zoom, scale, self.invert)
        if pix.n == 4:
            fmt = Gdk.MemoryFormat.R8G8B8A8
        elif pix.n == 1:
            fmt = Gdk.MemoryFormat.R8
        else:
            fmt = Gdk.MemoryFormat.R8G8B8
        data = GLib.Bytes.new(pix.samples)
        tex = Gdk.MemoryTexture.new(pix.width, pix.height, fmt, data, pix.stride)
        self._textures[index] = (tex, self.zoom, scale, self.invert)
        return tex

    def set_invert(self, invert):
        if invert == self.invert:
            return
        self.invert = invert
        self._textures.clear()
        self.queue_draw()

    # -------------------------------------------------------------- zoom
    def _set_zoom(self, z):
        z = _clamp(z, ZOOM_MIN, ZOOM_MAX)
        if abs(z - self.zoom) < 1e-6:
            return
        self.zoom = z
        self._textures.clear()
        self.recompute_layout()
        self.queue_resize()
        self.queue_draw()

    def zoom_by(self, factor):
        if not self.doc:
            return
        vx, vy, vw, vh = self._viewport()
        cx = vx + vw / 2
        cy = vy + vh / 2
        old = self.zoom
        self._set_zoom(self.zoom * factor)
        actual = self.zoom / old
        self._request_scroll(cx * actual - vw / 2, cy * actual - vh / 2)

    def set_zoom(self, z):
        if not self.doc:
            return
        self.zoom_by(_clamp(z, ZOOM_MIN, ZOOM_MAX) / self.zoom)

    def fit_width(self):
        if not self.doc:
            return
        _, _, vw, vh = self._viewport()
        pw, _ = self.doc.page_size(self.current_page())
        target = (vw - 2 * MARGIN - 4) / pw
        self.set_zoom(target)

    def reset_zoom(self):
        self.set_zoom(1.0)

    def _viewport(self):
        if not self._vadj:
            return 0, 0, max(self._width, 1), max(self._height, 1)
        return (self._hadj.get_value(), self._vadj.get_value(),
                max(self._hadj.get_page_size(), 1),
                max(self._vadj.get_page_size(), 1))

    def _request_scroll(self, x, y):
        self._pending = (_clamp(x, 0, max(0, self._width)),
                         _clamp(y, 0, max(0, self._height)))
        self._apply_pending()
        GLib.idle_add(self._apply_pending)

    def _apply_pending(self):
        if not self._pending or not self._vadj:
            return False
        x, y = self._pending
        self._hadj.set_value(x)
        self._vadj.set_value(y)
        if abs(self._hadj.get_value() - x) < 0.5 and abs(self._vadj.get_value() - y) < 0.5:
            self._pending = None
        return False

    def scroll_to_page(self, index):
        if not self.layout:
            return
        index = _clamp(index, 0, len(self.layout) - 1)
        self._request_scroll(self.layout[index]["x"], self.layout[index]["y"] - MARGIN + 4)

    # ------------------------------------------------------------ snapshot
    def do_snapshot(self, snapshot, width=None, height=None):
        if width is None:
            width = self.get_width()
        if height is None:
            height = self.get_height()
        snapshot.append_color(
            Gdk.RGBA(red=0, green=0, blue=0, alpha=1),
            Graphene.Rect().init(0, 0, width, height),
        )
        if not self.doc or not self.layout:
            return
        vx, vy, vw, vh = self._viewport()
        top, bottom = vy - 400, vy + vh + 400
        for lay in self.layout:
            if lay["y"] > bottom or lay["y"] + lay["h"] < top:
                continue
            tex = self._texture_for(lay["index"])
            if tex is not None:
                snapshot.append_texture(
                    tex, Graphene.Rect().init(lay["x"], lay["y"], lay["w"], lay["h"])
                )
        cairo_ctx = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
        if cairo_ctx is not None:
            self._draw_overlays(cairo_ctx, top, bottom)
            self._draw_active(cairo_ctx)

    # ------------------------------------------------------------ overlay
    def _draw_overlays(self, cr, top, bottom):
        inv = self.invert
        for ann in self.annots:
            lay = self.layout[ann.page]
            if lay["y"] > bottom or lay["y"] + lay["h"] < top:
                continue
            if ann.kind == "stroke":
                self._draw_stroke(cr, lay, ann.points, ann.color, ann.width,
                                  ann.opacity, inv)
            elif ann.kind == "highlight":
                self._draw_quads(cr, lay, ann.quads, ann.color, ann.opacity, inv)
            elif ann.kind == "note":
                self._draw_note(cr, lay, ann, inv)

    def _draw_active(self, cr):
        if not self._active:
            return
        lay = self.layout[self._active["page"]]
        inv = self.invert
        if self._active["kind"] == "highlight":
            color = self.tool_state.highlight_color
            pts = self._active["pts"]
            # live preview: free band following the stroke
            self._draw_stroke(cr, lay, pts, color,
                              self.tool_state.highlight_width,
                              self.tool_state.highlight_opacity, inv)
        else:
            self._draw_stroke(cr, lay, self._active["pts"],
                              self._active["color"], self._active["width"], 0.95, inv)

    def _color(self, rgb, inv):
        return _invert(rgb) if inv else rgb

    def _draw_stroke(self, cr, lay, points, color, base_width, opacity, inv):
        r, g, b = self._color(color, inv)
        z = self.zoom
        cr.set_source_rgba(r, g, b, opacity)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        ox, oy = lay["x"], lay["y"]
        if len(points) == 1:
            x = ox + points[0][0] * z
            y = oy + points[0][1] * z
            w = max(1.0, base_width * z)
            cr.arc(x, y, w / 2, 0, 2 * math.pi)
            cr.fill()
            return
        for a, b2 in zip(points, points[1:]):
            x0, y0 = ox + a[0] * z, oy + a[1] * z
            x1, y1 = ox + b2[0] * z, oy + b2[1] * z
            pressure = ((a[2] + b2[2]) / 2) if len(a) > 2 else 1.0
            cr.set_line_width(max(0.6, base_width * z * (0.45 + 0.55 * pressure)))
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()

    def _draw_quads(self, cr, lay, quads, color, opacity, inv):
        r, g, b = self._color(color, inv)
        z = self.zoom
        cr.set_source_rgba(r, g, b, opacity)
        for x0, y0, x1, y1 in quads:
            cr.rectangle(lay["x"] + x0 * z, lay["y"] + y0 * z,
                         (x1 - x0) * z, (y1 - y0) * z)
        cr.fill()

    def _draw_note(self, cr, lay, ann, inv):
        r, g, b = self._color(ann.color, inv)
        z = self.zoom
        x = lay["x"] + ann.pos[0] * z
        y = lay["y"] + ann.pos[1] * z
        w = max(8.0, ann.size[0] * z)
        h = max(8.0, ann.size[1] * z)

        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.rectangle(x + 2, y + 2, w, h)
        cr.fill()

        cr.set_source_rgba(r, g, b, 1.0)
        cr.rectangle(x, y, w, h)
        cr.fill()

        head = min(10.0, h * 0.3)
        cr.set_source_rgba(0, 0, 0, 0.18)
        cr.rectangle(x, y, w, head)
        cr.fill()

        text = " ".join((ann.text or "").split())
        if text:
            cr.set_source_rgba(0.05, 0.05, 0.05, 0.9)
            size = max(7.0, min(12.0, h * 0.3))
            cr.select_font_face("sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(size)
            cr.move_to(x + 4, y + head + size)
            cr.show_text(text[:48])
        else:
            cr.set_source_rgba(0.05, 0.05, 0.05, 0.75)
            for i in range(3):
                ly = y + head + 6 + i * 6
                if ly < y + h - 2:
                    cr.rectangle(x + 4, ly, w - 8, 1.6)
            cr.fill()

        if ann is self.selected:
            cr.set_line_width(1.5)
            cr.set_source_rgba(0.2, 0.6, 1.0, 0.95)
            cr.rectangle(x - 1, y - 1, w + 2, h + 2)
            cr.stroke()
            cr.set_source_rgba(0.2, 0.6, 1.0, 1.0)
            cr.rectangle(x + w - HANDLE / 2, y + h - HANDLE / 2, HANDLE, HANDLE)
            cr.fill()

    # ------------------------------------------------------------- stylus
    def _pressure(self, gesture):
        ok, value = gesture.get_axis(Gdk.AxisUse.PRESSURE)
        if not ok or value is None or value <= 0:
            return 1.0
        return _clamp(float(value), 0.05, 1.0)

    def _on_stylus_down(self, gesture, x, y):
        if not self.doc:
            return
        self._pointer_press(x, y, self._pressure(gesture))

    def _on_stylus_motion(self, gesture, x, y):
        if self._note_gesture is not None:
            self._note_move(x, y)
        elif self._pan is not None:
            self._pan_update(x, y)
        elif self._active is not None:
            self._draw_update(x, y, self._pressure(gesture))

    def _on_stylus_up(self, gesture, x, y):
        if self._note_gesture is not None:
            self._note_release()
        elif self._pan is not None:
            self._end_pan()
        elif self._active is not None:
            self._end_draw()

    # ------------------------------------------------------- pointer logic
    def _pointer_press(self, x, y, pressure):
        tool = self.tool_state.tool
        if tool == ToolState.HAND:
            self._hand_press(x, y)
            return
        if tool == ToolState.ERASER:
            self._erase_at(x, y)
            return
        page = self._page_at(x, y)
        if page is None:
            self._begin_pan(x, y)
            return
        if tool == ToolState.NOTE:
            self._place_note(page, x, y)
            return
        px, py = self._to_pdf(page, x, y)
        if tool == ToolState.HIGHLIGHT:
            self._active = {"kind": "highlight", "page": page, "pts": [(px, py, pressure)]}
        else:
            self._active = {
                "kind": "stroke", "page": page,
                "color": self.tool_state.pen_color,
                "width": self.tool_state.pen_width,
                "pts": [(px, py, pressure)],
            }
        self.queue_draw()

    def _draw_update(self, x, y, pressure):
        active = self._active
        if not active:
            return
        page = active["page"]
        pw, ph = self.doc.page_size(page)
        px, py = self._to_pdf(page, x, y)
        active["pts"].append((_clamp(px, 0, pw), _clamp(py, 0, ph), pressure))
        self.queue_draw()

    def _end_draw(self):
        active = self._active
        self._active = None
        if not active or not active["pts"]:
            self.queue_draw()
            return
        if active["kind"] == "highlight":
            self._commit(self._finalize_highlight(active))
        else:
            self._commit(Stroke(active["page"], active["color"],
                                active["width"], active["pts"]))
        self.queue_draw()

    def _finalize_highlight(self, active):
        page = active["page"]
        pts = active["pts"]
        lines = self.doc.text_lines(page)
        chosen = []
        for px, py, _p in pts:
            for lb in lines:
                x0, y0, x1, y1 = lb
                if x0 - 3 <= px <= x1 + 3 and y0 - 2 <= py <= y1 + 2:
                    if lb not in chosen:
                        chosen.append(lb)
                    break
        if chosen:
            return Highlight(page, self.tool_state.highlight_color,
                             self.tool_state.highlight_opacity, chosen)
        return Stroke(page, self.tool_state.highlight_color,
                      self.tool_state.highlight_width, pts,
                      opacity=self.tool_state.highlight_opacity)

    # -------------------------------------------------------------- pan
    def _begin_pan(self, x, y):
        self._pan = {
            "lvx": x - self._hadj.get_value(),
            "lvy": y - self._vadj.get_value(),
            "x0": x, "y0": y, "moved": False,
        }

    def _pan_update(self, x, y):
        pan = self._pan
        if not pan:
            return
        vx = x - self._hadj.get_value()
        vy = y - self._vadj.get_value()
        self._hadj.set_value(self._hadj.get_value() + (pan["lvx"] - vx))
        self._vadj.set_value(self._vadj.get_value() + (pan["lvy"] - vy))
        pan["lvx"], pan["lvy"] = vx, vy
        if abs(x - pan["x0"]) + abs(y - pan["y0"]) > 8:
            pan["moved"] = True

    def _end_pan(self):
        self._pan = None

    # ---------------------------------------------------- note move/resize
    def _hand_press(self, x, y):
        ann = self._note_at(x, y)
        if ann is not None:
            lay = self.layout[ann.page]
            z = self.zoom
            hx = lay["x"] + (ann.pos[0] + ann.size[0]) * z
            hy = lay["y"] + (ann.pos[1] + ann.size[1]) * z
            on_handle = abs(x - hx) <= HANDLE and abs(y - hy) <= HANDLE
            self.selected = ann
            px, py = self._to_pdf(ann.page, x, y)
            self._note_gesture = {
                "ann": ann,
                "mode": "resize" if on_handle else "move",
                "start": (px, py),
                "orig_pos": ann.pos,
                "orig_size": ann.size,
                "moved": False,
            }
            self.queue_draw()
            return
        if self.selected is not None:
            self.selected = None
            self.queue_draw()
        self._begin_pan(x, y)

    def _note_move(self, x, y):
        g = self._note_gesture
        ann = g["ann"]
        px, py = self._to_pdf(ann.page, x, y)
        dx = px - g["start"][0]
        dy = py - g["start"][1]
        pw, ph = self.doc.page_size(ann.page)
        if g["mode"] == "resize":
            ann.size = (_clamp(g["orig_size"][0] + dx, NOTE_MIN_SIZE, pw),
                        _clamp(g["orig_size"][1] + dy, NOTE_MIN_SIZE, ph))
        else:
            ann.pos = (_clamp(g["orig_pos"][0] + dx, 0, max(0.0, pw - ann.size[0])),
                       _clamp(g["orig_pos"][1] + dy, 0, max(0.0, ph - ann.size[1])))
        if abs(dx) + abs(dy) > 0.5:
            g["moved"] = True
        self.queue_draw()

    def _note_release(self):
        g = self._note_gesture
        self._note_gesture = None
        if g is None:
            return
        ann = g["ann"]
        if not g["moved"]:
            self._open_note(ann)
            return
        old = (g["orig_pos"], g["orig_size"])
        new = (ann.pos, ann.size)
        self._persist_note(ann)
        self._push(
            lambda a=ann, p=old: self._set_note_geom(a, p),
            lambda a=ann, p=new: self._set_note_geom(a, p),
        )

    def _set_note_geom(self, ann, geom):
        ann.pos, ann.size = geom
        self._persist_note(ann)
        self.queue_draw()

    def _persist_note(self, ann):
        try:
            self.doc.update_note_geometry(ann)
            self.doc.save()
        except Exception:
            pass

    # ----------------------------------------------------------- zoom touch
    def _on_zoom_begin(self, gesture, sequence):
        if self._active is not None:
            self._active = None
            self.queue_draw()
        self._pan = None
        self._note_gesture = None
        self._zoom0 = self.zoom

    def _on_zoom_update(self, gesture, sequence):
        ok, cx, cy = gesture.get_bounding_box_center()
        if not ok:
            return
        scale = gesture.get_scale_delta() or 1.0
        target = _clamp(self._zoom0 * scale, ZOOM_MIN, ZOOM_MAX)
        vx, vy, _vw, _vh = self._viewport()
        vpx = cx - self._hadj.get_value()
        vpy = cy - self._vadj.get_value()
        old = self.zoom
        self._set_zoom(target)
        actual = self.zoom / old
        self._request_scroll(cx * actual - vpx, cy * actual - vpy)

    def _on_zoom_end(self, gesture, sequence):
        pass

    # ---------------------------------------------------------- eraser/note
    def _hit(self, ann, x, y):
        page = self._page_at(x, y)
        if page is None or page != ann.page:
            return False
        lay = self.layout[page]
        z = self.zoom
        lx = x - lay["x"]
        ly = y - lay["y"]
        tol = max(8.0, 5.0 * z)
        if ann.kind == "stroke":
            pts = [(p[0] * z, p[1] * z) for p in ann.points]
            return self._near_polyline(lx, ly, pts, tol + ann.width * z)
        if ann.kind == "highlight":
            for x0, y0, x1, y1 in ann.quads:
                if (x0 * z - tol <= lx <= x1 * z + tol
                        and y0 * z - tol <= ly <= y1 * z + tol):
                    return True
            return False
        if ann.kind == "note":
            nx, ny = ann.pos[0] * z, ann.pos[1] * z
            return (nx - tol <= lx <= nx + ann.size[0] * z + tol
                    and ny - tol <= ly <= ny + ann.size[1] * z + tol)
        return False

    @staticmethod
    def _near_polyline(px, py, pts, tol):
        if not pts:
            return False
        if len(pts) == 1:
            return math.hypot(px - pts[0][0], py - pts[0][1]) <= tol
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dx, dy = x1 - x0, y1 - y0
            seg2 = dx * dx + dy * dy
            if seg2 == 0:
                dist = math.hypot(px - x0, py - y0)
            else:
                t = _clamp(((px - x0) * dx + (py - y0) * dy) / seg2, 0, 1)
                dist = math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
            if dist <= tol:
                return True
        return False

    def _erase_at(self, x, y):
        for ann in reversed(self.annots):
            if self._hit(ann, x, y):
                self._remove_annot(ann)
                self._push(
                    lambda a=ann: self._add_annot(a),
                    lambda a=ann: self._remove_annot(a),
                )
                return

    def _note_at(self, x, y):
        for ann in reversed(self.annots):
            if ann.kind == "note" and self._hit(ann, x, y):
                return ann
        return None

    def _place_note(self, page, x, y):
        pw, ph = self.doc.page_size(page)
        px, py = self._to_pdf(page, x, y)
        ann = Note(page, self.tool_state.note_color,
                   (_clamp(px, 0, pw), _clamp(py, 0, ph)))
        self._open_note(ann, is_new=True)

    def _open_note(self, ann, is_new=False):
        from .notedialog import NoteDialog

        parent = self.get_root()
        old_text = ann.text
        dialog = NoteDialog(parent, ann.text)
        dialog.set_transient_for(parent)

        def on_done(text):
            if text is None:
                return
            new_text = text.strip()
            if not new_text:
                if ann in self.annots:
                    self._remove_annot(ann)
                    self._push(
                        lambda a=ann: self._add_annot(a),
                        lambda a=ann: self._remove_annot(a),
                    )
                return
            ann.text = new_text
            if is_new:
                self._commit(ann)
                return
            self.doc.update_note_text(ann)
            try:
                self.doc.save()
            except Exception:
                pass
            self.queue_draw()
            if new_text != old_text:
                self._push(
                    lambda a=ann, t=old_text: self._set_note_text(a, t),
                    lambda a=ann, t=new_text: self._set_note_text(a, t),
                )

        dialog.connect_text(on_done)
        dialog.present()

    def _set_note_text(self, ann, text):
        ann.text = text
        self.doc.update_note_text(ann)
        try:
            self.doc.save()
        except Exception:
            pass
        self.queue_draw()

    # ------------------------------------------------------ add / remove
    def _add_annot(self, ann, persist=True):
        if ann not in self.annots:
            self.annots.append(ann)
        if persist:
            try:
                self.doc.write_annot(ann)
                self.doc.save()
            except Exception as exc:
                print("annotatsiya saqlanmadi:", exc)
        self.queue_draw()

    def _remove_annot(self, ann, persist=True):
        if ann in self.annots:
            self.annots.remove(ann)
        if self.selected is ann:
            self.selected = None
        if persist:
            self.doc.delete_annot(ann)
            try:
                self.doc.save()
            except Exception:
                pass
        self.queue_draw()

    def _commit(self, ann):
        self._add_annot(ann)
        self._push(
            lambda a=ann: self._remove_annot(a),
            lambda a=ann: self._add_annot(a),
        )

    # ------------------------------------------------------- undo / redo
    def _push(self, undo_fn, redo_fn):
        self._undo.append((undo_fn, redo_fn))
        self._redo.clear()
        self._notify_history()

    def _notify_history(self):
        if self.on_history_changed:
            self.on_history_changed(bool(self._undo), bool(self._redo))
        if self.on_changed:
            self.on_changed()

    def undo(self):
        if not self._undo:
            return
        undo_fn, redo_fn = self._undo.pop()
        undo_fn()
        self._redo.append((undo_fn, redo_fn))
        self._notify_history()

    def redo(self):
        if not self._redo:
            return
        undo_fn, redo_fn = self._redo.pop()
        redo_fn()
        self._undo.append((undo_fn, redo_fn))
        self._notify_history()
