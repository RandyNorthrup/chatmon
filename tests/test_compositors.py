"""tests/test_sway.py's checks on KWin and Hyprland: Chatmon on a headless compositor of the test's own
(tests/compositor_session.py), driven with a pointer and a keyboard the compositor is given, looked at through its
own screenshots and window lists, and read the way a screen reader reads it (AT-SPI, and Orca where it's installed).

Where a compositor does a thing its own way (where it puts a window, whether it lets a layer surface keep the
keyboard on demand), the check takes what the product allows and the run notes what was seen (`observe`).

These run where KWin or Hyprland is installed and skip elsewhere with the reason; CHATMON_COMPOSITORS=1 makes a
missing piece a failure instead. CI's `sway` job doesn't run this file."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import compositor_session  # tests/ is on the path: pytest's rootdir import mode
import sway_session
from compositor_session import COMPOSITORS
from sway_session import BTN_RIGHT, Probe
from test_sway import DESK, DESK_WINDOW, SETUP, _orca_said, _screen_reader, _spoken, centre, colour, drawn_columns, penguin

KEYBOARD_EXCLUSIVE, KEYBOARD_ON_DEMAND = 1, 2  # layer.py's

# The plain window some tests open under the overlay. sway tiles it over the whole output; KWin places a new window
# at its own size (centred) and Hyprland tiles it inside gaps, so here it's maximized, to be under the chatmon too
# (sway, tiling, leaves it as it is).
DESK_WINDOW = DESK_WINDOW.replace("desk.show()\n", "desk.showMaximized()\n").replace("settled()\n", "until(lambda: desk.width() >= 1200, 5)\nsettled()\n")


# What the product does wrong on a compositor, found by these checks (docs/delivery/reports/release/compositors/
# README.md has the evidence and the fixes proposed). Each check it fails is a strict xfail there: it passes the
# day the product is fixed, and then fails until the mark is taken away.
KWIN_KEEPS_THE_KEYBOARD = ("KWin 6.8 leaves the keyboard on the overlay after the overlay lets it go (keyboard interactivity "
                           "none): no window gets it back (README, problem 1)")
HYPRLAND_ENDS_THE_PRESS = ("Hyprland 0.57 releases the button on the overlay as soon as the pointer leaves its input region, "
                           "mid-drag: the chatmon drops (README, problem 2)")
KWIN_REFUSES_QTS_SELECTION = ("KWin 6.8 takes a selection only from the client with the keyboard, the overlay's connection when "
                              "the box copies, so Qt's copy is refused and Chatmon's windows read the overlay's: a 2 s freeze, "
                              "nothing pasted (README, problem 3; and problem 1 before it)")


def known_problem(request, session, compositor: str, reason: str) -> None:
    if session.NAME == compositor:
        request.node.add_marker(pytest.mark.xfail(strict=True, reason=reason))


def _needs(name, atspi=False, orca=False):
    why = compositor_session.unavailable(name, atspi=atspi, orca=orca)
    if why and os.environ.get("CHATMON_COMPOSITORS") == "1":
        pytest.fail(f"CHATMON_COMPOSITORS=1, but {why}")
    if why:
        pytest.skip(why)


def observe(session, request, **facts) -> None:
    """What this compositor did, where the check allows more than one way: a line in the run's notes
    (CHATMON_COMPOSITORS_NOTES, a file), and in the session's folder."""
    line = json.dumps({"compositor": session.NAME, "test": request.node.name, **facts}, default=str)
    with open(session.folder / "observed.jsonl", "a", encoding="utf-8") as out:
        out.write(line + "\n")
    notes = os.environ.get("CHATMON_COMPOSITORS_NOTES")
    if notes:
        with open(notes, "a", encoding="utf-8") as out:
            out.write(line + "\n")


def _keep(session, request) -> None:
    """The screenshots, kept where CHATMON_COMPOSITORS_SHOTS says (a folder), by compositor and test."""
    keep = os.environ.get("CHATMON_COMPOSITORS_SHOTS")
    if keep:
        to = Path(keep) / request.node.name.replace("[", "-").replace("]", "")
        to.mkdir(parents=True, exist_ok=True)
        for shot in session.folder.glob("*.png"):
            shutil.copy2(shot, to / shot.name)


@pytest.fixture(params=COMPOSITORS)
def desktop(request, tmp_path, qapp):
    _needs(request.param)
    session = compositor_session.start(request.param, tmp_path)
    yield session
    _keep(session, request)
    session.close()


@pytest.fixture
def chatmon(desktop):
    probe = Probe(desktop)
    probe.call(SETUP)
    yield probe
    probe.close()


@pytest.fixture
def hands(desktop):
    devices = compositor_session.devices(desktop)
    yield devices
    devices.close()


def test_the_fake_inputs_opcodes_match_the_protocol_file():
    """KWin's fake input, spoken by number, as the test bed's virtual pointer speaks wlr's."""
    import xml.etree.ElementTree as ET

    path = Path("/usr/share/plasma-wayland-protocols/fake-input.xml")
    if not path.exists():
        pytest.skip("plasma-wayland-protocols isn't installed")
    found = {r.get("name"): i for iface in ET.parse(path).getroot().iter("interface") for i, r in enumerate(iface.iter("request"))}
    named = {"authenticate": compositor_session.FAKE_AUTHENTICATE, "button": compositor_session.FAKE_BUTTON,
             "pointer_motion_absolute": compositor_session.FAKE_POINTER_MOTION_ABSOLUTE,
             "keyboard_key": compositor_session.FAKE_KEYBOARD_KEY, "destroy": compositor_session.FAKE_DESTROY}
    assert {name: found[name] for name in named} == named


# -- the overlay itself


def test_the_overlay_is_a_layer_surface_the_compositor_draws_and_keeps_out_of_its_windows(desktop, chatmon, request):
    state = chatmon.call(
        "result = dict(kind=type(surface).__name__, size=surface._size, layer=surface._layer is not None, "
        "content=surface._sub is not None, platform=QtGui.QGuiApplication.platformName(), layer_shell=surface.globals['zwlr_layer_shell_v1'][1])"
    )
    observe(desktop, request, layer_shell_version=state.pop("layer_shell"))
    assert state == {"kind": "LayerSurface", "size": [1280, 800], "layer": True, "content": True, "platform": "wayland"}
    assert desktop.views() == []  # not a window: the compositor neither places nor focuses it
    shot = desktop.screenshot()
    rect = penguin(chatmon)
    empty = desktop.background
    assert colour(shot, *centre(rect)) != empty  # the chatmon, composited
    assert colour(shot, 20, 20) == empty and colour(shot, 640, 100) == empty  # nothing anywhere else
    columns = drawn_columns(shot, rect, empty)
    assert columns and min(columns) >= rect[0] - 2 and max(columns) <= rect[0] + rect[2] + 2


def test_clicks_land_on_the_chatmon_and_pass_through_everywhere_else(desktop, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    chatmon.call("clicked = []; stage.clicked.connect(lambda: clicked.append(1))")
    x, y, w, h = penguin(chatmon)
    hands.click(300, 200)  # nowhere near it
    hands.click(x + 2, y + 2)  # inside its frame, but where the sprite is see-through
    hands.click(*centre((x, y, w, h)))  # on it
    got = chatmon.call("result = dict(desk=len(desk.presses), stage=len(clicked), box=box.isVisible())", settle=0.3)
    assert got == {"desk": 2, "stage": 1, "box": True}  # the click on it opened the ask box; the others went through


def test_the_keyboard_is_the_overlays_only_while_the_ask_box_is_open(desktop, chatmon, hands, request):
    known_problem(request, desktop, "kwin", KWIN_KEEPS_THE_KEYBOARD)
    chatmon.call(DESK_WINDOW)
    hands.move(300, 200)
    hands.type("ab")
    hands.click(*centre(penguin(chatmon)))  # the ask box, on the overlay
    chatmon.call("until(lambda: surface._kb_focus, 5)", settle=0.2)
    hands.type("hello")
    got = chatmon.call("result = dict(desk=desk.keys[:], entry=box.entry.text(), hosted=stage.hosts_windows(), mode=surface._kb_mode, "
                       "kept=surface._kb_focus, holds=surface._on_demand_holds)")
    observe(desktop, request, keyboard_mode=got["mode"], on_demand_holds=got["holds"])
    # Exclusive, or on demand where the compositor lets the overlay keep the keyboard so (sway 1.12 doesn't).
    assert got["mode"] in (KEYBOARD_EXCLUSIVE, KEYBOARD_ON_DEMAND) and (got["mode"] == KEYBOARD_ON_DEMAND) == got["holds"]
    assert {k: got[k] for k in ("desk", "entry", "hosted", "kept")} == {"desk": ["a", "b"], "entry": "hello", "hosted": True, "kept": True}
    hands.key("Escape")  # closes the box: the keyboard goes back to the window
    chatmon.call("until(lambda: not surface._kb_focus, 5)", settle=0.2)
    hands.type("c")
    got = chatmon.call("result = dict(desk=desk.keys[:], box=box.isVisible(), mode=surface._kb_mode)", settle=0.2)
    assert got == {"desk": ["a", "b", "c"], "box": False, "mode": 0}


def test_the_penguins_menu_opens_on_the_overlay_and_works_from_the_keyboard_and_pointer(desktop, chatmon, hands):
    chatmon.call(DESK_WINDOW)
    rect = penguin(chatmon)
    hands.click(*centre(rect), BTN_RIGHT)
    menu = chatmon.call("result = [list(r.getRect()) for r in stage.menu.rects()]", settle=0.3)
    assert len(menu) == 1
    chatmon.call("settled()")
    shot = desktop.screenshot()
    mx, my, mw, _mh = menu[0]
    assert colour(shot, mx + mw / 2, my + 4) != desktop.background  # drawn, over everything
    hands.key("Down")  # the first item: "Ask ..."
    assert chatmon.call("result = stage.menu.hover") == [0, 0]
    hands.key("Return")
    got = chatmon.call("result = dict(menu=stage.menu.is_open(), box=box.isVisible())", settle=0.3)
    assert got == {"menu": False, "box": True}  # picked from the keyboard: the ask box
    hands.key("Escape")
    hands.click(*centre(rect), BTN_RIGHT)
    chatmon.call("until(lambda: stage.menu.is_open(), 5); settled()")
    hands.click(1200, 60)  # elsewhere: the menu closes, and the click stops there
    got = chatmon.call("result = dict(menu=stage.menu.is_open(), desk=len(desk.presses))", settle=0.3)
    assert got == {"menu": False, "desk": 0}


def test_the_clipboard_goes_both_ways_between_the_overlay_other_apps_and_chatmons_own_windows(desktop, chatmon, hands, request):
    # The last step: Chatmon's own window reads Qt's clipboard, which a Wayland client gets only with the keyboard.
    known_problem(request, desktop, "kwin", KWIN_REFUSES_QTS_SELECTION)
    if shutil.which("wl-copy") is None:
        if os.environ.get("CHATMON_COMPOSITORS") == "1":
            pytest.fail("CHATMON_COMPOSITORS=1, but wl-clipboard isn't installed")
        pytest.skip("wl-clipboard isn't installed")
    chatmon.call(DESK_WINDOW)
    subprocess.run(["wl-copy", "from another app"], env=desktop.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
    hands.click(*centre(penguin(chatmon)))
    chatmon.call("until(lambda: surface._kb_focus and stage.clipboard_has_text(), 5)", settle=0.2)
    hands.key("v", mods=4)  # Ctrl+V
    assert chatmon.call("until(lambda: box.entry.text() != '', 5); result = box.entry.text()") == "from another app"
    hands.key("a", mods=4)
    hands.type("mine")
    hands.key("a", mods=4)
    hands.key("c", mods=4)  # Ctrl+C in the box: the overlay's clipboard
    chatmon.call("settled()", settle=0.2)
    pasted = subprocess.run(["wl-paste", "--no-newline"], env=desktop.env, capture_output=True, text=True, timeout=10, check=True)
    assert pasted.stdout == "mine"
    hands.key("Escape")  # the box closes; the desk window, Chatmon's own, has the keyboard (once the compositor says)
    got = chatmon.call("until(lambda: desk.isActiveWindow(), 5); import time; t = time.monotonic(); text = QtWidgets.QApplication.clipboard().text(); "
                       "result = [text, time.monotonic() - t]", settle=0.3)
    assert got[0] == "mine" and got[1] < 0.5


def test_it_gives_way_to_a_full_screen_window_and_comes_above_it_for_the_ask_box(desktop, chatmon, hands, request):
    # The last step: a full-screen window KWin no longer counts as active goes under the top layer.
    known_problem(request, desktop, "kwin", KWIN_KEEPS_THE_KEYBOARD)
    chatmon.call(DESK_WINDOW)
    chatmon.call("desk.showFullScreen(); until(lambda: desk.windowState() & Qt.WindowState.WindowFullScreen, 5); settled()", settle=0.5)
    x, y = centre(penguin(chatmon))
    desk = tuple(int(DESK[i : i + 2], 16) for i in (1, 3, 5))
    assert colour(desktop.screenshot("under"), x, y) == desk  # the top layer: under a full-screen video, game or slides
    chatmon.call("c.open_ask(); settled()", settle=0.5)
    assert colour(desktop.screenshot("above"), x, y) != desk  # the ask box asked for: above it, with the chatmon
    hands.key("Escape")
    chatmon.call("until(lambda: not box.isVisible(), 5); settled()", settle=0.5)
    assert colour(desktop.screenshot("under-again"), x, y) == desk


@pytest.mark.parametrize("name", COMPOSITORS)
def test_when_its_screen_goes_it_comes_back_on_the_one_left(tmp_path, qapp, name, request):
    _needs(name)
    session = compositor_session.start(name, tmp_path, outputs=2)
    try:
        probe = Probe(session)
        try:
            probe.call(SETUP)
            first = session.first_output()
            second = session.add_output()  # a second monitor plugged in, right of the first
            assert probe.call("until(lambda: len(QtGui.QGuiApplication.screens()) == 2, 5); result = stage.screen().name()") == first
            session.disable_output(first)  # the first unplugged
            # KWin moves the output left to where the first was (sway and Hyprland leave it where it is): Qt says so a
            # moment after the screen goes, and the stage follows on its next tick.
            got = probe.call(f"until(lambda: stage.screen() is not None and stage.screen().name() == {second!r} and surface._size is not None "
                             "and stage.origin() == stage.screen().geometry().topLeft(), 5); settled(); g = stage.screen().geometry(); "
                             "result = dict(screen=stage.screen().name(), size=surface._size, qt=[g.width(), g.height()], at=[g.x(), g.y()])",
                             settle=0.5)
            assert got["screen"] == second and got["size"] == got["qt"]  # a layer surface of its own there, configured to it
            x, y, w, h = probe.call("settled(); result = list(stage._penguin.getRect())")  # the stage's own coordinates: that output's
            observe(session, request, second_output_at=got["at"], chatmon=[x, y, w, h])
            assert colour(session.screenshot("second", output=second), x + w / 2, y + h / 2) != session.background
        finally:
            probe.close()
    finally:
        _keep(session, request)
        session.close()


# -- M3-04: buffers the size of what's shown


@pytest.mark.parametrize("name", COMPOSITORS)
@pytest.mark.parametrize("mode, scale", [("3840x2160", 2), ("2560x1440", 1.5)])
def test_buffers_are_the_size_of_what_is_shown_at_4k_and_fractional_scales(tmp_path, qapp, name, mode, scale, request):
    _needs(name)
    session = compositor_session.start(name, tmp_path, mode=mode, scale=scale)
    try:
        probe = Probe(session)
        try:
            probe.call(SETUP)
            got = probe.call(
                "result = dict(buffers=[[b.width, b.height] for b in surface._buffers], box=list(surface._box.getRect()), "
                "size=surface._size, scale=surface._scale(), backdrop=[surface._backdrop.width, surface._backdrop.height])"
            )
            shown = session.outputs()[0]
            observe(session, request, asked_scale=scale, compositor_scale=shown["scale"], overlay_scale=got["scale"], size=got["size"])
            w, h = (int(n) for n in mode.split("x"))
            real = shown["scale"]  # what the compositor made of the scale asked for
            assert abs(got["size"][0] - w / real) < 1 and abs(got["size"][1] - h / real) < 1 and got["scale"] == pytest.approx(real, abs=0.01)
            assert got["backdrop"] == [1, 1]  # the layer surface's own: one pixel
            assert 1 <= len(got["buffers"]) <= 2
            for bw, bh in got["buffers"]:
                assert bw * bh * 10 < w * h  # a tenth of the output's pixels, or less
                assert (bw, bh) == (round(got["box"][2] * got["scale"]), round(got["box"][3] * got["scale"]))  # whole device pixels
            probe.call("settled()")
            shot = session.screenshot()
            rect = penguin(probe)
            assert colour(shot, *centre(rect), scale=real) != session.background
            assert colour(shot, rect[0] - 40, rect[1] + rect[3] / 2, scale=real) == session.background
        finally:
            probe.close()
    finally:
        _keep(session, request)
        session.close()


def test_dragged_across_the_screen_it_is_drawn_once_where_it_is_and_nowhere_else(desktop, chatmon, hands, request):
    known_problem(request, desktop, "hyprland", HYPRLAND_ENDS_THE_PRESS)
    rect = penguin(chatmon)
    x, y = centre(rect)
    hands.move(x, y)
    hands.button(sway_session.BTN_LEFT, True)
    chatmon.call("settled()", settle=0.1)  # as a hand: the press, then the move (the overlay has heard the press)
    for step in range(1, 6):
        hands.move(x - 110 * step, y)  # each step farther than the subsurface's margin: it moves every time
        chatmon.call("settled()", settle=0.15)
        shot = desktop.screenshot(f"drag-{step}")
        now = penguin(chatmon)
        columns = drawn_columns(shot, (0, now[1] + now[3] * 0.3, 1280, now[3] * 0.4), desktop.background)
        assert now[0] < rect[0] - 100 * step + 20  # it moved with the pointer
        assert min(columns) >= now[0] - 2 and max(columns) <= now[0] + now[2] + 2, (step, now, columns[:3], columns[-3:])
        assert max(columns) - min(columns) >= now[2] / 2, (step, now, columns[:3], columns[-3:])
    hands.button(sway_session.BTN_LEFT, False)
    moved = chatmon.call("result = dict(box=list(surface._box.getRect()), buffers=len(surface._buffers))")
    assert moved["buffers"] <= 2


# -- M3-14: with a screen reader, the ask box a window of its own


@pytest.fixture(params=COMPOSITORS)
def reader_session(request, tmp_path, qapp):
    _needs(request.param, atspi=True)
    session = compositor_session.start(request.param, tmp_path, atspi=True)
    yield session
    _keep(session, request)
    session.close()


def test_with_a_screen_reader_the_ask_box_is_a_window_on_screen_and_focused(reader_session, qapp, request):
    session = reader_session
    probe = Probe(session)
    hands = compositor_session.devices(session)
    try:
        probe.call(SETUP)
        state = _screen_reader(session, probe)
        assert state["hosted"] is False and state["reader"] is not None
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.5)
        (view,) = session.views()
        r = view["rect"]
        centred = abs(r["x"] - (1280 - r["width"]) / 2) <= 1 and abs(r["y"] - (800 - r["height"]) / 2) <= 1
        observe(session, request, box=r, floating=view["floating"], centred=centred, frame=view.get("frame"))
        assert view["pid"] == state["pid"] and view["focused"]
        assert view["floating"]  # not tiled over your windows
        assert r["x"] >= 0 and r["y"] >= 0 and r["x"] + r["width"] <= 1280 and r["y"] + r["height"] <= 800  # all of it on screen
        hands.type("hi there")
        assert probe.call("result = box.entry.text()", settle=0.2) == "hi there"
        # A bubble while it's open: over the chatmon's head, not over the box (whose place only the compositor knows).
        probe.call("stage.show_message('A reminder', 'Stretch your legs.'); settled()", settle=0.4)
        bx, by, bw, bh = probe.call("result = list(stage._bubble_box.getRect())")
        observe(session, request, bubble=[bx, by, bw, bh], chatmon=penguin(probe))
        shot = session.screenshot()
        assert colour(shot, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2) != session.background  # the box, drawn
        assert bx + bw <= r["x"] or bx >= r["x"] + r["width"] or by + bh <= r["y"] or by >= r["y"] + r["height"]
    finally:
        hands.close()
        probe.close()


def test_with_the_box_a_window_the_penguins_menu_works_and_gives_the_keyboard_back(reader_session, qapp, request):
    session = reader_session
    known_problem(request, session, "kwin", KWIN_KEEPS_THE_KEYBOARD)
    probe = Probe(session)
    hands = compositor_session.devices(session)
    try:
        probe.call(SETUP)
        _screen_reader(session, probe)
        rect = penguin(probe)
        hands.click(*centre(rect))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.5)
        hands.type("ab")
        hands.click(*centre(rect), BTN_RIGHT)  # the penguin's menu: on the overlay
        assert probe.call("until(lambda: surface._kb_focus, 5); result = stage.menu.is_open()", settle=0.2)
        hands.key("Down")
        hands.key("Down")
        got = probe.call("result = dict(hover=stage.menu.hover, entry=box.entry.text())", settle=0.2)
        assert got == {"hover": [0, 1], "entry": "ab"}  # the menu has the keys, the box none of them
        hands.key("Escape")
        assert probe.call("until(lambda: not surface._kb_focus, 5); result = stage.menu.is_open()", settle=0.2) is False
        time.sleep(0.3)
        assert [v["focused"] for v in session.views()] == [True]  # the keyboard back to the box
        hands.type("c")
        assert probe.call("result = dict(entry=box.entry.text(), box=box.isVisible())", settle=0.2) == {"entry": "abc", "box": True}
    finally:
        hands.close()
        probe.close()


def test_with_the_box_a_window_its_own_menus_are_qts_beside_it(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = compositor_session.devices(session)
    try:
        probe.call(SETUP)
        _screen_reader(session, probe)
        hands.click(*centre(penguin(probe)))
        probe.call("until(lambda: box.isVisible() and box.windowHandle().isExposed(), 5)", settle=0.5)
        (view,) = session.views()
        r = view["rect"]
        at = probe.call("p = box.entry.mapTo(box, box.entry.rect().center()); result = [p.x(), p.y()]")  # in the box's window
        hands.click(r["x"] + at[0], r["y"] + at[1], BTN_RIGHT)  # right-click in the field: Qt's own context menu
        time.sleep(0.5)  # Qt's menu runs its own event loop (QMenu.exec): let it start before asking the probe anything
        got = probe.call("until(lambda: QtWidgets.QApplication.activePopupWidget() is not None, 5); p = QtWidgets.QApplication.activePopupWidget(); "
                         "result = dict(menu=type(p).__name__, shown=p.isVisible() and p.windowHandle().isExposed(), stage=stage.menu.is_open())", settle=0.3)
        assert got == {"menu": "QMenu", "shown": True, "stage": False}
        session.screenshot("context-menu")
        hands.key("Escape")
        assert probe.call("result = QtWidgets.QApplication.activePopupWidget() is None and box.isVisible()", settle=0.3)
    finally:
        hands.close()
        probe.close()


def test_a_screen_reader_finds_the_box_its_field_its_buttons_and_the_conversation(reader_session, qapp):
    session = reader_session
    probe = Probe(session)
    hands = compositor_session.devices(session)
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
    session = reader_session
    probe = Probe(session)
    hands = compositor_session.devices(session)
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
    hands = compositor_session.devices(session)
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


@pytest.mark.parametrize("name", COMPOSITORS)
def test_with_orca_the_box_as_a_window_is_announced_and_echoes_typing_and_bubbles_are_said(tmp_path, qapp, name, request):
    _needs(name, orca=True)
    session = compositor_session.start(name, tmp_path, atspi=True, orca=True)
    try:
        probe = Probe(session)
        hands = compositor_session.devices(session)
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
            box_name = probe.call("until(lambda: box.isVisible(), 5); result = box.title.text()", settle=1.0)
            # Typed once Orca has said where you are, as you would (on Hyprland it takes longer than the second
            # sway's checks wait, and a key typed sooner is echoed between the two).
            opened = time.monotonic()
            _orca_said(session, since, f"SPEECH OUTPUT: '{box_name} text'")
            heard_in = round(time.monotonic() - opened, 2)
            hands.type("ab")
            spoken = _spoken(_orca_said(session, since, "SPEECH OUTPUT: 'b'"))
            observe(session, request, spoken=spoken, field_said_after_s=heard_in)
            assert spoken[:2] == [box_name, f"{box_name} text"]  # the window, then its field
            assert spoken[-2:] == ["a", "b"]  # what's typed, echoed
        finally:
            hands.close()
            probe.close()
    finally:
        _keep(session, request)
        session.close()


@pytest.mark.parametrize("name", COMPOSITORS)
def test_with_orca_the_box_drawn_on_the_overlay_is_never_announced_as_a_window(tmp_path, qapp, name, request):
    """The other side of the test above, as it was before the box became a window for a screen reader: never
    announced as a window (no window:activate). Whether what's typed is echoed is the compositor's: KWin tells Orca
    of every key (its org.freedesktop.a11y keyboard monitor), so Orca echoes them there; sway and Hyprland don't."""
    _needs(name, orca=True)
    session = compositor_session.start(name, tmp_path, atspi=True, orca=True)
    try:
        probe = Probe(session)
        hands = compositor_session.devices(session)
        try:
            probe.call(SETUP + "c.config['accessibility']['accessible_ask_box'] = 'off'")
            assert probe.call("c._reader_seen = float('-inf'); c._reader_running(); c._check_hosting(); result = stage.hosts_windows()")
            since = len(session.orca_log.read_text(encoding="utf-8", errors="replace"))
            hands.click(*centre(penguin(probe)))
            box_name = probe.call("until(lambda: box.isVisible(), 5); result = box.title.text()", settle=1.0)
            hands.type("ab")
            time.sleep(1.5)
            spoken = _spoken(_orca_said(session, since, "never", seconds=0.5))
            observe(session, request, spoken=spoken, echoed="a" in spoken and "b" in spoken)
            assert box_name not in spoken  # no window announced
            if name != "kwin":
                assert "a" not in spoken and "b" not in spoken
        finally:
            hands.close()
            probe.close()
    finally:
        _keep(session, request)
        session.close()
