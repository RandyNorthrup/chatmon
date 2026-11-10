"""The stage on Wayland: a layer-shell overlay surface.

On a Wayland desktop the penguin can't be an X window over the screen: through
XWayland, clicks pass through that window only if the compositor reads its X
input shape, and Hyprland, Sway and other wlroots-style compositors don't, so
the window swallows every click and can take focus. A layer-shell surface is
how Wayland does an overlay: it sits above panels, takes the keyboard only
while you're typing in the ask box, and its input region (the penguin, its
bubble, the ask box, a menu) is the only part that gets clicks.

Everything the penguin shows is drawn on it: the penguin, its bubbles, its
menus (stagemenu.py) and the ask box (Qt widgets the stage hosts). Nothing is
left as an XWayland window, which a compositor would put under the overlay,
decorate with its borders and keep the keyboard from.

The stage paints into shared-memory buffers here, through the small Wayland
client in wayland.py; the pointer and keyboard events that land on it go back
to the stage, the keys through libxkbcommon (xkb.py). Used when the compositor
offers zwlr_layer_shell_v1 (not GNOME, which keeps the X window: Mutter does
read X input shapes and lets a clicked X window take the keyboard).
"""

from __future__ import annotations

import ctypes
import math
import threading
from dataclasses import dataclass, field
import mmap
import os
import sys

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPointF, QRect, QSocketNotifier, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QRegion, QScreen

from . import wayland, xkb
from .wayland import DISPLAY_ID, Connection, decode

STAGE_ENV = "PENGUIN_COMPANION_STAGE"  # "window" keeps the X window on Wayland too
DEBUG = bool(os.environ.get("PENGUIN_COMPANION_DEBUG"))  # log the overlay's focus changes to stderr


def _debug(message: str) -> None:
    if DEBUG:
        print(f"penguin-companion [overlay] {message}", file=sys.stderr, flush=True)
NAMESPACE = "penguin-companion"

# Opcodes (requests unless they say event), from the protocol XML files.
REGISTRY_BIND = 0
EV_REGISTRY_GLOBAL, EV_REGISTRY_GLOBAL_REMOVE = 0, 1
COMPOSITOR_CREATE_SURFACE, COMPOSITOR_CREATE_REGION = 0, 1
SHM_CREATE_POOL = 0
SHM_POOL_CREATE_BUFFER, SHM_POOL_DESTROY = 0, 1
BUFFER_DESTROY = 0
EV_BUFFER_RELEASE = 0
SURFACE_DESTROY, SURFACE_ATTACH, SURFACE_FRAME, SURFACE_SET_INPUT_REGION, SURFACE_COMMIT = 0, 1, 3, 5, 6
SURFACE_SET_BUFFER_SCALE, SURFACE_DAMAGE_BUFFER = 8, 9
EV_SURFACE_PREFERRED_BUFFER_SCALE = 2
REGION_DESTROY, REGION_ADD = 0, 1
SEAT_GET_POINTER, SEAT_GET_KEYBOARD, SEAT_RELEASE = 0, 1, 3
EV_SEAT_CAPABILITIES = 0
POINTER_RELEASE = 1
EV_POINTER_ENTER, EV_POINTER_LEAVE, EV_POINTER_MOTION, EV_POINTER_BUTTON, EV_POINTER_AXIS = 0, 1, 2, 3, 4
KEYBOARD_RELEASE = 0
EV_KEYBOARD_KEYMAP, EV_KEYBOARD_ENTER, EV_KEYBOARD_LEAVE, EV_KEYBOARD_KEY = 0, 1, 2, 3
EV_KEYBOARD_MODIFIERS, EV_KEYBOARD_REPEAT_INFO = 4, 5
OUTPUT_RELEASE = 0
EV_OUTPUT_GEOMETRY, EV_OUTPUT_DONE, EV_OUTPUT_SCALE, EV_OUTPUT_NAME = 0, 2, 3, 4
LAYER_SHELL_GET_LAYER_SURFACE = 0
LAYER_SURFACE_SET_SIZE, LAYER_SURFACE_SET_ANCHOR, LAYER_SURFACE_SET_EXCLUSIVE_ZONE = 0, 1, 2
LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY, LAYER_SURFACE_ACK_CONFIGURE, LAYER_SURFACE_DESTROY = 4, 6, 7
EV_LAYER_SURFACE_CONFIGURE, EV_LAYER_SURFACE_CLOSED = 0, 1
CURSOR_SHAPE_GET_POINTER = 1
CURSOR_DEVICE_DESTROY, CURSOR_DEVICE_SET_SHAPE = 0, 1
VIEWPORTER_GET_VIEWPORT = 1
VIEWPORT_DESTROY, VIEWPORT_SET_DESTINATION = 0, 2
FRACTIONAL_GET = 1
FRACTIONAL_DESTROY = 0
EV_FRACTIONAL_PREFERRED_SCALE = 0
TEXT_INPUT_MANAGER_GET = 1
TI_DESTROY, TI_ENABLE, TI_DISABLE, TI_SET_SURROUNDING_TEXT = 0, 1, 2, 3
TI_SET_CONTENT_TYPE, TI_SET_CURSOR_RECTANGLE, TI_COMMIT = 5, 6, 7
EV_TI_ENTER, EV_TI_LEAVE, EV_TI_PREEDIT, EV_TI_COMMIT_STRING, EV_TI_DELETE_SURROUNDING, EV_TI_DONE = 0, 1, 2, 3, 4, 5
SURROUNDING_MAX = 4000  # bytes: a Wayland message can't carry more
DATA_DEVICE_MANAGER_CREATE_SOURCE, DATA_DEVICE_MANAGER_GET_DEVICE = 0, 1
DATA_DEVICE_SET_SELECTION = 1
EV_DATA_DEVICE_DATA_OFFER, EV_DATA_DEVICE_SELECTION = 0, 5
DATA_OFFER_RECEIVE, DATA_OFFER_DESTROY = 1, 2
EV_DATA_OFFER_OFFER = 0
DATA_SOURCE_OFFER, DATA_SOURCE_DESTROY = 0, 1
EV_DATA_SOURCE_SEND, EV_DATA_SOURCE_CANCELLED = 1, 2
PRIMARY_MANAGER_CREATE_SOURCE, PRIMARY_MANAGER_GET_DEVICE = 0, 1
PRIMARY_DEVICE_SET_SELECTION = 0
EV_PRIMARY_DEVICE_DATA_OFFER, EV_PRIMARY_DEVICE_SELECTION = 0, 1
PRIMARY_OFFER_RECEIVE, PRIMARY_OFFER_DESTROY = 0, 1
EV_PRIMARY_OFFER_OFFER = 0
PRIMARY_SOURCE_OFFER, PRIMARY_SOURCE_DESTROY = 0, 1
EV_PRIMARY_SOURCE_SEND, EV_PRIMARY_SOURCE_CANCELLED = 0, 1
TEXT_TYPES = ("text/plain;charset=utf-8", "UTF8_STRING", "text/plain", "TEXT", "STRING")  # best first
PASTE_MAX = 4 * 1024 * 1024  # bytes of clipboard text to take at most

LAYER_OVERLAY = 3
ANCHOR_ALL = 1 | 2 | 4 | 8  # top, bottom, left, right: the whole output
KEYBOARD_NONE, KEYBOARD_EXCLUSIVE, KEYBOARD_ON_DEMAND = 0, 1, 2  # on_demand: layer-shell version 4
KEYMAP_XKB_V1 = 1
SHM_ARGB8888 = 0  # premultiplied, byte order B G R A: QImage's ARGB32_Premultiplied on little-endian
CAP_POINTER, CAP_KEYBOARD = 1, 2
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
AXIS_VERTICAL = 0
CURSOR_SHAPES = {"default": 1, "pointer": 4, "text": 9, "grab": 16, "grabbing": 17}
WHEEL_PER_PIXEL = 8  # Qt's angle delta (120 a notch) per pixel of Wayland scroll (15 a notch)
REPEAT_RATE, REPEAT_DELAY = 25, 600  # until the compositor says (wl_keyboard version 4)
MAX_BUFFERS = 3

# The interfaces we bind, and the newest version of each we speak.
WANTED = {
    "wl_compositor": 6,  # 4: damage_buffer; 6: preferred_buffer_scale
    "wl_shm": 1,
    "wl_seat": 5,
    "wl_output": 4,  # 4: name
    "zwlr_layer_shell_v1": 4,  # 4: keyboard on demand
    "wp_cursor_shape_manager_v1": 1,
    "wp_viewporter": 1,
    "wp_fractional_scale_manager_v1": 1,
    "zwp_text_input_manager_v3": 1,  # input methods (fcitx5, IBus...) through the compositor
    "wl_data_device_manager": 3,  # the clipboard
    "zwp_primary_selection_device_manager_v1": 1,  # selected text, pasted with the middle button
}
NEEDED = {"wl_compositor": 4, "wl_shm": 1, "zwlr_layer_shell_v1": 1}


def wanted(env=os.environ) -> bool:
    """Whether to try a layer-shell stage at all."""
    if not sys.platform.startswith("linux") or env.get(STAGE_ENV) == "window":
        return False
    return QGuiApplication.platformName() in ("xcb", "wayland") and wayland.socket_path(env) is not None


class Output:
    def __init__(self, oid: int, version: int):
        self.id, self.version = oid, version
        self.name: str | None = None
        self.x = self.y = 0
        self.scale = 1


class Buffer:
    """One shared-memory buffer the stage paints into, and what it's missing."""

    def __init__(self, conn: Connection, shm: int, width: int, height: int, on_release):
        self.conn = conn
        self.width, self.height = width, height
        stride = width * 4
        size = stride * height
        fd = os.memfd_create("penguin-companion", os.MFD_CLOEXEC)
        try:
            os.ftruncate(fd, size)
            self.map = mmap.mmap(fd, size)
            pool = conn.new_id()
            conn.request(shm, SHM_CREATE_POOL, "nhi", pool, fd, size)
            self.id = conn.new_id(lambda opcode, args: on_release(self) if opcode == EV_BUFFER_RELEASE else None)
            conn.request(pool, SHM_POOL_CREATE_BUFFER, "niiiiu", self.id, 0, width, height, stride, SHM_ARGB8888)
            conn.request(pool, SHM_POOL_DESTROY)  # the buffer keeps it alive
        finally:
            os.close(fd)  # request() sent a copy
        self._pixels = ctypes.c_char.from_buffer(self.map)
        self.image = QImage(sip.voidptr(ctypes.addressof(self._pixels)), width, height, stride, QImage.Format.Format_ARGB32_Premultiplied)
        self.busy = False  # the compositor has it
        self.stale = QRegion()  # what changed on the stage since this one was painted

    def destroy(self) -> None:
        self.conn.request(self.id, BUFFER_DESTROY)
        self.conn.forget(self.id)
        self.image = None
        self._pixels = None
        self.map.close()


def _write_all(fd: int, data: bytes) -> None:
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view) :]
    except OSError:
        pass  # the other side stopped reading
    finally:
        os.close(fd)


class PipeReader(QObject):
    """Reads a pipe to its end without blocking, then says what it got."""

    finished = pyqtSignal(bytes)

    def __init__(self, fd: int, limit: int, parent: QObject):
        super().__init__(parent)
        self.fd, self.limit, self.data = fd, limit, bytearray()
        os.set_blocking(fd, False)
        self.notifier = QSocketNotifier(fd, QSocketNotifier.Type.Read, self)
        self.notifier.activated.connect(self._read)
        self.timer = QTimer(self, singleShot=True)
        self.timer.timeout.connect(self._end)
        self.timer.start(5000)  # an app that never finishes writing

    def _read(self) -> None:
        try:
            chunk = os.read(self.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            chunk = b""
        self.data += chunk
        if not chunk or len(self.data) >= self.limit:
            self._end()

    def _end(self) -> None:
        if self.fd < 0:
            return
        self.notifier.setEnabled(False)
        self.timer.stop()
        os.close(self.fd)
        self.fd = -1
        self.finished.emit(bytes(self.data[: self.limit]))


@dataclass(frozen=True)
class Channel:
    """A selection protocol's names and opcodes (the clipboard's and the
    primary selection's are alike but numbered differently)."""

    manager: str
    create_source: int
    get_device: int
    set_selection: int
    ev_data_offer: int
    ev_selection: int
    offer_receive: int
    offer_destroy: int
    ev_offer: int
    source_offer: int
    source_destroy: int
    ev_send: int
    ev_cancelled: int


CLIPBOARD = Channel(
    "wl_data_device_manager", DATA_DEVICE_MANAGER_CREATE_SOURCE, DATA_DEVICE_MANAGER_GET_DEVICE, DATA_DEVICE_SET_SELECTION,
    EV_DATA_DEVICE_DATA_OFFER, EV_DATA_DEVICE_SELECTION, DATA_OFFER_RECEIVE, DATA_OFFER_DESTROY, EV_DATA_OFFER_OFFER,
    DATA_SOURCE_OFFER, DATA_SOURCE_DESTROY, EV_DATA_SOURCE_SEND, EV_DATA_SOURCE_CANCELLED,
)
PRIMARY = Channel(
    "zwp_primary_selection_device_manager_v1", PRIMARY_MANAGER_CREATE_SOURCE, PRIMARY_MANAGER_GET_DEVICE,
    PRIMARY_DEVICE_SET_SELECTION, EV_PRIMARY_DEVICE_DATA_OFFER, EV_PRIMARY_DEVICE_SELECTION, PRIMARY_OFFER_RECEIVE,
    PRIMARY_OFFER_DESTROY, EV_PRIMARY_OFFER_OFFER, PRIMARY_SOURCE_OFFER, PRIMARY_SOURCE_DESTROY, EV_PRIMARY_SOURCE_SEND,
    EV_PRIMARY_SOURCE_CANCELLED,
)


class Selection:
    """The clipboard or the primary selection, as this connection has it:
    what other apps offer (read only when you paste), and what we offer."""

    def __init__(self, surface: LayerSurface, channel: Channel):
        self.surface, self.ch, self.conn = surface, channel, surface.conn
        self.devices: dict[int, int] = {}  # seat id: device id
        self.offers: dict[int, set[str]] = {}  # offers the compositor made: their types
        self.current: int | None = None  # the offer that's the selection now
        self.source: tuple[int, bytes] | None = None  # what we offer
        self.readers: list[PipeReader] = []

    def add_devices(self) -> None:
        manager = self.surface.globals.get(self.ch.manager)
        if manager is None:
            return
        for seat in self.surface._seat_versions:
            if seat not in self.devices:
                device = self.conn.new_id(self._device_event)
                self.conn.request(manager[0], self.ch.get_device, "no", device, seat)
                self.devices[seat] = device

    def has_text(self) -> bool:
        return self.current is not None and bool(self.offers.get(self.current, set()) & set(TEXT_TYPES))

    def paste(self, then) -> None:
        if not self.has_text():
            return
        types = self.offers[self.current]
        mime = next(t for t in TEXT_TYPES if t in types)
        read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        self.conn.request(self.current, self.ch.offer_receive, "sh", mime, write_fd)
        os.close(write_fd)  # request() sent a copy; the other app has the writing end
        self.surface._flush()
        reader = PipeReader(read_fd, PASTE_MAX, self.surface)
        self.readers.append(reader)

        def done(data: bytes) -> None:
            self.readers.remove(reader)
            then(data.decode("utf-8", errors="replace"))

        reader.finished.connect(done)

    def copy(self, text: str) -> None:
        device = next(iter(self.devices.values()), None)
        manager = self.surface.globals.get(self.ch.manager)
        if device is None or manager is None or not text:
            return
        self._drop_source()
        source = self.conn.new_id(self._source_event)
        self.conn.request(manager[0], self.ch.create_source, "n", source)
        for mime in TEXT_TYPES:
            self.conn.request(source, self.ch.source_offer, "s", mime)
        self.source = (source, text.encode("utf-8"))
        self.conn.request(device, self.ch.set_selection, "ou", source, self.surface._input_serial)

    def _device_event(self, opcode: int, args: bytes) -> None:
        if opcode == self.ch.ev_data_offer:  # an object the compositor made; its types follow
            (offer,) = decode("n", args)
            self.offers[offer] = set()
            self.conn.listen(offer, lambda op, a, o=offer: self._offer_event(o, op, a))
        elif opcode == self.ch.ev_selection:
            (offer,) = decode("o", args)
            if self.current is not None and self.current != offer:
                self._drop_offer(self.current)
            self.current = offer or None

    def _offer_event(self, offer: int, opcode: int, args: bytes) -> None:
        if opcode == self.ch.ev_offer:
            (mime,) = decode("s", args)
            self.offers.setdefault(offer, set()).add(mime)

    def _drop_offer(self, offer: int) -> None:
        self.offers.pop(offer, None)
        self.conn.request(offer, self.ch.offer_destroy)
        self.conn.forget(offer)

    def _source_event(self, opcode: int, args: bytes) -> None:
        if opcode == self.ch.ev_send:
            decode("sh", args)
            fd = self.conn.take_fd()
            if self.source is None:
                os.close(fd)
                return
            threading.Thread(target=_write_all, args=(fd, self.source[1]), daemon=True).start()  # a slow reader can't stall us
        elif opcode == self.ch.ev_cancelled:  # someone else's is the selection now
            self._drop_source()

    def _drop_source(self) -> None:
        if self.source is not None:
            self.conn.request(self.source[0], self.ch.source_destroy)
            self.conn.forget(self.source[0])
            self.source = None


@dataclass
class TextState:
    """A text field with the focus: its text, cursor and selection anchor (Qt's
    UTF-16 positions) and the cursor's rectangle on the stage."""

    text: str
    cursor: int
    anchor: int
    rect: QRect


@dataclass
class PendingIM:
    preedit: str = ""
    cursor: tuple[int, int] = (0, 0)  # bytes into the preedit; (-1, -1) hides it
    commit: str = ""
    before: int = 0  # bytes to delete before the cursor
    after: int = 0


@dataclass
class TextInput:
    id: int
    entered: bool = False  # the seat's text-input focus is on our surface
    enabled: bool = False
    commits: int = 0
    sent: tuple | None = None  # the state last sent: (text, cursor, anchor, rect), in bytes
    pending: PendingIM = field(default_factory=PendingIM)


def _utf8_len(s: str) -> int:
    return len(s.encode("utf-8", errors="surrogatepass"))


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le", errors="surrogatepass")) // 2


def _from_utf16(s: str, units: int) -> str:
    """The first `units` UTF-16 units of s (Qt's positions), as a str."""
    return s.encode("utf-16-le", errors="surrogatepass")[: units * 2].decode("utf-16-le", errors="ignore")


def utf16_offset(s: str, byte_offset: int) -> int:
    """A UTF-8 byte offset into s (the protocol's) as UTF-16 units (Qt's)."""
    return _utf16_len(s.encode("utf-8", errors="surrogatepass")[: max(0, byte_offset)].decode("utf-8", errors="ignore"))


def crop_surrounding(text: str, cursor: int, anchor: int) -> tuple[str, int, int]:
    """The text around the cursor, at most SURROUNDING_MAX bytes, with the
    cursor and anchor (UTF-16 positions in) as byte offsets into it (out)."""
    lo, hi = sorted((cursor, anchor))
    head = _from_utf16(text, lo)  # before the selection
    selection = _from_utf16(text, hi)[len(head) :]
    tail = text[len(head) + len(selection) :]
    if _utf8_len(selection) > SURROUNDING_MAX:  # too long to send: just the cursor's side of it
        selection = ""
    room = SURROUNDING_MAX - _utf8_len(selection)
    while _utf8_len(head) + _utf8_len(tail) > room:  # trim the far ends, keeping what's near the cursor
        if len(head) >= len(tail):
            head = head[1:]
        else:
            tail = tail[:-1]
    start, end = _utf8_len(head), _utf8_len(head) + _utf8_len(selection)
    return head + selection + tail, *((start, end) if cursor <= anchor else (end, start))


def delete_lengths(sent: tuple | None, before: int, after: int) -> tuple[int, int]:
    """Bytes to delete around the cursor, as UTF-16 units, using the text we sent."""
    if not sent or not (before or after):
        return 0, 0
    data, cursor = sent[0].encode("utf-8", errors="surrogatepass"), sent[1]
    gone_before = data[max(0, cursor - before) : cursor].decode("utf-8", errors="ignore")
    gone_after = data[cursor : cursor + after].decode("utf-8", errors="ignore")
    return _utf16_len(gone_before), _utf16_len(gone_after)


class LayerSurface(QObject):
    """The stage's surface on Wayland (penguin.Stage drives it)."""

    # Everything is drawn on the overlay: an XWayland window would be under it,
    # get the compositor's borders, and not get the keyboard when it asks.
    draws_menus = True
    hosts_windows = True

    def __init__(self, stage, conn: Connection):
        super().__init__()
        self.stage = stage
        self.conn = conn
        self.globals: dict[str, tuple[int, int]] = {}  # interface: (object id, version)
        self.outputs: dict[int, Output] = {}  # registry name: output
        self.pointers: dict[int, tuple[int, int | None]] = {}  # seat id: (pointer id, cursor shape device id)
        self.keyboards: dict[int, int] = {}  # seat id: keyboard id
        self.text_inputs: dict[int, TextInput] = {}  # seat id: its text input
        self._input_serial = 0  # the latest input event's serial: setting a selection needs one
        self.selections = {
            "clipboard": Selection(self, CLIPBOARD),
            "primary": Selection(self, PRIMARY),
        }
        self._text_state: TextState | None = None  # the focused text field, as the stage last said
        self._seat_versions: dict[int, int] = {}
        self._registry = conn.new_id(self._registry_event)
        conn.request(DISPLAY_ID, 1, "n", self._registry)  # wl_display.get_registry
        self._surface = self._layer = self._viewport = self._fractional = None
        self._output: Output | None = None
        self._qt_origin = QPointF()  # top-left, in Qt's coordinates, of the screen the surface is on
        self._qt_width = 1
        self._size: tuple[int, int] | None = None  # logical size, once configured
        self._preferred_int = 0  # wl_surface.preferred_buffer_scale
        self._preferred_120 = 0  # wp_fractional_scale, in 120ths
        self._buffers: list[Buffer] = []
        self._pending = QRegion()  # changed since the last commit
        self._frame_pending = False
        self._input: tuple | None = None
        self._input_dirty = False
        self._held = 0  # pointer buttons down on the stage
        self._pointer_on = False
        self._last = (0.0, 0.0)  # where the pointer is, surface-local
        self._screen_later: tuple[QScreen, QRect] | None = None
        self._cursor = "default"
        self._enter_serial = 0
        self._xkb_lib = None
        self._keyboard: xkb.Keyboard | None = None
        self._kb_focus = False  # whether the keyboard is ours
        self._kb_wanted = False  # whether the stage wants it (the ask box is open)
        self._kb_grab = False
        self._kb_mode = KEYBOARD_NONE
        self._repeat_rate, self._repeat_delay = REPEAT_RATE, REPEAT_DELAY
        self._repeat_key: tuple[int, xkb.Key] | None = None
        self._repeat_timer = QTimer(self)
        self._repeat_timer.timeout.connect(self._repeat)
        self._last_scale = 0.0
        self._closing = False
        self._notifier: QSocketNotifier | None = None
        self._write_notifier: QSocketNotifier | None = None
        self._present_timer = QTimer(self)
        self._present_timer.setSingleShot(True)
        self._present_timer.timeout.connect(self._present)

    @classmethod
    def create(cls, stage) -> LayerSurface | None:
        """A layer surface for the stage, or None if this compositor can't."""
        conn = Connection.open()
        if conn is None:
            return None
        surface = cls(stage, conn)
        # Two round trips: the globals, then what the bound outputs and seats say about themselves.
        if not (conn.roundtrip() and conn.roundtrip()) or not surface.usable():
            conn.close()
            return None
        surface._start()
        return surface

    def usable(self) -> bool:
        return all(name in self.globals and self.globals[name][1] >= version for name, version in NEEDED.items())

    def _start(self) -> None:
        self._add_text_inputs()
        for selection in self.selections.values():
            selection.add_devices()
        self._notifier = QSocketNotifier(self.conn.fileno(), QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._readable)
        self._write_notifier = QSocketNotifier(self.conn.fileno(), QSocketNotifier.Type.Write, self)
        self._write_notifier.setEnabled(False)
        self._write_notifier.activated.connect(self._flush)

    # -- what the stage uses

    def set_screen(self, screen: QScreen, geometry: QRect) -> None:
        if self._held:  # moving the surface would drop the drag; move it on release
            self._screen_later = (screen, QRect(geometry))
            return
        self._screen_later = None
        output = self._output_for(screen)
        origin, width = QPointF(geometry.topLeft()), max(1, geometry.width())
        if self._surface is not None and output is self._output and origin == self._qt_origin and width == self._qt_width:
            return
        self._qt_origin, self._qt_width = origin, width
        self._output = output
        _debug(f"surface for screen {screen.name()} {geometry} on output {output.name if output else None}")
        self._destroy_surface()
        self._create_surface()

    def damage(self, region: QRegion) -> None:
        for buf in self._buffers:
            buf.stale = buf.stale.united(region)
        self._pending = self._pending.united(region)
        self._schedule()

    def set_input(self, rects: list[QRect]) -> None:
        key = tuple((r.x(), r.y(), r.width(), r.height()) for r in rects)
        if key != self._input:
            self._input = key
            self._input_dirty = True
            self._schedule()

    def follow_pointer(self, hit) -> None:
        pass  # the compositor sends us only what lands in the input region

    def device_scale(self) -> float:
        """Device pixels per stage pixel, for drawing sprites at full resolution."""
        return self._scale() * self._k() if self._size else 0.0

    def set_cursor(self, shape: str) -> None:
        """The pointer's shape over the stage: "default", "pointer", "text"..."""
        if shape != self._cursor:
            self._cursor = shape
            if self._pointer_on:
                self._set_cursor(self._enter_serial)

    # The clipboard and the primary selection (middle-click paste): Qt's own
    # can't be used for what's on the overlay. Through XWayland they're X
    # selections, which the compositor only syncs while an X window has the
    # keyboard; natively, the compositor gives them only to the connection with
    # the keyboard, ours here, not Qt's.

    def clipboard_has_text(self, which: str = "clipboard") -> bool:
        return self.selections[which].has_text()

    def paste(self, then, which: str = "clipboard") -> None:
        """Read the clipboard's (or primary selection's) text; hand it to `then`."""
        self.selections[which].paste(then)

    def copy(self, text: str, which: str = "clipboard") -> None:
        """Put text on the clipboard (or primary selection), for any app to paste."""
        self.selections[which].copy(text)
        self._flush()

    def set_text_input(self, state: TextState | None) -> None:
        """The text field that has the focus on the stage (None: none does),
        for input methods: what's around the cursor and where the cursor is."""
        self._text_state = state
        for ti in self.text_inputs.values():
            self._send_text_state(ti)
        self._flush()

    def focus_keyboard(self, on: bool, grab: bool = True) -> None:
        """Let the overlay have the keyboard while the ask box is open, or not.

        `grab` takes it now: `exclusive`, until the keyboard has arrived and
        the pointer is on the overlay, then `on_demand`, so your desktop's own
        focus rules (click, or follow the mouse) take over from there. Hand
        over any sooner and a compositor that refocuses on the change (as
        Hyprland does) gives the keyboard to whatever is under the pointer,
        say a terminal, when you opened the box from the tray. Without `grab`
        it's `on_demand` from the start: the box gets the keyboard when you
        click it.
        """
        self._kb_wanted = on
        self._kb_grab = on and grab
        on_demand = self.globals["zwlr_layer_shell_v1"][1] >= 4
        if not on:
            self._stop_repeat()
            mode = KEYBOARD_NONE
        elif on_demand and (not grab or (self._kb_focus and self._pointer_inside())):
            mode = KEYBOARD_ON_DEMAND
        else:
            mode = KEYBOARD_EXCLUSIVE  # also all an older layer shell has
        self._set_keyboard_mode(mode)

    def _maybe_on_demand(self) -> None:
        """While grabbing: hand over to on_demand once that keeps the keyboard here."""
        if self._kb_wanted and self._kb_mode == KEYBOARD_EXCLUSIVE and self._kb_focus and self._pointer_inside():
            self.focus_keyboard(True, self._kb_grab)

    def _pointer_inside(self) -> bool:
        """Whether the pointer is on something of ours (the input region), not
        just on the surface: the penguin may have walked out from under it."""
        if not self._pointer_on or not self._input:
            return False
        local, _ = self._local(*self._last)
        return any(x <= local.x() < x + w and y <= local.y() < y + h for x, y, w, h in self._input)

    def close(self) -> None:
        self._closing = True
        self._present_timer.stop()
        self._stop_repeat()
        self._destroy_surface()
        for _pointer, device in self.pointers.values():
            if device is not None:
                self.conn.request(device, CURSOR_DEVICE_DESTROY)
        if self._keyboard is not None:
            self._keyboard.close()
            self._keyboard = None
        self.conn.flush()
        for notifier in (self._notifier, self._write_notifier):
            if notifier is not None:
                notifier.setEnabled(False)
        self.conn.close()

    # -- the connection

    def _readable(self) -> None:
        if not self.conn.read():
            self._lost()
            return
        self._flush()

    def _flush(self) -> None:
        done = self.conn.flush()
        if self.conn.closed:
            self._lost()
        elif self._write_notifier is not None:
            self._write_notifier.setEnabled(not done)

    def _lost(self) -> None:
        if self._closing:
            return
        self._closing = True
        for notifier in (self._notifier, self._write_notifier):
            if notifier is not None:
                notifier.setEnabled(False)
        # Without the compositor there's no screen to be on; say why rather than linger unseen.
        print(f"penguin-companion: lost the Wayland connection ({self.conn.error or 'closed'}); quitting.", file=sys.stderr)
        QGuiApplication.quit()

    # -- globals

    def _registry_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_REGISTRY_GLOBAL:
            name, interface, version = decode("usu", args)
            if interface not in WANTED:
                return
            use = min(version, WANTED[interface])
            oid = self.conn.new_id()
            self.conn.request(self._registry, REGISTRY_BIND, "usun", name, interface, use, oid)
            if interface == "wl_output":
                output = Output(oid, use)
                self.outputs[name] = output
                self.conn.listen(oid, lambda op, a, o=output: self._output_event(o, op, a))
            elif interface == "wl_seat":
                self._seat_versions[oid] = use
                self.conn.listen(oid, lambda op, a, s=oid: self._seat_event(s, op, a))
                if self._notifier is not None:  # a seat that came later
                    self._add_text_inputs()
                    for selection in self.selections.values():
                        selection.add_devices()
            elif interface not in self.globals:
                self.globals[interface] = (oid, use)
        elif opcode == EV_REGISTRY_GLOBAL_REMOVE:
            (name,) = decode("u", args)
            output = self.outputs.pop(name, None)
            if output is not None:
                if output.version >= 3:
                    self.conn.request(output.id, OUTPUT_RELEASE)
                self.conn.forget(output.id)
                # A layer surface on it gets `closed`, and comes back on another screen.

    def _output_event(self, output: Output, opcode: int, args: bytes) -> None:
        if opcode == EV_OUTPUT_GEOMETRY:
            output.x, output.y = decode("ii", args[:8])
        elif opcode == EV_OUTPUT_SCALE:
            (output.scale,) = decode("i", args)
            if output is self._output:
                self._rescale()
        elif opcode == EV_OUTPUT_NAME:
            (output.name,) = decode("s", args)

    def _output_for(self, screen: QScreen) -> Output | None:
        outputs = list(self.outputs.values())
        for output in outputs:
            if output.name and output.name == screen.name():
                return output
        if len(outputs) == 1:
            return outputs[0]
        geo = screen.geometry()
        for output in outputs:
            if (output.x, output.y) == (geo.x(), geo.y()):
                return output
        return None  # the compositor picks one

    # -- the pointer

    def _seat_event(self, seat: int, opcode: int, args: bytes) -> None:
        if opcode != EV_SEAT_CAPABILITIES:
            return
        (caps,) = decode("u", args)
        if caps & CAP_KEYBOARD and seat not in self.keyboards:
            keyboard = self.conn.new_id(self._keyboard_event)
            self.conn.request(seat, SEAT_GET_KEYBOARD, "n", keyboard)
            self.keyboards[seat] = keyboard
        elif not caps & CAP_KEYBOARD and seat in self.keyboards:
            keyboard = self.keyboards.pop(seat)
            if self._seat_versions.get(seat, 1) >= 3:
                self.conn.request(keyboard, KEYBOARD_RELEASE)
            self.conn.forget(keyboard)
        has = seat in self.pointers
        if caps & CAP_POINTER and not has:
            pointer = self.conn.new_id(self._pointer_event)
            self.conn.request(seat, SEAT_GET_POINTER, "n", pointer)
            device = None
            if "wp_cursor_shape_manager_v1" in self.globals:
                device = self.conn.new_id()
                self.conn.request(self.globals["wp_cursor_shape_manager_v1"][0], CURSOR_SHAPE_GET_POINTER, "no", device, pointer)
            self.pointers[seat] = (pointer, device)
        elif not caps & CAP_POINTER and has:
            pointer, device = self.pointers.pop(seat)
            if device is not None:
                self.conn.request(device, CURSOR_DEVICE_DESTROY)
            if self._seat_versions.get(seat, 1) >= 3:
                self.conn.request(pointer, POINTER_RELEASE)
            self.conn.forget(pointer)

    def _local(self, x: float, y: float) -> tuple[QPointF, QPointF]:
        k = self._k()
        local = QPointF(x / k, y / k)
        return local, self._qt_origin + local

    def _pointer_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_POINTER_ENTER:
            serial, surface, x, y = decode("uoff", args)
            self._pointer_on = surface == self._surface
            if not self._pointer_on:
                return
            self._last = (x, y)
            self._enter_serial = self._input_serial = serial
            self.stage.move(*self._local(x, y))
            self._set_cursor(serial)
            self._maybe_on_demand()
        elif opcode == EV_POINTER_LEAVE:
            self._pointer_on = False
            if not self._held:
                self.stage.pointer_left()
        elif opcode == EV_POINTER_MOTION and (self._pointer_on or self._held):
            _time, x, y = decode("uff", args)
            self._last = (x, y)
            self.stage.move(*self._local(x, y))
            self._maybe_on_demand()
        elif opcode == EV_POINTER_BUTTON and (self._pointer_on or self._held):
            serial, _time, button, state = decode("uuuu", args)
            self._input_serial = serial
            qt_button = {BTN_LEFT: Qt.MouseButton.LeftButton, BTN_RIGHT: Qt.MouseButton.RightButton, BTN_MIDDLE: Qt.MouseButton.MiddleButton}.get(button)
            if qt_button is None:
                return
            local, gpos = self._local(*self._last)
            if state == 1:
                self._held += 1
                self.stage.press(local, gpos, qt_button)
            else:
                self._held = max(0, self._held - 1)
                self.stage.release(local, gpos, qt_button)
                if not self._held and self._screen_later is not None:
                    self.set_screen(*self._screen_later)
        elif opcode == EV_POINTER_AXIS and self._pointer_on:
            _time, axis, value = decode("uuf", args)
            dx, dy = (0, value) if axis == AXIS_VERTICAL else (value, 0)
            self.stage.wheel(*self._local(*self._last), round(-dx * WHEEL_PER_PIXEL), round(-dy * WHEEL_PER_PIXEL))

    def _set_cursor(self, serial: int) -> None:
        shape = CURSOR_SHAPES.get(self._cursor, CURSOR_SHAPES["default"])
        for _pointer, device in self.pointers.values():
            if device is not None:
                self.conn.request(device, CURSOR_DEVICE_SET_SHAPE, "uu", serial, shape)
        self._flush()

    # -- the keyboard

    def _keyboard_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_KEYBOARD_KEYMAP:
            fmt, size = decode("uhu", args)
            fd = self.conn.take_fd()
            try:
                if fmt == KEYMAP_XKB_V1:
                    with mmap.mmap(fd, size, mmap.MAP_PRIVATE, mmap.PROT_READ) as m:
                        text = m[:size].rstrip(b"\0").decode("utf-8", errors="replace")
                    self._set_keymap(text)
            finally:
                os.close(fd)
        elif opcode == EV_KEYBOARD_ENTER:
            serial, surface = decode("uo", args[:8])
            _debug(f"keyboard enter (ours: {surface == self._surface})")
            if surface == self._surface:
                self._input_serial = serial
            if surface == self._surface:
                self._kb_focus = True
                self.stage.keyboard_focus(True)
                self._maybe_on_demand()
        elif opcode == EV_KEYBOARD_LEAVE:
            _debug("keyboard leave")
            if self._kb_focus:
                self._kb_focus = False
                self._stop_repeat()
                self.stage.keyboard_focus(False)
        elif opcode == EV_KEYBOARD_MODIFIERS:
            _serial, depressed, latched, locked, group = decode("uuuuu", args)
            if self._keyboard is not None:
                self._keyboard.set_modifiers(depressed, latched, locked, group)
        elif opcode == EV_KEYBOARD_REPEAT_INFO:
            self._repeat_rate, self._repeat_delay = decode("ii", args)
        elif opcode == EV_KEYBOARD_KEY and self._kb_focus and self._keyboard is not None:
            serial, _time, code, state = decode("uuuu", args)
            self._input_serial = serial
            if state == 1:
                key = self._keyboard.press(code)
                self._stop_repeat()
                if key is not None:
                    self.stage.key(key, True, False)
                    if self._repeat_rate > 0 and self._keyboard.repeats(code):
                        self._repeat_key = (code, key)
                        self._repeat_timer.start(max(1, self._repeat_delay))
            else:
                if self._repeat_key is not None and self._repeat_key[0] == code:
                    self._stop_repeat()
                self.stage.key(self._keyboard.release(code), False, False)

    def _set_keymap(self, text: str) -> None:
        if self._xkb_lib is None:
            self._xkb_lib = xkb.library()
        if self._xkb_lib is None:
            print("penguin-companion: libxkbcommon not found; can't type in the ask box.", file=sys.stderr)
            return
        if self._keyboard is not None:
            self._keyboard.close()
        try:
            self._keyboard = xkb.Keyboard(self._xkb_lib, text)
        except ValueError as exc:
            self._keyboard = None
            print(f"penguin-companion: {exc}", file=sys.stderr)

    def _repeat(self) -> None:
        if self._repeat_key is None or not self._kb_focus:
            self._stop_repeat()
            return
        self.stage.key(self._repeat_key[1], True, True)
        self._repeat_timer.start(max(1, 1000 // self._repeat_rate))

    def _stop_repeat(self) -> None:
        self._repeat_key = None
        self._repeat_timer.stop()

    def _set_keyboard_mode(self, mode: int) -> None:
        _debug(f"keyboard interactivity {self._kb_mode} -> {mode} (focus={self._kb_focus}, pointer_on={self._pointer_on})")
        if mode == self._kb_mode or self._layer is None:
            self._kb_mode = mode
            return
        self._kb_mode = mode
        self.conn.request(self._layer, LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY, "u", mode)
        self.conn.request(self._surface, SURFACE_COMMIT)
        self._flush()


    # -- input methods (text-input-unstable-v3)

    def _add_text_inputs(self) -> None:
        manager = self.globals.get("zwp_text_input_manager_v3")
        if manager is None:
            return
        for seat in self._seat_versions:
            if seat not in self.text_inputs:
                ti = TextInput(self.conn.new_id())
                self.conn.listen(ti.id, lambda op, a, t=ti: self._text_input_event(t, op, a))
                self.conn.request(manager[0], TEXT_INPUT_MANAGER_GET, "no", ti.id, seat)
                self.text_inputs[seat] = ti

    def _send_text_state(self, ti: TextInput) -> None:
        """Enable, update or disable a text input to match the focused field."""
        if not ti.entered:
            return
        state = self._text_state
        c = self.conn
        if state is None:
            if ti.enabled:
                ti.enabled, ti.sent = False, None
                c.request(ti.id, TI_DISABLE)
                self._ti_commit(ti)
            return
        sent = self._wire_state(state)
        if ti.enabled and sent == ti.sent:
            return
        _debug(f"text input {'update' if ti.enabled else 'enable'}: {sent}")
        if not ti.enabled:
            ti.enabled = True
            c.request(ti.id, TI_ENABLE)
            c.request(ti.id, TI_SET_CONTENT_TYPE, "uu", 0, 0)  # normal text
        text, cursor, anchor, rect = sent
        c.request(ti.id, TI_SET_SURROUNDING_TEXT, "sii", text, cursor, anchor)
        c.request(ti.id, TI_SET_CURSOR_RECTANGLE, "iiii", *rect)
        ti.sent = sent
        self._ti_commit(ti)

    def _ti_commit(self, ti: TextInput) -> None:
        self.conn.request(ti.id, TI_COMMIT)
        ti.commits += 1

    def _wire_state(self, state: TextState) -> tuple[str, int, int, tuple[int, int, int, int]]:
        """The field as the protocol has it: UTF-8 byte offsets, at most
        SURROUNDING_MAX bytes around the cursor, the cursor in surface pixels."""
        text, cursor, anchor = crop_surrounding(state.text, state.cursor, state.anchor)
        k = self._k()
        r = state.rect
        rect = (math.floor(r.x() * k), math.floor(r.y() * k), max(1, math.ceil(r.width() * k)), max(1, math.ceil(r.height() * k)))
        return text, cursor, anchor, rect

    def _text_input_event(self, ti: TextInput, opcode: int, args: bytes) -> None:
        _debug(f"text input event {opcode} {args[:40]!r}")
        if opcode == EV_TI_ENTER:
            (surface,) = decode("o", args)
            ti.entered = surface == self._surface
            ti.enabled, ti.sent = False, None
            self._send_text_state(ti)
            self._flush()
        elif opcode == EV_TI_LEAVE:
            ti.entered = ti.enabled = False
            ti.sent, ti.pending = None, PendingIM()
            self.stage.input_method("", None, "", 0, 0)  # drop any half-typed text
        elif opcode == EV_TI_PREEDIT:
            text, begin, end = decode("sii", args)
            ti.pending.preedit, ti.pending.cursor = text or "", (begin, end)
        elif opcode == EV_TI_COMMIT_STRING:
            (text,) = decode("s", args)
            ti.pending.commit = text or ""
        elif opcode == EV_TI_DELETE_SURROUNDING:
            ti.pending.before, ti.pending.after = decode("uu", args)
        elif opcode == EV_TI_DONE:
            pending, ti.pending = ti.pending, PendingIM()
            if not ti.entered:
                return
            before, after = delete_lengths(ti.sent, pending.before, pending.after)
            preedit, cursor = pending.preedit, None
            if pending.cursor != (-1, -1):  # -1, -1: hide the cursor
                cursor = (utf16_offset(preedit, pending.cursor[0]), utf16_offset(preedit, pending.cursor[1]))
            self.stage.input_method(preedit, cursor, pending.commit, before, after)

    # -- the surface

    def _create_surface(self) -> None:
        c = self.conn
        compositor = self.globals["wl_compositor"][0]
        self._surface = c.new_id(self._surface_event)
        c.request(compositor, COMPOSITOR_CREATE_SURFACE, "n", self._surface)
        if "wp_viewporter" in self.globals and "wp_fractional_scale_manager_v1" in self.globals:
            self._viewport = c.new_id()
            c.request(self.globals["wp_viewporter"][0], VIEWPORTER_GET_VIEWPORT, "no", self._viewport, self._surface)
            self._fractional = c.new_id(self._fractional_event)
            c.request(self.globals["wp_fractional_scale_manager_v1"][0], FRACTIONAL_GET, "no", self._fractional, self._surface)
        self._layer = c.new_id(self._layer_event)
        output = self._output.id if self._output is not None else None
        c.request(self.globals["zwlr_layer_shell_v1"][0], LAYER_SHELL_GET_LAYER_SURFACE, "noous", self._layer, self._surface, output, LAYER_OVERLAY, NAMESPACE)
        c.request(self._layer, LAYER_SURFACE_SET_SIZE, "uu", 0, 0)  # the whole output, from the anchors
        c.request(self._layer, LAYER_SURFACE_SET_ANCHOR, "u", ANCHOR_ALL)
        c.request(self._layer, LAYER_SURFACE_SET_EXCLUSIVE_ZONE, "i", -1)  # over panels too, not pushed aside by them
        c.request(self._layer, LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY, "u", self._kb_mode)
        self._send_input([])  # take no clicks until the penguin is drawn
        self._input_dirty = self._input is not None
        c.request(self._surface, SURFACE_COMMIT)
        self._flush()

    def _destroy_surface(self) -> None:
        c = self.conn
        for buf in self._buffers:
            buf.destroy()
        self._buffers = []
        if self._viewport is not None:
            c.request(self._viewport, VIEWPORT_DESTROY)
        if self._fractional is not None:
            c.request(self._fractional, FRACTIONAL_DESTROY)
            c.forget(self._fractional)
        if self._layer is not None:
            c.request(self._layer, LAYER_SURFACE_DESTROY)
            c.forget(self._layer)
        if self._surface is not None:
            c.request(self._surface, SURFACE_DESTROY)
            c.forget(self._surface)
        self._surface = self._layer = self._viewport = self._fractional = None
        self._size = None
        self._frame_pending = False
        self._preferred_int = self._preferred_120 = 0

    def _layer_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_LAYER_SURFACE_CONFIGURE:
            serial, width, height = decode("uuu", args)
            _debug(f"configure {width}x{height}")
            self.conn.request(self._layer, LAYER_SURFACE_ACK_CONFIGURE, "u", serial)
            if (width, height) != self._size:
                self._size = (width, height)
                self._rescale()
            else:
                self._schedule()
        elif opcode == EV_LAYER_SURFACE_CLOSED:
            _debug("closed by the compositor")
            # Its screen went away: start again wherever the stage is now.
            self._destroy_surface()
            if not self._closing:
                QTimer.singleShot(0, self._recreate)

    def _recreate(self) -> None:
        if self._closing or self._surface is not None:
            return
        self._output = self._output_for(self.stage.screen()) if self.stage.screen() is not None else None
        self._create_surface()

    def _surface_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_SURFACE_PREFERRED_BUFFER_SCALE:
            (self._preferred_int,) = decode("i", args)
            self._rescale()

    def _fractional_event(self, opcode: int, args: bytes) -> None:
        if opcode == EV_FRACTIONAL_PREFERRED_SCALE:
            (self._preferred_120,) = decode("u", args)
            self._rescale()

    def _scale(self) -> float:
        if self._viewport is not None and self._preferred_120:
            return self._preferred_120 / 120
        if self._preferred_int:
            return float(self._preferred_int)
        return float(self._output.scale if self._output is not None else 1)

    def _k(self) -> float:
        """Wayland's logical pixels per Qt pixel (1 unless XWayland is scaled differently)."""
        return self._size[0] / self._qt_width if self._size else 1.0

    def _buffer_size(self) -> tuple[int, int]:
        w, h = self._size
        s = self._scale()
        if self._viewport is not None:
            return max(1, round(w * s)), max(1, round(h * s))
        n = max(1, round(s))
        return w * n, h * n

    def _rescale(self) -> None:
        """New size or scale: new buffers, painted in full."""
        if self._size is None or self._surface is None:
            return
        for buf in self._buffers:
            buf.destroy()
        self._buffers = []
        if self._viewport is not None:
            self.conn.request(self._viewport, VIEWPORT_SET_DESTINATION, "ii", *self._size)
        else:
            self.conn.request(self._surface, SURFACE_SET_BUFFER_SCALE, "i", max(1, round(self._scale())))
        self._pending = QRegion(0, 0, self._qt_width, math.ceil(self._size[1] / self._k()))
        self._schedule()
        scale = self.device_scale()
        if scale != self._last_scale:
            self._last_scale = scale
            QTimer.singleShot(0, lambda: self.stage.scale_changed(scale))

    def _schedule(self) -> None:
        if not self._present_timer.isActive():
            self._present_timer.start(0)

    def _present(self) -> None:
        if self._closing or self._size is None or self._surface is None:
            return
        c = self.conn
        commit = False
        if self._input_dirty:
            self._send_input(self._input or ())
            self._input_dirty = False
            commit = True
        if not self._pending.isEmpty() and not self._frame_pending:
            buf = self._free_buffer()
            if buf is not None:
                self._paint(buf)
                c.request(self._surface, SURFACE_ATTACH, "oii", buf.id, 0, 0)
                for r in self._to_buffer(self._pending, buf):
                    c.request(self._surface, SURFACE_DAMAGE_BUFFER, "iiii", r.x(), r.y(), r.width(), r.height())
                buf.busy = True
                self._pending = QRegion()
                callback = c.new_id(self._frame_done)
                c.request(self._surface, SURFACE_FRAME, "n", callback)
                self._frame_pending = True
                commit = True
        if commit:
            c.request(self._surface, SURFACE_COMMIT)
        self._flush()

    def _frame_done(self, _opcode: int, _args: bytes) -> None:
        self._frame_pending = False
        if not self._pending.isEmpty():
            self._schedule()

    def _released(self, buf: Buffer) -> None:
        buf.busy = False
        if not self._pending.isEmpty():
            self._schedule()

    def _free_buffer(self) -> Buffer | None:
        for buf in self._buffers:
            if not buf.busy:
                return buf
        if len(self._buffers) >= MAX_BUFFERS:
            return None  # one comes back with wl_buffer.release
        w, h = self._buffer_size()
        buf = Buffer(self.conn, self.globals["wl_shm"][0], w, h, self._released)
        buf.stale = QRegion(0, 0, self._qt_width, math.ceil(h / self._dpr(buf)))
        self._buffers.append(buf)
        return buf

    def _dpr(self, buf: Buffer) -> float:
        return buf.width / self._qt_width

    def _paint(self, buf: Buffer) -> None:
        if buf.stale.isEmpty():
            return
        buf.image.setDevicePixelRatio(self._dpr(buf))
        p = QPainter(buf.image)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setClipRegion(buf.stale)
        self.stage.paint(p, buf.stale)
        p.end()
        buf.stale = QRegion()

    def _to_buffer(self, region: QRegion, buf: Buffer) -> list[QRect]:
        """Buffer pixels to damage. PyQt6 can't list a region's rectangles, so
        its bounding box: the penguin and its bubble are next to each other."""
        r, d = region.boundingRect(), self._dpr(buf)
        x0, y0 = math.floor(r.x() * d), math.floor(r.y() * d)
        x1, y1 = math.ceil((r.x() + r.width()) * d), math.ceil((r.y() + r.height()) * d)
        return [QRect(x0, y0, x1 - x0, y1 - y0)]

    def _send_input(self, rects) -> None:
        c = self.conn
        region = c.new_id()
        c.request(self.globals["wl_compositor"][0], COMPOSITOR_CREATE_REGION, "n", region)
        k = self._k()
        for x, y, w, h in rects:
            x0, y0 = math.floor(x * k), math.floor(y * k)
            c.request(region, REGION_ADD, "iiii", x0, y0, math.ceil((x + w) * k) - x0, math.ceil((y + h) * k) - y0)
        c.request(self._surface, SURFACE_SET_INPUT_REGION, "o", region)
        c.request(region, REGION_DESTROY)
