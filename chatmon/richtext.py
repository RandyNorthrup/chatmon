"""Markdown in the bubbles: made safe, then made readable.

Answers come from an AI, and an AI may quote anything: a web page, a file, a prompt written to attack. Qt
would fetch whatever an answer's markdown or HTML names: an image is a file read, a path on a Windows share
is an SMB connection that hands over the user's NTLM hash, /dev/zero fills the memory, a pipe freezes the
app. So every document here (`SafeDocument`) answers every resource request with nothing, HTML is not
parsed at all (`MARKDOWN`), and images become "[image]" before anything draws them (`without_images`).

Then `render` makes what's left readable in a bubble: code blocks wrap, on a tinted panel, in a fixed-width
font; headings stay near the text's size; links are underlined, in the style's link colour; and a chat's
turns (each beginning "**You:**", as the app writes them) are found, ruled apart and offered for copying.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QFontDatabase,
    QImage,
    QTextBlock,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
    QTextLength,
)

# GitHub's markdown (tables, strikethrough, task lists, bare links) with no HTML: no <img>, no CSS
# backgrounds, no <link> stylesheets, nothing that names a resource but markdown's own images.
MARKDOWN = QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML
TURN = "You:"  # a chat turn starts with a paragraph beginning "**You:**" (app.py's transcript)
HEADING_MOST = 1  # headings are at most one step larger than the text (Qt makes a level-1 heading three)
CODE_PAD = 6  # px inside a code block's panel
CODE_SPACE = 4  # px above and below it
COPY_SCHEME = "chatmon-copy"  # the ask box's Copy links: chatmon-copy:<token>/<n>


def nothing(kind: int) -> object:
    """What a document gets when it asks for a resource: never anything read from anywhere. An image gets
    a 1×1 see-through picture rather than nothing, because given nothing (or bytes that aren't a picture)
    Qt goes and reads the file the image names itself."""
    if kind == QTextDocument.ResourceType.ImageResource.value:
        blank = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
        blank.fill(Qt.GlobalColor.transparent)
        return blank
    return b""


class SafeDocument(QTextDocument):
    """A document that loads nothing: every image, stylesheet or page it names comes back empty."""

    def loadResource(self, kind: int, url: QUrl) -> object:
        return nothing(kind)


def without_images(doc: QTextDocument) -> None:
    """Take every image out of a document just made from markdown, before anything draws it. Laid out, an
    image only asks its document for a resource (which `SafeDocument` refuses); drawn on a screen scaled
    past 1, Qt first looks for its "@2x" file on disk by the name it gives. An image becomes "[image]"."""
    spans = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid() and fragment.charFormat().isImageFormat():
                spans.append((fragment.position(), fragment.length()))
            it += 1
        block = block.next()
    cursor = QTextCursor(doc)
    for position, length in reversed(spans):
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText("[image]", QTextCharFormat())


def set_markdown(doc: QTextDocument, markdown: str) -> None:
    """Fill `doc` from markdown safely: no HTML, and no images by the time it returns."""
    doc.setMarkdown(markdown, MARKDOWN)
    without_images(doc)


@dataclass(frozen=True)
class Look:
    """What `render` colours things with."""

    link: QColor
    code_fill: QColor
    code_points: float  # the code font's size


@dataclass
class Rendered:
    """What `render` found in the text."""

    code: list[str] = field(default_factory=list)  # each code block's text, in order
    turns: list[int] = field(default_factory=list)  # where each chat turn starts (document positions)
    answers: list[str] = field(default_factory=list)  # each turn's answer, as plain text (empty while it's awaited)
    copy_token: str = ""  # the token in this text's Copy links (none: no Copy links)


def render(doc: QTextDocument, markdown: str, look: Look, copy_token: str = "", copy_last: bool = True) -> Rendered:
    """Set `doc` to `markdown`, safely, and dress it for a bubble. With `copy_token`, each code block and each
    turn's answer gets a Copy link (`COPY_SCHEME`:token/n, n counting code blocks then answers); the last
    turn's only with `copy_last` (not while its answer is still coming)."""
    set_markdown(doc, markdown)
    _cap_headings(doc)
    _colour_links(doc, look.link)
    groups = _code_groups(doc)
    out = Rendered(copy_token=copy_token)
    out.code = ["\n".join(b.text() for b in group) for group in groups]
    starts = _turn_starts(doc)
    answers = _answer_ranges(doc, starts)
    out.answers = [_plain(doc, a, b) for a, b in answers]

    # Everything is inserted from the end backwards, so the positions found above stay true; code blocks are
    # framed last, by cursors that move with what's inserted round them.
    framing = []
    for group in groups:
        c = QTextCursor(doc)
        c.setPosition(group[0].position())
        c.setPosition(group[-1].position() + group[-1].length() - 1, QTextCursor.MoveMode.KeepAnchor)
        c.setKeepPositionOnInsert(True)
        framing.append(c)
    inserts: list[tuple[int, str, int | None]] = []  # (position, kind, copy index)
    if copy_token:
        for n, group in enumerate(groups):
            inserts.append((group[-1].position() + group[-1].length() - 1, "copy code", n))
        for n, ((_, end), text) in enumerate(zip(answers, out.answers, strict=True)):
            if text.strip() and (copy_last or n < len(answers) - 1):
                inserts.append((end, "copy answer", len(groups) + n))
    for start in starts[1:]:
        inserts.append((start - 1, "rule", None))
    # Last first; where several go after the same block: the code's Copy, then the answer's, then the rule.
    rank = {"copy code": 0, "copy answer": 1, "rule": 2}
    for position, kind, n in sorted(inserts, key=lambda i: (i[0], rank[i[1]]), reverse=True):
        _insert_after(doc, position, kind, n, copy_token, look.link)
    for c in framing:
        _frame_code(c, look)
    out.turns = _turn_starts(doc)
    return out


def copy_url(token: str, n: int) -> str:
    return f"{COPY_SCHEME}:{token}/{n}"


def copy_index(url: QUrl, token: str) -> int | None:
    """Which Copy link `url` is, if it's one of this text's (`token`): an answer can't make one of its own."""
    if url.scheme() != COPY_SCHEME or not token:
        return None
    given, _, n = url.path().partition("/")
    return int(n) if given == token and n.isdigit() else None


# -- the parts


def _spans(doc: QTextDocument, wanted) -> list[tuple[int, int]]:
    """(position, length) of every fragment whose format `wanted` accepts: collected first, since changing a
    format as fragments are walked splits and joins them under the walk."""
    spans = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid() and wanted(block, fragment.charFormat()):
                spans.append((fragment.position(), fragment.length()))
            it += 1
        block = block.next()
    return spans


def _merge(doc: QTextDocument, spans: list[tuple[int, int]], look: QTextCharFormat) -> None:
    c = QTextCursor(doc)
    for position, length in spans:
        c.setPosition(position)
        c.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        c.mergeCharFormat(look)


def _cap_headings(doc: QTextDocument) -> None:
    smaller = QTextCharFormat()
    smaller.setProperty(QTextFormat.Property.FontSizeAdjustment, HEADING_MOST)
    big = _spans(doc, lambda b, f: b.blockFormat().headingLevel() > 0 and f.intProperty(QTextFormat.Property.FontSizeAdjustment) > HEADING_MOST)
    _merge(doc, big, smaller)


def _colour_links(doc: QTextDocument, colour: QColor) -> None:
    """Qt colours links when it reads the markdown, in the app palette's link colour, whatever they're drawn on;
    and doesn't underline them, so colour alone would tell them apart. They take the style's, underlined."""
    look = QTextCharFormat()
    look.setForeground(colour)
    look.setFontUnderline(True)
    _merge(doc, _spans(doc, lambda b, f: f.isAnchor()), look)


def is_code(block: QTextBlock) -> bool:
    """Part of a code block: fenced (```) or indented, both of which Qt marks with a language, maybe empty."""
    return block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeLanguage)


def _code_groups(doc: QTextDocument) -> list[list[QTextBlock]]:
    """Each code block's lines (Qt makes each line a block of its own). Two fences one after the other with
    the same language read as one."""
    groups: list[list[QTextBlock]] = []
    block, last = doc.begin(), None
    while block.isValid():
        if is_code(block):
            language = block.blockFormat().stringProperty(QTextFormat.Property.BlockCodeLanguage)
            if last == language and groups and groups[-1][-1].next() == block:
                groups[-1].append(block)
            else:
                groups.append([block])
            last = language
        else:
            last = None
        block = block.next()
    return groups


def _turn_starts(doc: QTextDocument) -> list[int]:
    """Where each chat turn begins: a paragraph whose first words are a bold "You:"."""
    starts = []
    block = doc.begin()
    while block.isValid():
        if not is_code(block) and block.text().startswith(TURN):
            it = block.begin()
            if not it.atEnd() and it.fragment().charFormat().fontWeight() >= 600:
                starts.append(block.position())
        block = block.next()
    return starts


def _answer_ranges(doc: QTextDocument, starts: list[int]) -> list[tuple[int, int]]:
    """(start, end) of each turn's answer: after the question's paragraph (and the "Attached: …" line after
    it, if any) up to the next turn."""
    ranges = []
    for i, start in enumerate(starts):
        question = doc.findBlock(start)
        first = question.next()
        if first.isValid() and first.text().startswith("Attached:") and first.begin().fragment().charFormat().fontItalic():
            first = first.next()
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else doc.characterCount() - 1
        begin = first.position() if first.isValid() else end
        ranges.append((min(begin, end), end))
    return ranges


def _plain(doc: QTextDocument, start: int, end: int) -> str:
    c = QTextCursor(doc)
    c.setPosition(start)
    c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    return c.selection().toPlainText().strip()


def _insert_after(doc: QTextDocument, position: int, kind: str, n: int | None, token: str, colour: QColor) -> None:
    """A block of our own after the one that ends at `position`: a rule between turns, or a Copy link."""
    c = QTextCursor(doc)
    c.setPosition(position)
    block = QTextBlockFormat()
    if kind == "rule":
        block.setTopMargin(4)
        block.setBottomMargin(4)
        block.setProperty(QTextFormat.Property.BlockTrailingHorizontalRulerWidth, QTextLength(QTextLength.Type.PercentageLength, 100))
        c.insertBlock(block, QTextCharFormat())
        return
    block.setAlignment(Qt.AlignmentFlag.AlignRight)
    block.setTopMargin(0)
    block.setBottomMargin(2)
    c.insertBlock(block, QTextCharFormat())
    link = QTextCharFormat()
    link.setAnchor(True)
    link.setAnchorHref(copy_url(token, n or 0))
    link.setForeground(colour)
    link.setFontUnderline(True)
    link.setProperty(QTextFormat.Property.FontSizeAdjustment, -1)
    link.setToolTip("Copy this code" if kind == "copy code" else "Copy this answer")
    c.insertText("Copy code" if kind == "copy code" else "Copy", link)


def _frame_code(c: QTextCursor, look: Look) -> None:
    """A code block on its own tinted panel, in a fixed-width font, wrapping rather than running off the edge."""
    doc = c.document()
    code = QTextBlockFormat(doc.findBlock(c.selectionStart()).blockFormat())
    code.setNonBreakableLines(False)
    code.setTopMargin(0)
    code.setBottomMargin(0)
    mono = QTextCharFormat()
    mono.setFontFamilies(code_families())
    mono.setFontFixedPitch(True)
    mono.setFontPointSize(look.code_points)
    c.mergeCharFormat(mono)
    panel = QTextFrameFormat()
    panel.setBackground(look.code_fill)
    panel.setPadding(CODE_PAD)
    panel.setTopMargin(CODE_SPACE)
    panel.setBottomMargin(CODE_SPACE)
    panel.setBorder(0)
    frame = c.insertFrame(panel)
    # A block's format is kept on the separator before it, and the frame's own marks are separators: the
    # code's format ends up on the marks, the code's first line without it. Put each where it belongs.
    fix = QTextCursor(doc)
    block = doc.findBlock(frame.firstPosition())
    while block.isValid() and block.position() <= frame.lastPosition():
        fix.setPosition(block.position())
        fix.setBlockFormat(code)
        block = block.next()
    for mark in (frame.firstPosition() - 1, frame.lastPosition() + 1):
        outside = doc.findBlock(mark)
        if outside.isValid() and not outside.text():
            fix.setPosition(outside.position())
            fix.setBlockFormat(_HAIRLINE)


_HAIRLINE = QTextBlockFormat()  # the empty line a frame leaves either side of itself: as good as none
_HAIRLINE.setLineHeight(1, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
_HAIRLINE.setTopMargin(0)
_HAIRLINE.setBottomMargin(0)


def code_families() -> list[str]:
    """Fixed-width fonts for code, best first: Qt's own pick on Windows is Courier New, thin and wide."""
    return ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()]
