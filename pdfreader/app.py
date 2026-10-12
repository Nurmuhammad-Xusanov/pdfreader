import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from .window import MainWindow


class Application(Gtk.Application):
    def __init__(self, reading_mode=False):
        super().__init__(
            application_id="com.nismo.pdfreader",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.reading_mode = reading_mode

    def do_activate(self):
        win = self.get_active_window()
        if not win:
            win = MainWindow(self)
            win.present()
            if self.reading_mode:
                win.enter_reading_mode()
        else:
            win.present()

    def do_open(self, files, _n_files, _hint):
        self.do_activate()
        win = self.get_active_window()
        if self.reading_mode:
            win.enter_reading_mode()
        for gfile in files:
            win.load_file(gfile.get_path())
            break


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    reading_mode = False
    rest = []
    for arg in argv:
        if arg in ("-r", "--reading-mode"):
            reading_mode = True
        else:
            rest.append(arg)

    app = Application(reading_mode=reading_mode)
    return app.run(rest if rest else sys.argv[:1])
