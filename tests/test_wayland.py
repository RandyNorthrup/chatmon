"""The stage's Wayland overlay: the wire format, the opcodes, and a layer
surface talking to a pretend compositor over a socket pair."""

import array
import mmap
import os
import socket
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QRegion  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from penguin_companion import layer, wayland  # noqa: E402

linux_only = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Wayland is Linux only")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_encode_and_decode_round_trip():
    data, fds = wayland.encode(7, 3, "iufsoa", [-5, 9, 1.5, "hi", 0, b"\x01\x02\x03"])
    oid, word = struct.unpack_from("<II", data)
    assert (oid, word & 0xFFFF, word >> 16) == (7, 3, len(data))
    assert len(data) % 4 == 0 and fds == []
    assert wayland.decode("iufsoa", data[8:]) == [-5, 9, 1.5, "hi", 0, b"\x01\x02\x03"]


def test_strings_are_nul_terminated_and_padded():
    data, _ = wayland.encode(1, 0, "s", ["abc"])  # 3 bytes + NUL fills one word
    assert data[8:] == struct.pack("<I", 4) + b"abc\0"
    data, _ = wayland.encode(1, 0, "s", [None])
    assert data[8:] == struct.pack("<I", 0)


def test_file_descriptors_travel_beside_the_bytes():
    data, fds = wayland.encode(2, 0, "nhi", [5, 42, 100])
    assert fds == [42] and len(data) == 8 + 8  # the fd takes no room in the message


def test_socket_path(tmp_path):
    assert wayland.socket_path({}) is None
    assert wayland.socket_path({"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": "/run/user/5"}) == "/run/user/5/wayland-1"
    assert wayland.socket_path({"WAYLAND_DISPLAY": "/tmp/w"}) == "/tmp/w"


# -- the opcodes in layer.py, checked against the protocol files where they're installed

PROTOCOLS = [
    Path("/usr/share/wayland/wayland.xml"),
    Path("/usr/share/wayland-protocols/stable/viewporter/viewporter.xml"),
    Path("/usr/share/wayland-protocols/staging/cursor-shape/cursor-shape-v1.xml"),
    Path("/usr/share/wayland-protocols/staging/fractional-scale/fractional-scale-v1.xml"),
    Path("/usr/share/wlr-protocols/unstable/wlr-layer-shell-unstable-v1.xml"),
]

CHECKS = {  # constant: (interface, "request" or "event", name)
    "REGISTRY_BIND": ("wl_registry", "request", "bind"),
    "EV_REGISTRY_GLOBAL": ("wl_registry", "event", "global"),
    "EV_REGISTRY_GLOBAL_REMOVE": ("wl_registry", "event", "global_remove"),
    "COMPOSITOR_CREATE_SURFACE": ("wl_compositor", "request", "create_surface"),
    "COMPOSITOR_CREATE_REGION": ("wl_compositor", "request", "create_region"),
    "SHM_CREATE_POOL": ("wl_shm", "request", "create_pool"),
    "SHM_POOL_CREATE_BUFFER": ("wl_shm_pool", "request", "create_buffer"),
    "SHM_POOL_DESTROY": ("wl_shm_pool", "request", "destroy"),
    "BUFFER_DESTROY": ("wl_buffer", "request", "destroy"),
    "EV_BUFFER_RELEASE": ("wl_buffer", "event", "release"),
    "SURFACE_DESTROY": ("wl_surface", "request", "destroy"),
    "SURFACE_ATTACH": ("wl_surface", "request", "attach"),
    "SURFACE_FRAME": ("wl_surface", "request", "frame"),
    "SURFACE_SET_INPUT_REGION": ("wl_surface", "request", "set_input_region"),
    "SURFACE_COMMIT": ("wl_surface", "request", "commit"),
    "SURFACE_SET_BUFFER_SCALE": ("wl_surface", "request", "set_buffer_scale"),
    "SURFACE_DAMAGE_BUFFER": ("wl_surface", "request", "damage_buffer"),
    "EV_SURFACE_PREFERRED_BUFFER_SCALE": ("wl_surface", "event", "preferred_buffer_scale"),
    "REGION_DESTROY": ("wl_region", "request", "destroy"),
    "REGION_ADD": ("wl_region", "request", "add"),
    "SEAT_GET_POINTER": ("wl_seat", "request", "get_pointer"),
    "SEAT_RELEASE": ("wl_seat", "request", "release"),
    "EV_SEAT_CAPABILITIES": ("wl_seat", "event", "capabilities"),
    "POINTER_RELEASE": ("wl_pointer", "request", "release"),
    "EV_POINTER_ENTER": ("wl_pointer", "event", "enter"),
    "EV_POINTER_LEAVE": ("wl_pointer", "event", "leave"),
    "EV_POINTER_MOTION": ("wl_pointer", "event", "motion"),
    "EV_POINTER_BUTTON": ("wl_pointer", "event", "button"),
    "EV_POINTER_AXIS": ("wl_pointer", "event", "axis"),
    "SEAT_GET_KEYBOARD": ("wl_seat", "request", "get_keyboard"),
    "KEYBOARD_RELEASE": ("wl_keyboard", "request", "release"),
    "EV_KEYBOARD_KEYMAP": ("wl_keyboard", "event", "keymap"),
    "EV_KEYBOARD_ENTER": ("wl_keyboard", "event", "enter"),
    "EV_KEYBOARD_LEAVE": ("wl_keyboard", "event", "leave"),
    "EV_KEYBOARD_KEY": ("wl_keyboard", "event", "key"),
    "EV_KEYBOARD_MODIFIERS": ("wl_keyboard", "event", "modifiers"),
    "EV_KEYBOARD_REPEAT_INFO": ("wl_keyboard", "event", "repeat_info"),
    "OUTPUT_RELEASE": ("wl_output", "request", "release"),
    "EV_OUTPUT_GEOMETRY": ("wl_output", "event", "geometry"),
    "EV_OUTPUT_DONE": ("wl_output", "event", "done"),
    "EV_OUTPUT_SCALE": ("wl_output", "event", "scale"),
    "EV_OUTPUT_NAME": ("wl_output", "event", "name"),
    "VIEWPORTER_GET_VIEWPORT": ("wp_viewporter", "request", "get_viewport"),
    "VIEWPORT_DESTROY": ("wp_viewport", "request", "destroy"),
    "VIEWPORT_SET_DESTINATION": ("wp_viewport", "request", "set_destination"),
    "CURSOR_SHAPE_GET_POINTER": ("wp_cursor_shape_manager_v1", "request", "get_pointer"),
    "CURSOR_DEVICE_DESTROY": ("wp_cursor_shape_device_v1", "request", "destroy"),
    "CURSOR_DEVICE_SET_SHAPE": ("wp_cursor_shape_device_v1", "request", "set_shape"),
    "FRACTIONAL_GET": ("wp_fractional_scale_manager_v1", "request", "get_fractional_scale"),
    "FRACTIONAL_DESTROY": ("wp_fractional_scale_v1", "request", "destroy"),
    "EV_FRACTIONAL_PREFERRED_SCALE": ("wp_fractional_scale_v1", "event", "preferred_scale"),
    "LAYER_SHELL_GET_LAYER_SURFACE": ("zwlr_layer_shell_v1", "request", "get_layer_surface"),
    "LAYER_SURFACE_SET_SIZE": ("zwlr_layer_surface_v1", "request", "set_size"),
    "LAYER_SURFACE_SET_ANCHOR": ("zwlr_layer_surface_v1", "request", "set_anchor"),
    "LAYER_SURFACE_SET_EXCLUSIVE_ZONE": ("zwlr_layer_surface_v1", "request", "set_exclusive_zone"),
    "LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY": ("zwlr_layer_surface_v1", "request", "set_keyboard_interactivity"),
    "LAYER_SURFACE_ACK_CONFIGURE": ("zwlr_layer_surface_v1", "request", "ack_configure"),
    "LAYER_SURFACE_DESTROY": ("zwlr_layer_surface_v1", "request", "destroy"),
    "EV_LAYER_SURFACE_CONFIGURE": ("zwlr_layer_surface_v1", "event", "configure"),
    "EV_LAYER_SURFACE_CLOSED": ("zwlr_layer_surface_v1", "event", "closed"),
}


def _opcodes() -> dict:
    found = {}
    for path in PROTOCOLS:
        if not path.exists():
            continue
        for iface in ET.parse(path).getroot().iter("interface"):
            for kind in ("request", "event"):
                for i, message in enumerate(iface.iter(kind)):
                    found[(iface.get("name"), kind, message.get("name"))] = i
    return found


def test_opcodes_match_the_protocol_files():
    found = _opcodes()
    checked = 0
    for constant, key in CHECKS.items():
        if key in found:
            assert getattr(layer, constant) == found[key], f"{constant} should be {found[key]} ({key})"
            checked += 1
    if not checked:
        pytest.skip("no Wayland protocol files installed")


# -- a layer surface against a pretend compositor


class Server:
    """The compositor's end of the socket: reads requests, sends events."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buf = b""
        self.fds: list[int] = []

    def requests(self) -> list[tuple[int, int, bytes]]:
        self.sock.setblocking(False)
        while True:
            try:
                data, anc, _, _ = self.sock.recvmsg(1 << 20, socket.CMSG_SPACE(16 * 4))
            except BlockingIOError:
                break
            for level, kind, payload in anc:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    fds = array.array("i")
                    fds.frombytes(payload[: len(payload) - len(payload) % 4])
                    self.fds += list(fds)
            if not data:
                break
            self.buf += data
        out = []
        while len(self.buf) >= 8:
            oid, word = struct.unpack_from("<II", self.buf)
            size = word >> 16
            out.append((oid, word & 0xFFFF, self.buf[8:size]))
            self.buf = self.buf[size:]
        return out

    def send(self, oid: int, opcode: int, sig: str = "", *args) -> None:
        data, fds = wayland.encode(oid, opcode, sig, list(args))
        if fds:
            self.sock.sendmsg([data], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))])
        else:
            self.sock.sendall(data)


class FakeScreen:
    def name(self):
        return "eDP-1"


class FakeStage:
    def __init__(self):
        self.calls = []

    def paint(self, p, region):
        p.fillRect(QRect(10, 10, 50, 50), QColor(255, 0, 0))

    def press(self, pos, gpos, button):
        self.calls.append(("press", pos, gpos, button))
        return True

    def move(self, pos, gpos):
        self.calls.append(("move", pos, gpos))

    def release(self, pos, gpos, button):
        self.calls.append(("release", pos, gpos, button))

    def pointer_left(self):
        self.calls.append(("left",))

    def wheel(self, pos, gpos, dx, dy):
        self.calls.append(("wheel", dx, dy))

    def key(self, key, pressed, repeat):
        self.calls.append(("key", key.text, pressed))

    def keyboard_focus(self, on):
        self.calls.append(("keyboard", on))

    def scale_changed(self, scale):
        self.calls.append(("scale", scale))

    def screen(self):
        return FakeScreen()


def named(reqs, oid, opcode):
    return [payload for o, op, payload in reqs if o == oid and op == opcode]


@linux_only
def test_layer_surface_draws_and_takes_clicks_only_on_the_penguin(qapp):
    client, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    server = Server(server_sock)
    conn = wayland.Connection(client)
    stage = FakeStage()
    surf = layer.LayerSurface(stage, conn)
    conn.flush()

    (registry,) = [wayland.decode("n", p)[0] for o, op, p in server.requests() if o == wayland.DISPLAY_ID and op == 1]
    globals_ = [("wl_compositor", 6), ("wl_shm", 1), ("wl_seat", 7), ("wl_output", 4), ("zwlr_layer_shell_v1", 4), ("xdg_wm_base", 6)]
    for name, (interface, version) in enumerate(globals_, start=1):
        server.send(registry, layer.EV_REGISTRY_GLOBAL, "usu", name, interface, version)
    conn.read()
    conn.flush()
    bound = {}
    for _o, _op, payload in server.requests():
        _name, interface, version, oid = wayland.decode("usun", payload)
        bound[interface] = (oid, version)
    assert "xdg_wm_base" not in bound  # only what it uses
    assert bound["wl_compositor"][1] == 6 and bound["wl_seat"][1] == 5  # never newer than it speaks
    assert surf.usable()

    server.send(bound["wl_output"][0], layer.EV_OUTPUT_NAME, "s", "eDP-1")
    server.send(bound["wl_seat"][0], layer.EV_SEAT_CAPABILITIES, "u", layer.CAP_POINTER)
    conn.read()
    surf._start()
    surf.set_screen(FakeScreen(), QRect(0, 0, 1280, 800))
    conn.flush()
    reqs = server.requests()
    (pointer,) = [wayland.decode("n", p)[0] for p in named(reqs, bound["wl_seat"][0], layer.SEAT_GET_POINTER)]
    (get,) = named(reqs, bound["zwlr_layer_shell_v1"][0], layer.LAYER_SHELL_GET_LAYER_SURFACE)
    layer_id, surface_id, output, which, namespace = wayland.decode("noous", get)
    assert (output, which, namespace) == (bound["wl_output"][0], layer.LAYER_OVERLAY, "penguin-companion")
    assert named(reqs, layer_id, layer.LAYER_SURFACE_SET_ANCHOR) == [struct.pack("<I", 15)]
    assert named(reqs, layer_id, layer.LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY) == [struct.pack("<I", 0)]  # never the keyboard
    assert named(reqs, layer_id, layer.LAYER_SURFACE_SET_EXCLUSIVE_ZONE) == [struct.pack("<i", -1)]
    assert named(reqs, surface_id, layer.SURFACE_SET_INPUT_REGION)  # an empty one, before anything's drawn
    assert not [r for r in reqs if r[0] == surface_id and r[1] == layer.SURFACE_ATTACH]  # nothing before configure

    # Configured at 1280x800 on a scale-2 screen: draw a patch and make it the only clickable part.
    server.send(surface_id, layer.EV_SURFACE_PREFERRED_BUFFER_SCALE, "i", 2)
    server.send(layer_id, layer.EV_LAYER_SURFACE_CONFIGURE, "uuu", 7, 1280, 800)
    conn.read()
    surf.damage(QRegion(10, 10, 50, 50))
    surf.set_input([QRect(10, 10, 50, 50)])
    surf._present()
    reqs = server.requests()
    assert named(reqs, layer_id, layer.LAYER_SURFACE_ACK_CONFIGURE) == [struct.pack("<I", 7)]
    assert struct.pack("<i", 2) in named(reqs, surface_id, layer.SURFACE_SET_BUFFER_SCALE)
    (pool_req,) = named(reqs, bound["wl_shm"][0], layer.SHM_CREATE_POOL)
    _pool, size = wayland.decode("ni", pool_req)
    assert size == 2560 * 1600 * 4
    (buffer_req,) = [p for o, op, p in reqs if op == layer.SHM_POOL_CREATE_BUFFER and o == _pool]
    _buf, offset, w, h, stride, fmt = wayland.decode("niiiiu", buffer_req)
    assert (w, h, stride, fmt) == (2560, 1600, 2560 * 4, layer.SHM_ARGB8888)
    assert named(reqs, surface_id, layer.SURFACE_ATTACH)
    (damage,) = named(reqs, surface_id, layer.SURFACE_DAMAGE_BUFFER)
    assert wayland.decode("iiii", damage) == [0, 0, 2560, 1600]  # a new surface: all of it
    regions = {wayland.decode("n", p)[0] for p in named(reqs, bound["wl_compositor"][0], layer.COMPOSITOR_CREATE_REGION)}
    region_adds = [wayland.decode("iiii", p) for o, op, p in reqs if o in regions and op == layer.REGION_ADD]
    assert region_adds == [[10, 10, 50, 50]]  # the only part that takes clicks
    assert reqs[-1][:2] == (surface_id, layer.SURFACE_COMMIT)

    # The next change waits for the frame callback, then sends only what changed.
    (callback,) = [wayland.decode("n", p)[0] for p in named(reqs, surface_id, layer.SURFACE_FRAME)]
    surf.damage(QRegion(10, 10, 50, 50))
    surf._present()
    assert not named(server.requests(), surface_id, layer.SURFACE_COMMIT)
    server.send(callback, 0, "u", 0)  # wl_callback.done
    server.send(_buf, layer.EV_BUFFER_RELEASE)
    conn.read()
    surf._present()
    reqs = server.requests()
    assert not named(reqs, bound["wl_shm"][0], layer.SHM_CREATE_POOL)  # the released buffer is reused
    (damage,) = named(reqs, surface_id, layer.SURFACE_DAMAGE_BUFFER)
    assert wayland.decode("iiii", damage) == [20, 20, 100, 100]  # in buffer pixels

    # The pixels the compositor would show: red where the stage painted, clear elsewhere.
    pixels = mmap.mmap(server.fds[-1], size, prot=mmap.PROT_READ)
    b, g, r, a = pixels[(40 * 2560 + 40) * 4 : (40 * 2560 + 40) * 4 + 4]
    assert (r, g, b, a) == (255, 0, 0, 255)
    assert pixels[(400 * 2560 + 400) * 4 + 3] == 0
    pixels.close()

    # A click on the penguin, in surface coordinates, reaches the stage.
    server.send(pointer, layer.EV_POINTER_ENTER, "uoff", 11, surface_id, 30.0, 30.5)
    server.send(pointer, layer.EV_POINTER_BUTTON, "uuuu", 12, 0, layer.BTN_LEFT, 1)
    server.send(pointer, layer.EV_POINTER_BUTTON, "uuuu", 13, 0, layer.BTN_LEFT, 0)
    server.send(pointer, layer.EV_POINTER_LEAVE, "uo", 14, surface_id)
    conn.read()
    kinds = [c[0] for c in stage.calls]
    assert kinds[:4] == ["move", "press", "release", "left"]
    _, pos, gpos, button = stage.calls[1]
    assert pos == QPointF(30.0, 30.5) and gpos == QPointF(30.0, 30.5) and button == Qt.MouseButton.LeftButton

    surf.close()
    for fd in server.fds:
        os.close(fd)
    server_sock.close()


@linux_only
def test_a_protocol_error_closes_the_connection():
    client, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    conn = wayland.Connection(client)
    Server(server_sock).send(wayland.DISPLAY_ID, 0, "ous", 5, 1, "bad request")
    assert conn.read() is False
    assert "bad request" in conn.error
    conn.close()
    server_sock.close()


@linux_only
def test_ids_come_back_only_after_delete_id():
    client, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    conn = wayland.Connection(client)
    first = conn.new_id()
    second = conn.new_id()
    assert (first, second) == (2, 3)
    Server(server_sock).send(wayland.DISPLAY_ID, 1, "u", first)  # delete_id
    conn.read()
    assert conn.new_id() == first and conn.new_id() == 4
    conn.close()
    server_sock.close()


@linux_only
def test_file_descriptors_come_with_their_events():
    client, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    conn = wayland.Connection(client)
    got = []

    def handler(opcode, args):
        got.append((wayland.decode("uhu", args), os.read(conn.take_fd(), 5)))

    oid = conn.new_id(handler)
    r, w = os.pipe()
    os.write(w, b"hello")
    Server(server_sock).send(oid, 0, "uhu", 1, r, 5)
    os.close(r)
    os.close(w)
    assert conn.read()
    assert got == [([1, 5], b"hello")]
    conn.close()
    server_sock.close()


def _xkb():
    from penguin_companion import xkb

    lib = xkb.library()
    if lib is None:
        pytest.skip("libxkbcommon isn't installed")
    return xkb, lib


def _configured(qapp, layer_version=4):
    """A layer surface past setup, configured, with a pointer and a keyboard."""
    client, server_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    server = Server(server_sock)
    conn = wayland.Connection(client)
    stage = FakeStage()
    surf = layer.LayerSurface(stage, conn)
    conn.flush()
    (registry,) = [wayland.decode("n", p)[0] for o, op, p in server.requests() if o == wayland.DISPLAY_ID and op == 1]
    for name, (interface, version) in enumerate(
        [("wl_compositor", 6), ("wl_shm", 1), ("wl_seat", 7), ("wl_output", 4), ("zwlr_layer_shell_v1", layer_version)], start=1
    ):
        server.send(registry, layer.EV_REGISTRY_GLOBAL, "usu", name, interface, version)
    conn.read()
    conn.flush()
    bound = {}
    for _o, _op, payload in server.requests():
        _name, interface, version, oid = wayland.decode("usun", payload)
        bound[interface] = oid
    server.send(bound["wl_seat"], layer.EV_SEAT_CAPABILITIES, "u", layer.CAP_POINTER | layer.CAP_KEYBOARD)
    conn.read()
    surf._start()
    surf.set_screen(FakeScreen(), QRect(0, 0, 1280, 800))
    conn.flush()
    reqs = server.requests()
    ids = {
        "pointer": wayland.decode("n", named(reqs, bound["wl_seat"], layer.SEAT_GET_POINTER)[0])[0],
        "keyboard": wayland.decode("n", named(reqs, bound["wl_seat"], layer.SEAT_GET_KEYBOARD)[0])[0],
    }
    (get,) = named(reqs, bound["zwlr_layer_shell_v1"], layer.LAYER_SHELL_GET_LAYER_SURFACE)
    ids["layer"], ids["surface"] = wayland.decode("noous", get)[:2]
    server.send(ids["layer"], layer.EV_LAYER_SURFACE_CONFIGURE, "uuu", 1, 1280, 800)
    conn.read()
    surf._present()
    server.requests()
    return conn, server, stage, surf, ids


def interactivity(reqs, ids):
    return [wayland.decode("u", p)[0] for p in named(reqs, ids["layer"], layer.LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY)]


@linux_only
def test_typing_reaches_the_stage_through_the_keymap(qapp):
    xkb, lib = _xkb()
    conn, server, stage, surf, ids = _configured(qapp)
    keymap = xkb.keymap_from_names(lib, "de").encode() + b"\0"  # z and y swap places on a German keyboard
    fd = os.memfd_create("keymap")
    os.write(fd, keymap)
    server.send(ids["keyboard"], layer.EV_KEYBOARD_KEYMAP, "uhu", layer.KEYMAP_XKB_V1, fd, len(keymap))
    os.close(fd)
    server.send(ids["keyboard"], layer.EV_KEYBOARD_ENTER, "uoa", 1, ids["surface"], b"")
    server.send(ids["keyboard"], layer.EV_KEYBOARD_KEY, "uuuu", 2, 0, 21, 1)  # the key that's Y in the US
    server.send(ids["keyboard"], layer.EV_KEYBOARD_KEY, "uuuu", 3, 0, 21, 0)
    server.send(ids["keyboard"], layer.EV_KEYBOARD_MODIFIERS, "uuuuu", 4, 1, 0, 0, 0)  # Shift
    server.send(ids["keyboard"], layer.EV_KEYBOARD_KEY, "uuuu", 5, 0, 30, 1)
    server.send(ids["keyboard"], layer.EV_KEYBOARD_LEAVE, "uo", 6, ids["surface"])
    conn.read()
    keys = [c for c in stage.calls if c[0] in ("key", "keyboard")]
    assert keys == [("keyboard", True), ("key", "z", True), ("key", "z", False), ("key", "A", True), ("keyboard", False)]
    surf.close()
    server.sock.close()


@linux_only
def test_the_keyboard_is_taken_only_while_the_ask_box_is_open(qapp):
    conn, server, stage, surf, ids = _configured(qapp)
    surf.set_input([QRect(100, 100, 200, 100)])  # the box
    surf._present()
    server.requests()
    surf.focus_keyboard(True)  # opened by you: take it now
    assert interactivity(server.requests(), ids) == [layer.KEYBOARD_EXCLUSIVE]
    server.send(ids["keyboard"], layer.EV_KEYBOARD_ENTER, "uoa", 1, ids["surface"], b"")
    conn.read()
    conn.flush()
    assert interactivity(server.requests(), ids) == []  # the pointer's elsewhere: handing over now would lose it
    server.send(ids["pointer"], layer.EV_POINTER_ENTER, "uoff", 2, ids["surface"], 150.0, 150.0)
    conn.read()
    conn.flush()
    assert interactivity(server.requests(), ids) == [layer.KEYBOARD_ON_DEMAND]  # on the box: your focus rules from here
    surf.focus_keyboard(False)
    assert interactivity(server.requests(), ids) == [layer.KEYBOARD_NONE]
    surf.focus_keyboard(True, grab=False)  # opened by itself: only when clicked
    assert interactivity(server.requests(), ids) == [layer.KEYBOARD_ON_DEMAND]
    surf.close()
    server.sock.close()


@linux_only
def test_an_older_layer_shell_keeps_the_keyboard_exclusive(qapp):
    conn, server, stage, surf, ids = _configured(qapp, layer_version=3)
    surf.focus_keyboard(True, grab=False)
    assert interactivity(server.requests(), ids) == [layer.KEYBOARD_EXCLUSIVE]  # no on_demand before version 4
    surf.close()
    server.sock.close()


@linux_only
def test_the_wheel_scrolls(qapp):
    conn, server, stage, surf, ids = _configured(qapp)
    server.send(ids["pointer"], layer.EV_POINTER_ENTER, "uoff", 1, ids["surface"], 10.0, 10.0)
    server.send(ids["pointer"], layer.EV_POINTER_AXIS, "uuf", 0, layer.AXIS_VERTICAL, 15.0)  # one notch down
    conn.read()
    assert ("wheel", 0, -120) in stage.calls
    surf.close()
    server.sock.close()
