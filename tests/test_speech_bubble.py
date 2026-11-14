"""Speech bubbles: they fit on the screen, their titles and buttons fit in them, they stay long enough to read,
and their links work (M2-03, M2-04, M2-07, M2-08, M2-09)."""

import pytest
from PyQt6.QtCore import QPointF, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QFontMetricsF, QGuiApplication
from PyQt6.QtWidgets import QApplication

from chatmon import bubble, styles
from chatmon.bubble import SpeechBubble, TimeoutPolicy, text_lines

LONG = "\n\n".join(f"Paragraph {i}: the build log said something worth reading about this step." for i in range(60))
STYLES = ["electric", "leaf", "plain"]


def make(name: str = "electric") -> SpeechBubble:
    message = SpeechBubble()
    message.set_style(styles.get(name), False)
    return message


@pytest.mark.parametrize("name", STYLES)
def test_a_long_message_is_capped_and_more_has_the_rest(qapp, name):
    message = make(name)
    asked = []
    message.on_more = lambda title, text: asked.append((title, text))
    message.max_height = 320
    message.show("Build log", LONG, [("Open it", None)], None, 0.0)
    assert message.size.height() <= 320
    labels = [b.label for b in message.buttons]
    assert labels == ["Open it", SpeechBubble.MORE]
    capped = message.size.height()
    message.show("Build log", LONG + "\n\nAnd more.", [("Open it", None)], None, 1.0)
    assert message.size.height() == capped  # longer text, same height: it's cut, not grown
    message.buttons[-1].action()
    assert asked == [("Build log", LONG + "\n\nAnd more.")]


def test_without_a_more_handler_it_is_still_capped(qapp):
    message = make()
    message.show("Build log", LONG, [], None, 0.0)
    screen = QGuiApplication.primaryScreen().availableGeometry().height()
    assert message.size.height() <= SpeechBubble.SCREEN_SHARE * screen
    assert message.buttons == []


def test_a_short_message_is_not_cut(qapp):
    message = make()
    message.on_more = lambda title, text: None
    message.show("Hi", "Just a line.", [("OK", None)], None, 0.0)
    assert [b.label for b in message.buttons] == ["OK"]
    assert message._clip is None


@pytest.mark.parametrize("name", STYLES)
def test_buttons_wrap_onto_rows_inside_the_bubble(qapp, name):
    message = make(name)
    specs = [(f"Snooze for {m} minutes", None) for m in (5, 10, 15, 30, 60)] + [("Done", None)]
    message.show("Reminder", "Stretch.", specs, None, 0.0)
    rects = [b.rect for b in message.buttons]
    assert len({round(r.top()) for r in rects}) > 1, "more than one row"
    content = message._content
    for i, r in enumerate(rects):
        assert content.left() - 0.5 <= r.left() and r.right() <= content.right() + 0.5, i
        assert 0 <= r.top() and r.bottom() <= message.size.height()
        for other in rects[i + 1 :]:
            assert not r.intersects(other), "buttons don't overlap"
    assert content.width() <= message._max_width(message.doc.defaultFont()) - 2 * bubble.PAD + 0.5


def test_a_long_title_wraps_to_two_lines_and_is_cut_short(qapp):
    font = QFont(QApplication.font())
    font.setPointSizeF(10.5)
    lines = text_lines("A title so long that it can't possibly fit on one line, or even on two of them, in a bubble", font, 200, 2)
    assert len(lines) == 2 and lines[-1].endswith("…")
    assert all(QFontMetricsF(font).horizontalAdvance(line) <= 200 + 0.5 for line in lines)
    assert text_lines("Short", font, 200, 2) == ["Short"]


@pytest.mark.parametrize("name", STYLES)
def test_a_long_title_stays_inside_the_bubble_and_clear_of_the_close_button(qapp, name):
    message = make(name)
    message.show("A title so long that it can't possibly fit on one line, or even on two of them, in any bubble", "Body.", [], None, 0.0)
    metrics = QFontMetricsF(message._title_font)
    assert len(message._title_lines) == 2
    room = message._content.width() - SpeechBubble.CLOSE_W
    assert all(metrics.horizontalAdvance(line) <= room + 0.5 for line in message._title_lines)
    assert message._body_top >= message._content.top() + 2 * metrics.lineSpacing()  # the text starts below both lines
    assert message._close_rect.left() >= message._content.left() + room - 1


def test_a_bubble_stays_long_enough_to_read(qapp):
    message = make()
    message.show("Focus stopped", "", [], 3, 0.0)  # 2 words: 4 + 0.6 s, more than the 3 asked
    message.tick(4.5)
    assert message.visible()
    message.tick(4.7)
    assert not message.visible()
    words = " ".join(["word"] * 48)  # 50 words with the title's two: 4 + 15 = 19 s, more than 12
    message.show("Two words", words, [], 12, 100.0)
    message.tick(118.9)
    assert message.visible()
    message.tick(119.1)
    assert not message.visible()
    message.show("Asked for longer", "", [], 30, 200.0)  # a long timeout asked for is kept
    message.tick(229)
    assert message.visible()


def test_the_policy_can_keep_bubbles_until_closed_or_longer(qapp):
    message = make()
    message.timeout_policy = TimeoutPolicy(until_closed=True)
    message.show("Hi", "there", [], 5, 0.0)
    message.tick(10_000)
    assert message.visible()
    message.timeout_policy = TimeoutPolicy(factor=2.0)
    message.show("Hi", "there", [], 5, 0.0)  # 5 s asked, 4.6 to read: 10 s
    message.tick(9.9)
    assert message.visible()
    message.tick(10.1)
    assert not message.visible()
    message.timeout_policy = TimeoutPolicy()
    message.show("An alert", "Stays until answered.", [("OK", None)], None, 0.0)
    message.tick(10_000)
    assert message.visible()


def test_a_hovered_bubble_waits_and_then_goes_on_from_where_it_was(qapp):
    message = make()
    message.show("Focus stopped", "", [], 3, 0.0)  # goes at 4.6
    message.tick(1.0)
    message.set_hovered(True)  # at the clock last told: 1.0
    message.tick(30.0)
    assert message.visible(), "it doesn't go while it's being read"
    message.set_hovered(False, 30.0)  # 29 s hovered: it goes at 33.6
    message.tick(33.5)
    assert message.visible()
    message.tick(33.7)
    assert not message.visible()


def link_points(message: SpeechBubble) -> dict[str, list[QPointF]]:
    """Every point over the text, by what link_at says is there."""
    found: dict[str, list[QPointF]] = {}
    c = message._content
    y = message._body_top
    while y < c.bottom():
        x = c.left()
        while x < c.right():
            url = message.link_at(QPointF(x, y))
            found.setdefault(url.toString() if url else "", []).append(QPointF(x, y))
            x += 2
        y += 2
    return found


def test_links_in_a_bubble_can_be_clicked_but_only_safe_ones(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    message = make()
    message.show("Links", "Read [the docs](https://example.com/docs), [write](mailto:help@example.com) or [this](file:///etc/passwd).", [("OK", None)], None, 0.0)
    found = link_points(message)
    assert set(found) == {"", "https://example.com/docs", "mailto:help@example.com"}
    for url, points in found.items():
        if url:
            assert message.hit(points[0]) == "link"
            assert message.open_link_at(points[0])
    assert opened == ["https://example.com/docs", "mailto:help@example.com"]
    # the file: link is there, and is drawn as one, but isn't offered or opened
    layout = message.doc.documentLayout()
    over_file = [p for p in found[""] if layout.anchorAt(p - QPointF(message._content.x(), message._body_top)).startswith("file:")]
    assert over_file, "the test reaches the file: link"
    assert message.hit(over_file[0]) == "body" and not message.open_link_at(over_file[0])
    assert opened == ["https://example.com/docs", "mailto:help@example.com"]


def test_only_safe_schemes_ever_open(qapp, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.scheme()) or True)
    for url in ("https://a.example", "http://a.example", "mailto:x@y.z", "file:///etc/passwd", "smb://server/share", "javascript:alert(1)", "chatmon-copy:x/1"):
        bubble.open_link(QUrl(url))
    assert opened == ["https", "http", "mailto"]


@pytest.fixture
def big_desktop_font(qapp):
    old = QFont(QApplication.font())
    font = QFont(old)
    font.setPointSizeF(16)
    QApplication.setFont(font)
    yield
    QApplication.setFont(old)


def test_text_follows_a_larger_desktop_font(big_desktop_font):
    message = make()
    message.show("Hi", "Some text to read " * 10, [], None, 0.0)
    assert message.doc.defaultFont().pointSizeF() == pytest.approx(16)
    assert message._title_font.pointSizeF() == pytest.approx(16)


def test_the_text_size_setting_scales_text_and_widths(qapp):
    small, large = make(), make()
    large.set_text_scale(1.5)
    for message in (small, large):
        message.show("Hi", "Some text to read, " * 30, [("OK", None)], None, 0.0)
    assert large.doc.defaultFont().pointSizeF() == pytest.approx(small.doc.defaultFont().pointSizeF() * 1.5)
    assert large.size.width() > small.size.width() * 1.3
    large.set_text_scale(100)
    assert large.text_scale == 3.0
