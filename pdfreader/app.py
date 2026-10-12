import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from .window import MainWindow


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.nismo.pdfreader",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

    def do_activate(self):
        win = self.get_active_window()
        if not win:
            win = MainWindow(self)
        win.present()

    def do_open(self, files, _n_files, _hint):
        self.do_activate()
        win = self.get_active_window()
        for gfile in files:
            win.load_file(gfile.get_path())
            break


def main(argv=None):
    app = Application()
    return app.run(argv if argv is not None else sys.argv)
