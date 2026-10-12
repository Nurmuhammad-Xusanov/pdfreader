#!/usr/bin/env bash
# User-space installer for PDF Reader (no root required).
# Installs the app to ~/.local so it works from any directory and shows up
# in the app menu / as the default PDF handler.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="com.nismo.pdfreader"
DESTDIR_BIN="$HOME/.local/bin"
DESTDIR_APPS="$HOME/.local/share/applications"
DESTDIR_ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
PREFIX="$HOME/.local"

cd "$DIR"

echo "==> Installing Python package (user-space)"
if python3 -m pip install --user . --force-reinstall; then
    :
else
    echo "==> PEP 668 (externally-managed) detected, retrying with --break-system-packages"
    python3 -m pip install --user --break-system-packages . --force-reinstall
fi

echo "==> Installing desktop entry and icon"
mkdir -p "$DESTDIR_APPS" "$DESTDIR_ICONS"
install -m 644 com.nismo.pdfreader.svg "$DESTDIR_ICONS/$APP_ID.svg"
# Use an absolute Exec so launchers work even when ~/.local/bin is not on $PATH
{
    sed "s|^Exec=.*|Exec=$PREFIX/bin/pdfreader %U|" com.nismo.pdfreader.desktop
} > "$DESTDIR_APPS/$APP_ID.desktop"

echo "==> Refreshing desktop database and icon cache"
if command -v update-desktop-database >/dev/null; then
    update-desktop-database "$DESTDIR_APPS" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "==> Setting PDF Reader as the default handler for application/pdf"
xdg-mime default "$APP_ID.desktop" application/pdf || true

echo ""
echo "Installed. Launch with: $PREFIX/bin/pdfreader"
echo "Uninstall with: python3 -m pip uninstall com-nismo-pdfreader && rm -rf $DESTDIR_APPS/$APP_ID.desktop $DESTDIR_ICONS/$APP_ID.svg"