"""The ask box: keyboard focus shows, the field takes several lines, a chat opens at its newest exchange, the box
can be made bigger, answers and code can be copied, an answer on its way can be watched and stopped, and the box
fades (M2-06, M2-07, M2-10, M2-11, M2-12, M2-16, M2-18, M2-19)."""

import time

import pytest
from PyQt6.QtCore import QEventLoop, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QTextFormat
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QToolButton

from chatmon import bubble, richtext, styles
from chatmon.bubble import AskBox

STYLES = ["electric", "fire", "ghost", "fairy", "leaf", "plain"]
CHAT = "\n\n".join(
    ["**You:** first question", "First answer.", "**You:** second question", "Second answer."]
    + ["**You:** and the newest one", "Here is a long answer."]
    + [f"Paragraph {i} of the long answer, which goes on for a while." for i in range(40)]
)


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


@pytest.fixture
def box(qapp):
    box = AskBox()
    box.set_reduced_motion(True)  # most tests don't watch it fade
    yield box
    box.set_busy(None)
    box.hide()
    box.deleteLater()
    spin(0.01)


def open_chat(box: AskBox, text: str = "", at_end: bool = False, activate: bool = False) -> None:
    box.open(QPoint(700, 900), "Ask Sparky", "Enter to ask · Shift+Enter for a new line", "Ask anything", text=text, activate=activate)
    box.chatting(True)
    if text:
        box.set_answer(text, at_end=at_end)


# -- focus (M2-06)


def ring(box: AskBox, control, colour: QColor) -> int:
    """How many of the points 1 px in from the middle of each edge of `control`, as drawn in the box (on its
    bubble), are `colour`: 4 with a full outline."""
    img = box.grab(QRect(control.mapTo(box, QPoint(0, 0)), control.size())).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    points = [(1, h // 2), (w - 2, h // 2), (w // 2, 1), (w // 2, h - 2)]
    return sum(1 for x, y in points if abs(img.pixelColor(x, y).red() - colour.red()) < 40 and abs(img.pixelColor(x, y).green() - colour.green()) < 40 and abs(img.pixelColor(x, y).blue() - colour.blue()) < 40 and img.pixelColor(x, y).alpha() > 200)


@pytest.mark.parametrize("name", STYLES)
def test_every_control_shows_a_focus_outline(box, name):
    box.set_style(styles.get(name), False)
    open_chat(box, "**You:** hi\n\nHello.", activate=True)
    box.set_attachments(["notes.md (2 KB)"])
    box.set_resettable(True)
    box.set_busy("Claude", time.monotonic())
    box.activateWindow()
    spin(0.05)
    focus = styles.get(name).colours().title
    chip = next(b for b in box.chips.findChildren(QToolButton) if b.objectName() == "chip")
    close = next(b for b in box.findChildren(QToolButton) if b.accessibleName() == "Close")
    controls = {
        "History": box.history_button, "New chat": box.reset_button, "Expand": box.expand_button, "Close": close,
        "Attach": box.attach_button, "chip": chip, "Stop": box.stop_button, "field": box.entry,
    }
    for what, control in controls.items():
        box.answer.setFocus()
        spin(0.01)
        assert ring(box, control, focus) < 4, f"{what} has no outline without the focus"
        control.setFocus(Qt.FocusReason.TabFocusReason)
        spin(0.01)
        assert control.hasFocus(), what
        assert ring(box, control, focus) == 4, f"{what} shows its focus ({name})"


@pytest.mark.parametrize("name", STYLES)
def test_the_focus_colour_stands_out_from_the_bubble(qapp, name):
    c = styles.get(name).colours()
    assert styles.contrast(c.title, c.fill) >= 3.0 and styles.contrast(c.title, c.accent) >= 1.5  # unlike the borders it replaces


# -- text size (M2-07)


def test_the_text_size_setting_grows_the_box_and_its_text(box):
    open_chat(box, "**You:** hi\n\nHello there.")
    width, points = box.width(), box.answer.document().defaultFont().pointSizeF()
    box.set_text_scale(1.5)
    assert box.width() == pytest.approx(width * 1.5, abs=2)
    assert box.answer.document().defaultFont().pointSizeF() == pytest.approx(points * 1.5)
    assert box.entry.font().pointSizeF() == pytest.approx(points * 1.5, abs=0.1)


@pytest.fixture
def big_desktop_font(qapp):
    old = QFont(QApplication.font())
    font = QFont(old)
    font.setPointSizeF(16)
    QApplication.setFont(font)
    yield
    QApplication.setFont(old)


def test_a_larger_desktop_font_grows_the_box(big_desktop_font):
    box = AskBox()
    try:
        open_chat(box, "**You:** hi\n\nHello there.")
        assert box.answer.document().defaultFont().pointSizeF() == pytest.approx(16)
        assert box.width() > AskBox.WIDTH * 1.4
    finally:
        box.hide()
        box.deleteLater()


# -- the newest exchange first (M2-10)


def newest_top(box: AskBox) -> int:
    doc = box.answer.document()
    starts = [b for b in iter_blocks(doc) if b.text().startswith("You: and the newest")]
    return int(doc.documentLayout().blockBoundingRect(starts[0]).top())


def iter_blocks(doc):
    block = doc.begin()
    while block.isValid():
        yield block
        block = block.next()


def test_a_long_answer_opens_at_the_start_of_the_newest_exchange(box):
    open_chat(box, CHAT, at_end=True)
    spin(0.05)
    bar = box.answer.verticalScrollBar()
    assert bar.maximum() > 0, "the chat is longer than the box"
    assert bar.value() == newest_top(box) and bar.value() < bar.maximum(), "its question at the top, not the answer's end"
    box.set_answer(CHAT, at_end=False)
    spin(0.05)
    assert bar.value() == 0


def test_turns_are_ruled_apart(box):
    open_chat(box, CHAT, at_end=True)
    rules = [b for b in iter_blocks(box.answer.document()) if b.blockFormat().hasProperty(QTextFormat.Property.BlockTrailingHorizontalRulerWidth)]
    assert len(rules) == 2  # three turns


# -- bigger (M2-11)


def test_the_box_can_be_made_bigger_and_back(box):
    changed = []
    box.expand_changed.connect(changed.append)
    open_chat(box, CHAT, at_end=True)
    small = box.size()
    box.expand_button.click()
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert changed == [True] and box.expanded
    assert box.height() > small.height() and box.height() <= AskBox.SCREEN_SHARE * screen.height() + 1
    assert box.height() >= 0.45 * screen.height(), "it takes about 55% of the screen's height"
    assert box.width() == pytest.approx(min(small.width() * AskBox.EXPANDED_WIDTH, screen.width() * 0.9), abs=2)
    assert box.expand_button.accessibleName() == "Make the box smaller"
    box.expand_button.click()
    assert changed == [True, False] and box.size() == small
    assert box.expand_button.accessibleName() == "Make the box bigger"


def test_collapsed_the_box_never_passes_its_share_of_the_screen(box):
    open_chat(box, CHAT, at_end=True)
    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert box.height() <= AskBox.SCREEN_SHARE * screen.height() + 1


# -- several lines (M2-12)


def test_shift_enter_adds_a_line_and_enter_sends_it_all(box):
    sent = []
    box.submitted.connect(sent.append)
    open_chat(box, activate=True)
    one_line = box.entry.height()
    QTest.keyClicks(box.entry, "line one")
    QTest.keyClick(box.entry, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(box.entry, "line two")
    QTest.keyClick(box.entry, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClicks(box.entry, "line three")
    assert box.entry.text() == "line one\nline two\nline three"
    assert box.entry.height() > one_line * 2, "it grew to show them"
    QTest.keyClick(box.entry, Qt.Key.Key_Return)
    assert sent == ["line one\nline two\nline three"] and box.entry.text() == ""
    spin(0.01)
    assert box.entry.height() == one_line, "and back to one line"


def test_a_short_paste_keeps_its_line_breaks(box):
    open_chat(box, activate=True)
    box.take_paste("text", "def f():\n    return 1\n")
    assert box.entry.text() == "def f():\n    return 1\n"


def test_a_name_stays_on_one_line(box):
    sent = []
    box.submitted.connect(sent.append)
    box.open(QPoint(700, 900), "Name your chatmon", "Enter to save", "A name", activate=True)
    box.chatting(False)
    box.take_paste("text", "Sparky\nthe\nBrave")
    assert box.entry.text() == "Sparky the Brave"
    QTest.keyClick(box.entry, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert sent == ["Sparky the Brave"]


def test_the_field_keeps_the_calls_the_app_and_overlay_use(box):
    open_chat(box, activate=True)
    e = box.entry
    e.setText("first\nsecond")
    assert e.text() == "first\nsecond"
    e.selectAll()
    assert e.hasSelectedText() and e.selectedText() == "first\nsecond"
    assert e.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection) == "first\nsecond"  # Qt's own answer can't reach Python
    e.end(False)
    e.insert(" and third")
    assert e.text() == "first\nsecond and third"
    e.clear()
    assert e.text() == ""
    box.set_answer("Some words to select.")
    box.answer.selectAll()
    assert box.answer.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection) == "Some words to select."


# -- Copy (M2-16)


def copy_links(box: AskBox) -> list[tuple[str, QPoint]]:
    """Each Copy link's href and a point on it, in the answer's viewport, scrolled to."""
    doc = box.answer.document()
    out = []
    for block in iter_blocks(doc):
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            href = fragment.charFormat().anchorHref()
            if href.startswith(richtext.COPY_SCHEME):
                out.append((href, block, fragment.position() - block.position()))
            it += 1
    return out


def click_link(box: AskBox, block, offset: int) -> None:
    doc = box.answer.document()
    rect = doc.documentLayout().blockBoundingRect(block)
    line = block.layout().lineForTextPosition(offset)
    bar = box.answer.verticalScrollBar()
    bar.setValue(int(rect.top()))
    x = rect.left() + line.cursorToX(offset)[0] + 4
    y = rect.top() + line.y() + line.height() / 2 - bar.value()
    QTest.mouseClick(box.answer.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(x), int(y)))


def test_each_answer_and_code_block_can_be_copied(box):
    copied = []
    box.copy_requested.connect(copied.append)
    chat = "**You:** how?\n\nLike this:\n\n```python\nprint(1)\n```\n\n**You:** and then?\n\nThat's it."
    open_chat(box, chat, at_end=True)
    links = copy_links(box)
    assert len(links) == 3  # the code block, and each answer
    for _, block, offset in links:
        click_link(box, block, offset)
    assert copied[0] == "print(1)"
    assert copied[1].startswith("Like this:") and "print(1)" in copied[1] and "Copy" not in copied[1]
    assert copied[2] == "That's it."


def test_a_copy_link_written_by_an_answer_copies_nothing(box, monkeypatch):
    opened = []
    monkeypatch.setattr(bubble, "open_link", lambda url: opened.append(url.toString()))
    copied = []
    box.copy_requested.connect(copied.append)
    open_chat(box, "**You:** hi\n\n[Copy](chatmon-copy:0000/0) this.", at_end=True)
    forged = [(b, o) for href, b, o in copy_links(box) if href.endswith(":0000/0")]
    assert forged
    click_link(box, *forged[0])
    assert copied == [] and opened == ["chatmon-copy:0000/0"]  # handed to open_link, which opens only the web


def test_an_answer_still_coming_has_no_copy_link(box):
    open_chat(box, "**You:** hi\n\nHello.\n\n**You:** more?", at_end=True)
    box.set_busy("Claude", time.monotonic())
    box.append_partial("Coming")
    spin(0.2)
    hrefs = [h for h, _, _ in copy_links(box)]
    assert len(hrefs) == 1  # the first answer's only


# -- busy, Stop and streamed text (M2-18)


def test_an_answer_on_its_way_shows_who_and_how_long_and_can_be_stopped(box):
    stops = []
    box.stop_requested.connect(lambda: stops.append(1))
    open_chat(box, "**You:** hi", at_end=True)
    box.set_busy("Claude", time.monotonic() - 12.2)
    assert box.busy.isVisibleTo(box) and box.stop_button.isVisibleTo(box)
    assert box.busy_label.text() == "Claude is answering… 12 s"
    spin(1.1)
    assert box.busy_label.text() == "Claude is answering… 13 s", "it counts each second"
    box.stop_button.click()
    assert stops == [1]
    box.set_busy(None)
    assert not box.busy.isVisibleTo(box) and not box._busy_clock.isActive()


def test_streamed_text_shows_as_it_comes_and_the_answer_replaces_it(box):
    open_chat(box, "**You:** hi", at_end=True)
    box.set_busy("Claude", time.monotonic())
    box.append_partial("Hello ")
    box.append_partial("there, **friend**")
    spin(0.2)
    assert "Hello there, friend" in box.answer.toPlainText() and "You: hi" in box.answer.toPlainText()
    box.set_partial("Hi again")
    spin(0.2)
    assert "Hi again" in box.answer.toPlainText() and "Hello" not in box.answer.toPlainText()
    box.set_busy(None)
    box.set_answer("**You:** hi\n\nThe whole answer.", at_end=True)
    spin(0.2)
    assert "The whole answer." in box.answer.toPlainText() and "Hi again" not in box.answer.toPlainText()


def test_hiding_stops_every_clock(box):
    open_chat(box, "**You:** hi", at_end=True)
    box.set_busy("Claude", time.monotonic())
    box.append_partial("x")
    box.hide()
    assert [t for t in box.findChildren(QTimer) if t.isActive()] == []


# -- fades (M2-19)


def ghosts() -> list:
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, bubble._Ghost) and w.isVisible()]


def test_it_fades_in_and_out(qapp):
    box = AskBox()
    closed = []
    box.closed.connect(lambda: closed.append(1))
    try:
        box.open(QPoint(700, 900), "Ask", "hint", "", activate=False)
        assert box.windowOpacity() < 0.5, "it starts see-through"
        spin(0.35)
        assert box.windowOpacity() == pytest.approx(1.0)
        geometry = box.geometry()
        box.dismiss()
        assert not box.isVisible() and closed == [1], "closed at once, as far as anyone is concerned"
        fading = ghosts()
        assert len(fading) == 1 and fading[0].geometry() == geometry
        spin(0.4)
        assert ghosts() == []
    finally:
        box.hide()
        box.deleteLater()


def test_with_reduced_motion_it_comes_and_goes_at_once(box):
    box.open(QPoint(700, 900), "Ask", "hint", "", activate=False)
    assert box.windowOpacity() == pytest.approx(1.0)
    box.dismiss()
    assert not box.isVisible() and ghosts() == []
