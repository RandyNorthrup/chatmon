"""The overlay on a real compositor: Chatmon on a headless sway of the test's own (tests/sway_session.py), driven
with a pointer and a keyboard sway is given, looked at through sway's own screenshot and window tree, and read the
way a screen reader reads it (AT-SPI, and Orca where it's installed).

These run where sway, grim and dbus are installed (CI's `sway` job; WSL), and skip elsewhere with the reason."""

import os
import re
import shutil
import subprocess
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sway_session  # tests/ is on the path: pytest's rootdir import mode
from sway_session import BTN_RIGHT, Input, Probe, Session

BACKGROUND = (0, 0, 0)  # sway's own, with no wallpaper: what shows wherever the overlay draws nothing
DESK = "#334466"  # the plain window some tests open under the overlay, as on a desktop with a window open

SETUP = """
import time
c.behavior.set_walk(False, time.monotonic())  # still, so it's where the test looks
until(lambda: stage.bubble.drawn(), 2.5)  # the greeting, 1.5 s in
stage.dismiss_message()
until(lambda: not stage.bubble.drawn(), 5)
settled()
"""

DESK_WINDOW = f"""
class Desk(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.presses, self.keys = [], []
        self.setWindowTitle("desk")
        self.setStyleSheet("background: {DESK}")
    def mousePressEvent(self, event):
        self.presses.append((event.position().x(), event.position().y(), event.button().name))
    def keyPressEvent(self, event):
        self.keys.append(event.text())
desk = Desk()
desk.show()
until(lambda: desk.windowHandle() is not None and desk.windowHandle().isExposed(), 5)
settled()
"""


def _needs(atspi=False, orca=False):
    """Skip with the reason where this can't run; in CI's sway job (CHATMON_SWAY=1), where it must, fail instead
    (Orca aside: Ubuntu 24.04's is 46, older than the remote controller Chatmon speaks through)."""
    why = sway_session.unavailable(atspi=atspi, orca=orca)
    if why and os.environ.get("CHATMON_SWAY") == "1" and not (orca and sway_session.unavailable(atspi=atspi) is None):
        pytest.fail(f"CHATMON_SWAY=1, but {why}")
    if why:
        pytest.skip(why)


@pytest.fixture
def sway(tmp_path, qapp):
    _needs()
    session = Session(tmp_path)
    yield session
    session.close()


@pytest.fixture
def chatmon(sway):
    probe = Probe(sway)
    probe.call(SETUP)
    yield probe
    probe.close()


@pytest.fixture
def hands(sway):
    devices = Input(sway)
    yield devices
    devices.close()


def penguin(probe) -> tuple[float, float, float, float]:
    """Where the chatmon is drawn: (x, y, w, h) in sway's layout coordinates (the stage covers the one output)."""
    return tuple(probe.call("result = list(stage._penguin.getRect()) if stage.origin() == QPoint(0, 0) else None"))


def centre(rect) -> tuple[float, float]:
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def colour(image, x, y, scale=1) -> tuple[int, int, int]:
    c = image.pixelColor(round(x * scale), round(y * scale))
    return c.red(), c.green(), c.blue()


def drawn_columns(image, rect, scale=1, background=BACKGROUND) -> list[int]:
    """The x of every column (layout pixels) in `rect`'s rows, across the whole output, where anything is drawn."""
    _x, y, _w, h = rect
    rows = range(round(y * scale), round((y + h) * scale), max(1, round(scale)))
    return [x for x in range(image.width() // round(scale)) if any(colour(image, x, r / scale, scale) != background for r in rows)]


def test_the_virtual_pointers_opcodes_match_the_protocol_file():
    """The test bed's own pointer speaks wlr-virtual-pointer by number, as layer.py speaks its protocols."""
    import xml.etree.ElementTree as ET
    from pathlib import Path

    path = Path("/usr/share/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml")
    if not path.exists():
        pytest.skip("wlr-protocols isn't installed")
    found = {}
    for iface in ET.parse(path).getroot().iter("interface"):
        for i, request in enumerate(iface.iter("request")):
            found[(iface.get("name"), request.get("name"))] = i
    assert found[("zwlr_virtual_pointer_manager_v1", "create_virtual_pointer")] == sway_session.VPOINTER_MANAGER_CREATE
    named = {"motion_absolute": sway_session.VPOINTER_MOTION_ABSOLUTE, "button": sway_session.VPOINTER_BUTTON,
             "axis": sway_session.VPOINTER_AXIS, "frame": sway_session.VPOINTER_FRAME, "destroy": sway_session.VPOINTER_DESTROY}
    assert {name: found[("zwlr_virtual_pointer_v1", name)] for name in named} == named


# -- the overlay itself


def test_the_overlay_is_a_layer_surface_sway_draws_and_keeps_out_of_its_windows(sway, chatmon):
    state = chatmon.call(
        "result = dict(kind=type(surface).__name__, size=surface._size, layer=surface._layer is not None, "
        "content=surface._sub is not None, platform=QtGui.QGuiApplication.platformName())"
    )
    assert state == {"kind": "LayerSurface", "size": [1280, 800], "layer": True, "content": True, "platform": "wayland"}
    assert sway.views() == []  # not a window: sway neither tiles nor focuses it
    shot = sway.screenshot()
    rect = penguin(chatmon)
    assert colour(shot, *centre(rect)) != BACKGROUND  # the chatmon, composited by sway
    assert colour(shot, 20, 20) == BACKGROUND and colour(shot, 640, 100) == BACKGROUND  # nothing anywhere else
    columns = drawn_columns(shot, rect)
    assert columns and min(columns) >= rect[0] - 2 and max(columns) <= rect[0] + rect[2] + 2


def test_clicks_land_on_the_chatmon_and_pass_through_everywhere_else(sway, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    chatmon.call("clicked = []; stage.clicked.connect(lambda: clicked.append(1))")
    x, y, w, h = penguin(chatmon)
    hands.click(300, 200)  # nowhere near it
    hands.click(x + 2, y + 2)  # inside its frame, but where the sprite is see-through
    hands.click(*centre((x, y, w, h)))  # on it
    got = chatmon.call("result = dict(desk=len(desk.presses), stage=len(clicked), box=box.isVisible())", settle=0.3)
    assert got == {"desk": 2, "stage": 1, "box": True}  # the click on it opened the ask box; the others went through


def test_the_keyboard_is_the_overlays_only_while_the_ask_box_is_open(sway, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    hands.move(300, 200)
    hands.type("ab")
    hands.click(*centre(penguin(chatmon)))  # the ask box, on the overlay
    chatmon.call("until(lambda: surface._kb_focus, 5)", settle=0.2)
    hands.type("hello")
    got = chatmon.call("result = dict(desk=desk.keys[:], entry=box.entry.text(), hosted=stage.hosts_windows(), mode=surface._kb_mode, "
                       "kept=surface._kb_focus, holds=surface._on_demand_holds)")
    # sway (1.12) takes the keyboard back from an on_demand layer surface on the commit that makes it one: the overlay
    # saw that on the handover, took the keyboard again, and keeps it exclusive while the box is open.
    assert got == {"desk": ["a", "b"], "entry": "hello", "hosted": True, "mode": 1, "kept": True, "holds": False}
    hands.key("Escape")  # closes the box: the keyboard goes back to the window
    chatmon.call("until(lambda: not surface._kb_focus, 5)", settle=0.2)
    hands.type("c")
    got = chatmon.call("result = dict(desk=desk.keys[:], box=box.isVisible(), mode=surface._kb_mode)", settle=0.2)
    assert got == {"desk": ["a", "b", "c"], "box": False, "mode": 0}


def test_the_penguins_menu_opens_on_the_overlay_and_works_from_the_keyboard_and_pointer(sway, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    rect = penguin(chatmon)
    hands.click(*centre(rect), BTN_RIGHT)
    menu = chatmon.call("result = [list(r.getRect()) for r in stage.menu.rects()]", settle=0.3)
    assert len(menu) == 1
    chatmon.call("settled()")
    shot = sway.screenshot()
    mx, my, mw, _mh = menu[0]
    assert colour(shot, mx + mw / 2, my + 4) != BACKGROUND  # drawn, over everything
    hands.key("Down")  # the first item: "Ask ..."
    look = chatmon.call("result = stage.menu.hover")
    assert look == [0, 0]
    hands.key("Return")
    got = chatmon.call("result = dict(menu=stage.menu.is_open(), box=box.isVisible())", settle=0.3)
    assert got == {"menu": False, "box": True}  # picked from the keyboard: the ask box
    hands.key("Escape")
    hands.click(*centre(rect), BTN_RIGHT)
    chatmon.call("until(lambda: stage.menu.is_open(), 5); settled()")
    hands.click(1200, 60)  # elsewhere: the menu closes, and the click stops there
    got = chatmon.call("result = dict(menu=stage.menu.is_open(), desk=len(desk.presses))", settle=0.3)
    assert got == {"menu": False, "desk": 0}


def test_the_clipboard_goes_both_ways_between_the_overlay_other_apps_and_chatmons_own_windows(sway, chatmon, hands):
    """The overlay keeps its own clipboard (Qt's can't reach what's on it): another app's copy pasted into the ask
    box, the box's copy pasted by another app (wl-clipboard's, separate processes) and by Chatmon's own windows,
    which read Qt's clipboard in the same process: before, they froze two seconds and got nothing."""
    if shutil.which("wl-copy") is None:
        if os.environ.get("CHATMON_SWAY") == "1":
            pytest.fail("CHATMON_SWAY=1, but wl-clipboard isn't installed")
        pytest.skip("wl-clipboard isn't installed (CI's sway job installs it)")
    chatmon.call(DESK_WINDOW)
    subprocess.run(["wl-copy", "from another app"], env=sway.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
    hands.click(*centre(penguin(chatmon)))
    chatmon.call("until(lambda: surface._kb_focus and stage.clipboard_has_text(), 5)", settle=0.2)
    hands.key("v", mods=4)  # Ctrl+V
    assert chatmon.call("until(lambda: box.entry.text() != '', 5); result = box.entry.text()") == "from another app"
    hands.key("a", mods=4)
    hands.type("mine")
    hands.key("a", mods=4)
    hands.key("c", mods=4)  # Ctrl+C in the box: the overlay's clipboard
    chatmon.call("settled()", settle=0.2)
    pasted = subprocess.run(["wl-paste", "--no-newline"], env=sway.env, capture_output=True, text=True, timeout=10, check=True)
    assert pasted.stdout == "mine"
    hands.key("Escape")  # the box closes; the desk window, Chatmon's own, has the keyboard
    got = chatmon.call("import time; t = time.monotonic(); text = QtWidgets.QApplication.clipboard().text(); result = [text, time.monotonic() - t]", settle=0.3)
    assert got[0] == "mine" and got[1] < 0.5


def test_it_gives_way_to_a_full_screen_window_and_comes_above_it_for_the_ask_box(sway, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    chatmon.call("desk.showFullScreen(); until(lambda: desk.windowState() & Qt.WindowState.WindowFullScreen, 5); settled()", settle=0.5)
    x, y = centre(penguin(chatmon))
    desk = tuple(int(DESK[i : i + 2], 16) for i in (1, 3, 5))
    assert colour(sway.screenshot("under"), x, y) == desk  # the top layer: under a full-screen video, game or slides
    chatmon.call("c.open_ask(); settled()", settle=0.5)
    assert colour(sway.screenshot("above"), x, y) != desk  # the ask box asked for: above it, with the chatmon
    hands.key("Escape")
    chatmon.call("until(lambda: not box.isVisible(), 5); settled()", settle=0.5)
    assert colour(sway.screenshot("under-again"), x, y) == desk


def test_when_its_screen_goes_it_comes_back_on_the_one_left(sway, chatmon):
    sway.msg("command", "create_output")  # a second monitor plugged in: HEADLESS-2, right of the first
    assert chatmon.call("until(lambda: len(QtGui.QGuiApplication.screens()) == 2, 5); result = stage.screen().name()") == "HEADLESS-1"
    sway.msg("command", "output HEADLESS-1 disable")  # the first unplugged
    got = chatmon.call("until(lambda: stage.screen() is not None and stage.screen().name() == 'HEADLESS-2' and surface._size is not None, 5); "
                       "settled(); g = stage.screen().geometry(); result = dict(screen=stage.screen().name(), size=surface._size, qt=[g.width(), g.height()])",
                       settle=0.5)
    assert got["screen"] == "HEADLESS-2" and got["size"] == got["qt"]  # a layer surface of its own there, configured to it
    x, y, w, h = chatmon.call("result = list(stage._penguin.getRect())")  # the stage's own coordinates: that output's
    assert colour(sway.screenshot("second", output="HEADLESS-2"), x + w / 2, y + h / 2) != BACKGROUND


# -- M3-04: buffers the size of what's shown


@pytest.mark.parametrize("mode, scale", [("3840x2160", 2), ("2560x1440", 1.5)])
def test_buffers_are_the_size_of_what_is_shown_at_4k_and_fractional_scales(tmp_path, qapp, mode, scale):
    _needs()
    session = Session(tmp_path, mode=mode, scale=scale)
    try:
        probe = Probe(session)
        try:
            probe.call(SETUP)
            got = probe.call(
                "result = dict(buffers=[[b.width, b.height] for b in surface._buffers], box=list(surface._box.getRect()), "
                "size=surface._size, scale=surface._scale(), backdrop=[surface._backdrop.width, surface._backdrop.height])"
            )
            w, h = (int(n) for n in mode.split("x"))
            assert abs(got["size"][0] - w / scale) < 1 and abs(got["size"][1] - h / scale) < 1 and got["scale"] == scale
            assert got["backdrop"] == [1, 1]  # the layer surface's own: one pixel
            assert 1 <= len(got["buffers"]) <= 2
            for bw, bh in got["buffers"]:
                assert bw * bh * 10 < w * h  # a tenth of the output's pixels, or less (about a twentieth here)
                assert (bw, bh) == (round(got["box"][2] * scale), round(got["box"][3] * scale))  # whole device pixels
            probe.call("settled()")
            shot = session.screenshot()
            rect = penguin(probe)
            assert colour(shot, *centre(rect), scale=scale) != BACKGROUND
            assert colour(shot, rect[0] - 40, rect[1] + rect[3] / 2, scale=scale) == BACKGROUND
        finally:
            probe.close()
    finally:
        session.close()


def test_dragged_across_the_screen_it_is_drawn_once_where_it_is_and_nowhere_else(sway, chatmon, hands):
    """The subsurface goes with the chatmon, its new place and pixels shown together: in every frame sway shows,
    the chatmon is where the stage put it, once, with no trail where it was."""
    rect = penguin(chatmon)
    x, y = centre(rect)
    hands.move(x, y)
    hands.button(sway_session.BTN_LEFT, True)
    seen = []
    for step in range(1, 6):
        hands.move(x - 110 * step, y)  # each step farther than the subsurface's margin: it moves every time
        chatmon.call("settled()", settle=0.15)
        shot = sway.screenshot(f"drag-{step}")
        now = penguin(chatmon)
        columns = drawn_columns(shot, (0, now[1] + now[3] * 0.3, 1280, now[3] * 0.4))
        seen.append((now, min(columns), max(columns)))
        assert now[0] < rect[0] - 100 * step + 20  # it moved with the pointer
        assert min(columns) >= now[0] - 2 and max(columns) <= now[0] + now[2] + 2, (step, now, columns[:3], columns[-3:])
    hands.button(sway_session.BTN_LEFT, False)
    moved = chatmon.call("result = dict(box=list(surface._box.getRect()), buffers=len(surface._buffers))")
    assert moved["buffers"] <= 2


# -- M3-14: with a screen reader, the ask box a window of its own


def _screen_reader(session, probe):
    """A screen reader on, as Orca and GNOME say so (org.a11y.Status), and Chatmon told to look again."""
    session.screen_reader_on()
    return probe.call("c._reader_seen = float('-inf'); c._reader_running(); c._check_hosting(); settled(); result = dict(hosted=stage.hosts_windows(), "
                      "reader=getattr(c._reader, 'name', None), pid=__import__('os').getpid())")


@pytest.fixture
def reader_session(tmp_path, qapp):
    _needs(atspi=True)
    session = Session(tmp_path, atspi=True)
    yield session
    session.close()


def test_with_a_screen_reader_the_ask_box_is_a_window_sway_floats_centres_and_focuses(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP)
        state = _screen_reader(session, probe)
        assert state["hosted"] is False and state["reader"] is not None
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.3)
        (view,) = session.views()
        r = view["rect"]
        assert view["pid"] == state["pid"] and view["floating"] and view["focused"]  # not tiled over your windows; focused
        assert abs(r["x"] - (1280 - r["width"]) / 2) <= 1 and abs(r["y"] - (800 - r["height"]) / 2) <= 1  # sway centres it
        hands.type("hi there")
        assert probe.call("result = box.entry.text()", settle=0.2) == "hi there"
        # A bubble while it's open: over the chatmon's head, not over the box (whose place only sway knows).
        probe.call("stage.show_message('A reminder', 'Stretch your legs.'); settled()", settle=0.4)
        bx, by, bw, bh = probe.call("result = list(stage._bubble_box.getRect())")
        assert bx + bw <= r["x"] or bx >= r["x"] + r["width"] or by + bh <= r["y"] or by >= r["y"] + r["height"]
        shot = session.screenshot()
        assert colour(shot, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2) != BACKGROUND  # the box, drawn by sway
    finally:
        hands.close()
        probe.close()


def test_with_the_box_a_window_the_penguins_menu_works_and_gives_the_keyboard_back(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP)
        _screen_reader(session, probe)
        rect = penguin(probe)
        hands.click(*centre(rect))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.3)
        hands.type("ab")
        hands.click(*centre(rect), BTN_RIGHT)  # the penguin's menu: on the overlay, Qt's menus having no window to go with
        assert probe.call("until(lambda: surface._kb_focus, 5); result = stage.menu.is_open()", settle=0.2)
        hands.key("Down")
        hands.key("Down")
        got = probe.call("result = dict(hover=stage.menu.hover, entry=box.entry.text())", settle=0.2)
        assert got == {"hover": [0, 1], "entry": "ab"}  # the menu has the keys, the box none of them
        hands.key("Escape")
        assert probe.call("until(lambda: not surface._kb_focus, 5); result = stage.menu.is_open()", settle=0.2) is False
        assert [v["focused"] for v in session.views()] == [True]  # sway gave the keyboard back to the box
        hands.type("c")
        assert probe.call("result = dict(entry=box.entry.text(), box=box.isVisible())", settle=0.2) == {"entry": "abc", "box": True}
    finally:
        hands.close()
        probe.close()


def test_with_the_box_a_window_its_own_menus_are_qts_beside_it(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP)
        _screen_reader(session, probe)
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.3)
        (view,) = session.views()
        r = view["rect"]
        at = probe.call("p = box.entry.mapTo(box, box.entry.rect().center()); result = [p.x(), p.y()]")  # in the box's window
        hands.click(r["x"] + at[0], r["y"] + at[1], BTN_RIGHT)  # right-click in the field: Qt's own context menu
        # Qt runs its menu in an event loop of its own (QMenu.exec): let it start before asking the probe anything,
        # or the question is held up inside the menu's loop until the menu closes.
        time.sleep(0.5)
        got = probe.call("until(lambda: QtWidgets.QApplication.activePopupWidget() is not None, 5); p = QtWidgets.QApplication.activePopupWidget(); "
                         "result = dict(menu=type(p).__name__, shown=p.isVisible() and p.windowHandle().isExposed(), stage=stage.menu.is_open())", settle=0.3)
        assert got == {"menu": "QMenu", "shown": True, "stage": False}
        hands.key("Escape")
        assert probe.call("result = QtWidgets.QApplication.activePopupWidget() is None and box.isVisible()", settle=0.3)
    finally:
        hands.close()
        probe.close()


def test_a_screen_reader_finds_the_box_its_field_its_buttons_and_the_conversation(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP)
        state = _screen_reader(session, probe)
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible(), 5); box.set_answer('The **answer** is forty-two.')", settle=0.5)
        hands.type("why")
        (app,) = sway_session.atspi_tree(session, state["pid"])
        name = probe.call("result = box.title.text()")  # "Ask <its name>"
        (window,) = sway_session.find(app, name=name, role="filler")  # the box: a window of its own
        assert {"active", "showing", "visible"} <= set(window["states"])
        (field,) = sway_session.find(window, role="text", name=name)
        assert field["text"] == "why" and {"editable", "focused"} <= set(field["states"])
        assert field["description"].startswith("Enter to ask")  # its hint
        (conversation,) = sway_session.find(window, name="Conversation")
        assert conversation["text"] == "The answer is forty-two."  # read as words, without the markdown
        buttons = {n["name"] for n in sway_session.find(window, role=lambda r: r in ("push button", "button")) if "showing" in n["states"]}
        assert {"History", "Close", "Attach"} <= buttons
        (bigger,) = sway_session.find(window, role="check box")
        assert bigger["name"] == "Make the box bigger"
    finally:
        hands.close()
        probe.close()


@pytest.mark.parametrize("setting, a_window", [("auto", True), ("off", False)])
def test_only_as_a_window_of_its_own_is_the_box_ever_an_active_window_to_a_screen_reader(reader_session, qapp, setting, a_window):
    """Why the box becomes a window for a screen reader. Drawn on the overlay (Settings' "accessible ask box" off),
    Qt still lists it in AT-SPI's tree, but it is never a window anyone activates: no window:activate, so a screen
    reader neither announces it nor follows what's typed in it (Orca, below). As a window of its own, it is."""
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP + f"c.config['accessibility']['accessible_ask_box'] = '{setting}'")
        state = _screen_reader(session, probe)
        assert state["hosted"] is not a_window and state["reader"] is not None
        events = sway_session.AtspiEvents(session, ["window:activate", "object:state-changed:focused"])
        hands.click(*centre(penguin(probe)))
        name = probe.call("until(lambda: box.isVisible(), 5); result = box.title.text()", settle=0.5)
        time.sleep(0.3)
        heard = events.stop()
        activated = [e["source"] for e in heard if e["type"] == "window:activate"]
        focused = [e["source"] for e in heard if e["type"] == "object:state-changed:focused" and e["detail1"] == 1]
        assert focused == [name]  # its field, named for what the box asks, either way
        assert activated == ([name] if a_window else [])
    finally:
        hands.close()
        probe.close()


def test_what_changes_in_the_box_reaches_atspi_listeners(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = Input(session)
    try:
        probe.call(SETUP)
        _screen_reader(session, probe)
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible(), 5)", settle=0.3)
        events = sway_session.AtspiEvents(session, ["object:text-changed", "object:state-changed:focused"])
        probe.call("box.set_answer('Your tea has steeped.')", settle=0.5)
        time.sleep(0.5)
        heard = events.stop()
        inserted = [e for e in heard if e["type"] == "object:text-changed:insert" and e["source"] == "Conversation"]
        assert inserted and inserted[-1]["data"] == "Your tea has steeped."
    finally:
        hands.close()
        probe.close()


def _orca_said(session, since: int, wanted: str, seconds: float = 10.0) -> str:
    """What Orca's debug log says from `since` on, once `wanted` is in it (or `seconds` have passed)."""
    deadline = time.monotonic() + seconds
    log = ""
    while wanted not in log and time.monotonic() < deadline:
        time.sleep(0.2)
        log = session.orca_log.read_text(encoding="utf-8", errors="replace")[since:] if session.orca_log.exists() else ""
    return log


def _spoken(log: str) -> list[str]:
    return re.findall(r"SPEECH OUTPUT: '(.*?)'\{", log)


def test_with_orca_the_box_as_a_window_is_announced_and_echoes_typing_and_bubbles_are_said(tmp_path, qapp):
    _needs(orca=True)
    session = Session(tmp_path, atspi=True, orca=True)
    try:
        probe = Probe(session)
        hands = Input(session)
        try:
            probe.call(SETUP)
            state = probe.call("c._reader_seen = float('-inf'); c._check_hosting(); result = dict(hosted=stage.hosts_windows(), reader=c._reader.name)")
            assert state == {"hosted": False, "reader": "Orca"}  # found by its own service, and the box a window for it
            since = len(session.orca_log.read_text(encoding="utf-8", errors="replace"))
            probe.call("c.say('Tea is ready', 'Your **green** tea has steeped.')", settle=0.5)
            log = _orca_said(session, since, "SPEECH OUTPUT: 'Tea is ready. Your green tea has steeped.'")
            assert "PresentMessage called with: 'Tea is ready. Your green tea has steeped.'" in log  # Chatmon asked it
            assert "Tea is ready. Your green tea has steeped." in _spoken(log)  # and Orca said it (to its speech server)
            since += len(log)
            hands.click(*centre(penguin(probe)))
            name = probe.call("until(lambda: box.isVisible(), 5); result = box.title.text()", settle=1.0)
            hands.type("ab")
            spoken = _spoken(_orca_said(session, since, "SPEECH OUTPUT: 'b'"))
            assert spoken[:2] == [name, f"{name} text"]  # the window, then its field
            assert spoken[-2:] == ["a", "b"]  # what's typed, echoed
        finally:
            hands.close()
            probe.close()
    finally:
        session.close()


def test_with_orca_the_box_drawn_on_the_overlay_is_neither_announced_nor_echoed(tmp_path, qapp):
    """The other side of the test above, as it was before the box became a window for a screen reader."""
    _needs(orca=True)
    session = Session(tmp_path, atspi=True, orca=True)
    try:
        probe = Probe(session)
        hands = Input(session)
        try:
            probe.call(SETUP + "c.config['accessibility']['accessible_ask_box'] = 'off'")
            assert probe.call("c._reader_seen = float('-inf'); c._reader_running(); c._check_hosting(); result = stage.hosts_windows()")
            since = len(session.orca_log.read_text(encoding="utf-8", errors="replace"))
            hands.click(*centre(penguin(probe)))
            name = probe.call("until(lambda: box.isVisible(), 5); result = box.title.text()", settle=1.0)
            hands.type("ab")
            time.sleep(1.5)
            spoken = _spoken(_orca_said(session, since, "never", seconds=0.5))
            assert name not in spoken and "a" not in spoken and "b" not in spoken
        finally:
            hands.close()
            probe.close()
    finally:
        session.close()
