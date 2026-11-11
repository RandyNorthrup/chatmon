"""Things worth a heads-up: a low battery, a filling disk, waiting updates.

Each check tells you once, not every minute: a battery warning once per level
until you plug in, a full disk once a day, waiting updates once a day.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable


@dataclass
class Notice:
    key: str
    title: str
    text: str
    urgent: bool = False


UPOWER = "org.freedesktop.UPower"
DISPLAY_DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"  # every battery the computer runs on, as one
POWER_SUPPLY = Path("/sys/class/power_supply")


def read_battery() -> tuple[float, bool] | None:
    """(percent, plugged in), or None without a battery. On Linux, all the computer's batteries as one (a laptop
    can have two), as the desktop's own battery icon shows them."""
    if sys.platform not in ("win32", "darwin"):
        reading = upower_battery() or sysfs_battery()
        if reading is not None:
            return reading
    try:
        import psutil

        battery = psutil.sensors_battery()
        if battery is not None:
            return float(battery.percent), bool(battery.power_plugged)
    except Exception:
        pass
    return None


def upower_battery() -> tuple[float, bool] | None:
    """UPower's DisplayDevice: its batteries combined, weighted by what each holds.
    https://upower.freedesktop.org/docs/UPower.html#UPower.GetDisplayDevice"""
    try:
        from PyQt6.QtDBus import QDBusConnection

        from .presence import _dbus_call
    except ImportError:
        return None
    bus = QDBusConnection.systemBus()
    if not bus.isConnected():
        return None

    def get(path: str, interface: str, name: str):
        return _dbus_call(bus, UPOWER, path, "org.freedesktop.DBus.Properties", "Get", interface, name)

    if not get(DISPLAY_DEVICE, "org.freedesktop.UPower.Device", "IsPresent"):  # no battery, or no UPower
        return None
    percent = get(DISPLAY_DEVICE, "org.freedesktop.UPower.Device", "Percentage")
    on_battery = get("/org/freedesktop/UPower", UPOWER, "OnBattery")
    if not isinstance(percent, (int, float)) or on_battery is None:
        return None
    return float(percent), not bool(on_battery)


def sysfs_battery(base: Path = POWER_SUPPLY) -> tuple[float, bool] | None:
    """The kernel's batteries (not a mouse's or a headset's), combined as UPower does: by what each holds, when
    they all say it in the same unit, else their percentages averaged."""
    found = []  # (percent, (unit, now, full) or None)
    plugged = True
    for bat in sorted(base.glob("BAT*")):
        try:
            if (bat / "scope").is_file() and (bat / "scope").read_text().strip() == "Device":
                continue
            percent = float((bat / "capacity").read_text().strip())
            plugged = plugged and (bat / "status").read_text().strip() != "Discharging"
        except (OSError, ValueError):
            continue
        held = None
        for unit in ("energy", "charge"):  # µWh, or µAh
            try:
                held = (unit, float((bat / f"{unit}_now").read_text()), float((bat / f"{unit}_full").read_text()))
                break
            except (OSError, ValueError):
                pass
        found.append((percent, held))
    if not found:
        return None
    units = {held[0] for _, held in found if held}
    if len(units) == 1 and all(held for _, held in found) and sum(held[2] for _, held in found) > 0:
        percent = 100.0 * sum(held[1] for _, held in found) / sum(held[2] for _, held in found)
    else:
        percent = sum(p for p, _ in found) / len(found)
    return min(100.0, percent), plugged


def disk_folders() -> list[Path]:
    """The system disk and the one your files are on."""
    home = Path.home()
    return [Path(home.anchor), home]


def read_disks(folders: list[Path]) -> list[tuple[str, float]]:
    """(folder, percent used) for each folder on a different disk."""
    seen, out = set(), []
    for folder in folders:
        try:
            device = os.stat(folder).st_dev
            usage = shutil.disk_usage(folder)
        except OSError:
            continue
        if device in seen or usage.total == 0:
            continue
        seen.add(device)
        out.append((str(folder), 100.0 * usage.used / usage.total))
    return out


# -- updates waiting: each system's own tool, reading what it already knows (no network, no administrator)


def count_apt(output: str, code: int = 0) -> int | None:
    return sum(1 for line in output.splitlines() if "upgradable from" in line) if code == 0 else None


def count_flatpak(output: str, code: int = 0) -> int | None:
    return sum(1 for line in output.splitlines() if line.strip()) if code == 0 else None


def count_dnf(output: str, code: int) -> int | None:
    """`dnf check-update --cacheonly`: exit code 100 with a line for each package ("name.arch  version  repo"),
    0 with none."""
    if code == 0:
        return 0
    if code != 100:
        return None
    lines = []
    for line in output.splitlines():
        if line.startswith(("Obsoleting", "Security:", "Last metadata")) or line.startswith(" "):
            continue
        if re.match(r"^\S+\.\S+\s+\S+\s+\S+\s*$", line):
            lines.append(line)
    return len(lines)


def count_pacman(output: str, code: int) -> int | None:
    """`pacman -Qu`: a line for each package; exit code 1 when there are none."""
    if code == 1 and not output.strip():
        return 0
    return sum(1 for line in output.splitlines() if line.strip()) if code == 0 else None


def count_zypper(output: str, code: int) -> int | None:
    """`zypper --no-refresh --xmlout list-updates`: an <update> for each."""
    if code != 0:
        return None
    return len(re.findall(r'<update\b[^>]*\bkind="package"', output))


def count_windows(output: str, code: int) -> int | None:
    """Windows Update, searched offline: "<count>|<restart needed>"."""
    m = re.fullmatch(r"(\d+)\|(True|False)", output.strip())
    return int(m.group(1)) if code == 0 and m else None


def count_softwareupdate(output: str, code: int) -> int | None:
    """macOS `softwareupdate --list --no-scan`: a "* Label: ..." line for each update it already knows of."""
    if code != 0:
        return None
    return sum(1 for line in output.splitlines() if line.lstrip().startswith("* "))


def windows_restart_needed(output: str) -> bool:
    return output.strip().endswith("|True")


# What Windows Update knows already (Online = false: from its last look, no network); the plain Users group
# may ask both. https://learn.microsoft.com/en-us/windows/win32/wua_sdk/secured-methods-and-properties-in-the-wua-api
_WINDOWS_UPDATES = (
    "$ErrorActionPreference = 'Stop';"
    "$q = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher(); $q.Online = $false;"
    "$n = $q.Search(\"IsInstalled=0 and IsHidden=0 and Type='Software'\").Updates.Count;"
    "$r = (New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired;"
    "[Console]::Out.Write(\"$n|$r\")"
)


@dataclass(frozen=True)
class UpdateCheck:
    name: str
    argv: list[str]
    count: Callable[[str, int], int | None] = field(compare=False)  # (output, exit code) -> how many, None: couldn't tell


def update_checks() -> list[UpdateCheck]:
    """This system's ways of knowing about waiting updates, each from what it already knows."""
    if sys.platform == "win32":
        from .paths import powershell

        return [UpdateCheck("windows", powershell(_WINDOWS_UPDATES), count_windows)]
    if sys.platform == "darwin":
        # What macOS found at its own last look (--no-scan: no network, no administrator).
        return [UpdateCheck("softwareupdate", ["/usr/sbin/softwareupdate", "--list", "--no-scan"], count_softwareupdate)]
    checks = [
        UpdateCheck("apt", ["apt", "list", "--upgradable"], count_apt),
        UpdateCheck("dnf", ["dnf", "check-update", "--cacheonly", "--quiet"], count_dnf),
        UpdateCheck("pacman", ["pacman", "-Qu"], count_pacman),
        UpdateCheck("zypper", ["zypper", "--no-refresh", "--quiet", "--xmlout", "list-updates"], count_zypper),
        UpdateCheck("flatpak", ["flatpak", "remote-ls", "--updates", "--cached", "--columns=application"], count_flatpak),
    ]
    return [c for c in checks if shutil.which(c.argv[0])]


class Watcher:
    def __init__(self, battery_low: float, battery_critical: float, disk_full: float):
        self.battery_low = battery_low
        self.battery_critical = battery_critical
        self.disk_full = disk_full
        self._battery_told: str | None = None
        self._disk_told: dict[str, date] = {}
        self._updates_told: date | None = None

    def battery(self, reading: tuple[float, bool] | None) -> Notice | None:
        if reading is None or self.battery_low <= 0:
            return None
        percent, plugged = reading
        if plugged or percent > self.battery_low + 2:
            self._battery_told = None
            return None
        level = "critical" if percent <= self.battery_critical else "low" if percent <= self.battery_low else None
        if level is None or level == self._battery_told or (level == "low" and self._battery_told == "critical"):
            return None
        self._battery_told = level
        if level == "critical":
            return Notice("battery", "Battery almost empty", f"Battery at {percent:.0f}%. Plug in now.", urgent=True)
        return Notice("battery", "Battery low", f"Battery at {percent:.0f}%. Time to find the charger.", urgent=True)

    def disks(self, readings: list[tuple[str, float]], today: date) -> list[Notice]:
        out = []
        if self.disk_full <= 0:
            return out
        for folder, percent in readings:
            if percent >= self.disk_full and self._disk_told.get(folder) != today:
                self._disk_told[folder] = today
                out.append(Notice(f"disk:{folder}", "Disk almost full", f"The disk holding {folder} is {percent:.0f}% full.", urgent=True))
        return out

    def updates(self, count: int, today: date, restart: bool = False) -> Notice | None:
        if (count <= 0 and not restart) or self._updates_told == today:
            return None
        self._updates_told = today
        if restart:
            return Notice("updates", "Restart to finish updating", "Your computer has installed updates that need a restart to finish.")
        plural = "s" if count != 1 else ""
        return Notice("updates", "Updates waiting", f"{count} system update{plural} waiting to install.")
