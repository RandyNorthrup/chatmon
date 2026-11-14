"""The stage when it's the Wayland overlay: the ask box drawn on it, its menus,
its sprites at the screen's real resolution. A pretend surface stands in for
the compositor; tests/test_wayland.py covers the surface itself."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QPoint, QPointF, QRect, Qt, QTimer, QUrl  # noqa: E402
from PyQt6.QtGui import QAction, QImage, QKeySequence, QPainter, QRegion  # noqa: E402
from PyQt6.QtWidgets import QMenu  # noqa: E402

from chatmon import paths, xkb  # noqa: E402
from chatmon.behavior import Behavior  # noqa: E402
from chatmon.bubble import AskBox  # noqa: E402
from chatmon.penguin import Stage  # noqa: E402
from chatmon.sprites import Sprites  # noqa: E402
from chatmon.stagemenu import label_parts  # noqa: E402


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


class Overlay:
    """Records what the stage asks of its surface."""

    hosts_windows = True
    draws_menus = True

    def __init__(self, stage):
        self.focus: list[tuple[bool, bool]] = []
        self.input: list[QRect] = []
        self.damaged = QRegion()
        self.cursor = "default"

    def set_screen(self, screen, geometry):
        pass

    def damage(self, region):
        self.damaged = self.damaged.united(region)

    def set_input(self, rects):
        self.input = list(rects)

    def follow_pointer(self, hit):
        pass

    def device_scale(self):
        return 1.0

    def set_cursor(self, shape):
        self.cursor = shape

    def focus_keyboard(self, on, grab=True):
        self.focus.append((on, grab))

    clipboard = "from another app"
    primary = "selected elsewhere"
    copied: list = []

    def clipboard_has_text(self, which="clipboard"):
        return bool(getattr(self, which))

    def paste(self, then, which="clipboard"):
        then(getattr(self, which))

    def copy(self, text, which="clipboard"):
        self.copied.append((which, text) if which != "clipboard" else text)

    def close(self):
        pass


@pytest.fixture
def stage(qapp):
    sprites = Sprites(paths.anim_dir(), 120)
    s = Stage(sprites, Behavior(sprites.anims(), now=0, x=400), surface_factory=Overlay)
    box = AskBox()
    s.host(box)
    yield s, box
    s.close_stage()


def key(text, qt_key=None, mods=Qt.KeyboardModifier.NoModifier):
    return xkb.Key(qt_key if qt_key is not None else ord(text.upper()), text, mods)


def centre_of(box, widget) -> QPointF:
    return QPointF(widget.mapTo(box, widget.rect().center()) + box.geometry().topLeft())


def test_the_first_open_takes_the_keyboard_and_closing_gives_it_back(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    assert s.surface.focus == [(True, True)]  # even the first open, which sends no Show event
    box.dismiss()
    spin(0.1)
    assert s.surface.focus[-1] == (False, False)
    box.open(QPoint(400, 600), "Hi", "hint", "a name", activate=False)  # nobody asked: click it to type
    spin(0.1)
    assert s.surface.focus[-1] == (True, False)


def test_typing_and_clicking_reach_the_box(stage):
    s, box = stage
    sent = []
    box.submitted.connect(sent.append)
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    for ch in "hi there":
        s.key(key(ch), True, False)
    s.key(key("\r", Qt.Key.Key_Return), True, False)
    assert sent == ["hi there"]
    # the box takes clicks on itself only, not on its see-through margin
    rects = [QRect(*r).translated(s.origin()) for r in s.surface.input]
    assert any(r.contains(box.geometry().center()) for r in rects)
    assert not any(r.contains(box.geometry().bottomLeft() + QPoint(2, -2)) for r in rects)
    # its close button
    close = next(b for b in box.findChildren(type(box.reset_button)) if b.text() == "✕")
    gpos = centre_of(box, close)
    assert s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.LeftButton)
    s.release(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.LeftButton)
    assert not box.isVisible()


def test_it_is_drawn_on_the_stage(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    geo = box.geometry()
    img = QImage(1200, 900, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    s.paint(p, QRegion(0, 0, 1200, 900))
    p.end()
    inside = geo.center() - s.origin()
    assert img.pixelColor(inside).alpha() > 200
    assert s.surface.damaged.intersects(geo.translated(-s.origin()))


def test_its_context_menu_is_drawn_by_the_stage_too(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    gpos = centre_of(box, box.entry)
    s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.RightButton)
    s.release(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.RightButton)
    assert s.menu.is_open()
    labels = [label_parts(i.action)[0] for i in s.menu.panels[0].items if i.kind == "action"]
    assert "Paste" in labels and "Select All" in labels  # no &-marks
    s.close_menu()
    assert not s.menu.is_open()


def test_esc_closes_an_open_menu_not_the_box_under_it(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    gpos = centre_of(box, box.entry)
    s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.RightButton)
    assert s.menu.is_open()
    s.key(key("\x1b", Qt.Key.Key_Escape), True, False)
    s.key(key("\x1b", Qt.Key.Key_Escape), False, False)
    assert not s.menu.is_open() and box.isVisible()  # the menu went, the box stayed
    s.key(key("\x1b", Qt.Key.Key_Escape), True, False)
    assert not box.isVisible()  # with no menu open, Esc is the box's


def test_the_keyboard_picks_from_the_penguins_menu_and_the_overlay_takes_it_while_open(stage):
    s, box = stage
    ran = []
    menu = QMenu()
    menu.addAction("Ask", lambda: ran.append("ask"))
    menu.addAction("Hide", lambda: ran.append("hide"))
    spin(0.1)
    s.open_menu(menu, QPoint(300, 300))
    assert s.surface.focus == [(True, True)]  # a popup menu takes the keyboard
    spin(0.05)
    s.surface.damaged = QRegion()
    for k in (Qt.Key.Key_Down, Qt.Key.Key_Down):
        s.key(key("", k), True, False)
    spin(0.05)
    panel = s.menu.panels[0]
    assert s.surface.damaged.intersects(panel.item_rect(1).translated(panel.rect.topLeft()))  # the lit row drawn again
    s.key(key("\r", Qt.Key.Key_Return), True, False)
    assert ran == ["hide"] and not s.menu.is_open()
    assert s.surface.focus[-1] == (False, False)  # and gives it back
    menu.deleteLater()


def test_closing_the_box_closes_its_context_menu(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    gpos = centre_of(box, box.entry)
    s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.RightButton)
    assert s.menu.is_open()
    box.dismiss()
    spin(0.1)
    assert not s.menu.is_open() and s.surface.input != [(0, 0, s._geo.width(), s._geo.height())]  # not catching every click


def test_the_wheel_scrolls_a_long_menu(stage):
    s, box = stage
    menu = QMenu()
    for i in range(80):
        menu.addAction(f"Chat {i}")
    s.open_menu(menu, QPoint(300, 50))
    panel = s.menu.panels[0]
    assert panel.scrolls()
    centre = QPointF(panel.rect.center())
    s.wheel(centre, centre + QPointF(s.origin()), 0, -120)
    assert panel.scroll > 0
    s.close_menu()
    menu.deleteLater()


class Clock:
    def __init__(self, t=10.0):
        self.t = t

    def __call__(self):
        return self.t


def bubble_point(s, wanted) -> QPointF:
    """A point on the stage over the part of the bubble `wanted` names ("link", "body", a button's index)."""
    box = s._bubble_box
    for y in range(int(box.top()), int(box.bottom())):
        for x in range(int(box.left()), int(box.right())):
            if s.bubble.hit(QPointF(x, y) - box.topLeft()) == wanted:
                return QPointF(x, y)
    raise AssertionError(f"no {wanted} in the bubble")


def test_a_bubble_waits_while_the_pointer_is_on_it(stage):
    s, box = stage
    clock = Clock()
    s._clock = clock
    s.show_message("Reminder", "Stretch your legs, it has been an hour.", timeout_s=3)
    s._tick()
    stay = s.bubble.expires() - clock.t
    on = bubble_point(s, "body")
    clock.t += 1
    s.move(on, on + QPointF(s.origin()))
    clock.t += stay + 5  # long past when it would have gone
    s._tick()
    assert s.message_visible()
    s.pointer_left()
    clock.t += stay - 1 - 0.2  # the rest of its time, nearly
    s._tick()
    assert s.message_visible()
    clock.t += 0.4
    s._tick()
    assert not s.message_visible()


def test_a_link_in_a_bubble_shows_a_hand_and_opens_on_a_click(stage, monkeypatch):
    from chatmon import bubble

    opened = []
    monkeypatch.setattr(bubble, "open_link", lambda url: opened.append(url.toString()))
    s, box = stage
    s.show_message("Answer", "See [the docs](https://example.com/docs) for more.", timeout_s=None)
    spin(0.3)
    link = bubble_point(s, "link")
    gpos = link + QPointF(s.origin())
    s.move(link, gpos)
    assert s.surface.cursor == "pointer"
    assert s.press(link, gpos, Qt.MouseButton.LeftButton)
    s.release(link, gpos, Qt.MouseButton.LeftButton)
    assert opened == ["https://example.com/docs"] and s.message_visible()  # opened, and the bubble stays
    elsewhere = bubble_point(s, "body")
    s.move(elsewhere, elsewhere + QPointF(s.origin()))
    assert s.surface.cursor == "default"


def test_a_bubble_is_never_taller_than_its_share_of_the_stages_screen(stage):
    s, box = stage
    s._use_screen(s.screen(), again=True)
    assert s.bubble.max_height == pytest.approx(0.4 * s.screen().availableGeometry().height())


def test_only_the_ask_boxs_border_is_drawn_again_as_its_art_moves(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    ring = s.hosted.ring()
    geo = box.geometry()
    assert ring.contains(geo.topLeft() + QPoint(3, geo.height() // 2)) and not ring.contains(geo.center())
    frames = iter(range(1000, 2000))
    s.hosted.anim_key = lambda now: next(frames)  # a new frame of its art at every tick
    s._tick()
    s.surface.damaged = QRegion()
    s._tick()
    local = geo.translated(-s.origin())
    assert s.surface.damaged.contains(local.topLeft() + QPoint(3, local.height() // 2))
    assert not s.surface.damaged.contains(local.center())  # the words inside aren't drawn again


def test_a_message_goes_above_the_open_box(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    s.show_message("Reminder", "stretch")
    spin(0.2)
    assert s._bubble_box.bottom() <= box.geometry().top() - s.origin().y()


def test_menu_labels(qapp):
    assert label_parts(QAction("Cu&t\tCtrl+X")) == ("Cut", "Ctrl+X")
    assert label_parts(QAction("Salt && pepper")) == ("Salt & pepper", "")
    menu = QMenu()
    action = menu.addAction("Quit")
    action.setShortcut("Ctrl+Q")
    native = QKeySequence("Ctrl+Q").toString(QKeySequence.SequenceFormat.NativeText)  # ⌘Q on macOS
    assert label_parts(action) == ("Quit", native)


def test_sprites_are_drawn_at_the_screens_resolution(qapp):
    one, two = Sprites(paths.anim_dir(), 120, 1.0), Sprites(paths.anim_dir(), 120, 2.0)
    a, b = one.frame("idle", 0, False), two.frame("idle", 0, False)
    assert abs(a.width() - b.width()) <= 1 and abs(a.height() - b.height()) <= 1  # the same size on screen
    assert b.pixmap.devicePixelRatio() == 2.0 and b.image.height() == 2 * b.height()  # twice the pixels
    assert abs(one.height - two.height) <= 1
    centre = QPoint(a.width() // 2, a.height() // 2)
    assert a.hit(centre.x(), centre.y()) and b.hit(centre.x(), centre.y())
    assert not b.hit(-5, -5)


def test_hosting_the_box_doesnt_open_it(stage):
    """QGraphicsScene.addWidget shows what it embeds; the box must stay closed until asked."""
    s, box = stage
    spin(0.1)
    assert not box.isVisible() and s.surface.focus == []  # no keyboard taken, nothing drawn


def test_input_method_text_goes_into_the_box(stage):
    s, box = stage
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    for ch in "ab":
        s.key(key(ch), True, False)
    state = s.hosted.text_state()
    assert (state.text, state.cursor, state.anchor) == ("ab", 2, 2)
    assert box.geometry().translated(-s.origin()).contains(state.rect.center())  # the caret, on the stage
    s.input_method("にほ", (6, 6), "", 0, 0)  # composing: not in the text yet
    assert box.entry.text() == "ab"
    s.input_method("", None, "日本", 1, 0)  # commit, replacing the "b"
    assert box.entry.text() == "a日本"
    s.keyboard_focus(False)
    assert s.hosted.text_state() is None  # no keyboard here: no input method either


def test_the_box_uses_the_overlays_clipboard(stage):
    s, box = stage
    s.surface.copied = []
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    ctrl = Qt.KeyboardModifier.ControlModifier
    s.key(key("\x16", Qt.Key.Key_V, ctrl), True, False)
    assert box.entry.text() == "from another app"
    s.key(key("\x01", Qt.Key.Key_A, ctrl), True, False)
    s.key(key("\x03", Qt.Key.Key_C, ctrl), True, False)
    assert s.surface.copied == ["from another app"]
    s.surface.clipboard = "two\nlines"
    s.key(key("\x16", Qt.Key.Key_V, ctrl), True, False)  # replaces the selection, on one line
    assert box.entry.text() == "two lines"
    s.key(key("\x01", Qt.Key.Key_A, ctrl), True, False)
    s.key(key("\x18", Qt.Key.Key_X, ctrl), True, False)
    assert box.entry.text() == "" and s.surface.copied[-1] == "two lines"
    # the right-click menu's clipboard items do the same
    gpos = centre_of(box, box.entry)
    s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.RightButton)
    paste = next(i.action for i in s.menu.panels[0].items if i.action.objectName() == "edit-paste")
    assert paste.isEnabled()
    s.close_menu()
    paste.trigger()
    assert box.entry.text() == "two lines"


def test_ctrl_v_pastes_under_a_russian_layout(stage):
    """The keys the overlay's keyboard makes from a us,ru keymap with Russian active, as the stage gets them."""
    lib = xkb.library()
    if lib is None:
        pytest.skip("libxkbcommon isn't installed (the overlay is Linux only)")
    s, box = stage
    board = xkb.Keyboard(lib, xkb.keymap_from_names(lib, "us,ru"))
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    board.set_modifiers(0, 0, 0, 1)
    s.key(board.press(47), True, False)  # the key that is V in the US: a Russian letter
    assert box.entry.text() == "м"
    board.set_modifiers(4, 0, 0, 1)  # Ctrl
    s.key(board.press(47), True, False)
    assert box.entry.text() == "мfrom another app"
    board.close()


def test_selecting_is_the_primary_selection_and_middle_click_pastes_it(stage):
    s, box = stage
    s.surface.copied = []
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    for ch in "hello":
        s.key(key(ch), True, False)
    s.key(key("\x01", Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier), True, False)
    spin(0.1)
    assert ("primary", "hello") in s.surface.copied
    gpos = centre_of(box, box.entry)
    s.press(gpos - QPointF(s.origin()), gpos, Qt.MouseButton.MiddleButton)
    assert "selected elsewhere" in box.entry.text()


def test_files_pictures_and_long_text_paste_into_the_box_as_attachments(stage, tmp_path):
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QImage

    s, box = stage
    pasted = []
    box.pasted.connect(lambda kind, payload: pasted.append((kind, payload)))
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    s.keyboard_focus(True)
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0)
    png = QByteArray()
    buffer = QBuffer(png)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    notes = tmp_path / "my notes.txt"
    ctrl = Qt.KeyboardModifier.ControlModifier
    for offered in (
        ("text/uri-list", f"{QUrl.fromLocalFile(str(notes)).toString()}\r\n".encode()),
        ("image/png", bytes(png)),
        ("text/plain", ("a long log line\n" * 20).encode()),
        ("text/plain", b"short"),
    ):
        s.surface.paste_rich = lambda then, offered=offered: then(*offered)
        s.key(key("\x16", Qt.Key.Key_V, ctrl), True, False)
    assert pasted[0] == ("files", [str(notes)])
    assert pasted[1][0] == "image" and pasted[1][1].width() == 4
    assert pasted[2][0] == "text" and pasted[2][1].startswith("a long log line")
    assert len(pasted) == 3 and box.entry.text() == "short"  # short text is typed in, as before


def test_a_drop_lands_in_the_open_ask_box_only(stage, tmp_path):
    s, box = stage
    pasted = []
    box.pasted.connect(lambda kind, payload: pasted.append((kind, payload)))
    inside = centre_of(box, box.entry) if box.isVisible() else None
    assert inside is None or not s.drop_at(inside)
    box.open(QPoint(400, 600), "Ask", "hint", "placeholder")
    spin(0.1)
    inside = centre_of(box, box.entry)
    assert s.drop_at(inside) and not s.drop_at(QPointF(5, 5))
    notes = tmp_path / "notes.txt"
    s.dropped("text/uri-list", f"{QUrl.fromLocalFile(str(notes)).toString()}\r\n".encode())
    assert pasted == [("files", [str(notes)])]
