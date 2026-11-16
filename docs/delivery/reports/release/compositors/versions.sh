#!/bin/bash
# What the compositor checks ran on, in WSL: written to versions.txt beside this script.
#   bash docs/delivery/reports/release/compositors/versions.sh
out=/mnt/c/Users/Randy/Coding/chatmon-wt/compositors/docs/delivery/reports/release/compositors/versions.txt
{
  echo "# $(date -Iseconds)"
  echo "WSL: $(. /etc/os-release; echo "$PRETTY_NAME"), kernel $(uname -r); DRM devices: $(ls /dev/dri | tr '\n' ' ')($(basename "$(readlink -f /sys/class/drm/renderD128/device)"))"
  echo "kwin_wayland --version: $(kwin_wayland --version 2>&1)"
  echo "Hyprland --version: $(Hyprland --version 2>&1 | head -1)"
  echo "sway --version: $(sway --version)"
  echo "orca --version: $(orca --version 2>&1 | head -1)"
  echo "Mesa (llvmpipe): $(pacman -Q mesa)"
  echo
  echo "## packages"
  pacman -Q kwin kwayland libkscreen plasma-wayland-protocols karchive hyprland aquamarine hyprutils hyprlang sway wlroots0.20 grim \
    wl-clipboard dbus at-spi2-core orca python-gobject mesa qt6-base qt6-wayland libxkbcommon python 2>&1
  echo
  echo "## the venvs (packaging/requirements-test.txt)"
  for venv in /var/tmp/plans-venv /var/tmp/m4a-venv; do
    echo "$venv: $($venv/bin/python -c 'import sys, PyQt6.QtCore as q; print("Python", sys.version.split()[0], "PyQt6", q.PYQT_VERSION_STR, "Qt", q.qVersion())')"
  done
  echo
  echo "## installed for this work (pacman.log, 2026-11-15)"
  grep -E '^\[2026-11-15T1[2-9]' /var/log/pacman.log | grep -E "PACMAN\] Running|downgraded|installed (kwin|karchive|plasma-wayland-protocols) "
  echo "(karchive 6.31.0-2, which kwin pulled in, wants OpenSSL 4, newer than this system's 3.6.5: its OpenSSL 3 build, 6.31.0-1, from the Arch archive, instead of a full system upgrade on a shared WSL)"
  echo "(Hyprland 0.57.0 and Aquamarine 0.15.1 were installed already: $(grep -E 'installed hyprland |upgraded hyprland ' /var/log/pacman.log | tail -1))"
} > "$out"
cat "$out"
