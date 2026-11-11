from datetime import date
from pathlib import Path

from chatmon import heads_up
from chatmon.heads_up import Watcher, count_apt, count_flatpak, read_disks

TODAY = date(2026, 10, 31)


def test_battery_warns_once_per_level():
    w = Watcher(20, 10, 90)
    assert w.battery((50, False)) is None
    low = w.battery((19, False))
    assert low.title == "Battery low" and low.urgent
    assert w.battery((18, False)) is None
    assert w.battery((9, False)).title == "Battery almost empty"
    assert w.battery((8, False)) is None
    assert w.battery((15, False)) is None  # back up to "low" after critical: no repeat


def test_battery_resets_when_plugged_in():
    w = Watcher(20, 10, 90)
    assert w.battery((19, False))
    assert w.battery((19, True)) is None
    assert w.battery((19, False))


def test_battery_off_or_missing():
    assert Watcher(0, 10, 90).battery((5, False)) is None
    assert Watcher(20, 10, 90).battery(None) is None


def test_disk_once_a_day():
    w = Watcher(20, 10, 90)
    assert [n.key for n in w.disks([("/", 95), ("/home", 50)], TODAY)] == ["disk:/"]
    assert w.disks([("/", 96)], TODAY) == []
    assert len(w.disks([("/", 96)], date(2026, 11, 1))) == 1


def test_updates_once_a_day():
    w = Watcher(20, 10, 90)
    assert w.updates(0, TODAY) is None
    assert w.updates(3, TODAY).text == "3 system updates waiting to install."
    assert w.updates(4, TODAY) is None
    assert w.updates(1, date(2026, 11, 1)).text == "1 system update waiting to install."


def test_counts():
    apt = "Listing...\nfoo/questing-updates 1.2 amd64 [upgradable from: 1.1]\nbar/questing 2 all [upgradable from: 1]\n"
    assert count_apt(apt) == 2
    assert count_flatpak("org.a.App\n\norg.b.App\n") == 2


def test_read_disks_skips_duplicates_and_missing(tmp_path):
    (tmp_path / "sub").mkdir()
    readings = read_disks([tmp_path, tmp_path / "sub", Path("/definitely/not/here")])
    assert len(readings) == 1 and 0 <= readings[0][1] <= 100


def test_dnf_pacman_zypper_and_windows_update_counts():
    from chatmon import heads_up

    dnf = (
        "\n"
        "firefox.x86_64                     145.0-1.fc44              updates\n"
        "kernel-core.x86_64                 6.17.4-300.fc44           updates\n"
        "Obsoleting Packages\n"
        "foo.noarch                         2.0-1.fc44                updates\n"
        "    foo-old.noarch                 1.0-1.fc44                @updates\n"
    )
    assert heads_up.count_dnf(dnf, 100) == 3 and heads_up.count_dnf("", 0) == 0
    assert heads_up.count_dnf("Error: Cache-only enabled but no cache", 1) is None  # couldn't tell: nothing said
    assert heads_up.count_pacman("linux 6.17.3-1 -> 6.17.4-1\nfirefox 144-1 -> 145-1\n", 0) == 2
    assert heads_up.count_pacman("", 1) == 0
    zypper = (
        '<?xml version="1.0"?><stream><update-status version="0.6"><update-list>'
        '<update name="vim" edition="9.1-2" arch="x86_64" kind="package"/>'
        '<update name="openSUSE-2026-1" kind="patch"/>'
        '<update name="curl" edition="8.17-1" arch="x86_64" kind="package">x</update>'
        "</update-list></update-status></stream>"
    )
    assert heads_up.count_zypper(zypper, 0) == 2 and heads_up.count_zypper("", 4) is None
    assert heads_up.count_windows("3|False", 0) == 3 and not heads_up.windows_restart_needed("3|False")
    assert heads_up.count_windows("0|True", 0) == 0 and heads_up.windows_restart_needed("0|True")
    assert heads_up.count_windows("Exception calling Search", 1) is None


def test_a_restart_to_finish_updating_is_its_own_heads_up():
    from datetime import date

    w = Watcher(20, 10, 90)
    notice = w.updates(0, date(2026, 11, 11), restart=True)
    assert notice.title == "Restart to finish updating"
    assert w.updates(5, date(2026, 11, 11)) is None  # once a day


def test_each_platform_has_its_own_checks(monkeypatch):
    from chatmon import heads_up

    monkeypatch.setattr(heads_up.sys, "platform", "win32")
    (check,) = heads_up.update_checks()
    import base64

    assert check.name == "windows" and check.argv[0].lower().endswith("powershell.exe") and check.argv[-2] == "-EncodedCommand"
    assert "Online = $false" in base64.b64decode(check.argv[-1]).decode("utf-16-le")
    monkeypatch.setattr(heads_up.sys, "platform", "linux")
    monkeypatch.setattr(heads_up.shutil, "which", lambda name: f"/usr/bin/{name}" if name in ("dnf", "flatpak") else None)
    assert [c.name for c in heads_up.update_checks()] == ["dnf", "flatpak"]
    assert "--cacheonly" in heads_up.update_checks()[0].argv


def test_macos_software_update_count():
    from chatmon import heads_up

    listed = (
        "Software Update Tool\n\nSoftware Update found the following new or updated software:\n"
        "* Label: macOS Tahoe 26.1-25B78\n\tTitle: macOS Tahoe 26.1, Version: 26.1, Size: 4.2GiB, Recommended: YES, Action: restart,\n"
        "* Label: Safari26.1\n\tTitle: Safari, Version: 26.1, Size: 160MiB, Recommended: YES,\n"
    )
    assert heads_up.count_softwareupdate(listed, 0) == 2
    assert heads_up.count_softwareupdate("No new software available.\n", 0) == 0
    assert heads_up.count_softwareupdate("", 1) is None


def test_macos_lists_updates_without_looking_online():
    """The real command, on a Mac: --no-scan exists, and it answers without network or administrator."""
    import subprocess
    import sys

    import pytest

    from chatmon import heads_up

    if sys.platform != "darwin":
        pytest.skip("macOS only")
    (check,) = heads_up.update_checks()
    out = subprocess.run(check.argv, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert isinstance(check.count(out.stdout, out.returncode), int)


def _battery(base, name, percent, status, **held):
    bat = base / name
    bat.mkdir(parents=True)
    (bat / "capacity").write_text(f"{percent}\n")
    (bat / "status").write_text(f"{status}\n")
    for key, value in held.items():
        (bat / key).write_text(f"{value}\n")
    return bat


def test_two_batteries_count_as_one_weighted_by_what_each_holds(tmp_path):
    _battery(tmp_path, "BAT0", 100, "Full", energy_now=20_000_000, energy_full=20_000_000)  # a small one, full
    _battery(tmp_path, "BAT1", 25, "Discharging", energy_now=15_000_000, energy_full=60_000_000)  # a big one, low
    percent, plugged = heads_up.sysfs_battery(tmp_path)
    assert round(percent) == 44 and not plugged  # 35 of 80 Wh, not the first one's 100%


def test_batteries_in_different_units_are_averaged_and_a_mouses_is_left_out(tmp_path):
    _battery(tmp_path, "BAT0", 80, "Charging", energy_now=1, energy_full=2)
    _battery(tmp_path, "BAT1", 40, "Charging", charge_now=1, charge_full=2)
    (_battery(tmp_path, "BAT2", 5, "Discharging") / "scope").write_text("Device\n")
    assert heads_up.sysfs_battery(tmp_path) == (60.0, True)
    assert heads_up.sysfs_battery(tmp_path / "none") is None
