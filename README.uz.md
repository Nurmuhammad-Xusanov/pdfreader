# PDF Reader

[English](README.md) | **O'zbekcha**

Linux uchun yengil, native GTK4 PDF o'quvchi va annotator. PyMuPDF yordamida
annotatsiyalarni to'g'ridan-to'g'ri PDF faylning o'ziga yozadi — hech qanday
proprietary yon-fayl (sidecar) yo'q.

![GTK4](https://img.shields.io/badge/GTK-4-4a90d9) ![Python](https://img.shields.io/badge/Python-3.14-3776ab) ![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.28-ef4444)

## Ustunliklari

- **Native PDF annotatsiya** — barcha chizmalar/belgilar standart PDF
  annotatsiyalari (`Ink`, `Highlight`, `Text`) sifatida saqlanadi. Faylni
  istalgan boshqa PDF o'quvchi bilan ochsangiz ham ko'rinadi.
- **Avtomatik saqlash** — har bir amal tugagach darhol saqlanadi (incremental
  save). Saqlash tugmasini bosishni unutib qo'ysangiz ham annotatsiya yo'qolmaydi.
- **OLED-black dizayn** — to'liq qora fon, ko'zni charchatmaydi va AMOLED
  ekranlarda quvvat tejaydi. `Tungi rejim` sahifani invert qiladi.
- **Stilus (MPP 2.0) qo'llab-quvvatlanadi** — bosimga sezgir chizish; barmoq va
  stilus bir vaqtda ishlaydi (stilus har doim chizadi, barmoq/2-barmoq navigatsiya).
- **Aqlli marker** — highlight matn qatorlariga avtomatik yopishadi.
  Watermark/background matn **filtrlanadi**, shuning uchun stamp ustiga bosganda
  butun sahifani bo'yab tashlamaydi.
- **Izohlar (sticky note)** — istalgan joyga qo'yish, matnini tahrirlash,
  `Qo'l` asbobi bilan ko'chirish va o'lchamini o'zgartirish; o'lcham PDF ichida
  saqlanadi.
- **Undo / Redo** — har bir amalni bekor qilish va qaytarish.
- **Tez va yengil** — faqat ko'rinadigan sahifalar render qilinadi (lazy render),
  `GtkSnapshot` bilan chiziladi.
- **Bir nusxa (single instance)** — faylni ikki marta bosganda yangi oyna emas,
  mavjud oynada ochiladi.
- **Desktop integratsiya** — `.desktop` entry, ikonka va `application/pdf` uchun
  standart handler; fayl menejeridan ikki marta bosib ochish mumkin.

## Asboblar

| Asbob | Vazifasi |
|-------|----------|
| Qo'l | Sahifani surish, izohlarni ko'chirish/o'lchamlash |
| Marker | Matnga yopishadigan highlight |
| Qalam | Erkin chizish (bosimga sezgir) |
| O'chirg'ich | Chizma/belgini o'chirish |
| Izoh | Sticky note qo'yish/tahrirlash |

Ranglar palitrasi va chizma qalinligini (`-`/`+`) tanlash mumkin.

## Klaviatura tugmalari

| Tugma | Amal |
|-------|------|
| `Ctrl+O` | Ochish |
| `Ctrl+S` | Saqlash |
| `Ctrl+Shift+S` | Boshqa nom bilan saqlash |
| `Ctrl+Z` | Bekor qilish |
| `Ctrl+Alt+Z` / `Ctrl+Shift+Z` | Qaytarish |
| `Ctrl+F` | Kenglikka moslash |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / 100% |
| `Ctrl+scroll` | Sichqoncha bilan zoom |
| `n` / `p` | Keyingi / oldingi sahifa |
| `Ctrl+I` | Tungi rejim |
| `F11` | Butun ekran |
| `Ctrl+Q` | Yopish |

## O'rnatish

Talablar: GTK4 (PyGObject), Python 3.11+.

```bash
git clone https://github.com/Nurmuhammad-Xusanov/pdfreader.git
cd pdfreader
python -m venv --system-site-packages .venv   # GTK4 system'dan olinadi
.venv/bin/pip install pymupdf
```

## Ishga tushirish

```bash
./run.sh [/path/to/file.pdf]
```

Desktop integratsiya (ixtiyoriy):

```bash
cp com.nismo.pdfreader.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications
xdg-mime default com.nismo.pdfreader.desktop application/pdf
```

## Konfiguratsiya

`~/.config/pdfreader/config.toml` yarating:

```toml
night_mode = true          # OLED tungi rejimda boshlash
fullscreen_on_open = true  # butun ekranda ochish (o'quv rejimi)
```

O'quv rejimini (tungi + butun ekran) ishga tushirishda ham so'rash mumkin:

```bash
./run.sh --reading-mode /path/to/file.pdf
```

## Tuzilishi

```
pdfreader/
  app.py          Gtk.Application (HANDLES_OPEN, single instance)
  config.py       ~/.config/pdfreader/config.toml o'quvchi
  window.py       oyna, ixcham toolbar, menyu, harakatlar (actions)
  canvas.py       render, overlay, gesture'lar, undo/redo, izoh geom
  document.py     PyMuPDF wrapper: render, text bbox, annot persist
  annotations.py  Stroke / Highlight / Note modeli
  tools.py        ToolState (aktiv asbob, rang, qalinlik)
  notedialog.py   izoh tahrirlash dialogi
  icons/          symbolic SVG ikonkalar
```
