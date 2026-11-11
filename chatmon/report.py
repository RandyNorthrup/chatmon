"""Reporting a problem, or an idea: a GitHub issue form, filled in with what helps fix it.

Only what's put in the form's link: Chatmon's version, how it was installed, the system and desktop, Qt's
version and the brain's name. Never your name, files, chats, keys or log; the form asks for those only
if you want to add them.
"""

from __future__ import annotations

import os
import platform
import sys
from urllib.parse import urlencode

from . import __version__
from .updates import REPO

ISSUES = f"https://github.com/{REPO}/issues/new"
# How it was installed (updates.install_kind), as the form's dropdown words it.
INSTALL = {
    "windows": "Windows installer",
    "macos": "macOS .pkg or .dmg",
    "deb": ".deb (Ubuntu, Debian)",
    "rpm": ".rpm (Fedora)",
    "pipx": "pipx",
    "manual": "pip, or from the source",
}
BUG, IDEA = "bug_report.yml", "feature_request.yml"


def system() -> str:
    """"Windows 11 (10.0.26100), x86_64", "macOS 15.4, arm64", "Linux 6.12 (Fedora 44), Wayland, KDE"..."""
    machine = platform.machine() or "?"
    if sys.platform == "win32":
        release, build = platform.release(), platform.version()
        return f"Windows {release} ({build}), {machine}"
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0] or '?'}, {machine}"
    parts = [f"{platform.system()} {platform.release().split('-')[0]}"]
    try:
        distro = platform.freedesktop_os_release().get("PRETTY_NAME")
    except OSError:
        distro = None
    if distro:
        parts[0] += f" ({distro})"
    parts.append(machine)
    session = os.environ.get("XDG_SESSION_TYPE")
    desktop = os.environ.get("XDG_CURRENT_DESKTOP")
    parts += [p for p in (session.capitalize() if session else None, desktop) if p]
    return ", ".join(parts)


def qt() -> str:
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        from PyQt6.QtGui import QGuiApplication

        name = QGuiApplication.platformName() if QGuiApplication.instance() else ""
        return f"Qt {QT_VERSION_STR}" + (f" ({name})" if name else "")
    except ImportError:
        return "Qt ?"


def url(template: str = BUG, *, install: str = "", brain: str = "", title: str = "") -> str:
    """The new-issue form, filled in. Field names are the form's ids (.github/ISSUE_TEMPLATE)."""
    fields = {"template": template, "version": __version__, "system": f"{system()}; {qt()}"}
    if install in INSTALL:
        fields["install"] = INSTALL[install]
    if brain:
        fields["brain"] = brain
    if title:
        fields["title"] = title[:120]
    return f"{ISSUES}?{urlencode(fields)}"
