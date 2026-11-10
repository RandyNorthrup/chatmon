"""The stage when it's the Wayland overlay: the ask box drawn on it, its menus,
its sprites at the screen's real resolution. A pretend surface stands in for
the compositor; tests/test_wayland.py covers the surface itself."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QPoint, QPointF, QRect, Qt, QTimer  # noqa: E402
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
    rects = [r.translated(s.origin()) for r in s.surface.input]
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
