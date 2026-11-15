"""A real Wayland compositor for the overlay's tests: a headless sway of the test's own, with a session bus of its
own, input devices the test drives, and a look at what is on screen.

The overlay's other tests talk to a pretend compositor (tests/test_wayland.py), which can't say how a real one
places, focuses, composites or reads the overlay. These run Chatmon on sway itself, as it runs on a sway desktop:
Qt on Wayland, the overlay on its own connection (layer.py). Nothing here touches the desktop the tests run on:
sway draws to memory (WLR_BACKENDS=headless, the pixman renderer, no input devices but the test's), the session
bus and every folder Chatmon, Orca and AT-SPI write to are the test's own.

- `Session` starts the bus and sway (and, when asked, AT-SPI's registry and Orca).
- `Input` is a pointer and a keyboard on sway's seat, made through its virtual-pointer and virtual-keyboard
  protocols over chatmon/wayland.py's connection.
- `Probe` is a whole Chatmon (tests/app_harness.make_companion) in a process of its own on that sway, which runs
  the Python it's sent and answers in JSON: how the tests look inside it.
- `atspi_tree` and `atspi_events` read Chatmon the way a screen reader does: through libatspi, in the system's
  Python (python3-gi), from outside.

Run as a script (`python tests/sway_session.py probe FOLDER`) it is the probe. Not a test file itself.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:  # run as a script (the probe): Chatmon from this checkout
    sys.path.insert(0, str(ROOT))

SWAY_ENV = {"WLR_BACKENDS": "headless", "WLR_RENDERER": "pixman", "WLR_LIBINPUT_NO_DEVICES": "1"}
OUTPUT = "HEADLESS-1"
START_S = 15.0  # sway, the bus or the probe taking longer than this to come up is a failure, not slowness
SYSTEM_PYTHON = "/usr/bin/python3"  # where python3-gi is: libatspi's bindings, as Orca uses them

# Linux input event codes (linux/input-event-codes.h), as wl_keyboard and the virtual keyboard take them.
KEYS = {
    "Escape": 1, "BackSpace": 14, "Tab": 15, "Return": 28, "Control_L": 29, "Shift_L": 42, "space": 57,
    "Home": 102, "Up": 103, "Prior": 104, "Left": 105, "Right": 106, "End": 107, "Down": 108, "Next": 109,
    **{c: code for code, row in ((2, "1234567890"), (16, "qwertyuiop"), (30, "asdfghjkl"), (44, "zxcvbnm")) for c, code in zip(row, range(code, code + len(row)), strict=True)},
}
BTN_LEFT, BTN_RIGHT = 0x110, 0x111

# Opcodes, from wlr-virtual-pointer-unstable-v1.xml and wlroots' virtual-keyboard-unstable-v1.xml.
VPOINTER_MANAGER_CREATE = 0
VPOINTER_MOTION_ABSOLUTE, VPOINTER_BUTTON, VPOINTER_AXIS, VPOINTER_FRAME, VPOINTER_DESTROY = 1, 2, 3, 4, 8
VKEYBOARD_MANAGER_CREATE = 0
VKEYBOARD_KEYMAP, VKEYBOARD_KEY, VKEYBOARD_MODIFIERS, VKEYBOARD_DESTROY = 0, 1, 2, 3


def unavailable(atspi: bool = False, orca: bool = False) -> str | None:
    """Why these tests can't run here (None: they can). CI's sway job installs all of it."""
    if not sys.platform.startswith("linux"):
        return "a real Wayland compositor runs on Linux only"
    for tool in ("sway", "swaymsg", "grim", "dbus-daemon"):
        if shutil.which(tool) is None:
            return f"{tool} isn't installed (CI's sway job installs sway, grim and dbus)"
    try:
        from PyQt6.QtCore import QLibraryInfo

        plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms"
    except ImportError:
        return "PyQt6 isn't installed"
    if not any(plugins.glob("libqwayland*.so")):
        return "this Qt has no Wayland platform plugin"
    if atspi or orca:
        if _atspi_launcher() is None:
            return "AT-SPI's bus launcher isn't installed (at-spi2-core)"
        check = subprocess.run([SYSTEM_PYTHON, "-c", "import gi; gi.require_version('Atspi', '2.0'); from gi.repository import Atspi"],
                               capture_output=True, timeout=30, check=False) if Path(SYSTEM_PYTHON).exists() else None
        if check is None or check.returncode:
            return "the system's Python has no libatspi bindings (python3-gi, gir1.2-atspi-2.0)"
    if orca:
        if shutil.which("orca") is None:
            return "Orca isn't installed"
        said = subprocess.run(["orca", "--version"], capture_output=True, text=True, timeout=30, check=False).stdout  # "Orca version 51.1 (...)"
        words = said.split()
        number = words[words.index("version") + 1] if "version" in words[:-1] else ""
        major = int(number.split(".")[0]) if number.split(".")[0].isdigit() else 0
        if major < 49:
            return f"Orca {major or '?'} has no remote controller to speak through (49 or later has)"
    return None


def _atspi_launcher() -> str | None:
    for path in ("/usr/libexec/at-spi-bus-launcher", "/usr/lib/at-spi-bus-launcher", "/usr/lib/at-spi2-core/at-spi-bus-launcher"):
        if Path(path).exists():
            return path
    return None


class Session:
    """A session bus, a headless sway and (when asked) AT-SPI's registry and Orca, all of the test's own."""

    def __init__(self, folder: Path, mode: str = "1280x800", scale: float = 1, atspi: bool = False, orca: bool = False):
        self.folder = folder
        # A short folder: a socket's path can't be much over 100 characters.
        self.run = Path(tempfile.mkdtemp(prefix="sway-", dir="/tmp"))
        self.run.chmod(0o700)
        home = folder / "home"
        for sub in ("config", "data", "cache", "state"):
            (home / sub).mkdir(parents=True, exist_ok=True)
        self.env = {
            k: v for k, v in os.environ.items()
            if k not in ("DISPLAY", "WAYLAND_DISPLAY", "SWAYSOCK", "DBUS_SESSION_BUS_ADDRESS", "XAUTHORITY", "QT_QPA_PLATFORM")
        }
        self.env.update(
            XDG_RUNTIME_DIR=str(self.run), HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
            XDG_DATA_HOME=str(home / "data"), XDG_CACHE_HOME=str(home / "cache"), XDG_STATE_HOME=str(home / "state"),
            XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="sway", GSETTINGS_BACKEND="memory", NO_AT_BRIDGE="0",
        )
        self._procs: list[tuple[str, subprocess.Popen]] = []
        self._logs: list = []
        try:
            self._start_bus()
            self._start_sway(mode, scale)
            if atspi or orca:
                self._start_atspi()
            if orca:
                self._start_orca()
        except BaseException:
            self.close()
            raise

    # -- starting

    def _spawn(self, name: str, argv: list[str], env: dict | None = None) -> subprocess.Popen:
        log = open(self.folder / f"{name}.log", "wb")  # closed in close(), with the process
        self._logs.append(log)
        proc = subprocess.Popen(argv, env=env or self.env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self._procs.append((name, proc))
        return proc

    def _start_bus(self) -> None:
        config = self.folder / "session.conf"
        config.write_text(
            "<!DOCTYPE busconfig PUBLIC '-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN' "
            "'http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd'>\n"
            f"<busconfig><type>session</type><listen>unix:path={self.run}/bus</listen><standard_session_servicedirs/>"
            "<policy context='default'><allow send_destination='*' eavesdrop='true'/><allow eavesdrop='true'/><allow own='*'/></policy>"
            "</busconfig>\n",
            encoding="utf-8",
        )
        self._spawn("dbus", ["dbus-daemon", "--nofork", "--nopidfile", f"--config-file={config}"])
        self.env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={self.run}/bus"
        self._wait(lambda: (self.run / "bus").exists(), "the session bus")

    def _start_sway(self, mode: str, scale: float) -> None:
        config = self.folder / "sway.conf"
        # Nothing of the desktop's own config: one output, of the size and scale the test asks, and no bar.
        config.write_text(f"output {OUTPUT} mode {mode} scale {scale}\nfocus_follows_mouse no\n", encoding="utf-8")
        self.sway = self._spawn("sway", ["sway", "-d", "-c", str(config)], env={**self.env, **SWAY_ENV})
        self._wait(lambda: any(self.run.glob("wayland-*.lock")) and any(self.run.glob("sway-ipc.*.sock")), "sway")
        socket = next(p for p in self.run.glob("wayland-*") if p.suffix != ".lock")
        # By its whole path: the probe's harness gives Chatmon a runtime folder of its own (app_harness), and a
        # relative WAYLAND_DISPLAY would then point into that.
        self.env["WAYLAND_DISPLAY"] = str(socket)
        self.env["SWAYSOCK"] = str(next(self.run.glob("sway-ipc.*.sock")))
        self._wait(lambda: bool(self.outputs()), "sway's output")
        self.background = self._background()

    def _start_atspi(self) -> None:
        # As on a desktop: the session bus starts AT-SPI's bus launcher when it's first asked for the
        # accessibility bus (org.a11y.Bus.service), as a child of its own, which goes with it.
        self._wait(lambda: self.a11y_address() is not None, "AT-SPI's bus")
        address = self.a11y_address() or ""
        # The registry is started on the accessibility bus when it's first asked for, as a screen reader would.
        subprocess.run(["dbus-send", f"--bus={address}", "--print-reply", "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
                        "org.freedesktop.DBus.StartServiceByName", "string:org.a11y.atspi.Registry", "uint32:0"],
                       capture_output=True, timeout=30, check=False)
        self._wait(lambda: self._bus_has(address, "org.a11y.atspi.Registry"), "AT-SPI's registry")

    def _start_orca(self) -> None:
        self.orca_log = self.folder / "orca-debug.out"
        self._spawn("orca", ["orca", "--replace", "--debug-file", str(self.orca_log)])
        self._wait(lambda: self._bus_has(self.env["DBUS_SESSION_BUS_ADDRESS"], "org.gnome.Orca1.Service")
                   or self._bus_has(self.env["DBUS_SESSION_BUS_ADDRESS"], "org.gnome.Orca.Service"), "Orca", 40.0)

    def _wait(self, ready, what: str, seconds: float = START_S) -> None:
        deadline = time.monotonic() + seconds
        while not ready():
            for name, proc in self._procs:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} stopped while waiting for {what}:\n{self.log(name)[-3000:]}")
            if time.monotonic() > deadline:
                raise RuntimeError(f"{what} didn't come up in {seconds} s")
            time.sleep(0.05)

    def _bus_has(self, address: str, name: str) -> bool:
        out = subprocess.run(
            ["dbus-send", f"--bus={address}", "--print-reply", "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus",
             "org.freedesktop.DBus.NameHasOwner", f"string:{name}"],
            capture_output=True, text=True, timeout=10, check=False,
        ) if address else None
        return out is not None and "boolean true" in out.stdout

    def screen_reader_on(self) -> None:
        """A screen reader running, as Chatmon and Qt can tell: accessibility on for the session (org.a11y.Status
        IsEnabled, which turns on Qt's AT-SPI bridge, as Orca and GNOME's setting do) and, unless the real Orca
        runs here, the pretend Orca remote controller (tests/fake_orca.py) on the session bus, which is how Chatmon
        finds Orca 49 and later. (at-spi2-core 2.62 has dropped ScreenReaderEnabled, the other way it looks.)"""
        subprocess.run(
            ["dbus-send", "--session", "--print-reply", "--dest=org.a11y.Bus", "/org/a11y/bus", "org.freedesktop.DBus.Properties.Set",
             "string:org.a11y.Status", "string:IsEnabled", "variant:boolean:true"],
            capture_output=True, timeout=10, check=True, env=self.env,
        )
        bus = self.env["DBUS_SESSION_BUS_ADDRESS"]
        if not self._bus_has(bus, "org.gnome.Orca1.Service"):
            self.said = self.folder / "fake-orca-said.txt"
            self._spawn("fake-orca", [sys.executable, str(HERE / "fake_orca.py"), str(self.said)], env={**self.env, "QT_QPA_PLATFORM": "offscreen"})
            self._wait(lambda: self._bus_has(bus, "org.gnome.Orca1.Service"), "the pretend Orca")

    def a11y_address(self) -> str | None:
        out = subprocess.run(
            ["dbus-send", "--session", "--print-reply=literal", "--dest=org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus.GetAddress"],
            capture_output=True, text=True, timeout=10, check=False, env=self.env,
        )
        address = out.stdout.strip()
        return address if out.returncode == 0 and address.startswith("unix:") else None

    def _background(self) -> tuple[int, int, int]:
        """The colour sway shows where nothing is drawn, read off the whole output before any client draws: black in
        sway 1.12, dark grey (63, 63, 63) in Ubuntu 24.04's 1.9. Read, not set: swaybg, the way to set it, draws its
        black unevenly at a fractional scale under 1.9 (46 in a corner, 14 in the middle, at 1.5), and the tests
        tell the overlay's pixels from this colour, so it has to be one colour across the output; anything else fails
        here. Not at the very edge: at a fractional scale 1.9 draws the last row and column a shade off (62 for 63)."""
        shot = subprocess.run(["grim", "-o", OUTPUT, "-t", "ppm", "-"], capture_output=True, timeout=60, env=self.env, check=True).stdout
        magic, width, height, _maxval, pixels = shot.split(maxsplit=4)  # P6, then the bytes, three a pixel
        w, h = int(width), int(height)
        assert magic == b"P6" and len(pixels) == w * h * 3, "grim's PPM wasn't what it should be"
        points = [(x, y) for x in (4, w // 3, w // 2, w - 5) for y in (4, h // 2, 2 * h // 3, h - 5)]
        seen = {tuple(pixels[(y * w + x) * 3 : (y * w + x) * 3 + 3]) for x, y in points}
        if len(seen) != 1:
            raise RuntimeError(f"sway's empty output isn't one colour: {sorted(seen)}")
        r, g, b = seen.pop()
        return r, g, b

    # -- looking

    def msg(self, kind: str, *args: str):
        out = subprocess.run(["swaymsg", "-r", "-t", kind, *args], capture_output=True, text=True, timeout=10, env=self.env, check=False)
        if out.returncode and kind != "command":
            raise RuntimeError(f"swaymsg -t {kind}: {out.stderr or out.stdout}")
        return json.loads(out.stdout) if out.stdout.strip() else None

    def outputs(self) -> list[dict]:
        try:
            return [o for o in self.msg("get_outputs") or [] if o.get("active")]
        except (RuntimeError, json.JSONDecodeError):
            return []

    def views(self) -> list[dict]:
        """Every window sway manages (not layer surfaces, which aren't in its tree): tiled and floating."""
        found: list[dict] = []

        def walk(node: dict, floating: bool) -> None:
            if node.get("type") in ("con", "floating_con") and (node.get("app_id") is not None or node.get("pid")):
                found.append({**node, "floating": floating})
            for child in node.get("nodes", []):
                walk(child, floating)
            for child in node.get("floating_nodes", []):
                walk(child, True)

        walk(self.msg("get_tree"), False)
        return found

    def screenshot(self, name: str = "shot", output: str = OUTPUT):
        """What sway shows on an output now, as a QImage (grim, through the screencopy protocol)."""
        from PyQt6.QtGui import QImage

        path = self.folder / f"{name}.png"
        subprocess.run(["grim", "-o", output, str(path)], check=True, timeout=30, env=self.env, capture_output=True)
        image = QImage(str(path))
        assert not image.isNull(), f"grim's {path} didn't load"
        return image

    def log(self, name: str) -> str:
        path = self.folder / f"{name}.log"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    # -- stopping

    def close(self) -> None:
        for _name, proc in reversed(self._procs):
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for _name, proc in reversed(self._procs):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)
        self._procs = []
        self._stop_strays()
        for log in self._logs:
            log.close()
        self._logs = []
        shutil.rmtree(self.run, ignore_errors=True)

    def _stop_strays(self) -> None:
        """What the session started that left its process group (Orca's speech-dispatcher daemonizes): every
        process whose command line names this session's own folder."""
        mine = str(self.run).encode()
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit() or int(proc.name) == os.getpid():
                continue
            try:
                if mine in (proc / "cmdline").read_bytes():
                    os.kill(int(proc.name), signal.SIGTERM)
            except (OSError, ValueError):
                continue  # gone already, or not ours to read


class Input:
    """A pointer and a keyboard on sway's seat, as if plugged in: moved, clicked and typed on by the test.

    Positions are in sway's layout coordinates (logical pixels), the overlay's own."""

    def __init__(self, session: Session):
        from chatmon import wayland, xkb
        from chatmon.wayland import DISPLAY_ID, Connection, decode

        self._w, self._decode = wayland, decode
        conn = Connection.open(session.env)
        assert conn is not None, "couldn't connect to sway"
        self.conn = conn
        found: dict[str, tuple[int, int]] = {}

        def global_(opcode: int, args: bytes) -> None:
            if opcode == 0:
                name, interface, version = decode("usu", args)
                found.setdefault(interface, (name, version))

        registry = conn.new_id(global_)
        conn.request(DISPLAY_ID, 1, "n", registry)
        assert conn.roundtrip(5.0)
        ids = {}
        for interface in ("wl_seat", "zwlr_virtual_pointer_manager_v1", "zwp_virtual_keyboard_manager_v1"):
            assert interface in found, f"sway doesn't offer {interface}"
            ids[interface] = conn.new_id()
            conn.request(registry, 0, "usun", found[interface][0], interface, 1, ids[interface])
        output = session.outputs()[0]["rect"]
        self.extent = (output["width"], output["height"])
        self.pointer = conn.new_id()
        conn.request(ids["zwlr_virtual_pointer_manager_v1"], VPOINTER_MANAGER_CREATE, "on", ids["wl_seat"], self.pointer)
        self.keyboard = conn.new_id()
        conn.request(ids["zwp_virtual_keyboard_manager_v1"], VKEYBOARD_MANAGER_CREATE, "on", ids["wl_seat"], self.keyboard)
        lib = xkb.library()
        assert lib is not None, "libxkbcommon isn't installed"
        keymap = xkb.keymap_from_names(lib, "us").encode() + b"\0"
        fd = os.memfd_create("keymap", os.MFD_CLOEXEC)
        try:
            os.write(fd, keymap)
            conn.request(self.keyboard, VKEYBOARD_KEYMAP, "uhu", 1, fd, len(keymap))  # 1: xkb_v1
        finally:
            os.close(fd)
        assert conn.roundtrip(5.0), conn.error
        self._t0 = time.monotonic()
        self.at = (0.0, 0.0)

    def _ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000) & 0xFFFFFFFF

    def _sync(self) -> None:
        assert self.conn.roundtrip(5.0), self.conn.error  # sway has handled it, and sent the events it made

    def move(self, x: float, y: float) -> None:
        w, h = self.extent
        self.conn.request(self.pointer, VPOINTER_MOTION_ABSOLUTE, "uuuuu", self._ms(), round(x), round(y), w, h)
        self.conn.request(self.pointer, VPOINTER_FRAME)
        self.at = (x, y)
        self._sync()

    def button(self, button: int, down: bool) -> None:
        self.conn.request(self.pointer, VPOINTER_BUTTON, "uuu", self._ms(), button, 1 if down else 0)
        self.conn.request(self.pointer, VPOINTER_FRAME)
        self._sync()

    def click(self, x: float, y: float, button: int = BTN_LEFT) -> None:
        self.move(x, y)
        self.button(button, True)
        self.button(button, False)

    def key(self, name: str, mods: int = 0) -> None:
        """Press and let go of a key; `mods`: xkb's mask held (Shift 1, Ctrl 4)."""
        code = KEYS[name]
        if mods:
            self.conn.request(self.keyboard, VKEYBOARD_MODIFIERS, "uuuu", mods, 0, 0, 0)
        self.conn.request(self.keyboard, VKEYBOARD_KEY, "uuu", self._ms(), code, 1)
        self.conn.request(self.keyboard, VKEYBOARD_KEY, "uuu", self._ms(), code, 0)
        if mods:
            self.conn.request(self.keyboard, VKEYBOARD_MODIFIERS, "uuuu", 0, 0, 0, 0)
        self._sync()

    def type(self, text: str) -> None:
        for ch in text:
            self.key("space" if ch == " " else ch)

    def close(self) -> None:
        self.conn.request(self.pointer, VPOINTER_DESTROY)
        self.conn.request(self.keyboard, VKEYBOARD_DESTROY)
        self.conn.flush()
        self.conn.close()


class ProbeError(RuntimeError):
    pass


class Probe:
    """A whole Chatmon on the session's sway, in a process of its own: `call` runs Python in it and returns its
    `result` (as JSON can carry it). In there: `c` the Companion, `stage`, `box` (its ask box), `surface` (the
    overlay's LayerSurface), `spin(s)`, `until(condition, s)`, `settled()` and Qt's core and widget classes."""

    def __init__(self, session: Session, env: dict | None = None):
        self.session = session
        self.log = session.folder / "probe.log"
        self._err = open(self.log, "wb")  # closed in close()
        child = {**session.env, "QT_QPA_PLATFORM": "wayland", "PYTHONPATH": str(ROOT), **(env or {})}
        self.proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "probe", str(session.folder / "probe")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._err, env=child, text=True, bufsize=1,
        )
        try:
            ready = self._read(START_S * 2)
        except BaseException:
            self.close()
            raise
        if ready.get("ready") is not True:
            self.close()
            raise ProbeError(f"the probe didn't start: {ready}\n{self.stderr()}")

    def _read(self, seconds: float) -> dict:
        import select

        assert self.proc.stdout is not None
        readable, _, _ = select.select([self.proc.stdout], [], [], seconds)
        line = self.proc.stdout.readline() if readable else ""
        if not line:
            if self.proc.poll() is None:  # stuck: where, from its threads' stacks (faulthandler, registered in _probe)
                self.proc.send_signal(signal.SIGUSR1)
                time.sleep(0.5)
            raise ProbeError(f"the probe said nothing in {seconds} s (exit {self.proc.poll()}):\n{self.stderr()}")
        return json.loads(line)

    def call(self, code: str, seconds: float = 30.0, settle: float = 0.05):
        """Run `code` in the probe once it has handled what sway sent it (for `settle` s at least); its `result`."""
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"code": code, "settle": settle}) + "\n")
        self.proc.stdin.flush()
        answer = self._read(seconds)
        if "error" in answer:
            raise ProbeError(f"{answer['error']}\nin:\n{code}")
        return answer.get("result")

    def stderr(self) -> str:
        self._err.flush()
        return self.log.read_text(encoding="utf-8", errors="replace")[-6000:]

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                assert self.proc.stdin is not None
                self.proc.stdin.write(json.dumps({"quit": True}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait(timeout=10)
        for stream in (self.proc.stdin, self.proc.stdout):
            if stream is not None:
                stream.close()
        self._err.close()


# -- AT-SPI, as a screen reader reads it

_ATSPI_TREE = r"""
import json, sys
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

def node(acc, depth):
    out = {"role": acc.get_role_name(), "name": acc.get_name() or "", "description": acc.get_description() or ""}
    states = acc.get_state_set()
    out["states"] = sorted(Atspi.StateType(s).value_nick for s in range(Atspi.StateType.LAST_DEFINED) if states.contains(Atspi.StateType(s)))
    text = acc.get_text_iface() if hasattr(acc, "get_text_iface") else None
    if text is not None:
        out["text"] = Atspi.Text.get_text(text, 0, Atspi.Text.get_character_count(text))
    try:
        out["actions"] = [Atspi.Action.get_action_name(acc, i) for i in range(Atspi.Action.get_n_actions(acc))]
    except Exception:
        out["actions"] = []
    try:
        box = Atspi.Component.get_extents(acc, Atspi.CoordType.WINDOW)
        out["extents"] = [box.x, box.y, box.width, box.height]
    except Exception:
        out["extents"] = None
    if depth < 30:
        out["children"] = [node(acc.get_child_at_index(i), depth + 1) for i in range(acc.get_child_count())]
    return out

desktop = Atspi.get_desktop(0)
apps = []
for i in range(desktop.get_child_count()):
    app = desktop.get_child_at_index(i)
    if app is None:
        continue
    try:
        pid = app.get_process_id()
    except Exception:
        pid = 0
    if sys.argv[1] == "*" or pid == int(sys.argv[1]):
        apps.append({"pid": pid, **node(app, 0)})
print(json.dumps(apps))
"""

_ATSPI_EVENTS = r"""
import json, sys, time
import gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib

def got(event):
    try:
        source = event.source.get_name() or "", event.source.get_role_name()
    except Exception:
        source = "", ""
    any_data = event.any_data if isinstance(event.any_data, (str, int, float, bool)) else str(event.any_data)
    print(json.dumps({"type": event.type, "detail1": event.detail1, "detail2": event.detail2, "data": any_data,
                      "source": source[0], "role": source[1]}), flush=True)

listener = Atspi.EventListener.new(got)
for kind in sys.argv[2:]:
    listener.register(kind)
print(json.dumps({"listening": True}), flush=True)
GLib.timeout_add(int(float(sys.argv[1]) * 1000), lambda: Atspi.event_quit())
Atspi.event_main()
"""


def atspi_tree(session: Session, pid: int | str = "*") -> list[dict]:
    """The accessible tree of the app with this process id (every app: "*"), as libatspi reads it."""
    out = subprocess.run([SYSTEM_PYTHON, "-c", _ATSPI_TREE, str(pid)], capture_output=True, text=True, timeout=60, env=session.env, check=False)
    if out.returncode:
        raise RuntimeError(f"reading AT-SPI failed:\n{out.stderr[-3000:]}")
    return json.loads(out.stdout)


class AtspiEvents:
    """AT-SPI events of the kinds given (e.g. "object:text-changed"), heard for `seconds` from when it starts,
    as a screen reader registers for and hears them."""

    def __init__(self, session: Session, kinds: list[str], seconds: float = 20.0):
        self.proc = subprocess.Popen([SYSTEM_PYTHON, "-c", _ATSPI_EVENTS, str(seconds), *kinds], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, env=session.env)
        assert self.proc.stdout is not None
        first = self.proc.stdout.readline()
        if '"listening"' not in first:
            self.proc.kill()
            raise RuntimeError(f"the AT-SPI listener didn't start: {first}{self.proc.communicate(timeout=10)[1][-3000:]}")

    def stop(self) -> list[dict]:
        self.proc.send_signal(signal.SIGINT)
        try:
            out, _err = self.proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, _err = self.proc.communicate(timeout=10)
        return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def find(tree, **want) -> list[dict]:
    """Every node of an AT-SPI tree whose fields match `want` (a value, or a function of the field)."""
    found = []
    nodes = list(tree) if isinstance(tree, list) else [tree]
    while nodes:
        n = nodes.pop(0)
        if all(v(n.get(k)) if callable(v) else n.get(k) == v for k, v in want.items()):
            found.append(n)
        nodes.extend(n.get("children", []))
    return found


# -- the probe: a whole Chatmon on that sway


def _probe(folder: str) -> int:
    import contextlib
    import faulthandler
    import traceback

    faulthandler.register(signal.SIGUSR1)  # Probe._read asks for the stacks when the probe is stuck

    import pytest
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import QSocketNotifier

    sys.path.insert(0, str(HERE))
    import app_harness

    Path(folder).mkdir(parents=True, exist_ok=True)
    with pytest.MonkeyPatch.context() as mp:
        companion = app_harness.make_companion(Path(folder), mp)
        c = next(companion)
        app = QtWidgets.QApplication.instance()
        surface = c.stage.surface

        def settled(seconds: float = 5.0) -> bool:
            """Everything the overlay has drawn is on screen: no change waiting, no frame outstanding."""
            return app_harness.until(lambda: c.stage._timer.remainingTime() != 0 and getattr(surface, "_pending", QtGui.QRegion()).isEmpty()
                                     and not getattr(surface, "_frame_pending", False), seconds)

        ns: dict = {"c": c, "stage": c.stage, "box": c.ask_box, "surface": surface, "spin": app_harness.spin,
                    "until": app_harness.until, "settled": settled, "mp": mp, "QtCore": QtCore, "QtGui": QtGui, "QtWidgets": QtWidgets}
        ns.update({k: getattr(QtCore, k) for k in ("QPoint", "QPointF", "QRect", "Qt", "QTimer")})

        def answer(message: dict) -> None:
            sys.stdout.write(json.dumps(message, default=str) + "\n")
            sys.stdout.flush()

        stdin = sys.stdin

        def command() -> None:
            line = stdin.readline()
            if not line:
                app.quit()
                return
            message = json.loads(line)
            if message.get("quit"):
                notifier.setEnabled(False)
                app.quit()
                return
            app_harness.spin(message.get("settle", 0.05))  # what sway sent before this, handled first
            ns.pop("result", None)
            try:
                exec(compile(message["code"], "<probe>", "exec"), ns)  # noqa: S102  # the test's own code, in its own process
                answer({"result": ns.get("result")})
            except Exception:  # noqa: BLE001  # every failure goes back to the test, with its traceback
                answer({"error": traceback.format_exc()})

        notifier = QSocketNotifier(stdin.fileno(), QSocketNotifier.Type.Read)
        notifier.activated.connect(command)
        overlay = type(surface).__name__
        ok = app_harness.until(lambda: getattr(surface, "_size", None) is not None, START_S) if overlay == "LayerSurface" else True
        answer({"ready": ok, "overlay": overlay})
        app.exec()
        with contextlib.suppress(StopIteration):
            next(companion)
    return 0


if __name__ == "__main__" and sys.argv[1:2] == ["probe"]:
    sys.exit(_probe(sys.argv[2]))
