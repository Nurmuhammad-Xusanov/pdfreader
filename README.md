# PDF Reader

**English** | [O'zbekcha](README.uz.md)

A lightweight, native GTK4 PDF reader and annotator for Linux. It writes
annotations straight into the PDF file itself using PyMuPDF — no proprietary
sidecar files.

![GTK4](https://img.shields.io/badge/GTK-4-4a90d9) ![Python](https://img.shields.io/badge/Python-3.14-3776ab) ![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.28-ef4444)

## Highlights

- **Native PDF annotations** — every stroke and mark is stored as a standard PDF
  annotation (`Ink`, `Highlight`, `Text`). Open the file in any other PDF reader
  and your annotations are still there.
- **Autosave** — each action is saved immediately (incremental save). You never
  lose an annotation even if you forget to hit Save.
- **OLED-black design** — a fully black background that is easy on the eyes and
  saves power on AMOLED screens. `Night mode` inverts the page.
- **Stylus support (MPP 2.0)** — pressure-sensitive drawing; finger and stylus
  work together (the stylus always draws, one finger / two fingers navigate).
- **Smart highlighter** — highlights snap to text lines automatically.
  Watermark / background text is **filtered out**, so stamping over a watermark
  no longer paints the whole page.
- **Sticky notes** — place anywhere, edit the text, then move and resize them
  with the `Hand` tool; the size is persisted inside the PDF.
- **Undo / Redo** — revert and reapply any action.
- **Fast and light** — only visible pages are rendered (lazy rendering), drawn
  through `GtkSnapshot`.
- **Single instance** — opening a file again reuses the existing window instead
  of spawning a new one.
- **Desktop integration** — `.desktop` entry, icon, and a default handler for
  `application/pdf`, so you can open files with a double-click from your file
  manager.

## Tools

| Tool | Purpose |
|------|---------|
| Hand | Scroll the page, move/resize notes |
| Highlighter | Snap-to-text highlight |
| Pen | Freehand drawing (pressure-sensitive) |
| Eraser | Remove a stroke or mark |
| Note | Add / edit a sticky note |

Pick a color from the palette and adjust the stroke width with `-` / `+`.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save as |
| `Ctrl+Z` | Undo |
| `Ctrl+Alt+Z` / `Ctrl+Shift+Z` | Redo |
| `Ctrl+F` | Fit to width |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / 100% |
| `Ctrl+scroll` | Zoom with the mouse |
| `n` / `p` | Next / previous page |
| `Ctrl+I` | Night mode |
| `F11` | Fullscreen |
| `Ctrl+Q` | Quit |

## Install

Requirements: GTK4 (PyGObject) and Python 3.11+ from your system.

### One-command install (no root, no AUR)

```bash
git clone https://github.com/Nurmuhammad-Xusanov/pdfreader.git
cd pdfreader
./install.sh
```

This installs the app to `~/.local`, creates the `.desktop` entry and icon, and
makes PDF Reader the default handler for `application/pdf`. Launch it from the
app menu, by double-clicking a PDF, or with `~/.local/bin/pdfreader`.

### From the GitHub release

```bash
pipx run pip install ./pdfreader-0.1.0.whl
```

### Development install

```bash
python -m venv --system-site-packages .venv   # GTK4 comes from the system
.venv/bin/pip install pymupdf
```

## Run

```bash
./run.sh [/path/to/file.pdf]
```

## Configuration

Create `~/.config/pdfreader/config.toml`:

```toml
night_mode = true          # start in OLED night mode
fullscreen_on_open = true  # open fullscreen (reading mode)
```

Reading mode (night + fullscreen) can also be requested per launch:

```bash
./run.sh --reading-mode /path/to/file.pdf
```

## Project layout

```
pdfreader/
  app.py          Gtk.Application (HANDLES_OPEN, single instance)
  config.py       loads ~/.config/pdfreader/config.toml
  window.py       window, compact toolbar, menu, actions
  canvas.py       rendering, overlays, gestures, undo/redo, note geometry
  document.py     PyMuPDF wrapper: render, text bbox, annot persistence
  annotations.py  Stroke / Highlight / Note model
  tools.py        ToolState (active tool, color, width)
  notedialog.py   note editing dialog
  icons/          symbolic SVG icons
```
