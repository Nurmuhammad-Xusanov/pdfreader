import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .canvas import Canvas
from .config import load_config
from .document import Document
from .tools import ToolState

PALETTE = [
    (0.05, 0.05, 0.05),
    (1.0, 1.0, 1.0),
    (0.86, 0.15, 0.15),
    (0.15, 0.55, 1.0),
    (0.20, 0.80, 0.30),
    (1.0, 0.85, 0.0),
    (1.0, 0.55, 0.0),
    (0.85, 0.25, 0.85),
]


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_default_size(1180, 880)
        self.set_title("PDF Reader")

        self.document = None
        self.tool_state = ToolState()
        self.canvas = Canvas(self.tool_state)
        self.config = load_config()
        self._swatches = []
        self.btn_custom = None
        self._color_dialog = Gtk.ColorDialog()
        self._color_dialog.set_title("Rang tanlang")
        self._dirty = False

        self._install_css()
        self._install_icons()
        self._build_ui()
        self._build_actions()
        self.canvas.on_history_changed = self._on_history
        self.canvas.on_changed = self._on_canvas_changed
        self._apply_config()

    def _apply_config(self):
        if self.config.get("night_mode"):
            self.btn_invert.set_active(True)
        if self.config.get("fullscreen_on_open"):
            self._request_fullscreen()

    def _request_fullscreen(self):
        def _go(*_args):
            if not self.is_fullscreen():
                self.fullscreen()
            return False

        if self.get_mapped():
            _go()
        else:
            self.connect("map", _go)

    def enter_reading_mode(self):
        """Distraction-free mode used by the touch gesture: night + fullscreen."""
        self.btn_invert.set_active(True)
        self._request_fullscreen()

    # ---------------------------------------------------------- callbacks
    def _on_history(self, can_undo, can_redo):
        self.btn_undo.set_sensitive(can_undo)
        self.btn_redo.set_sensitive(can_redo)

    def _on_canvas_changed(self):
        self._dirty = True
        self._update_title()

    def _install_icons(self):
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        theme.add_search_path(os.path.join(os.path.dirname(__file__), "icons"))

    # -------------------------------------------------------------- theme
    def _install_css(self):
        swatch_css = "\n".join(
            ".swatches .sw-%d { background-image: none; background-color: rgba(%d,%d,%d,1); }"
            % (i, round(r * 255), round(g * 255), round(b * 255))
            for i, (r, g, b) in enumerate(PALETTE)
        )
        css = Gtk.CssProvider()
        css.load_from_string(
            """
            window, .background { background-color: #000000; color: #e6e6e6; }
            headerbar { background-color: #000000; color: #e6e6e6;
                        box-shadow: none; border-bottom: 1px solid #141414;
                        min-height: 40px; }
            headerbar button { background-image: none; background-color: #0d0d0d;
                        color: #e6e6e6; border: 1px solid #1c1c1c; min-width: 30px;
                        min-height: 30px; }
            headerbar button:hover { background-color: #171717; }

            .toolbar { background-color: #000000; padding: 4px 6px; }
            .toolbar button { background-image: none; background-color: transparent;
                        color: #d9d9d9; border: 1px solid transparent;
                        min-width: 30px; min-height: 30px; padding: 0;
                        border-radius: 8px; }
            .toolbar button:hover { background-color: #161616;
                        border-color: #232323; }
            .toolbar button:checked { background-color: #1f6feb;
                        color: #ffffff; border-color: #1f6feb; }
            .toolbar button:disabled { color: #4a4a4a; }

            .swatches .swatch { min-width: 22px; min-height: 22px; padding: 0;
                      border-radius: 5px; border: 2px solid #3a3a3a; }
            .swatches .swatch:hover { border-color: #6f6f6f; }
            .swatches .swatch.selected { border-color: #ffffff; }
            .swatches .sw-custom { background-image: linear-gradient(45deg,
                      #ff0000 0%, #ff8800 15%, #ffee00 30%, #22dd44 45%,
                      #00aaff 60%, #5533ff 75%, #cc00cc 90%, #ff0066 100%); }

            .toolbar-sep { background-color: #1c1c1c; min-width: 1px;
                           margin: 5px 4px; }
            .page-label { font-weight: 600; min-width: 60px; }
            .zoom-label { min-width: 46px; }
            .toolscroll { background-color: #000000;
                          border-bottom: 1px solid #141414; }
            .empty-icon { opacity: 0.28; }
            .placeholder { font-size: 1.05em; opacity: 0.5; }
            """
            + swatch_css
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ----------------------------------------------------------------- UI
    def _build_ui(self):
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

        self.lbl_title = Gtk.Label(label="PDF Reader")
        header.set_title_widget(self.lbl_title)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Asosiy menyu")
        menu_btn.set_menu_model(self._build_menu())
        header.pack_end(menu_btn)

        toolbar = self._build_toolbar()
        toolbar_scroll = Gtk.ScrolledWindow()
        toolbar_scroll.add_css_class("toolscroll")
        toolbar_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        toolbar_scroll.set_propagate_natural_height(True)
        toolbar_scroll.set_child(toolbar)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_child(self.canvas)
        self.canvas.attach(self.scrolled)
        self.scrolled.get_vadjustment().connect("value-changed", self._on_scroll)
        self.scrolled.get_hadjustment().connect("notify::page-size", self._on_scroll)

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        empty.set_halign(Gtk.Align.CENTER)
        empty.set_valign(Gtk.Align.CENTER)
        empty.set_vexpand(True)
        icon = Gtk.Image.new_from_icon_name("document-open-symbolic")
        icon.set_pixel_size(72)
        icon.add_css_class("empty-icon")
        empty.append(icon)
        placeholder = Gtk.Label(label="PDF ochish uchun Ctrl+O bosing")
        placeholder.add_css_class("placeholder")
        empty.append(placeholder)

        self.stack = Gtk.Stack()
        self.stack.add_named(empty, "empty")
        self.stack.add_named(self.scrolled, "document")
        self.stack.set_visible_child_name("empty")

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(toolbar_scroll)
        root.append(self.stack)
        self.set_child(root)

    def _build_menu(self):
        menu = Gio.Menu()

        file_section = Gio.Menu()
        file_section.append("Ochish…", "win.open")
        file_section.append("Saqlash", "win.save")
        file_section.append("Boshqa nom bilan saqlash…", "win.save-as")
        menu.append_section(None, file_section)

        edit_section = Gio.Menu()
        edit_section.append("Bekor qilish", "win.undo")
        edit_section.append("Qaytarish", "win.redo")
        menu.append_section(None, edit_section)

        view_section = Gio.Menu()
        view_section.append("Kenglikka moslash", "win.fit-width")
        view_section.append("100%", "win.zoom-reset")
        view_section.append("Tungi rejim", "win.toggle-invert")
        view_section.append("Butun ekran", "win.fullscreen")
        menu.append_section(None, view_section)

        app_section = Gio.Menu()
        app_section.append("Yopish", "win.close")
        menu.append_section(None, app_section)
        return menu

    # -------------------------------------------------------------- toolbar
    def _build_toolbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        bar.add_css_class("toolbar")

        # file operations
        bar.append(self._icon_button("document-open-symbolic", "Ochish (Ctrl+O)",
                                     lambda *_: self._action_open()))
        bar.append(self._icon_button("document-save-symbolic", "Saqlash (Ctrl+S)",
                                     lambda *_: self._save()))
        bar.append(self._icon_button("document-save-as-symbolic",
                                     "Boshqa nom bilan saqlash (Ctrl+Shift+S)",
                                     lambda *_: self._action_save_as()))
        bar.append(self._separator())

        # annotation tools (radio group)
        self.tool_buttons = {}
        group = None
        tools = [
            (ToolState.HAND, "hand-symbolic", "Qo'l / scroll"),
            (ToolState.HIGHLIGHT, "highlighter-symbolic", "Marker (matnga yopishadi)"),
            (ToolState.PEN, "pen-symbolic", "Qalam"),
            (ToolState.ERASER, "eraser-symbolic", "O'chirg'ich"),
            (ToolState.NOTE, "note-symbolic", "Izoh"),
        ]
        for tool, icon, tip in tools:
            btn = Gtk.ToggleButton()
            btn.set_icon_name(icon)
            btn.set_tooltip_text(tip)
            if group is None:
                group = btn
            else:
                btn.set_group(group)
            btn.connect("toggled", self._on_tool_toggled, tool)
            bar.append(btn)
            self.tool_buttons[tool] = btn
        self.tool_buttons[ToolState.HAND].set_active(True)
        bar.append(self._separator())

        # color palette
        swatch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        swatch_box.add_css_class("swatches")
        for i, _rgb in enumerate(PALETTE):
            btn = Gtk.Button()
            btn.add_css_class("swatch")
            btn.add_css_class(f"sw-{i}")
            btn.set_tooltip_text("Rang")
            btn.connect("clicked", self._on_color_clicked, i)
            swatch_box.append(btn)
            self._swatches.append(btn)
        self.btn_custom = Gtk.Button()
        self.btn_custom.add_css_class("swatch")
        self.btn_custom.add_css_class("sw-custom")
        self.btn_custom.set_tooltip_text("Maxsus rang…")
        self.btn_custom.connect("clicked", self._on_custom_color_clicked)
        swatch_box.append(self.btn_custom)
        bar.append(swatch_box)
        self._update_swatch_selection()
        bar.append(self._separator())

        # stroke width
        bar.append(self._icon_button("zoom-out-symbolic", "Ingichka",
                                     lambda *_: self._nudge_width(-2)))
        bar.append(self._icon_button("zoom-in-symbolic", "Qalin",
                                     lambda *_: self._nudge_width(2)))
        bar.append(self._separator())

        # history
        self.btn_undo = self._icon_button("edit-undo-symbolic", "Bekor qilish (Ctrl+Z)",
                                          lambda *_: self.canvas.undo())
        self.btn_undo.set_sensitive(False)
        bar.append(self.btn_undo)
        self.btn_redo = self._icon_button("edit-redo-symbolic", "Qaytarish (Ctrl+Alt+Z)",
                                          lambda *_: self.canvas.redo())
        self.btn_redo.set_sensitive(False)
        bar.append(self.btn_redo)
        bar.append(self._separator())

        # night / invert
        self.btn_invert = Gtk.ToggleButton()
        self.btn_invert.set_icon_name("night-light-symbolic")
        self.btn_invert.set_tooltip_text("Tungi rejim (Ctrl+I)")
        self.btn_invert.connect("toggled", lambda b: self.canvas.set_invert(b.get_active()))
        bar.append(self.btn_invert)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)

        # navigation
        bar.append(self._icon_button("go-previous-symbolic", "Oldingi sahifa",
                                     lambda *_: self._page_step(-1)))
        self.lbl_page = Gtk.Label(label="—")
        self.lbl_page.add_css_class("page-label")
        bar.append(self.lbl_page)
        bar.append(self._icon_button("go-next-symbolic", "Keyingi sahifa",
                                     lambda *_: self._page_step(1)))
        bar.append(self._separator())

        # zoom
        bar.append(self._icon_button("zoom-out-symbolic", "Kichraytirish (Ctrl+-)",
                                     lambda *_: self.canvas.zoom_by(1 / 1.25)))
        self.lbl_zoom = Gtk.Label(label="100%")
        self.lbl_zoom.add_css_class("zoom-label")
        bar.append(self.lbl_zoom)
        bar.append(self._icon_button("zoom-in-symbolic", "Kattalashtirish (Ctrl++)",
                                     lambda *_: self.canvas.zoom_by(1.25)))
        bar.append(self._icon_button("zoom-fit-best-symbolic", "Kenglikka moslash (Ctrl+F)",
                                     lambda *_: self.canvas.fit_width()))
        return bar

    def _icon_button(self, icon, tip, callback):
        btn = Gtk.Button()
        btn.set_icon_name(icon)
        btn.set_tooltip_text(tip)
        btn.connect("clicked", callback)
        return btn

    @staticmethod
    def _separator():
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.add_css_class("toolbar-sep")
        return sep

    # --------------------------------------------------------- toolbar cb
    def _on_tool_toggled(self, button, tool):
        if button.get_active():
            self.tool_state.set_tool(tool)
            self._update_swatch_selection()

    def _on_color_clicked(self, _button, index):
        self.tool_state.set_color(PALETTE[index])
        self._update_swatch_selection()

    def _on_custom_color_clicked(self, button):
        r, g, b = self.tool_state.current_color()
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue, rgba.alpha = r, g, b, 1.0
        self._color_dialog.choose_rgba(self, rgba, None, self._on_color_dialog_done)

    def _on_color_dialog_done(self, dialog, result):
        try:
            rgba = dialog.choose_rgba_finish(result)
        except GLib.Error:
            return  # dialog cancelled
        self.tool_state.set_color((rgba.red, rgba.green, rgba.blue))
        self._update_swatch_selection()

    def _update_swatch_selection(self):
        active = self.tool_state.current_color()
        found = False
        for i, btn in enumerate(self._swatches):
            if tuple(PALETTE[i]) == tuple(active):
                btn.add_css_class("selected")
                found = True
            else:
                btn.remove_css_class("selected")
        if self.btn_custom is not None:
            if found:
                self.btn_custom.remove_css_class("selected")
            else:
                self.btn_custom.add_css_class("selected")

    def _nudge_width(self, delta):
        self.tool_state.nudge_width(delta)

    # ----------------------------------------------------------- actions
    def _build_actions(self):
        app = self.get_application()
        specs = [
            ("open", self._action_open, ["<Control>o"]),
            ("save", self._save, ["<Control>s"]),
            ("save-as", self._action_save_as, ["<Control><Shift>s"]),
            ("zoom-in", lambda: self.canvas.zoom_by(1.25), ["<Control>plus", "<Control>equal"]),
            ("zoom-out", lambda: self.canvas.zoom_by(1 / 1.25), ["<Control>minus"]),
            ("zoom-reset", self.canvas.reset_zoom, ["<Control>0"]),
            ("fit-width", self.canvas.fit_width, ["<Control>f"]),
            ("next-page", lambda: self._page_step(1), ["<Control>Page_Down", "n"]),
            ("prev-page", lambda: self._page_step(-1), ["<Control>Page_Up", "p"]),
            ("first-page", lambda: self.canvas.scroll_to_page(0), ["<Control>Home"]),
            ("last-page", self._last_page, ["<Control>End"]),
            ("toggle-invert", self._toggle_invert, ["<Control>i"]),
            ("undo", self.canvas.undo, ["<Control>z"]),
            ("redo", self.canvas.redo, ["<Control><Alt>z", "<Control><Shift>z"]),
            ("fullscreen", self._toggle_fullscreen, ["F11"]),
            ("close", lambda: self.close(), ["<Control>q"]),
        ]
        for name, callback, accels in specs:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._make_handler(callback))
            self.add_action(action)
            app.set_accels_for_action(f"win.{name}", accels)

    @staticmethod
    def _make_handler(callback):
        def handler(_action, _param):
            callback()
        return handler

    def _toggle_fullscreen(self):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def _toggle_invert(self):
        self.btn_invert.set_active(not self.btn_invert.get_active())

    def _page_step(self, delta):
        if self.canvas.layout:
            self.canvas.scroll_to_page(self.canvas.current_page() + delta)

    def _last_page(self):
        if self.canvas.layout:
            self.canvas.scroll_to_page(len(self.canvas.layout) - 1)

    def _on_scroll(self, *_args):
        if self.canvas.layout:
            self.lbl_page.set_label(
                f"{self.canvas.current_page() + 1} / {len(self.canvas.layout)}"
            )
        self.lbl_zoom.set_label(f"{round(self.canvas.zoom * 100)}%")

    # ---------------------------------------------------------- document
    def load_file(self, path):
        if not path or not os.path.isfile(path):
            return
        if self.document is not None:
            self.document.close()
        self.document = Document(path)
        self.canvas.set_document(self.document)
        self.stack.set_visible_child_name("document")
        self._dirty = False
        self._update_title()
        self._on_scroll()

    def _update_title(self):
        name = "PDF Reader"
        if self.document is not None:
            name = os.path.basename(self.document.path)
        suffix = " •" if self._dirty else ""
        self.lbl_title.set_label(name + suffix)
        self.set_title(f"{name}{suffix} — PDF Reader")

    def _save(self):
        if self.document is None:
            return
        try:
            self.document.save()
            self._dirty = False
            self._update_title()
        except Exception as exc:  # pragma: no cover
            print("saqlashda xatolik:", exc)

    def _action_open(self):
        dialog = Gtk.FileDialog()
        dialog.set_title("PDF ochish")
        dialog.set_filters(self._pdf_filters())
        dialog.open(self, None, self._on_open_finished)

    def _on_open_finished(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if gfile is not None:
            self.load_file(gfile.get_path())

    def _action_save_as(self):
        if self.document is None:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Boshqa nom bilan saqlash")
        dialog.set_initial_name(os.path.basename(self.document.path))
        dialog.set_filters(self._pdf_filters())
        dialog.save(self, None, self._on_save_as_finished)

    def _on_save_as_finished(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        path = gfile.get_path()
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.document.save_as(path)
        except Exception as exc:  # pragma: no cover
            print("saqlashda xatolik:", exc)
            return
        self.load_file(path)

    @staticmethod
    def _pdf_filters():
        pdf_filter = Gtk.FileFilter()
        pdf_filter.set_name("PDF fayllar")
        pdf_filter.add_mime_type("application/pdf")
        pdf_filter.add_pattern("*.pdf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(pdf_filter)
        return filters
