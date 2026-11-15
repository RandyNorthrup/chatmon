"""Real compositors besides sway for the overlay's tests: a headless KWin (KDE Plasma's) and a headless Hyprland, each
of the test's own, with the session bus, probe and AT-SPI readers of tests/sway_session.py, which this builds on.

Each lacks something sway's tests use; its own way stands in:

- KWin has no screencopy protocol (grim), no virtual pointer or keyboard protocol and no window-tree IPC. Instead:
  its screenshot service on the session bus (org.kde.KWin.ScreenShot2, what Spectacle uses), its fake-input
  protocol (org_kde_kwin_fake_input, what KDE Connect and remote desktops use), and a KWin script, loaded through
  its scripting service, that lists the windows and outputs. kscreen-doctor turns outputs on and off. It runs with
  its virtual backend (`kwin_wayland --virtual`), drawing with Mesa's llvmpipe.
- Hyprland has grim's protocol, the virtual pointer and keyboard, and hyprctl, so sway_session's Input and grim
  serve as they are. Its backend library, Aquamarine, can't run headless on its own: it needs a KMS device or a
  Wayland compositor to run in, for its buffers. Here it runs in a headless KWin of its own (Aquamarine's Wayland
  backend, that KWin on a session bus of its own too), on an output Aquamarine's headless backend makes (`hyprctl
  output create headless`); the output the nesting makes is turned off. Where the only DRM device is vgem (WSL),
  whose render node refuses to allocate buffers, a small preload library, built here, has Hyprland open vgem's
  primary node in its place.

`unavailable(name)` says why a compositor can't run here. `start(name, folder, ...)` gives its Session; `devices(session)`
the pointer and keyboard for it. Not a test file itself.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import sway_session
from sway_session import KEYS, SYSTEM_PYTHON, Session

# sway too where CHATMON_COMPOSITORS_SWAY=1: the same checks on it, to compare (CI's sway job runs test_sway.py).
COMPOSITORS = ("kwin", "hyprland") + (("sway",) if os.environ.get("CHATMON_COMPOSITORS_SWAY") == "1" else ())
KWIN_OUTPUT = "Virtual-0"  # kwin_wayland --virtual names its outputs Virtual-0, Virtual-1...
HYPR_OUTPUT = "CHATMON-1"  # the headless output the test bed makes
HYPR_HOST_SOCKET = "kwin-host"  # the KWin Hyprland runs in

# org_kde_kwin_fake_input's requests, by number (plasma-wayland-protocols' fake-input.xml, version 6).
FAKE_AUTHENTICATE, FAKE_BUTTON, FAKE_POINTER_MOTION_ABSOLUTE, FAKE_KEYBOARD_KEY, FAKE_DESTROY = 0, 2, 9, 10, 11
MODIFIER_KEYS = ((1, "Shift_L"), (4, "Control_L"))  # xkb's modifier masks, as sway_session.Input.key takes them

# Has Hyprland open a DRM node other than the one it asks for (NODE_FROM: NODE_TO): vgem's primary node for its render
# node, which refuses the dumb buffers Mesa's software renderer allocates.
_REDIRECT_C = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

static const char *swap(const char *path)
{
    const char *from = getenv("NODE_FROM"), *to = getenv("NODE_TO");
    return (path && from && to && strcmp(path, from) == 0) ? to : path;
}

#define MODE(flags) mode_t mode = 0; \
    if ((flags) & (O_CREAT | O_TMPFILE)) { va_list ap; va_start(ap, flags); mode = va_arg(ap, mode_t); va_end(ap); }
#define WRAP(name) \
    int name(const char *path, int flags, ...) { static int (*real)(const char *, int, ...); MODE(flags); \
        if (!real) real = dlsym(RTLD_NEXT, #name); return real(swap(path), flags, mode); }
#define WRAP_AT(name) \
    int name(int dir, const char *path, int flags, ...) { static int (*real)(int, const char *, int, ...); MODE(flags); \
        if (!real) real = dlsym(RTLD_NEXT, #name); return real(dir, swap(path), flags, mode); }
#define WRAP_2(name) \
    int name(const char *path, int flags) { static int (*real)(const char *, int); \
        if (!real) real = dlsym(RTLD_NEXT, #name); return real(swap(path), flags); }

WRAP(open) WRAP(open64) WRAP_AT(openat) WRAP_AT(openat64) WRAP_2(__open_2) WRAP_2(__open64_2)
"""

# KWin's screenshot service writes the picture's raw pixels to a pipe it's handed: a file descriptor over D-Bus, which
# dbus-send can't pass. libgio can, in the system's Python (python3-gi), as for AT-SPI.
_KWIN_SHOT = r"""
import json, os, sys, threading
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

bus = Gio.DBusConnection.new_for_address_sync(
    os.environ["DBUS_SESSION_BUS_ADDRESS"],
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
r, w = os.pipe()
fds = Gio.UnixFDList.new()
index = fds.append(w)
os.close(w)
data = []
reader = threading.Thread(target=lambda: data.append(os.fdopen(r, "rb").read()))
reader.start()
options = {"native-resolution": GLib.Variant("b", True), "include-cursor": GLib.Variant("b", False)}
reply, _ = bus.call_with_unix_fd_list_sync(
    "org.kde.KWin.ScreenShot2", "/org/kde/KWin/ScreenShot2", "org.kde.KWin.ScreenShot2", "CaptureScreen",
    GLib.Variant("(sa{sv}h)", (sys.argv[2], options, index)), GLib.VariantType("(a{sv})"),
    Gio.DBusCallFlags.NONE, 30000, fds, None)
del fds  # KWin's copy of the pipe's end is all that's left: the read ends when KWin has written it all
import gc; gc.collect()
reader.join(30)
with open(sys.argv[1], "wb") as out:
    out.write(data[0])
print(json.dumps(reply.unpack()[0]))
"""

# A KWin script: the windows and outputs, printed to KWin's log after a tag, as JSON.
_KWIN_LIST = r"""
const box = g => g ? [g.x, g.y, g.width, g.height] : null;
const windows = workspace.windowList().map(w => ({
    caption: w.caption, pid: w.pid, resourceClass: w.resourceClass, normal: w.normalWindow, dialog: w.dialog,
    popup: w.popupWindow, special: w.specialWindow, dock: w.dock, managed: w.managed, deleted: w.deleted,
    active: w.active, fullScreen: w.fullScreen, keepAbove: w.keepAbove, layer: w.layer, minimized: w.minimized,
    frame: box(w.frameGeometry), client: box(w.clientGeometry), output: w.output ? w.output.name : null,
    // A layer surface (the overlay) is a "normal" window to KWin's scripts, as its namespace is none of KWin's
    // own: it tells by what a layer surface can't be, moved, minimized or switched to.
    layerShell: !w.moveable && !w.resizeable && !w.minimizable && w.skipSwitcher && w.skipTaskbar && w.skipPager,
}));
const outputs = workspace.screens.map(s => ({name: s.name, rect: box(s.geometry), scale: s.devicePixelRatio}));
print("%TAG% " + JSON.stringify({windows: windows, outputs: outputs}));
"""


def unavailable(name: str, atspi: bool = False, orca: bool = False) -> str | None:
    """Why this compositor's tests can't run here (None: they can)."""
    if not sys.platform.startswith("linux"):
        return "a real Wayland compositor runs on Linux only"
    if name == "sway":
        return sway_session.unavailable(atspi=atspi, orca=orca)
    tools = {"kwin": ("kwin_wayland", "kscreen-doctor", "dbus-daemon", "dbus-send"),
             "hyprland": ("Hyprland", "hyprctl", "kwin_wayland", "grim", "dbus-daemon", "dbus-send")}[name]
    for tool in tools:
        if shutil.which(tool) is None:
            return f"{tool} isn't installed ({name}'s tests need it)"
    if name == "kwin":
        check = subprocess.run([SYSTEM_PYTHON, "-c", "import gi; gi.require_version('Gio', '2.0'); from gi.repository import Gio"],
                               capture_output=True, timeout=30, check=False) if Path(SYSTEM_PYTHON).exists() else None
        if check is None or check.returncode:
            return "the system's Python has no GObject bindings (python3-gi), for KWin's screenshots"
    if name == "hyprland" and _vgem_nodes() is not None and shutil.which("cc") is None:
        return "the only DRM device is vgem, and there's no C compiler to build the node redirect Hyprland needs on it"
    try:
        from PyQt6.QtCore import QLibraryInfo

        plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms"
    except ImportError:
        return "PyQt6 isn't installed"
    if not any(plugins.glob("libqwayland*.so")):
        return "this Qt has no Wayland platform plugin"
    if atspi or orca:
        # sway_session's own look at AT-SPI and Orca, which asks for sway, swaymsg and grim first: those it may lack.
        why = sway_session.unavailable(atspi=atspi, orca=orca)
        if why is not None and why.split()[0] in ("sway", "swaymsg", "grim"):
            return _atspi_and_orca(orca)
        return why
    return None


def _atspi_and_orca(orca: bool) -> str | None:
    """sway_session.unavailable's AT-SPI and Orca checks, where sway itself isn't installed."""
    if sway_session._atspi_launcher() is None:
        return "AT-SPI's bus launcher isn't installed (at-spi2-core)"
    check = subprocess.run([SYSTEM_PYTHON, "-c", "import gi; gi.require_version('Atspi', '2.0'); from gi.repository import Atspi"],
                           capture_output=True, timeout=30, check=False) if Path(SYSTEM_PYTHON).exists() else None
    if check is None or check.returncode:
        return "the system's Python has no libatspi bindings (python3-gi, gir1.2-atspi-2.0)"
    if orca:
        if shutil.which("orca") is None:
            return "Orca isn't installed"
        words = subprocess.run(["orca", "--version"], capture_output=True, text=True, timeout=30, check=False).stdout.split()
        number = words[words.index("version") + 1] if "version" in words[:-1] else ""
        major = int(number.split(".")[0]) if number.split(".")[0].isdigit() else 0
        if major < 49:
            return f"Orca {major or '?'} has no remote controller to speak through (49 or later has)"
    return None


def _vgem_nodes() -> tuple[str, str] | None:
    """(render node, primary node) of vgem, where the first render node is vgem's; None elsewhere."""
    drm = Path("/sys/class/drm")
    renders = sorted(drm.glob("renderD*")) if drm.exists() else []
    if not renders:
        return None
    render = renders[0]
    device = (render / "device").resolve()
    driver = (device / "driver").resolve().name if (device / "driver").exists() else ""
    vgem = "vgem" in (device.name, driver)  # its own driver once; a "faux" device named vgem since Linux 6.15
    cards = sorted(p.name for p in (device / "drm").glob("card*")) if vgem else []
    return (f"/dev/dri/{render.name}", f"/dev/dri/{cards[0]}") if cards else None


def start(name: str, folder: Path, mode: str = "1280x800", scale: float = 1, atspi: bool = False, orca: bool = False,
          outputs: int = 1) -> Session:
    """A session of this compositor (`outputs`: how many it can show; the second is off until `add_output`)."""
    kind = {"kwin": KWinSession, "hyprland": HyprlandSession, "sway": SwaySession}[name]
    return kind(folder, mode=mode, scale=scale, atspi=atspi, orca=orca, outputs=outputs)


def devices(session: Session):
    """A pointer and a keyboard for this session: its own protocol on KWin, sway_session's on Hyprland."""
    return KWinInput(session) if isinstance(session, KWinSession) else sway_session.Input(session)


def _mode(mode: str) -> tuple[int, int]:
    w, h = mode.split("x")
    return int(w), int(h)


class _Common(Session):
    """What both share: the extra arguments, the desktop's name, and outputs and windows in sway's terms."""

    NAME = ""
    DESKTOP = ""

    def __init__(self, folder: Path, mode: str = "1280x800", scale: float = 1, atspi: bool = False, orca: bool = False,
                 outputs: int = 1):
        self.output_count = outputs
        self.mode, self.scale = mode, scale
        super().__init__(folder, mode=mode, scale=scale, atspi=atspi, orca=orca)

    def _start_bus(self) -> None:
        self.env["XDG_CURRENT_DESKTOP"] = self.DESKTOP  # what the session's bus, and so what it starts, sees
        super()._start_bus()

    def _run(self, argv: list[str], seconds: float = 30.0, env: dict | None = None) -> str:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=seconds, env=env or self.env, check=False)
        if out.returncode:
            raise RuntimeError(f"{' '.join(argv)}: {out.stderr or out.stdout}")
        return out.stdout

    def output_names(self) -> list[str]:
        return [o["name"] for o in self.outputs()]

    def first_output(self) -> str:
        raise NotImplementedError

    def _background(self) -> tuple[int, int, int]:
        """As sway_session's: the one colour of the empty output, read off it before any client draws."""
        shot = self.screenshot("empty")
        w, h = shot.width(), shot.height()
        points = [(x, y) for x in (4, w // 3, w // 2, w - 5) for y in (4, h // 2, 2 * h // 3, h - 5)]
        seen = {(shot.pixelColor(x, y).red(), shot.pixelColor(x, y).green(), shot.pixelColor(x, y).blue()) for x, y in points}
        if len(seen) != 1:
            raise RuntimeError(f"{self.NAME}'s empty output isn't one colour: {sorted(seen)}")
        r, g, b = seen.pop()
        return r, g, b


# -- KWin


class KWinSession(_Common):
    """A session bus, a headless KWin (its virtual backend) and, when asked, AT-SPI's registry and Orca."""

    NAME = "kwin"
    DESKTOP = "KDE"

    def _start_sway(self, mode: str, scale: float) -> None:  # the compositor's start, by sway_session's name
        w, h = _mode(mode)
        kwin_env = {**self.env, "LIBGL_ALWAYS_SOFTWARE": "1", "QT_LOGGING_RULES": "js=true;kwin_scripting=true", "QT_FORCE_STDERR_LOGGING": "1"}
        # The size in device pixels. Not --scale: the virtual backend multiplies the mode by it and leaves the
        # output's scale at 1. kscreen-doctor sets the scale, as Plasma's display settings do.
        argv = ["kwin_wayland", "--virtual", "--width", str(w), "--height", str(h), "--output-count", str(self.output_count),
                "--no-lockscreen", "--no-global-shortcuts", "--socket", "wayland-kwin"]
        self.kwin = self._spawn("kwin", argv, env=kwin_env)
        self._wait(lambda: (self.run / "wayland-kwin").exists() and self._bus_has(self.env["DBUS_SESSION_BUS_ADDRESS"], "org.kde.KWin.ScreenShot2"), "KWin")
        self.env["WAYLAND_DISPLAY"] = str(self.run / "wayland-kwin")
        self._queries = 0
        self._wait(lambda: len(self.outputs()) == self.output_count, "KWin's outputs")
        if scale != 1:
            self._kscreen(*(f"output.{name}.scale.{scale:g}" for name in self.output_names()))
            self._wait(lambda: all(o["scale"] == scale for o in self.outputs()), f"KWin's outputs at a scale of {scale:g}")
        for extra in self.output_names()[1:]:  # plugged in later, by the test (add_output)
            self._kscreen(f"output.{extra}.disable")
        self._wait(lambda: self.output_names() == [KWIN_OUTPUT], "KWin's first output alone")
        self.background = self._background()

    def first_output(self) -> str:
        return KWIN_OUTPUT

    def _kscreen(self, *args: str) -> None:
        self._run(["kscreen-doctor", *args], env={**self.env, "QT_QPA_PLATFORM": "wayland"}, seconds=60)

    def add_output(self) -> str:
        """The second output (made at the start, kept off) turned on, right of the first: plugged in."""
        name = f"Virtual-{len(self.output_names())}"
        self._kscreen(f"output.{name}.enable", f"output.{name}.position.{_mode(self.mode)[0] / self.scale:.0f},0")
        self._wait(lambda: name in self.output_names(), f"KWin's {name}")
        return name

    def disable_output(self, name: str) -> None:
        self._kscreen(f"output.{name}.disable")
        self._wait(lambda: name not in self.output_names(), f"KWin turning {name} off")

    def query(self) -> dict:
        """KWin's windows and outputs, as a script of its own sees them (_KWIN_LIST)."""
        self._queries += 1
        tag = f"CHATMON-QUERY-{os.getpid()}-{self._queries}"
        script = self.folder / f"kwin-query-{self._queries}.js"
        script.write_text(_KWIN_LIST.replace("%TAG%", tag), encoding="utf-8")
        call = ["dbus-send", "--session", "--print-reply", "--dest=org.kde.KWin", "/Scripting"]
        self._run([*call, "org.kde.kwin.Scripting.loadScript", f"string:{script}", f"string:{tag}"])
        try:
            self._run([*call, "org.kde.kwin.Scripting.start"])
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                for line in reversed(self.log("kwin").splitlines()):
                    if tag + " " in line:
                        return json.loads(line.split(tag + " ", 1)[1])
                time.sleep(0.05)
            raise RuntimeError(f"KWin's script said nothing in 10 s:\n{self.log('kwin')[-2000:]}")
        finally:
            self._run([*call, "org.kde.kwin.Scripting.unloadScript", f"string:{tag}"])
            script.unlink(missing_ok=True)

    def outputs(self) -> list[dict]:
        try:
            found = self.query()["outputs"]
        except (RuntimeError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return []
        return [{"name": o["name"], "active": True, "scale": o["scale"], "rect": dict(zip(("x", "y", "width", "height"), o["rect"], strict=True))}
                for o in found]

    def views(self) -> list[dict]:
        """Every window KWin manages, as sway_session lists sway's: not layer surfaces, popups or KWin's own."""
        found = []
        for w in self.query()["windows"]:
            if w["deleted"] or w["popup"] or w["layerShell"] or not (w["normal"] or w["dialog"]) or w["pid"] == self.kwin.pid:
                continue
            x, y, width, height = w["client"]
            found.append({"pid": w["pid"], "name": w["caption"], "app_id": w["resourceClass"], "floating": True,  # nothing tiles
                          "focused": w["active"], "fullscreen": w["fullScreen"], "output": w["output"], "frame": w["frame"],
                          "rect": {"x": x, "y": y, "width": width, "height": height}})
        return found

    def screenshot(self, name: str = "shot", output: str | None = None):
        """What KWin shows on an output now, as a QImage (its screenshot service), in device pixels."""
        from PyQt6.QtGui import QImage

        raw = self.folder / f"{name}.raw"
        out = subprocess.run([SYSTEM_PYTHON, "-c", _KWIN_SHOT, str(raw), output or KWIN_OUTPUT], capture_output=True,
                             text=True, timeout=60, env=self.env, check=False)
        if out.returncode:
            raise RuntimeError(f"KWin's screenshot failed:\n{out.stderr[-3000:]}")
        meta = json.loads(out.stdout)
        data = raw.read_bytes()
        raw.unlink()
        image = QImage(data, meta["width"], meta["height"], meta["stride"], QImage.Format(meta["format"])).copy()
        assert not image.isNull(), f"KWin's screenshot {meta} didn't load"
        image.save(str(self.folder / f"{name}.png"))
        return image


class KWinInput:
    """A pointer and a keyboard on KWin's seat, through its fake-input protocol: sway_session.Input's calls.
    Positions are in KWin's global logical coordinates."""

    def __init__(self, session: KWinSession):
        from chatmon.wayland import DISPLAY_ID, Connection, decode

        conn = Connection.open(session.env)
        assert conn is not None, "couldn't connect to KWin"
        self.conn = conn
        found: dict[str, tuple[int, int]] = {}

        def global_(opcode: int, args: bytes) -> None:
            if opcode == 0:
                name, interface, version = decode("usu", args)
                found.setdefault(interface, (name, version))

        registry = conn.new_id(global_)
        conn.request(DISPLAY_ID, 1, "n", registry)
        assert conn.roundtrip(5.0)
        assert "org_kde_kwin_fake_input" in found, "KWin doesn't offer org_kde_kwin_fake_input"
        name, version = found["org_kde_kwin_fake_input"]
        assert version >= 4, f"KWin's fake input is version {version}; the keyboard needs 4"
        self.version = min(version, 6)
        self.fake = conn.new_id()
        conn.request(registry, 0, "usun", name, "org_kde_kwin_fake_input", self.version, self.fake)
        conn.request(self.fake, FAKE_AUTHENTICATE, "ss", "Chatmon's tests", "drive the overlay under test")
        assert conn.roundtrip(5.0), conn.error
        rect = session.outputs()[0]["rect"]
        self.extent = (rect["width"], rect["height"])
        self.at = (0.0, 0.0)

    def _sync(self) -> None:
        assert self.conn.roundtrip(5.0), self.conn.error

    def move(self, x: float, y: float) -> None:
        self.conn.request(self.fake, FAKE_POINTER_MOTION_ABSOLUTE, "ff", float(x), float(y))
        self.at = (x, y)
        self._sync()

    def button(self, button: int, down: bool) -> None:
        self.conn.request(self.fake, FAKE_BUTTON, "uu", button, 1 if down else 0)
        self._sync()

    def click(self, x: float, y: float, button: int = sway_session.BTN_LEFT) -> None:
        self.move(x, y)
        self.button(button, True)
        self.button(button, False)

    def key(self, name: str, mods: int = 0) -> None:
        """Press and let go of a key; `mods`: xkb's mask held (Shift 1, Ctrl 4), as the modifier keys pressed."""
        held = [KEYS[key] for mask, key in MODIFIER_KEYS if mods & mask]
        for code in held:
            self.conn.request(self.fake, FAKE_KEYBOARD_KEY, "uu", code, 1)
        self.conn.request(self.fake, FAKE_KEYBOARD_KEY, "uu", KEYS[name], 1)
        self.conn.request(self.fake, FAKE_KEYBOARD_KEY, "uu", KEYS[name], 0)
        for code in reversed(held):
            self.conn.request(self.fake, FAKE_KEYBOARD_KEY, "uu", code, 0)
        self._sync()

    def type(self, text: str) -> None:
        for ch in text:
            self.key("space" if ch == " " else ch)

    def close(self) -> None:
        if self.version >= 5:
            self.conn.request(self.fake, FAKE_DESTROY)
        self.conn.flush()
        self.conn.close()


# -- Hyprland


class HyprlandSession(_Common):
    """A session bus, a headless Hyprland (in a headless KWin of its own) and, when asked, AT-SPI and Orca."""

    NAME = "hyprland"
    DESKTOP = "Hyprland"

    def _start_sway(self, mode: str, scale: float) -> None:  # the compositor's start, by sway_session's name
        self._start_host()
        config = self.folder / "hyprland.lua"
        # Nothing of a desktop's own config: the test's output, the nesting's off, no wallpaper, logo, animations
        # (screenshots mid-animation) or notices drawn over the output (a scale's, an unresponsive app's: the probe
        # stops answering inside Qt's own menus), no Xwayland, the log on its standard output. Hyprland's defaults
        # otherwise: tiling, gaps, borders, focus. Its cursor is in grim's screenshots, as sway 1.9's is.
        config.write_text(
            "\n".join([
                'hl.monitor({ output = "WAYLAND-1", disabled = true })',
                f'hl.monitor({{ output = "{HYPR_OUTPUT}", mode = "{mode}@60", position = "0x0", scale = {scale} }})',
                "hl.config({",
                "    debug = { enable_stdout_logs = true, disable_logs = false },",
                "    misc = { disable_hyprland_logo = true, disable_splash_rendering = true, force_default_wallpaper = 0,",
                "             background_color = 0x000000, disable_watchdog_warning = true, disable_scale_notification = true,",
                "             enable_anr_dialog = false },",
                "    animations = { enabled = false },",
                "    xwayland = { enabled = false },",
                "})",
                "",
            ]),
            encoding="utf-8",
        )
        # Not the desktop's systemd user manager's business (Hyprland would hand it this session's variables).
        hypr_env = {**self.env, "WAYLAND_DISPLAY": HYPR_HOST_SOCKET, "LIBSEAT_BACKEND": "noop", "LIBGL_ALWAYS_SOFTWARE": "1",
                    "HYPRLAND_NO_SD_NOTIFY": "1", "HYPRLAND_NO_SD_VARS": "1", "HYPRLAND_NO_SD_TARGET": "1",
                    "HYPRLAND_NO_CRASHREPORTER": "1", "XCURSOR_SIZE": "24"}
        nodes = _vgem_nodes()
        if nodes is not None:
            hypr_env.update(LD_PRELOAD=self._redirect(), NODE_FROM=nodes[0], NODE_TO=nodes[1])
        self.hyprland = self._spawn("hyprland", ["Hyprland", "-c", str(config)], env=hypr_env)
        self._wait(lambda: any((self.run / "hypr").glob("*/.socket.sock")), "Hyprland")
        self.env["HYPRLAND_INSTANCE_SIGNATURE"] = next((self.run / "hypr").glob("*/.socket.sock")).parent.name
        self.hyprctl("output", "create", "headless", HYPR_OUTPUT)
        self._wait(lambda: [o["name"] for o in self.outputs()] == [HYPR_OUTPUT], "Hyprland's output")
        self._wait(lambda: any(p.suffix != ".lock" for p in self.run.glob("wayland-*")), "Hyprland's socket")
        self.env["WAYLAND_DISPLAY"] = str(next(p for p in self.run.glob("wayland-*") if p.suffix != ".lock"))
        # The cursor starts in the middle: to the top right corner, out of the way (off the output but its tip).
        self.hyprctl("dispatch", f"hl.dsp.cursor.move({{ x = {self.outputs()[0]['rect']['width'] - 1}, y = 0 }})")
        self.background = self._background()

    def _start_host(self) -> None:
        """The KWin Hyprland runs in, on a bus of its own: nothing of KWin's is on the session's bus."""
        config = self.folder / "host-session.conf"
        config.write_text(
            (self.folder / "session.conf").read_text(encoding="utf-8").replace(f"unix:path={self.run}/bus", f"unix:path={self.run}/host-bus"),
            encoding="utf-8",
        )
        self._spawn("host-dbus", ["dbus-daemon", "--nofork", "--nopidfile", f"--config-file={config}"])
        self._wait(lambda: (self.run / "host-bus").exists(), "the host KWin's bus")
        host_env = {**self.env, "DBUS_SESSION_BUS_ADDRESS": f"unix:path={self.run}/host-bus", "LIBGL_ALWAYS_SOFTWARE": "1",
                    "XDG_CURRENT_DESKTOP": "KDE", "QT_FORCE_STDERR_LOGGING": "1"}
        self._spawn("kwin-host", ["kwin_wayland", "--virtual", "--width", "64", "--height", "64", "--no-lockscreen",
                                  "--no-global-shortcuts", "--socket", HYPR_HOST_SOCKET], env=host_env)
        self._wait(lambda: (self.run / HYPR_HOST_SOCKET).exists(), "the KWin Hyprland runs in")

    def _redirect(self) -> str:
        source, library = self.folder / "noderedirect.c", self.folder / "noderedirect.so"
        source.write_text(_REDIRECT_C, encoding="utf-8")
        self._run(["cc", "-shared", "-fPIC", "-O2", "-o", str(library), str(source), "-ldl"], seconds=120)
        return str(library)

    def first_output(self) -> str:
        return HYPR_OUTPUT

    def hyprctl(self, *args: str, json_out: bool = False):
        out = self._run(["hyprctl", *(["-j"] if json_out else []), *args])
        if json_out:
            return json.loads(out)
        if out.strip() not in ("ok", ""):
            raise RuntimeError(f"hyprctl {' '.join(args)}: {out}")
        return out

    def outputs(self) -> list[dict]:
        try:
            monitors = self.hyprctl("monitors", json_out=True)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return []
        return [{"name": m["name"], "active": True, "scale": m["scale"],
                 "rect": {"x": m["x"], "y": m["y"], "width": round(m["width"] / m["scale"]), "height": round(m["height"] / m["scale"])}}
                for m in monitors if not m.get("disabled") and m["width"] > 0]

    def views(self) -> list[dict]:
        """Every window Hyprland manages (`hyprctl clients`; layer surfaces aren't among them), in sway's terms."""
        found = []
        for c in self.hyprctl("clients", json_out=True):
            if not c.get("mapped", True):
                continue
            x, y = c["at"]
            width, height = c["size"]
            found.append({"pid": c["pid"], "name": c["title"], "app_id": c["class"], "floating": c["floating"],
                          "focused": c["focusHistoryID"] == 0, "fullscreen": bool(c.get("fullscreen")), "output": c["monitor"],
                          "rect": {"x": x, "y": y, "width": width, "height": height}})
        return found

    def add_output(self) -> str:
        """A second headless output, right of the first: plugged in."""
        name = f"CHATMON-{len(self.output_names()) + 1}"
        x = round(_mode(self.mode)[0] / self.scale)
        self.hyprctl("eval", f'hl.monitor({{ output = "{name}", mode = "{self.mode}@60", position = "{x}x0", scale = {self.scale} }})')
        self.hyprctl("output", "create", "headless", name)
        self._wait(lambda: name in self.output_names(), f"Hyprland's {name}")
        return name

    def disable_output(self, name: str) -> None:
        self.hyprctl("eval", f'hl.monitor({{ output = "{name}", disabled = true }})')
        self._wait(lambda: name not in self.output_names(), f"Hyprland turning {name} off")

    def screenshot(self, name: str = "shot", output: str | None = None):
        return super().screenshot(name, output or HYPR_OUTPUT)


# -- sway, for comparison


class SwaySession(Session):
    """sway_session's own session, with the calls the other two have: the same checks on sway, to compare."""

    NAME = "sway"

    def __init__(self, folder: Path, mode: str = "1280x800", scale: float = 1, atspi: bool = False, orca: bool = False,
                 outputs: int = 1):
        super().__init__(folder, mode=mode, scale=scale, atspi=atspi, orca=orca)  # sway makes outputs when asked

    def first_output(self) -> str:
        return sway_session.OUTPUT

    def output_names(self) -> list[str]:
        return [o["name"] for o in self.outputs()]

    def add_output(self) -> str:
        before = set(self.output_names())
        self.msg("command", "create_output")  # HEADLESS-2, right of the first
        self._wait(lambda: bool(set(self.output_names()) - before), "sway's new output")
        return (set(self.output_names()) - before).pop()

    def disable_output(self, name: str) -> None:
        self.msg("command", f"output {name} disable")
        self._wait(lambda: name not in self.output_names(), f"sway turning {name} off")
