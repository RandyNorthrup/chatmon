"""Markdown in the bubbles reads well: code wraps on its own panel and is coloured, headings stay modest
(M2-02, M2-17)."""

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor, QImage, QPainter, QTextDocument, QTextFormat

from chatmon import highlight, richtext, styles
from chatmon.bubble import AskBox, SpeechBubble

STYLES = ["electric", "fire", "ghost", "fairy", "leaf", "plain"]
LONG_CODE = "```python\nresult = compute_the_whole_thing(first_argument, second_argument, third_argument, fourth_argument)  # why\n```"


def wcag(a: QColor, b: QColor) -> float:
    def lum(c: QColor) -> float:
        out = 0.0
        for weight, v in ((0.2126, c.red()), (0.7152, c.green()), (0.0722, c.blue())):
            s = v / 255
            out += weight * (s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
        return out

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def blocks(doc: QTextDocument):
    block = doc.begin()
    while block.isValid():
        yield block
        block = block.next()


def code_blocks(doc: QTextDocument):
    return [b for b in blocks(doc) if richtext.is_code(b)]


@pytest.fixture
def box(qapp):
    box = AskBox()
    yield box
    box.hide()
    box.deleteLater()


def check_code_wraps(doc: QTextDocument, width: float, fill: QColor) -> None:
    code = code_blocks(doc)
    assert code, "the code block is there"
    for b in code:
        assert not b.blockFormat().nonBreakableLines()
        frame = doc.rootFrame()
        inner = [f for f in frame.childFrames() if f.firstPosition() <= b.position() <= f.lastPosition()]
        assert len(inner) == 1, "each code block is on a panel of its own"
        panel = inner[0].frameFormat()
        assert panel.background().color() == fill and panel.padding() >= 4
        if b.text():
            assert b.begin().fragment().charFormat().fontFamilies() == richtext.code_families()
    longest = code[0]
    assert longest.layout().lineCount() > 1, "the long line wrapped"
    for i in range(longest.layout().lineCount()):
        line = longest.layout().lineAt(i)
        assert line.naturalTextWidth() <= width + 0.5, "no line runs past the text's width"
    assert doc.size().width() <= width + 1


@pytest.mark.parametrize("name", STYLES)
def test_code_wraps_on_a_tinted_panel_in_a_speech_bubble(qapp, name):
    message = SpeechBubble()
    message.set_style(styles.get(name), False)
    message.show("Here's how", "Call it like this:\n\n" + LONG_CODE + "\n\nThat's all.", [], None, 0.0)
    c = styles.get(name).colours()
    check_code_wraps(message.doc, message.doc.textWidth(), c.code_fill)
    img = QImage(round(message.size.width()) + 10, round(message.size.height()) + 10, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    message.paint(p, message.size.width() / 2, 1.0)
    p.end()
    tinted = sum(1 for y in range(0, img.height(), 2) for x in range(0, img.width(), 2) if img.pixelColor(x, y).rgb() == c.code_fill.rgb())
    assert tinted > 100, "the panel is drawn"


@pytest.mark.parametrize("name", ["electric", "plain"])
def test_code_wraps_in_the_ask_box(box, name):
    box.set_style(styles.get(name), False)
    box.open(QPoint(600, 600), "Ask", "hint", "", text="**You:** how?\n\n" + LONG_CODE, activate=False)
    doc = box.answer.document()
    check_code_wraps(doc, box.answer.viewport().width(), styles.get(name).colours().code_fill)
    assert box.answer.horizontalScrollBar().maximum() == 0


def test_headings_stay_near_the_texts_size(qapp):
    message = SpeechBubble()
    message.show("Notes", "# A big heading\n\n## A smaller one\n\nBody text here.", [], None, 0.0)
    lines = {b.text(): b.layout().lineAt(0).height() for b in blocks(message.doc) if b.layout().lineCount()}
    body = lines["Body text here."]
    assert lines["A big heading"] <= body * 1.3 and lines["A smaller one"] <= body * 1.3
    assert lines["A big heading"] > body  # still a heading
    for b in blocks(message.doc):
        if b.blockFormat().headingLevel():
            assert b.begin().fragment().charFormat().intProperty(QTextFormat.Property.FontSizeAdjustment) <= richtext.HEADING_MOST


def formats_at(block, text: str) -> list[QColor]:
    """The highlighter's colours over `text` in `block`."""
    start = block.text().index(text)
    out = []
    for r in block.layout().formats():
        if r.start <= start and start + len(text) <= r.start + r.length:
            out.append(r.format.foreground().color())
    return out


def highlighted(doc_text: str, name: str = "electric"):
    message = SpeechBubble()
    message.set_style(styles.get(name), False)
    message.show("Code", doc_text, [], None, 0.0)
    return message, highlight.code_colours(styles.get(name).colours())


def test_python_keywords_strings_numbers_and_comments_are_coloured(qapp):
    message, colours = highlighted("Some prose with def and 42 in it.\n\n```python\ndef f(x):\n    return 'hi' + 42  # note\n```")
    prose, first, second = [b for b in blocks(message.doc) if b.text()][:3]
    assert prose.layout().formats() == [], "prose isn't coloured"
    assert formats_at(first, "def") == [colours.keyword]
    assert formats_at(second, "return") == [colours.keyword]
    assert formats_at(second, "'hi'") == [colours.string]
    assert formats_at(second, "42") == [colours.number]
    assert formats_at(second, "# note") == [colours.comment]
    assert formats_at(first, "f(x)") == []


def test_a_block_comment_carries_on_to_the_next_lines(qapp):
    message, colours = highlighted("```js\nconst a = 1; /* starts here\nstill a comment\nends */ let b = \"s\";\n```")
    code = code_blocks(message.doc)
    assert formats_at(code[0], "const") == [colours.keyword] and formats_at(code[0], "/* starts here") == [colours.comment]
    assert formats_at(code[1], "still a comment") == [colours.comment]
    assert formats_at(code[2], "ends */") == [colours.comment] and formats_at(code[2], "let") == [colours.keyword]
    assert formats_at(code[2], '"s"') == [colours.string]


def test_an_unnamed_language_gets_the_common_marks(qapp):
    message, colours = highlighted("```\nif ready: run(3)  # go\nurl#fragment // and this\n```")
    first, second = code_blocks(message.doc)
    assert formats_at(first, "if") == [colours.keyword] and formats_at(first, "3") == [colours.number]
    assert formats_at(first, "# go") == [colours.comment]
    assert formats_at(second, "url#fragment") == [], "a # inside a word isn't a comment"
    assert formats_at(second, "// and this") == [colours.comment]


@pytest.mark.parametrize("name", STYLES)
def test_code_colours_read_on_the_code_panel_and_stand_apart(qapp, name):
    c = styles.get(name).colours()
    colours = highlight.code_colours(c)
    for kind in ("keyword", "string", "number", "comment"):
        assert wcag(getattr(colours, kind), c.code_fill) >= 4.5, (name, kind)
    assert len({colours.keyword.rgb(), colours.string.rgb(), colours.number.rgb(), colours.comment.rgb()}) == 4, name
