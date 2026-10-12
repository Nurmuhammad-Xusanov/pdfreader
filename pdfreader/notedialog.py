import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class NoteDialog(Gtk.Window):
    def __init__(self, parent, text=""):
        super().__init__(title="Izoh")
        self.set_modal(True)
        self.set_default_size(380, 260)
        self._callback = None
        self._done = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.get_buffer().set_text(text or "")
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.view)
        box.append(scrolled)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)

        delete = Gtk.Button(label="O'chirish")
        delete.connect("clicked", lambda *_: self._finish(""))
        cancel = Gtk.Button(label="Bekor")
        cancel.connect("clicked", lambda *_: self._finish(None))
        save = Gtk.Button(label="Saqlash")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda *_: self._finish(self._text()))

        buttons.append(delete)
        buttons.append(cancel)
        buttons.append(save)
        box.append(buttons)

        self.set_child(box)
        self.connect("close-request", self._on_close)

    def _text(self):
        buf = self.view.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

    def connect_text(self, callback):
        self._callback = callback

    def _finish(self, value):
        self._done = True
        if self._callback:
            self._callback(value)
        self.close()

    def _on_close(self, *_args):
        if not self._done and self._callback:
            self._callback(None)
        self._done = True
        return False
