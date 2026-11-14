"""Speech bubbles: messages drawn by the stage, and the ask box you type in.

Both are drawn in the chosen bubble style (styles.py): a painted, animated bubble (bubbleart.py) with
its notch pointing at the penguin, or the plain one in the desktop's own colours.
"""

from __future__ import annotations

import html
import os
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
)
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from . import bubbleart, richtext, styles

ACCENT = QColor(styles.PLAIN_ACCENT)  # the penguin's glowing cyan nodes
PAD = 14
TAIL = 12
RADIUS = 14
FADE = 0.14  # seconds
SPILL = 3  # px an effect may reach past a bubble's frame (a flame's tip): the stage draws that much round it
ANIM_FPS = 30  # how often an animated bubble is redrawn (its frames crossfade in between)


def open_link(url: QUrl) -> None:
    """Links in answers open in the browser; nothing else (no files, no apps)."""
    if url.scheme() in ("http", "https", "mailto"):
        QDesktopServices.openUrl(url)


def colours() -> tuple[QColor, QColor]:
    """The plain bubble's fill and text, from the desktop's light or dark theme."""
    pal = QApplication.palette()
    fill = QColor(pal.color(QPalette.ColorRole.Base))
    fill.setAlpha(248)
    return fill, QColor(pal.color(QPalette.ColorRole.Text))


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


def _font(points: float, bold: bool = False) -> QFont:
    font = QFont(QApplication.font())
    font.setPointSizeF(points)
    font.setBold(bold)
    return font


@dataclass
class _Button:
    label: str
    action: Callable[[], None] | None
    rect: QRectF


class SpeechBubble:
    """A message above the penguin's head. It has no window of its own: the
    stage draws it, so it follows the penguin smoothly."""

    MAX_WIDTH = 340

    def __init__(self):
        self.title = ""
        self.doc = richtext.SafeDocument()
        self.doc.setDocumentMargin(0)
        self.buttons: list[_Button] = []
        self.size = QSizeF()
        self.hover: int | None = None
        self.on_close: Callable[[], None] | None = None
        self._shown_at = 0.0
        self._expires: float | None = None
        self._closing_at: float | None = None
        self._visible = False
        self._close_rect = QRectF()
        self._body_top = 0.0
        self._body = QRectF()
        self._content = QRectF()
        self.style = styles.get(None)
        self.animate = True
        self.art = bubbleart.art(self.style.name, "message")
        self._words: tuple[tuple, QPixmap] | None = None  # the title, text and buttons, drawn once
        self._frame: tuple[tuple, QPixmap] | None = None  # the whole bubble, drawn once per frame of its animation

    def set_style(self, style: styles.Style, animate: bool) -> None:
        """Draw in `style` from the next message on (and the one showing, if any)."""
        self.style, self.animate = style, animate
        self.art = bubbleart.art(style.name, "message")
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
        self._shown_at, self._closing_at = now, None
        self._expires = now + timeout_s if timeout_s else None
        self._visible = True
        self._layout()

    def _layout(self) -> None:
        """Lay the title, text and buttons out (from 0, 0), then put them inside the bubble."""
        self._words = None
        self._frame = None
        title_font, body_font = _font(10.5, bold=True), _font(10.5)
        self.doc.setDefaultFont(body_font)
        richtext.set_markdown(self.doc, self._text)
        has_text = bool(self._text)
        metrics = QFontMetricsF(body_font)
        self.buttons = [_Button(label, action, QRectF(0, 0, metrics.horizontalAdvance(label) + 28, metrics.height() + 10)) for label, action in self._button_specs]
        title_w = QFontMetricsF(title_font).horizontalAdvance(self.title) + 28
        buttons_w = sum(b.rect.width() for b in self.buttons) + 8 * max(0, len(self.buttons) - 1)
        inner_max = self.MAX_WIDTH - 2 * PAD  # the text's widest, whatever bubble it's in
        self.doc.setTextWidth(inner_max)
        inner = min(inner_max, max(160, title_w, buttons_w, self.doc.idealWidth() + 1 if has_text else 0))
        self.doc.setTextWidth(inner)
        title_h = QFontMetricsF(title_font).height()
        height = title_h
        body_top = height + 6
        if has_text:
            height += 6 + self.doc.size().height()
        if self.buttons:
            height += 12
            x = inner
            for b in reversed(self.buttons):
                x -= b.rect.width()
                b.rect.moveTo(x, height)
                x -= 8
            height += self.buttons[0].rect.height()
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
        self._close_rect = QRectF(origin.x() + inner - 18, origin.y() - 3, 22, title_h + 6)
        self._title_font, self._has_text = title_font, has_text

    def dismiss(self, now: float) -> None:
        """Closed as far as anyone is concerned; it fades out on its own."""
        if self.visible():
            self._closing_at = now
            self._expires = None
            if self.on_close:
                self.on_close()

    def tick(self, now: float) -> None:
        if self._expires is not None and now >= self._expires:
            self.dismiss(now)
        if self._closing_at is not None and now - self._closing_at >= FADE:
            self._visible, self._closing_at = False, None

    def opacity(self, now: float) -> float:
        if self._closing_at is not None:
            return max(0.0, 1 - (now - self._closing_at) / FADE)
        return min(1.0, (now - self._shown_at) / FADE)

    def hit(self, pos: QPointF) -> str | int | None:
        """What's at `pos` (bubble coordinates): a button's index, "close", "body"."""
        if self._close_rect.contains(pos):
            return "close"
        for i, b in enumerate(self.buttons):
            if b.rect.contains(pos):
                return i
        if self._body.contains(pos):
            return "body"
        return None

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
        if self.art:
            title_c, body_c = self.style.text_colours()
            colours_key: tuple = ()
        else:
            fill, text = colours()
            title_c = body_c = text
            colours_key = (fill.rgba(), text.rgba())
        size = (max(1, round((self.size.width() + 2 * SPILL) * ratio)), max(1, round((self.size.height() + 2 * SPILL) * ratio)))
        key = (ratio, size, round(tail_x * ratio), self.hover, self.anim_key(now), self.style.name, colours_key, title_c.rgba(), body_c.rgba())
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
                q.fillPath(path, fill)
                q.setPen(QPen(ACCENT, 2))
                q.drawPath(path)
            q.drawPixmap(QPointF(0, 0), self._words_pixmap(q, title_c, body_c))
            q.end()
            self._frame = (key, pix)
        return self._frame[1]

    def _words_pixmap(self, p: QPainter, title_c: QColor, body_c: QColor) -> QPixmap:
        """The title, ✕, text and buttons on a see-through pixmap the bubble's size. An animated bubble is
        drawn thirty times a second and laying out its text each time cost as much as some styles' art,
        so they are drawn once per message, button hovered and colours."""
        ratio = bubbleart.device_ratio(p)
        key = (ratio, self.hover, title_c.rgba(), body_c.rgba(), self.style.name)
        if self._words is None or self._words[0] != key:
            pix = QPixmap(max(1, round(self.size.width() * ratio)), max(1, round(self.size.height() * ratio)))
            pix.setDevicePixelRatio(ratio)
            pix.fill(Qt.GlobalColor.transparent)
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._draw_words(q, title_c, body_c)
            q.end()
            self._words = (key, pix)
        return self._words[1]

    def _draw_words(self, p: QPainter, title_c: QColor, body_c: QColor) -> None:
        style = self.style
        c = self._content
        p.setPen(title_c)
        p.setFont(self._title_font)
        p.drawText(QRectF(c.x(), c.y(), c.width() - 20, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.title)
        p.setFont(_font(9.5))
        p.drawText(self._close_rect, Qt.AlignmentFlag.AlignCenter, "✕")
        if self._has_text:
            p.save()
            p.translate(c.x(), self._body_top)
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette.setColor(QPalette.ColorRole.Text, body_c)
            ctx.palette.setColor(QPalette.ColorRole.Link, QColor(style.accent))
            self.doc.documentLayout().draw(p, ctx)
            p.restore()
        p.setFont(_font(10))
        for i, b in enumerate(self.buttons):
            look = style.primary if i == 0 else style.other
            outline = QColor(look.outline)
            if i == self.hover:  # lit up: filled with its outline colour
                fill, label = outline, QColor(look.fill) if look.fill and self.art else QColor("white")
            else:
                fill = QColor(look.fill) if look.fill else None
                label = QColor(look.text) if look.text else body_c
            p.setBrush(fill if fill is not None else Qt.BrushStyle.NoBrush)
            p.setPen(QPen(outline, 1.5))
            r = b.rect.adjusted(0.75, 0.75, -0.75, -0.75)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            p.setPen(label)
            p.drawText(b.rect, Qt.AlignmentFlag.AlignCenter, b.label)


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
        self.answer.setAccessibleName("Conversation")
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
            self.set_answer(self.answer.toMarkdown() if self.answer.isVisible() else "")
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
        if markdown:
            richtext.set_markdown(self.answer.document(), markdown)
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
        if self.art:
            title, text = self.style.text_colours()
        else:
            _, text = colours()
            title = text
        dim = QColor(text)
        dim.setAlpha(165)
        base = self.style.entry_colour() if self.art else QApplication.palette().color(QPalette.ColorRole.Base)
        accent = self.style.accent if self.art else ACCENT.name()
        self.answer.document().setDefaultStyleSheet(f"a {{ color: {accent}; }}")
        self.setStyleSheet(
            f"""
            QLabel, QTextBrowser {{ color: {text.name()}; background: transparent; font-size: 10.5pt; }}
            QLabel#title {{ font-weight: 600; color: {title.name()}; }}
            QLabel#hint {{ color: {dim.name(QColor.NameFormat.HexArgb)}; font-size: 9pt; }}
            QLineEdit {{ border: 1px solid {accent}; border-radius: 8px; padding: 6px 8px;
                         background: {base.name()}; color: {text.name()}; font-size: 10.5pt;
                         selection-background-color: {accent}; }}
            QToolButton {{ color: {title.name()}; border: none; padding: 2px 6px; }}
            QToolButton:hover {{ color: {accent}; }}
            QToolButton#attach {{ color: {accent}; border: 1.5px solid {accent}; border-radius: 13px;
                                  min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
                                  padding: 0 0 2px 0; font-size: 14pt; font-weight: 700; background: {base.name()}; }}
            QToolButton#attach:hover {{ color: {base.name()}; background: {accent}; }}
            QToolButton#chip {{ color: {text.name()}; border: 1px solid {accent}; border-radius: 9px;
                                padding: 1px 8px; font-size: 9pt; background: {base.name()}; }}
            QToolButton#chip:hover {{ color: {accent}; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {accent}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """
        )
        for child in self.findChildren(QWidget):
            child.ensurePolished()

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
        fill, _ = colours()
        path = bubble_path(QRectF(self.rect()).adjusted(1, 1, -1, -1 - TAIL), self._tail_x)
        p.fillPath(path, fill)
        p.setPen(QPen(ACCENT, 2))
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
