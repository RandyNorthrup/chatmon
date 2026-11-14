"""Speech bubbles: messages drawn by the stage, and the ask box you type in.

Both are drawn in the chosen bubble style (styles.py): a painted, animated bubble (bubbleart.py) with
its notch pointing at the penguin, or the plain one in the desktop's own colours.
"""

from __future__ import annotations

import html
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSizeF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAbstractTextDocumentLayout,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QTextLayout,
    QTextOption,
)
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from . import bubbleart, highlight, richtext, styles

ACCENT = QColor(styles.PLAIN_ACCENT)  # the penguin's glowing cyan nodes (the stage's menus; bubbles take the style's)
PAD = 14
TAIL = 12
RADIUS = 14
FADE = 0.14  # seconds
SPILL = 3  # px an effect may reach past a bubble's frame (a flame's tip): the stage draws that much round it
ANIM_FPS = 30  # how often an animated bubble is redrawn (its frames crossfade in between)
BODY_POINTS = 10.5  # the bubbles' text, at the desktop's usual font size
SAFE_SCHEMES = ("http", "https", "mailto")  # what a link in a bubble may open: nothing on this computer
WORD = re.compile(r"\w+")


def open_link(url: QUrl) -> None:
    """Links in answers open in the browser; nothing else (no files, no apps)."""
    if url.scheme() in SAFE_SCHEMES:
        QDesktopServices.openUrl(url)


PLAIN_ALPHA = 248  # the plain bubble's fill lets a trace of the desktop through


def colours() -> tuple[QColor, QColor]:
    """The plain bubble's fill and text, from the desktop's light or dark theme."""
    c = styles.get("plain").colours()
    fill = QColor(c.fill)
    fill.setAlpha(PLAIN_ALPHA)
    return fill, c.body


def look(c: styles.Colours, points: float) -> richtext.Look:
    """How rich text is dressed in a bubble with these colours and text size."""
    return richtext.Look(link=c.link, code_fill=c.code_fill, code_points=max(6.0, points - 0.5))


def paint_context(c: styles.Colours) -> QAbstractTextDocumentLayout.PaintContext:
    """The palette a bubble's document is drawn with: its text, its links, and its rules (a document draws a
    rule in its WindowText colour)."""
    ctx = QAbstractTextDocumentLayout.PaintContext()
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        ctx.palette.setColor(group, QPalette.ColorRole.Text, c.body)
        ctx.palette.setColor(group, QPalette.ColorRole.Link, c.link)
        ctx.palette.setColor(group, QPalette.ColorRole.WindowText, c.accent)
    return ctx


def wrap_anywhere(doc) -> None:
    """Long words and links break where they must rather than running off the bubble."""
    option = doc.defaultTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    doc.setDefaultTextOption(option)


def bubble_path(box: QRectF, tail_x: float) -> QPainterPath:
    """A rounded box with a tail under it pointing down at `tail_x` (the plain bubble)."""
    path = QPainterPath()
    path.addRoundedRect(box, RADIUS, RADIUS)
    tail = QPainterPath()
    tail.moveTo(tail_x - 9, box.bottom() - 1)
    tail.lineTo(tail_x, box.bottom() + TAIL)
    tail.lineTo(tail_x + 9, box.bottom() - 1)
    tail.closeSubpath()
    return path.united(tail)


def text_points(base: float, scale: float = 1.0) -> float:
    """A text size: `base` (its size with the desktop's usual font) grown with the desktop's font where that's
    larger, times the text-size setting `scale`."""
    desktop = QApplication.font().pointSizeF()
    grow = desktop / BODY_POINTS if desktop > BODY_POINTS else 1.0
    return base * grow * scale


def width_for(px: float, font: QFont) -> float:
    """`px`, a width that suits text at the usual size, for text in `font`: in proportion to its line height."""
    usual = QFont(font)
    usual.setPointSizeF(BODY_POINTS)
    return px * QFontMetricsF(font).height() / QFontMetricsF(usual).height()


def _font(points: float, bold: bool = False, scale: float = 1.0) -> QFont:
    font = QFont(QApplication.font())
    font.setPointSizeF(text_points(points, scale))
    font.setBold(bold)
    return font


def _colours_key(c: styles.Colours) -> tuple:
    """Colours as a cache key: the plain style's change with the desktop's theme."""
    return (c.fill.rgba(), c.title.rgba(), c.body.rgba(), c.link.rgba(), c.accent.rgba(), c.primary.fill.rgba() if c.primary.fill else 0)


@dataclass
class _Button:
    label: str
    action: Callable[[], None] | None
    rect: QRectF


@dataclass(frozen=True)
class TimeoutPolicy:
    """How long a speech bubble stays: long enough to read. At least `least` seconds plus `per_word` for each of
    its words, or what the message asked for if that's longer; times `factor` (a "longer" setting); or until it's
    closed. A message that asks to stay (no timeout: an alert, a question) stays whatever the policy."""

    until_closed: bool = False
    factor: float = 1.0
    least: float = 4.0
    per_word: float = 0.3

    def seconds(self, asked: float | None, words: int) -> float | None:
        if not asked or self.until_closed:
            return None
        return max(asked, self.least + self.per_word * words) * max(0.25, self.factor)


def text_lines(text: str, font: QFont, width: float, most: int) -> list[str]:
    """`text` broken into lines `width` px wide in `font`: at most `most`, the last cut short with "…"."""
    layout = QTextLayout(text, font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    spans = []
    layout.beginLayout()
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1.0, width))
        spans.append((line.textStart(), line.textLength()))
    layout.endLayout()
    lines = [text[start : start + length].strip() for start, length in spans[:most]]
    if len(spans) > most:
        rest = " ".join(text[spans[most - 1][0] :].split())
        lines[-1] = QFontMetricsF(font).elidedText(rest, Qt.TextElideMode.ElideRight, max(1.0, width))
    return lines or [""]


class SpeechBubble:
    """A message above the penguin's head. It has no window of its own: the
    stage draws it, so it follows the penguin smoothly."""

    MAX_WIDTH = 340  # px at the usual text size; it grows with the text (`_max_width`)
    SCREEN_SHARE = 0.4  # of the screen's height, at most
    TITLE_LINES = 2
    CLOSE_W = 22
    BUTTON_GAP = 8
    ROW_GAP = 6
    MORE = "More"

    def __init__(self):
        self.title = ""
        self.doc = richtext.SafeDocument()
        self.doc.setDocumentMargin(0)
        wrap_anywhere(self.doc)
        self.buttons: list[_Button] = []
        self.size = QSizeF()
        self.hover: int | None = None
        self.on_close: Callable[[], None] | None = None
        self.on_more: Callable[[str, str], None] | None = None  # More: (title, the whole text), to be read in full
        self.timeout_policy = TimeoutPolicy()
        self.max_height: float | None = None  # px; None: SCREEN_SHARE of the primary screen
        self.text_scale = 1.0
        self._text = ""
        self._button_specs: list = []
        self._shown_at = 0.0
        self._now = 0.0  # the clock as last told (show, tick)
        self._expires: float | None = None
        self._closing_at: float | None = None
        self._hovered = False
        self._paused_at: float | None = None
        self._visible = False
        self._close_rect = QRectF()
        self._body_top = 0.0
        self._body = QRectF()
        self._content = QRectF()
        self._title_lines: list[str] = []
        self._clip: float | None = None  # how much of the text shows, when it's cut short (px from its top)
        self.style = styles.get(None)
        self.animate = True
        self.art = bubbleart.art(self.style.name, "message")
        self.highlighter = highlight.CodeHighlighter(self.doc, highlight.code_colours(self.style.colours()))
        self._words: tuple[tuple, QPixmap] | None = None  # the title, text and buttons, drawn once
        self._frame: tuple[tuple, QPixmap] | None = None  # the whole bubble, drawn once per frame of its animation

    def set_style(self, style: styles.Style, animate: bool) -> None:
        """Draw in `style` from the next message on (and the one showing, if any)."""
        self.style, self.animate = style, animate
        self.art = bubbleart.art(style.name, "message")
        if self._visible and self._closing_at is None:
            self._layout()

    def set_text_scale(self, scale: float) -> None:
        """The text-size setting: 1 is the usual size (or the desktop's, if larger)."""
        self.text_scale = min(3.0, max(0.75, scale))
        if self._visible and self._closing_at is None:
            self._layout()

    def visible(self) -> bool:
        """Showing and not on its way out."""
        return self._visible and self._closing_at is None

    def drawn(self) -> bool:
        """Still on screen, perhaps fading out."""
        return self._visible

    def anim_key(self, now: float) -> int:
        """Changes as often as an animated bubble needs redrawing; -1 when it doesn't."""
        if self._visible and self.animate and self.art is not None:
            return int((now - self._shown_at) * ANIM_FPS)
        return -1

    def show(self, title: str, text: str, buttons, timeout_s: float | None, now: float) -> None:
        self.title = title
        self.hover = None
        self._text = text or ""
        self._button_specs = list(buttons or [])
        self._shown_at, self._closing_at, self._now = now, None, now
        self._hovered, self._paused_at = False, None
        self._visible = True
        self._layout()
        stay = self.timeout_policy.seconds(timeout_s, self.words())
        self._expires = now + stay if stay is not None else None

    def words(self) -> int:
        """How many words there are to read: the title's and the text's."""
        return len(WORD.findall(self.title)) + len(WORD.findall(self.doc.toPlainText()))

    def expires(self) -> float | None:
        """When it goes, on its own clock (None: when it's closed)."""
        return self._expires

    def set_hovered(self, on: bool, now: float | None = None) -> None:
        """The pointer is over it (or has left): its clock stops while you read, and goes on from where it was."""
        now = self._now if now is None else now
        if on == self._hovered:
            return
        self._hovered = on
        if on:
            self._paused_at = now
        elif self._paused_at is not None:
            if self._expires is not None:
                self._expires += max(0.0, now - self._paused_at)
            self._paused_at = None

    def _max_width(self, body: QFont) -> float:
        """The widest a bubble gets: wider with larger text, never past most of the screen."""
        screen = QGuiApplication.primaryScreen()
        room = screen.availableGeometry().width() * 0.9 if screen is not None else 2000
        return min(room, width_for(self.MAX_WIDTH, body))

    def _max_height(self) -> float:
        if self.max_height:
            return self.max_height
        screen = QGuiApplication.primaryScreen()
        return self.SCREEN_SHARE * (screen.availableGeometry().height() if screen is not None else 1000)

    def _layout(self) -> None:
        """Lay the title, text and buttons out (from 0, 0), then put them inside the bubble."""
        self._words = None
        self._frame = None
        scale = self.text_scale
        title_font, body_font = _font(BODY_POINTS, bold=True, scale=scale), _font(BODY_POINTS, scale=scale)
        self._title_font, self._button_font, self._close_font = title_font, _font(10, scale=scale), _font(9.5, scale=scale)
        self.doc.setDefaultFont(body_font)
        c = self.style.colours()
        self.highlighter.set_colours(highlight.code_colours(c))
        richtext.render(self.doc, self._text, look(c, body_font.pointSizeF()))
        has_text = bool(self._text)
        title_metrics, body_metrics = QFontMetricsF(title_font), QFontMetricsF(body_font)
        buttons = self._buttons(self._button_specs)
        inner_max = self._max_width(body_font) - 2 * PAD  # the text's widest, whatever bubble it's in
        self.doc.setTextWidth(inner_max)
        title_w = title_metrics.horizontalAdvance(self.title) + self.CLOSE_W + 6
        one_row = sum(b.rect.width() for b in buttons) + self.BUTTON_GAP * max(0, len(buttons) - 1)
        least = 160 * scale
        inner = min(inner_max, max(least, title_w, one_row, self.doc.idealWidth() + 1 if has_text else 0))
        self.doc.setTextWidth(inner)
        self._title_lines = text_lines(self.title, title_font, inner - self.CLOSE_W, self.TITLE_LINES)
        title_h = title_metrics.lineSpacing() * len(self._title_lines)
        chrome = (self.art.margins()[1] + self.art.margins()[3]) if self.art else 2 * PAD + TAIL
        room = self._max_height() - chrome - title_h  # for the text and the buttons
        text_h = self.doc.size().height() if has_text else 0.0
        rows_h = self._rows(buttons, inner)
        self._clip = None
        if has_text and 6 + text_h + (12 + rows_h if buttons else 0) > room:
            if self.on_more is not None:
                buttons = self._buttons(self._button_specs + [(self.MORE, self._more)])
                rows_h = self._rows(buttons, inner)
            ellipsis = body_metrics.lineSpacing()
            fits = room - 6 - (12 + rows_h if buttons else 0) - ellipsis
            self._clip = self._whole_lines(max(fits, 2 * body_metrics.lineSpacing()))
            text_h = self._clip + ellipsis
        height = title_h
        body_top = height + 6
        if has_text:
            height += 6 + text_h
        if buttons:
            height += 12
            for b in buttons:
                b.rect.translate(0, height)
            height += rows_h
        self.buttons = buttons
        if self.art:
            frame = self.art.frame_for(QSizeF(inner, height))
            origin = frame.text.topLeft()
            self.size = frame.size
            pad = self.art.pad + 4
            self._body = frame.text.adjusted(-pad, -pad, pad, pad)
        else:
            origin = QPointF(PAD, PAD)
            self.size = QSizeF(inner + 2 * PAD, height + 2 * PAD + TAIL)
            self._body = QRectF(0, 0, self.size.width(), self.size.height() - TAIL)
        self._content = QRectF(origin, QSizeF(inner, height))
        for b in self.buttons:
            b.rect.translate(origin)
        self._body_top = origin.y() + body_top
        line_h = title_metrics.lineSpacing()
        self._close_rect = QRectF(origin.x() + inner - self.CLOSE_W + 4, origin.y() - 3, self.CLOSE_W, line_h + 6)
        self._has_text = has_text

    def _buttons(self, specs) -> list[_Button]:
        metrics = QFontMetricsF(self._button_font)
        return [_Button(label, action, QRectF(0, 0, metrics.horizontalAdvance(label) + 28, metrics.height() + 10)) for label, action in specs]

    def _rows(self, buttons: list[_Button], inner: float) -> float:
        """Put the buttons in rows, each right-aligned and no wider than the text: their height in all."""
        rows: list[list[_Button]] = [[]]
        used = 0.0
        for b in buttons:
            b.rect.setWidth(min(b.rect.width(), inner))  # a label too long for any row is cut short
            if rows[-1] and used + self.BUTTON_GAP + b.rect.width() > inner:
                rows.append([])
                used = 0.0
            used += (self.BUTTON_GAP if rows[-1] else 0) + b.rect.width()
            rows[-1].append(b)
        y = 0.0
        for row in rows:
            if not row:
                continue
            x = inner - (sum(b.rect.width() for b in row) + self.BUTTON_GAP * (len(row) - 1))
            for b in row:
                b.rect.moveTo(x, y)
                x += b.rect.width() + self.BUTTON_GAP
            y += row[0].rect.height() + self.ROW_GAP
        return max(0.0, y - self.ROW_GAP)

    def _whole_lines(self, limit: float) -> float:
        """The bottom of the last line of text that ends within `limit` px of its top."""
        best = 0.0
        block = self.doc.begin()
        while block.isValid():
            lines = block.layout()
            top = lines.position().y()
            for i in range(lines.lineCount()):
                line = lines.lineAt(i)
                bottom = top + line.y() + line.height()
                if bottom <= limit:
                    best = max(best, bottom)
            block = block.next()
        return best or limit

    def _more(self) -> None:
        if self.on_more is not None:
            self.on_more(self.title, self._text)

    def dismiss(self, now: float) -> None:
        """Closed as far as anyone is concerned; it fades out on its own."""
        if self.visible():
            self._closing_at = now
            self._expires = None
            if self.on_close:
                self.on_close()

    def tick(self, now: float) -> None:
        self._now = now
        if self._expires is not None and not self._hovered and now >= self._expires:
            self.dismiss(now)
        if self._closing_at is not None and now - self._closing_at >= FADE:
            self._visible, self._closing_at = False, None

    def opacity(self, now: float) -> float:
        if self._closing_at is not None:
            return max(0.0, 1 - (now - self._closing_at) / FADE)
        return min(1.0, (now - self._shown_at) / FADE)

    def hit(self, pos: QPointF) -> str | int | None:
        """What's at `pos` (bubble coordinates): a button's index, "close", "link" (see `link_at`), "body"."""
        if self._close_rect.contains(pos):
            return "close"
        for i, b in enumerate(self.buttons):
            if b.rect.contains(pos):
                return i
        if self.link_at(pos) is not None:
            return "link"
        if self._body.contains(pos):
            return "body"
        return None

    def link_at(self, pos: QPointF) -> QUrl | None:
        """The link under `pos` (bubble coordinates), if it's one that may be opened: http, https or mailto."""
        if not self._has_text or not self._visible:
            return None
        local = pos - QPointF(self._content.x(), self._body_top)
        if local.x() < 0 or local.y() < 0 or local.x() > self._content.width() or (self._clip is not None and local.y() > self._clip):
            return None
        href = self.doc.documentLayout().anchorAt(local)
        url = QUrl(href) if href else None
        return url if url is not None and url.scheme() in SAFE_SCHEMES else None

    def open_link_at(self, pos: QPointF) -> bool:
        """Open the link under `pos` in the browser; False if there's none (or not one that may be opened)."""
        url = self.link_at(pos)
        if url is None:
            return False
        open_link(url)
        return True

    def paint(self, p: QPainter, tail_x: float, now: float) -> None:
        frame = self._frame_pixmap(bubbleart.device_ratio(p), tail_x, now)
        p.save()
        p.setOpacity(self.opacity(now))
        p.drawPixmap(QPointF(-SPILL, -SPILL), frame)
        p.restore()

    def _frame_pixmap(self, ratio: float, tail_x: float, now: float) -> QPixmap:
        """The whole bubble as it looks now, drawn once per frame of its animation (once, if it doesn't
        move) however often it is put on the screen: it follows a walking penguin at 60 frames a second,
        and drawing its art each time cost twice what the animation needs. A fade is applied to the
        finished picture, rather than to each layer as it's drawn."""
        c = self.style.colours()
        size = (max(1, round((self.size.width() + 2 * SPILL) * ratio)), max(1, round((self.size.height() + 2 * SPILL) * ratio)))
        key = (ratio, size, round(tail_x * ratio), self.hover, self.anim_key(now), self.style.name, _colours_key(c))
        if self._frame is None or self._frame[0] != key:
            pix = self._frame[1] if self._frame is not None and (self._frame[1].width(), self._frame[1].height()) == size else QPixmap(*size)
            pix.setDevicePixelRatio(ratio)
            pix.fill(Qt.GlobalColor.transparent)
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.translate(SPILL, SPILL)
            if self.art:
                self.art.paint(q, 0, 0, self._content.size(), tail_x, now - self._shown_at, self.animate)
            else:
                box = QRectF(1, 1, self.size.width() - 2, self.size.height() - TAIL - 2)
                path = bubble_path(box, tail_x)
                fill = QColor(c.fill)
                fill.setAlpha(PLAIN_ALPHA)
                q.fillPath(path, fill)
                q.setPen(QPen(c.accent, 2))
                q.drawPath(path)
            q.drawPixmap(QPointF(0, 0), self._words_pixmap(q, c))
            q.end()
            self._frame = (key, pix)
        return self._frame[1]

    def _words_pixmap(self, p: QPainter, c: styles.Colours) -> QPixmap:
        """The title, ✕, text and buttons on a see-through pixmap the bubble's size. An animated bubble is
        drawn thirty times a second and laying out its text each time cost as much as some styles' art,
        so they are drawn once per message, button hovered and colours."""
        ratio = bubbleart.device_ratio(p)
        key = (ratio, self.hover, _colours_key(c), self.style.name)
        if self._words is None or self._words[0] != key:
            pix = QPixmap(max(1, round(self.size.width() * ratio)), max(1, round(self.size.height() * ratio)))
            pix.setDevicePixelRatio(ratio)
            pix.fill(Qt.GlobalColor.transparent)
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._draw_words(q, c)
            q.end()
            self._words = (key, pix)
        return self._words[1]

    def _draw_words(self, p: QPainter, colours: styles.Colours) -> None:
        c = self._content
        p.setPen(colours.title)
        p.setFont(self._title_font)
        line_h = QFontMetricsF(self._title_font).lineSpacing()
        for i, line in enumerate(self._title_lines):
            p.drawText(QRectF(c.x(), c.y() + i * line_h, c.width() - self.CLOSE_W, line_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, line)
        p.setFont(self._close_font)
        p.drawText(self._close_rect, Qt.AlignmentFlag.AlignCenter, "✕")
        if self._has_text:
            p.save()
            p.translate(c.x(), self._body_top)
            if self._clip is not None:  # cut short: whole lines, then "…" (More has the rest)
                p.setClipRect(QRectF(-SPILL, -SPILL, c.width() + 2 * SPILL, self._clip + SPILL))
            self.doc.documentLayout().draw(p, paint_context(colours))
            p.restore()
            if self._clip is not None:
                p.setPen(colours.body)
                p.setFont(self.doc.defaultFont())
                p.drawText(QRectF(c.x(), self._body_top + self._clip, c.width(), line_h * 1.5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "…")
        p.setFont(self._button_font)
        metrics = QFontMetricsF(self._button_font)
        for i, b in enumerate(self.buttons):
            button = colours.primary if i == 0 else colours.other
            if i == self.hover:  # lit up: filled with its outline colour
                fill, label = button.hover_fill, button.hover_text
            else:
                fill, label = button.fill, button.text
            p.setBrush(fill if fill is not None else Qt.BrushStyle.NoBrush)
            p.setPen(QPen(button.outline, 1.5))
            r = b.rect.adjusted(0.75, 0.75, -0.75, -0.75)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            p.setPen(label)
            p.drawText(b.rect, Qt.AlignmentFlag.AlignCenter, metrics.elidedText(b.label, Qt.TextElideMode.ElideRight, b.rect.width() - 16))


class Entry(QLineEdit):
    """The field you type a question in. Pasting files, a picture or a long text attaches it (`pasted`)
    rather than squeezing it onto one line; a short text pastes as usual."""

    paste_requested = pyqtSignal()

    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_requested.emit()
        else:
            super().keyPressEvent(event)

    def edit_menu(self) -> QMenu:
        """Undo to Select All, as Qt's own menu for a field has them, without reading the clipboard to open: Qt's
        does, to enable Paste, which macOS takes for Chatmon reading it unasked."""
        menu = QMenu(self)
        writable, chosen = not self.isReadOnly(), self.hasSelectedText()
        for entry in (
            ("Undo", self.undo, writable and self.isUndoAvailable()),
            ("Redo", self.redo, writable and self.isRedoAvailable()),
            None,
            ("Cut", self.cut, writable and chosen),
            ("Copy", self.copy, chosen),
            ("Paste", self.paste_requested.emit, writable),
            ("Delete", self.del_, writable and chosen),
            None,
            ("Select All", self.selectAll, bool(self.text()) and self.selectedText() != self.text()),
        ):
            if entry is None:
                menu.addSeparator()
                continue
            label, act, on = entry
            menu.addAction(label, act).setEnabled(on)
        return menu

    def contextMenuEvent(self, event) -> None:
        if QGuiApplication.platformName() == "cocoa":
            # Its own menu, shown as a native one: Paste chosen in a menu Qt draws is no paste of yours to macOS,
            # which then asks whether Chatmon may, or inside that menu can't ask and stops it (macnative.py).
            from . import macnative

            menu = self.edit_menu()
            if not macnative.popup(menu, event.globalPos(), self):
                menu.exec(event.globalPos())
            menu.deleteLater()
            return
        menu = self.createStandardContextMenu()
        for action in menu.actions():
            if action.objectName() == "edit-paste":
                action.triggered.disconnect()
                action.triggered.connect(self.paste_requested.emit)
                action.setEnabled(not self.isReadOnly())
        menu.exec(event.globalPos())
        menu.deleteLater()


def clipboard_contents(mime: QMimeData | None) -> tuple[str, object] | None:
    """("files", [paths]), ("image", QImage) or ("text", str): what a paste would bring, best first. On
    Windows, a drop or a paste can also bring ("named", [winfiles.Dropped]): files that aren't on disk, which
    windrop.py reads, not Qt."""
    if mime is None:
        return None
    files = [os.path.normpath(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
    if files:
        return "files", files
    if mime.hasImage():
        image = mime.imageData()
        if isinstance(image, QImage) and not image.isNull():
            return "image", image
    if mime.hasText() and mime.text():
        return "text", mime.text()
    return None


def overlay_contents(mime: str, data: bytes) -> tuple[str, object] | None:
    """The same, from the overlay's own clipboard (a type and its bytes)."""
    if mime == "text/uri-list":
        files = [QUrl(line.strip()).toLocalFile() for line in data.decode("utf-8", errors="replace").splitlines() if line.startswith("file://")]
        return ("files", [os.path.normpath(f) for f in files if f]) if any(files) else None
    if mime.startswith("image/"):
        image = QImage.fromData(data)
        return ("image", image) if not image.isNull() else None
    text = data.decode("utf-8", errors="replace")
    return ("text", text) if text else None


def plain_tip(text: str) -> str:
    """A tooltip that shows `text` as it is: Qt reads a tooltip that looks like HTML as HTML, and a file's
    name can look like an <img> tag."""
    return "<qt>" + html.escape(text) + "</qt>"


class Answer(QTextBrowser):
    """The conversation above the field, in a document that loads nothing (a text browser's own would read
    any file an answer names)."""

    def __init__(self):
        super().__init__(openLinks=False)
        self.setOpenExternalLinks(False)
        self.setDocument(richtext.SafeDocument(self))


class AskBox(QWidget):
    """The bubble you type questions into, with real Qt widgets since it needs
    the keyboard. A window of its own, or drawn on the Wayland overlay by the
    stage (penguin.Hosted); the penguin holds still while it's open."""

    closed = pyqtSignal()
    submitted = pyqtSignal(str)
    reset_requested = pyqtSignal()
    history_requested = pyqtSignal(QPoint)  # where to show the list of chats (screen coordinates)
    attach_requested = pyqtSignal(QPoint)  # where to show what can be attached
    pasted = pyqtSignal(str, object)  # what clipboard_contents found: to attach
    attachment_removed = pyqtSignal(int)

    WIDTH = 380
    MAX_ANSWER = 320

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFixedWidth(self.WIDTH)
        self._anchor = QPoint(0, 0)
        self._tail_x = self.WIDTH / 2
        self.wants_keyboard = True
        self.style = styles.get(None)
        self.animate = True
        self.art: bubbleart.BubbleArt | None = None
        self._margins = (16, 12, 16, 14 + TAIL)
        self._opened_at = time.monotonic()
        self.stage_draws_art = False  # on the overlay: the stage draws the bubble, this only what's in it
        self._frames = QTimer(self)  # redraws an animated bubble while it's open
        self._frames.setInterval(1000 // ANIM_FPS)
        self._frames.timeout.connect(self.update)
        self.seen = True  # off while nothing on screen can be seen (set_seen): no frames

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self._margins)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("title")
        self.title.setTextFormat(Qt.TextFormat.PlainText)  # a name or a chat's title, never markup that could load a file
        top.addWidget(self.title, 1)
        self.history_button = QToolButton(text="History", autoRaise=True)
        self.history_button.setToolTip("Your earlier chats: pick one to carry on")
        self.history_button.clicked.connect(lambda: self.history_requested.emit(self._below(self.history_button)))
        top.addWidget(self.history_button)
        self.reset_button = QToolButton(text="New chat", autoRaise=True)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        top.addWidget(self.reset_button)
        close = QToolButton(text="✕", autoRaise=True)
        close.setToolTip("Close (Esc)")
        close.setAccessibleName("Close")
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        layout.addLayout(top)
        self.answer = Answer()
        self.answer.anchorClicked.connect(open_link)
        self.answer.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.answer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.answer.document().setDocumentMargin(2)
        wrap_anywhere(self.answer.document())
        self.answer.setAccessibleName("Conversation")
        self._markdown = ""  # what the answer area shows, as given: it's drawn again from this when the style changes
        self.highlighter = highlight.CodeHighlighter(self.answer.document(), highlight.code_colours(self.style.colours()))
        layout.addWidget(self.answer)
        self.chips = QWidget()  # what's attached to the next question, each with its ✕
        self.chips_layout = QHBoxLayout(self.chips)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(4)
        self.chips.hide()
        layout.addWidget(self.chips)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.attach_button = QToolButton(text="+")
        self.attach_button.setObjectName("attach")
        self.attach_button.setToolTip("Attach files, a picture or text (or paste them in)")
        self.attach_button.setAccessibleName("Attach")
        self.attach_button.setAccessibleDescription("Files, a picture or text; or paste them in")
        self.attach_button.clicked.connect(lambda: self.attach_requested.emit(self._below(self.attach_button)))
        row.addWidget(self.attach_button)
        self.entry = Entry()
        self.entry.returnPressed.connect(self._submit)
        self.entry.paste_requested.connect(self.paste_clipboard)
        row.addWidget(self.entry, 1)
        layout.addLayout(row)
        self._attached = 0
        self.setAcceptDrops(True)
        self._drop_target = None  # Windows: Chatmon's own (windrop.DropTarget), in place of Qt's
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.hint)
        self.set_style(self.style, self.animate)

    def set_style(self, style: styles.Style, animate: bool) -> None:
        self.style, self.animate = style, animate
        self.art = bubbleart.art(style.name, "ask")
        if self.art:
            left, top, right, bottom = self.art.margins()
            self._margins = (round(left), round(top), round(right), round(bottom))
        else:
            self._margins = (16, 12, 16, 14 + TAIL)
        self.layout().setContentsMargins(*self._margins)
        self._style()
        if self.isVisible():
            self.set_answer(self._markdown)
            self._run_frames()

    def _content_width(self) -> int:
        return self.WIDTH - self._margins[0] - self._margins[2]

    def anim_key(self, now: float) -> int:
        """Changes as often as its animated bubble needs drawing again; -1 when it doesn't."""
        if self.isVisible() and self.animate and self.art is not None:
            return int((now - self._opened_at) * ANIM_FPS)
        return -1

    def paint_art(self, p: QPainter, x: float, y: float) -> bool:
        """Draw the painted bubble with its top-left at (x, y); False for the plain one, which the box
        draws itself."""
        if not self.art:
            return False
        left, top, right, bottom = self._margins
        content = QSizeF(self.width() - left - right, self.height() - top - bottom)
        self.art.paint(p, x, y, content, self._tail_x, time.monotonic() - self._opened_at, self.animate)
        return True

    def _run_frames(self) -> None:
        if self.isVisible() and self.seen and self.animate and self.art is not None and not self.stage_draws_art:
            self._frames.start()
        else:
            self._frames.stop()

    def set_seen(self, on: bool) -> None:
        """Whether anything on screen can be seen (Windows: not while locked, or with the display off)."""
        self.seen = on
        self._run_frames()

    def open(self, anchor: QPoint, title: str, hint: str, placeholder: str, text: str = "", prefill: str = "", activate: bool = True) -> None:
        """Show it above `anchor`; `activate` gives it the keyboard (you asked for it)."""
        self.title.setText(title)
        self.hint.setText(QFontMetricsF(self.hint.font()).elidedText(hint, Qt.TextElideMode.ElideRight, self._content_width() - 2))
        self.setAccessibleName(title)  # a screen reader says what the box is for as you come to it
        self.entry.setAccessibleName(title)
        self.entry.setAccessibleDescription(hint)
        self.entry.setPlaceholderText(placeholder)
        self.entry.setText(prefill)
        self.entry.show()
        self.attach_button.show()
        self.history_button.show()
        self.reset_button.hide()
        self._anchor = QPoint(anchor)
        self.set_answer(text)
        self.wants_keyboard = activate
        if not self.isVisible():
            self._opened_at = time.monotonic()
        self.show()
        self.raise_()
        if activate:
            if QGuiApplication.platformName() == "cocoa":  # the keyboard comes to an app that's active
                from . import macnative

                macnative.activate()
            self.activateWindow()
        self.entry.setFocus()
        self.entry.end(False)
        self._run_frames()

    def show_notes(self, anchor: QPoint, title: str, markdown: str, hint: str = "Esc to close") -> None:
        """Something to read, not to answer (what's new in an update): the same bubble, scrolling, with
        no field to type in."""
        self.open(anchor, title, hint, "", text=markdown)
        self.entry.hide()
        self.attach_button.hide()
        self.history_button.hide()
        self.set_attachments([])
        self.answer.setFocus()  # it scrolls with the keys, and passes Esc on to close
        self._fit()

    def chatting(self, on: bool) -> None:
        """Asking questions (on), or something else (naming the chatmon): only questions take attachments
        and have a history."""
        self.attach_button.setVisible(on)
        self.history_button.setVisible(on)

    def set_attachments(self, labels: list[str]) -> None:
        """Show what's attached to the next question, each with a ✕ that takes it off."""
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._attached = len(labels)
        metrics = QFontMetricsF(_font(9))
        room, used, shown = self._content_width(), 0.0, 0
        for i, label in enumerate(labels):
            name = label.rpartition(" (")[0] or label  # "notes.md (2 KB)": the name on the chip, the size in its tip
            more = 64 if i < len(labels) - 1 else 0  # room left for "+2 more"
            space = min(150.0, room - used - more - 22 - metrics.horizontalAdvance("  ✕"))  # 22: padding and border
            if shown and space < 56:  # too little for a name you could read
                break
            text = metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, max(space, 56)) + "  ✕"
            width = metrics.horizontalAdvance(text) + 22
            chip = QToolButton(text=text)
            chip.setObjectName("chip")
            chip.setToolTip(plain_tip(f"{label}: click to take it off"))
            chip.setAccessibleName(f"Remove {label}")
            chip.clicked.connect(lambda _=False, i=i: self.attachment_removed.emit(i))
            self.chips_layout.addWidget(chip)
            used += width + 4
            shown += 1
        shown = labels[:shown]
        if len(labels) > len(shown):
            more = QLabel(f"+{len(labels) - len(shown)} more")
            more.setObjectName("hint")
            self.chips_layout.addWidget(more)
        self.chips_layout.addStretch(1)
        self.chips.setVisible(bool(labels))
        self._fit()

    def paste_clipboard(self) -> None:
        """Ctrl+V, or Paste: files and pictures attach; long text attaches; short text goes in the field."""
        found = None
        if sys.platform == "win32":  # files that aren't on disk (copied out of Outlook or a zip): never through Qt
            from . import windrop

            named = windrop.clipboard_named()
            found = ("named", named) if named else None
        found = found or clipboard_contents(QGuiApplication.clipboard().mimeData())
        if found is not None:
            self.take_paste(*found)

    def paste_overlay(self, mime: str, data: bytes) -> None:
        """A paste on the Wayland overlay, from its own clipboard."""
        found = overlay_contents(mime, data)
        if found is not None:
            self.take_paste(*found)

    def take_paste(self, kind: str, payload) -> None:
        from .attachments import long_paste

        if kind == "text" and not long_paste(payload):
            self.entry.insert(" ".join(payload.splitlines()))
        else:
            self.pasted.emit(kind, payload)

    def dragEnterEvent(self, event) -> None:
        if self.entry.isVisible() and clipboard_contents(event.mimeData()) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        found = clipboard_contents(event.mimeData())
        if found is not None:
            event.acceptProposedAction()
            self.take_drop(*found)

    def take_drop(self, kind: str, payload) -> None:
        self.pasted.emit(kind, payload) if kind != "text" else self.take_paste(kind, payload)

    def _own_drops(self) -> None:
        """On Windows, this window's drops go to Chatmon's own drop target (windrop.py), not Qt's, which
        corrupts the heap reading a file dropped out of a zip."""
        if sys.platform != "win32" or QGuiApplication.platformName() != "windows" or self.stage_draws_art:
            return
        if self._drop_target is None:
            from . import windrop

            self._drop_target = windrop.DropTarget(self.entry.isVisible, self.take_drop)
        self._drop_target.attach(int(self.winId()))

    def _below(self, widget: QWidget) -> QPoint:
        return widget.mapToGlobal(QPoint(0, widget.height()))

    def pause(self) -> None:
        """Out of the way while a dialog of the system's is open (it needs the keyboard): back with resume()."""
        self.hide()
        self._frames.stop()

    def resume(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()
        self._run_frames()

    def set_answer(self, markdown: str, at_end: bool = False) -> None:
        """What the bubble shows above the field: an answer, or the whole chat (`at_end`: scrolled to its
        latest, as a chat is read)."""
        self._markdown = markdown
        if markdown:
            c = self.style.colours()
            self.highlighter.set_colours(highlight.code_colours(c))
            richtext.render(self.answer.document(), markdown, look(c, BODY_POINTS))
            doc = self.answer.document()
            doc.setTextWidth(self._content_width() - 10)
            self.answer.setFixedHeight(min(int(doc.size().height()) + 4, self.MAX_ANSWER))
            self.answer.show()
        else:
            self.answer.clear()
            self.answer.hide()
        self._fit()
        bar = self.answer.verticalScrollBar()
        bar.setValue(bar.maximum() if at_end else 0)

    def set_resettable(self, on: bool) -> None:
        self.reset_button.setVisible(on)

    def input_rects(self) -> list[QRect]:
        """The bubble and its tail, without the see-through margin around them."""
        h = self.height()
        if self.art:
            k, (x0, y0, x1, y1) = self.art.k, self.art.text
            body = QRect(round(x0 * k), round(y0 * k), round(self.width() - (self.art.w - x1) * k - x0 * k), round(h - (self.art.h - y1) * k - y0 * k))
            tip_y = round(body.bottom() + (self.art.tip[1] - y1) * k)
            tail = QRect(round(self._tail_x) - 12, body.bottom() - 2, 24, max(4, tip_y - body.bottom() + 2))
            return [body, tail]
        body = QRect(0, 0, self.width(), h - TAIL)
        tail = QRect(round(self._tail_x) - 10, h - TAIL - 1, 20, TAIL + 1)
        return [body, tail]

    def place(self, anchor: QPoint) -> None:
        self._anchor = QPoint(anchor)
        self._fit()

    def dismiss(self) -> None:
        if self.isVisible():
            self.hide()
            self.closed.emit()

    def _fit(self) -> None:
        layout = self.layout()
        layout.activate()
        height = layout.totalSizeHint().height()
        screen = QGuiApplication.screenAt(self._anchor) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(self._anchor.x() - self.WIDTH // 2, geo.left() + 4), geo.right() - self.WIDTH - 4)
        y = max(self._anchor.y() - height, geo.top() + 4)
        if self.art:
            lo, hi = self.art.tail_range(self._content_width())
        else:
            lo, hi = RADIUS + TAIL, self.WIDTH - RADIUS - TAIL
        self._tail_x = min(max(self._anchor.x() - x, lo), hi)
        self.setGeometry(x, y, self.WIDTH, height)
        self.update()

    def _submit(self) -> None:
        text = self.entry.text().strip()
        if text or (self._attached and self.attach_button.isVisible()):
            self.entry.clear()
            self.submitted.emit(text)

    def _style(self) -> None:
        c = self.style.colours()
        text, title, dim, base, accent = c.body.name(), c.title.name(), c.dim.name(), c.entry.name(), c.accent.name()
        selection = f"selection-background-color: {c.selection.name()}; selection-color: {c.selection_text.name()};"
        self.setStyleSheet(
            f"""
            QLabel, QTextBrowser {{ color: {text}; background: transparent; font-size: 10.5pt; {selection} }}
            QLabel#title {{ font-weight: 600; color: {title}; }}
            QLabel#hint {{ color: {dim}; font-size: 9pt; }}
            QLineEdit {{ border: 1px solid {accent}; border-radius: 8px; padding: 6px 8px;
                         background: {base}; color: {c.entry_text.name()}; font-size: 10.5pt; {selection} }}
            QToolButton {{ color: {title}; border: none; padding: 2px 6px; }}
            QToolButton:hover {{ color: {c.link.name()}; }}
            QToolButton#attach {{ color: {accent}; border: 1.5px solid {accent}; border-radius: 13px;
                                  min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
                                  padding: 0 0 2px 0; font-size: 14pt; font-weight: 700; background: {base}; }}
            QToolButton#attach:hover {{ color: {base}; background: {accent}; }}
            QToolButton#chip {{ color: {c.entry_text.name()}; border: 1px solid {accent}; border-radius: 9px;
                                padding: 1px 8px; font-size: 9pt; background: {base}; }}
            QToolButton#chip:hover {{ color: {c.link.name()}; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {accent}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """
        )
        for child in self.findChildren(QWidget):
            child.ensurePolished()
        hint = self.entry.palette()
        hint.setColor(QPalette.ColorRole.PlaceholderText, c.placeholder)
        self.entry.setPalette(hint)

    def hideEvent(self, event) -> None:
        self._frames.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._own_drops()
        if QGuiApplication.platformName() == "cocoa" and not self.stage_draws_art:
            from . import macnative

            macnative.float_everywhere(self)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.art:
            if not self.stage_draws_art:
                self.paint_art(p, 0, 0)
            return
        c = self.style.colours()
        fill = QColor(c.fill)
        fill.setAlpha(PLAIN_ALPHA)
        path = bubble_path(QRectF(self.rect()).adjusted(1, 1, -1, -1 - TAIL), self._tail_x)
        p.fillPath(path, fill)
        p.setPen(QPen(c.accent, 2))
        p.drawPath(path)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        # The window manager closed it (Super+C and the like): same as Esc, so
        # the penguin stops waiting on a question nobody can see.
        event.ignore()
        self.dismiss()
