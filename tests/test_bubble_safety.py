"""An answer can never make Chatmon read a file (M2-01).

Qt fetches what markdown and HTML name: an image is a file read (a path on a Windows share, an SMB connection
that hands over the user's NTLM hash). Each test puts a real picture on disk, shows text that names it, and
checks the picture's bytes never came back: not from the document's resource requests (each one is recorded),
not from Qt reading the file itself when a request comes back empty (it keeps what it read), and not on screen.
"""

import pytest
from PyQt6.QtCore import QPoint, QUrl
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap, QTextDocument
from PyQt6.QtWidgets import QLabel

from chatmon import richtext, styles
from chatmon.bubble import AskBox, SpeechBubble

SECRET_SIZE = (61, 47)  # no picture Chatmon makes is this size
MAGENTA = QColor(255, 0, 255)


@pytest.fixture
def files(qapp, tmp_path):
    """Two real pictures: one named as an image, one as an HTML background."""
    out = {}
    for name in ("image", "background"):
        path = tmp_path / f"{name}.png"
        picture = QImage(*SECRET_SIZE, QImage.Format.Format_ARGB32)
        picture.fill(MAGENTA)
        assert picture.save(str(path))
        out[name] = (path, QUrl.fromLocalFile(str(path)))
    return out


@pytest.fixture
def asked(monkeypatch):
    """Every resource request a safe document gets, and what it gave back."""
    calls: list[tuple[str, object]] = []
    real = richtext.SafeDocument.loadResource

    def recording(self, kind, url):
        result = real(self, kind, url)
        calls.append((url.toString(), result))
        return result

    monkeypatch.setattr(richtext.SafeDocument, "loadResource", recording)
    return calls


def attack(files) -> str:
    image, background = files["image"][1].toString(), files["background"][1].toString()
    local = str(files["image"][0])
    return (
        f"Look: ![x]({image}) and ![y]({local}) and ![z][r]\n\n"
        f'<img src="{background}"> <div style="background-image: url({background})">bg</div>\n\n'
        f"[r]: {image}\n"
    )


def secret(value: object, files) -> bool:
    """Whether a resource came back with one of the pictures in it."""
    if isinstance(value, (QImage, QPixmap)):
        return (value.width(), value.height()) == SECRET_SIZE
    if isinstance(value, (bytes, bytearray)) or type(value).__name__ == "QByteArray":
        data = bytes(value)
        return any(data == path.read_bytes() for path, _ in files.values())
    return False


def images(doc: QTextDocument) -> int:
    n, block = 0, doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            n += it.fragment().charFormat().isImageFormat()
            it += 1
        block = block.next()
    return n


def assert_never_read(doc: QTextDocument, calls, files) -> None:
    leaked = [url for url, result in calls if secret(result, files)]
    assert leaked == [], f"a picture's bytes were read for {leaked}"
    assert all(url != files["background"][1].toString() for url, _ in calls), "HTML was read: its picture was asked for"
    assert images(doc) == 0, "an image was left in, for the screen to look for its @2x file"
    for _, url in files.values():
        # Qt keeps a picture it read itself (when a request came back empty) as the document's resource. (Asking
        # here asks the document again, for whatever it hasn't kept: so this comes last.)
        assert not secret(doc.resource(QTextDocument.ResourceType.ImageResource.value, url), files), f"Qt read {url.toString()} itself"


def magenta_pixels(image: QImage) -> int:
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    return sum(1 for y in range(0, image.height(), 2) for x in range(0, image.width(), 2) if image.pixelColor(x, y) == MAGENTA)


@pytest.mark.parametrize("style", ["electric", "plain"])
def test_a_speech_bubble_never_reads_a_file_an_answer_names(files, asked, style):
    message = SpeechBubble()
    message.set_style(styles.get(style), False)
    message.show("Hi", "a first message, drawn before the second", [], None, 0.0)
    canvas = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.setDevicePixelRatio(2.0)  # a scaled screen: where Qt looks for a picture's @2x file
    canvas.fill(QColor(0, 0, 0, 0))
    p = QPainter(canvas)
    message.paint(p, message.size.width() / 2, 0.5)  # laid out and drawn: the next text goes into a laid-out document
    p.end()
    message.show("Hi", attack(files), [], None, 1.0)
    canvas.fill(QColor(0, 0, 0, 0))
    p = QPainter(canvas)
    message.paint(p, message.size.width() / 2, 1.5)
    p.end()
    assert asked, "the laid-out document asked for the picture: the test reaches the place it guards"
    assert_never_read(message.doc, asked, files)
    shown = message.doc.toPlainText()
    assert shown.count("[image]") == 3
    assert '<img src="' in shown and "background-image" in shown, "HTML was read: it doesn't show as the text it is"
    assert magenta_pixels(canvas) == 0


def test_the_ask_box_never_reads_a_file_an_answer_names(files, asked):
    box = AskBox()
    try:
        box.open(QPoint(600, 600), "Ask Sparky", "Enter to ask", "Ask anything", text="**You:** hi\n\nA first answer.", activate=False)
        box.grab()  # laid out and drawn
        box.set_answer(attack(files), at_end=True)
        drawn = box.grab().toImage()
        doc = box.answer.document()
        assert asked, "the laid-out document asked for the picture: the test reaches the place it guards"
        assert_never_read(doc, asked, files)
        shown = box.answer.toPlainText()
        assert shown.count("[image]") == 3
        assert '<img src="' in shown, "HTML was read: it doesn't show as the text it is"
        assert magenta_pixels(drawn) == 0
    finally:
        box.hide()
        box.deleteLater()


def test_a_title_hint_or_attachment_name_is_shown_as_text(files):
    """Labels and tooltips read text that looks like HTML as HTML; a chat's title or a file's name can."""
    tag = f'<img src="{files["image"][1].toString()}">'
    box = AskBox()
    try:
        box.open(QPoint(600, 600), tag, tag, "Ask anything", activate=False)
        box.set_attachments([f"{tag} (2 KB)"])
        assert magenta_pixels(box.grab().toImage()) == 0
        assert box.title.text() == tag
        tips = [chip.toolTip() for chip in box.chips.findChildren(type(box.attach_button)) if chip.objectName() == "chip"]
        assert tips
        for tip in tips:
            shown = QLabel(tip)  # what a tooltip is drawn with
            shown.adjustSize()
            assert magenta_pixels(shown.grab().toImage()) == 0 and tag in shown.text().replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    finally:
        box.hide()
        box.deleteLater()


def test_a_resource_request_gets_nothing_from_anywhere(qapp, files):
    doc = richtext.SafeDocument()
    image = doc.loadResource(QTextDocument.ResourceType.ImageResource.value, files["image"][1])
    assert isinstance(image, QImage) and (image.width(), image.height()) == (1, 1)  # not empty: Qt would read the file itself
    assert doc.loadResource(QTextDocument.ResourceType.StyleSheetResource.value, files["image"][1]) == b""
    assert doc.loadResource(QTextDocument.ResourceType.MarkdownResource.value, QUrl("http://example.com/")) == b""
