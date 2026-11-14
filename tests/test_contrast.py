"""Every colour a bubble puts text in can be read (M2-05, M2-20).

The ratios here are WCAG 2.x contrast ratios computed by the test's own formula, checked against known values,
not by the module's. Text and links need 4.5:1 against what they sit on; a control's outline and the focus ring
need 3:1. Each painted style's fill is measured from its art, so a repainted bubble can't quietly break them.
"""

import json

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QImage, QPainter, QPalette
from PyQt6.QtWidgets import QApplication

from chatmon import bubbleart, paths, styles
from chatmon.bubble import AskBox, SpeechBubble

PAINTED = ["electric", "fire", "ghost", "fairy", "leaf"]
TEXT, OUTLINE = 4.5, 3.0


def wcag(a: QColor, b: QColor) -> float:
    def lum(c: QColor) -> float:
        out = 0.0
        for weight, v in ((0.2126, c.red()), (0.7152, c.green()), (0.0722, c.blue())):
            s = v / 255
            out += weight * (s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
        return out

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_test_formula_and_the_modules_agree_on_known_ratios(qapp):
    for a, b, ratio in (("#000000", "#ffffff", 21.0), ("#777777", "#ffffff", 4.48), ("#ffffff", "#26b8d9", 2.35), ("#ffffff", "#ffffff", 1.0)):
        assert wcag(QColor(a), QColor(b)) == pytest.approx(ratio, abs=0.01)
        assert styles.contrast(QColor(a), QColor(b)) == pytest.approx(ratio, abs=0.01)


def text_area_pixels(name: str) -> list[QColor]:
    """Colours across where a style's art has text drawn: its fill, inside the padding kept round the text."""
    entry = json.loads((paths.bubbles_dir() / "manifest.json").read_text(encoding="utf-8"))[name]
    img = QImage(str(paths.bubbles_dir() / f"{name}-still.png")).convertToFormat(QImage.Format.Format_ARGB32)
    art = bubbleart.art(name, "contrast test")
    inset = art.pad / art.k  # art px
    x0, y0, x1, y1 = (v + d for v, d in zip(entry["text"], (inset, inset, -inset, -inset), strict=True))
    return [img.pixelColor(int(x0 + fx * (x1 - x0)), int(y0 + fy * (y1 - y0))) for fx in (0.0, 0.25, 0.5, 0.75, 1.0) for fy in (0.0, 0.5, 1.0)]


def pairs(c: styles.Colours) -> list[tuple[str, QColor, QColor, float]]:
    """(what, foreground, background, ratio needed) for everything drawn in a bubble."""
    out = [
        ("title", c.title, c.fill, TEXT), ("body", c.body, c.fill, TEXT), ("hint", c.dim, c.fill, TEXT),
        ("link", c.link, c.fill, TEXT), ("selected text", c.selection_text, c.selection, TEXT),
        ("field text", c.entry_text, c.entry, TEXT), ("field hint", c.placeholder, c.entry, TEXT),
        ("code", c.body, c.code_fill, TEXT), ("link in code's panel", c.link, c.code_fill, TEXT),
        ("focus ring", c.accent, c.fill, OUTLINE), ("field border", c.accent, c.fill, OUTLINE),
    ]
    for which, b in (("primary", c.primary), ("other", c.other)):
        out.append((f"{which} label", b.text, b.fill if b.fill is not None else c.fill, TEXT))
        out.append((f"{which} label lit up", b.hover_text, b.hover_fill, TEXT))
        if b.fill is None or wcag(b.fill, c.fill) < OUTLINE:  # its outline is what shows where it is
            out.append((f"{which} outline", b.outline, c.fill, OUTLINE))
    return out


@pytest.mark.parametrize("name", PAINTED)
def test_a_painted_styles_fill_is_its_arts(qapp, name):
    fill = QColor(styles.get(name).fill)
    for pixel in text_area_pixels(name):
        assert pixel.alpha() >= 250  # the desktop shows through by a trace at most
        assert max(abs(pixel.red() - fill.red()), abs(pixel.green() - fill.green()), abs(pixel.blue() - fill.blue())) <= 24, (name, pixel.name())


@pytest.mark.parametrize("name", PAINTED)
def test_every_painted_style_reads_on_every_part_of_its_bubble(qapp, name):
    c = styles.get(name).colours()
    short = []
    for pixel in text_area_pixels(name):  # the worst spot of the fill, not its average
        real = styles.Colours(**{**c.__dict__, "fill": pixel})
        short += [(what, round(wcag(fg, bg), 2)) for what, fg, bg, need in pairs(real) if wcag(fg, bg) < need]
    assert short == [], f"{name}: {sorted(set(short))}"


@pytest.mark.parametrize("name", PAINTED)
def test_links_and_selections_reach_aa_on_their_bubble(qapp, name):
    """M2-20 on its own: the pairs the assessment found short (fairy's links were 2.6:1)."""
    c = styles.get(name).colours()
    assert wcag(c.link, c.fill) >= TEXT, f"{name} links: {wcag(c.link, c.fill):.2f}"
    assert wcag(c.selection_text, c.selection) >= TEXT, f"{name} selection: {wcag(c.selection_text, c.selection):.2f}"


def palette(base, text, highlight, highlighted, link, button, button_text) -> QPalette:
    pal = QPalette(QApplication.palette())
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, colour in (
            (QPalette.ColorRole.Base, base), (QPalette.ColorRole.Text, text), (QPalette.ColorRole.Highlight, highlight),
            (QPalette.ColorRole.HighlightedText, highlighted), (QPalette.ColorRole.Link, link),
            (QPalette.ColorRole.Button, button), (QPalette.ColorRole.ButtonText, button_text),
        ):
            pal.setColor(group, role, QColor(colour))
    return pal


HIGH_CONTRAST = {
    "windows high contrast black": palette("#000000", "#ffffff", "#1aebff", "#000000", "#ffff00", "#000000", "#ffffff"),
    "windows high contrast white": palette("#ffffff", "#000000", "#37006e", "#ffffff", "#00009f", "#ffffff", "#000000"),
}
ORDINARY = {
    "light": palette("#ffffff", "#1d1d1d", "#3584e4", "#ffffff", "#1a5fb4", "#f6f5f4", "#2e3436"),
    "dark": palette("#1e1e1e", "#e6e6e6", "#3d7bd9", "#ffffff", "#78aeed", "#2d2d2d", "#f0f0f0"),
    "faint": palette("#ffffff", "#999999", "#26b8d9", "#ffffff", "#66aaff", "#eeeeee", "#aaaaaa"),  # every pair short
}


@pytest.mark.parametrize("name", list(HIGH_CONTRAST))
def test_the_plain_style_wears_a_high_contrast_theme_as_it_is(qapp, name):
    pal = HIGH_CONTRAST[name]
    c = styles.get("plain").colours(pal)

    def role(r):
        return QColor(pal.color(QPalette.ColorGroup.Active, r))

    assert c.fill == role(QPalette.ColorRole.Base) and c.body == role(QPalette.ColorRole.Text)
    assert c.link == role(QPalette.ColorRole.Link)
    assert c.selection == role(QPalette.ColorRole.Highlight) and c.selection_text == role(QPalette.ColorRole.HighlightedText)
    assert c.primary.fill == role(QPalette.ColorRole.Highlight) and c.primary.text == role(QPalette.ColorRole.HighlightedText)
    assert c.other.fill == role(QPalette.ColorRole.Button) and c.other.text == role(QPalette.ColorRole.ButtonText)
    assert [(w, round(wcag(fg, bg), 2)) for w, fg, bg, need in pairs(c) if wcag(fg, bg) < need] == []


@pytest.mark.parametrize("name", list(ORDINARY))
def test_the_plain_style_reads_whatever_the_palette(qapp, name):
    pal = ORDINARY[name]
    c = styles.get("plain").colours(pal)
    assert [(w, round(wcag(fg, bg), 2)) for w, fg, bg, need in pairs(c) if wcag(fg, bg) < need] == []
    link = QColor(pal.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Link))
    assert c.link.blue() >= c.link.red() and (c.link == link or wcag(link, c.fill) < TEXT)  # still the theme's blue; changed only if short


@pytest.fixture
def high_contrast(qapp):
    old = QPalette(QApplication.palette())
    QApplication.setPalette(HIGH_CONTRAST["windows high contrast black"])
    yield HIGH_CONTRAST["windows high contrast black"]
    QApplication.setPalette(old)


def colour_count(img: QImage, colour: QColor) -> int:
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    return sum(1 for y in range(img.height()) for x in range(img.width()) if img.pixelColor(x, y) == colour)


def test_the_plain_bubble_draws_in_the_palettes_colours(high_contrast):
    """The plain bubble's border and its first button take Highlight; no fixed cyan is left."""
    message = SpeechBubble()
    message.set_style(styles.get("plain"), False)
    message.show("Reminder", "Stretch, and see [the notes](https://example.com).", [("Done", None), ("Later", None)], None, 0.0)
    img = QImage(message.size.toSize().width() + 10, message.size.toSize().height() + 10, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    message.paint(p, message.size.width() / 2, 1.0)
    p.end()
    highlight = high_contrast.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
    assert colour_count(img, highlight) > 100  # the border and the first button
    assert colour_count(img, QColor(styles.PLAIN_ACCENT)) == 0
    link = high_contrast.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Link)
    colours = []
    it = message.doc.begin().begin()
    while not it.atEnd():
        if it.fragment().charFormat().isAnchor():
            colours.append(it.fragment().charFormat().foreground().color())
        it += 1
    assert colours == [link]


@pytest.mark.parametrize("name", PAINTED)
def test_links_in_answers_wear_the_styles_colour_not_the_apps(qapp, name):
    """Qt colours a link as it reads markdown, in the app palette's colour: blue on a dark bubble, beige on pink."""
    want = QColor(styles.get(name).link)
    message = SpeechBubble()
    message.set_style(styles.get(name), False)
    message.show("Hi", "See [this](https://example.com) and https://example.org", [], None, 0.0)
    box = AskBox()
    try:
        box.set_style(styles.get(name), False)
        box.open(QPoint(600, 600), "Ask", "hint", "", text="See [this](https://example.com).", activate=False)
        for doc in (message.doc, box.answer.document()):
            found = []
            block = doc.begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    f = it.fragment().charFormat()
                    if f.isAnchor() and not f.anchorHref().startswith("chatmon-copy:"):
                        found.append((f.foreground().color().name(), f.fontUnderline()))
                    it += 1
                block = block.next()
            assert found and all(c == want.name() and underlined for c, underlined in found), (name, found)
    finally:
        box.hide()
        box.deleteLater()


@pytest.mark.parametrize("name", PAINTED + ["plain"])
def test_selected_text_in_the_ask_box_wears_the_selection_colours(qapp, name):
    c = styles.get(name).colours()
    box = AskBox()
    try:
        box.set_style(styles.get(name), False)
        box.open(QPoint(600, 600), "Ask", "hint", "", text="Some words to select, enough of them to see.", activate=False)
        box.answer.selectAll()
        drawn = box.answer.viewport().grab().toImage()
        assert colour_count(drawn, c.selection) > 50, name
        pal = box.answer.palette()
        assert pal.color(QPalette.ColorRole.Highlight) == c.selection and pal.color(QPalette.ColorRole.HighlightedText) == c.selection_text
    finally:
        box.hide()
        box.deleteLater()
