"""Speech bubbles: messages drawn by the stage, and the ask box you type in."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QMarginsF, QPoint, QPointF, QRectF, QSizeF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QAbstractTextDocumentLayout,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QPainter,
    QPalette,
    QPen,
    QTextDocument,
)
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from . import styles

RADIUS = styles.RADIUS
FADE = 0.14  # seconds


def open_link(url: QUrl) -> None:
    """Links in answers open in the browser; nothing else (no files, no apps)."""
    if url.scheme() in ("http", "https", "mailto"):
        QDesktopServices.openUrl(url)


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
        self.doc = QTextDocument()
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
        self.style = styles.get(None)
        self.animate = True
        self._rim: styles.Rim | None = None
        self._pad, self._tail = styles.PAD, styles.TAIL

    def set_style(self, style: styles.Style, animate: bool) -> None:
        self.style, self.animate = style, animate

    def margins(self) -> QMarginsF:
        """Room around the bubble that its rim's effect reaches into."""
        return self.style.reach(self.animate)

    def age(self, now: float) -> float:
        return now - self._shown_at

    def animating(self, now: float) -> bool:
        """Changing every frame: popping up, or a rim effect running."""
        if not self._visible:
            return False
        return self.animate and (bool(self.style.effect) or now - self._shown_at < styles.POP)

    def visible(self) -> bool:
        """Showing and not on its way out."""
        return self._visible and self._closing_at is None

    def drawn(self) -> bool:
        """Still on screen, perhaps fading out."""
        return self._visible

    def show(self, title: str, text: str, buttons, timeout_s: float | None, now: float) -> None:
        self.title = title
        self.hover = None
        title_font, body_font = _font(10.5, bold=True), _font(10.5)
        self.doc.setDefaultFont(body_font)
        self.doc.setMarkdown(text or "")
        has_text = bool(text)
        metrics = QFontMetricsF(body_font)
        self.buttons = [_Button(label, action, QRectF(0, 0, metrics.horizontalAdvance(label) + 26, metrics.height() + 10)) for label, action in buttons or []]
        title_w = QFontMetricsF(title_font).horizontalAdvance(title) + 28
        buttons_w = sum(b.rect.width() for b in self.buttons) + 8 * max(0, len(self.buttons) - 1)
        pad, tail = styles.padding(self.style), styles.tail_height(self.style)
        self._pad, self._tail = pad, tail
        inner_max = self.MAX_WIDTH - 2 * pad
        self.doc.setTextWidth(inner_max)
        inner = min(inner_max, max(140, title_w, buttons_w, self.doc.idealWidth() + 1 if has_text else 0))
        self.doc.setTextWidth(inner)
        title_h = QFontMetricsF(title_font).height()
        height = pad + title_h
        self._body_top = height + 6
        if has_text:
            height += 6 + self.doc.size().height()
        if self.buttons:
            height += 10
            x = pad + inner
            for b in reversed(self.buttons):
                x -= b.rect.width()
                b.rect.moveTo(x, height)
                x -= 8
            height += self.buttons[0].rect.height()
        height += pad
        self.size = QSizeF(inner + 2 * pad, height + tail)
        self._close_rect = QRectF(pad + inner - 16, pad - 2, 20, title_h + 4)
        self._shown_at, self._closing_at = now, None
        self._rim = None
        self._expires = now + timeout_s if timeout_s else None
        self._visible = True
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
        if QRectF(0, 0, self.size.width(), self.size.height() - self._tail).contains(pos):
            return "body"
        return None

    def paint(self, p: QPainter, tail_x: float, now: float) -> None:
        style = self.style
        _, text = style.colours()
        pad = self._pad
        accent, on_accent = QColor(style.accent), QColor(style.on_accent)
        age = now - self._shown_at
        p.save()
        p.setOpacity(self.opacity(now))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.animate:  # pop up from the tail's tip, shrink a little on the way out
            scale = styles.pop_scale(age)
            if self._closing_at is not None:
                scale *= 1 - 0.06 * min(1.0, (now - self._closing_at) / FADE)
            tip = QPointF(tail_x, self.size.height())
            p.translate(tip)
            p.scale(scale, scale)
            p.translate(-tip)
        box = QRectF(1, 1, self.size.width() - 2, self.size.height() - self._tail - 2)
        if self._rim is None or self._rim.box != box:
            self._rim = styles.Rim(box, RADIUS)
        styles.paint_under(p, style, self._rim, age, self.animate)
        styles.paint_body(p, style, box, tail_x)
        styles.paint_over(p, style, self._rim, age, self.animate)
        p.setPen(text)
        p.setFont(self._title_font)
        p.drawText(QRectF(pad, pad, self.size.width() - 2 * pad - 20, 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.title)
        p.setFont(_font(9.5))
        p.drawText(self._close_rect, Qt.AlignmentFlag.AlignCenter, "✕")
        if self._has_text:
            p.save()
            p.translate(pad, self._body_top)
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette.setColor(QPalette.ColorRole.Text, text)
            self.doc.documentLayout().draw(p, ctx)
            p.restore()
        p.setFont(_font(10))
        for i, b in enumerate(self.buttons):
            p.setBrush(accent if i == self.hover else Qt.BrushStyle.NoBrush)
            p.setPen(QPen(accent, 1.2))
            p.drawRoundedRect(b.rect.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
            p.setPen(on_accent if i == self.hover else text)
            p.drawText(b.rect, Qt.AlignmentFlag.AlignCenter, b.label)
        p.restore()


class AskBox(QWidget):
    """The bubble you type questions into. A real window, since it needs the
    keyboard; the penguin holds still while it's open."""

    closed = pyqtSignal()
    submitted = pyqtSignal(str)
    reset_requested = pyqtSignal()

    WIDTH = 380
    MAX_ANSWER = 320

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self._anchor = QPoint(0, 0)
        self._tail_x = self.WIDTH / 2
        self.style = styles.get(None)
        self.animate = True
        self._margins = QMarginsF()
        self._opened_at = time.monotonic()
        self._rim: styles.Rim | None = None
        self._tail = styles.TAIL
        self._frames = QTimer(self)  # redraws the rim's effect while it's open
        self._frames.setInterval(33)
        self._frames.timeout.connect(self.update)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("title")
        top.addWidget(self.title, 1)
        self.reset_button = QToolButton(text="New chat", autoRaise=True)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        top.addWidget(self.reset_button)
        close = QToolButton(text="✕", autoRaise=True)
        close.setToolTip("Close (Esc)")
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        layout.addLayout(top)
        self.answer = QTextBrowser(openLinks=False)
        self.answer.anchorClicked.connect(open_link)
        self.answer.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.answer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.answer.document().setDocumentMargin(2)
        layout.addWidget(self.answer)
        self.entry = QLineEdit()
        self.entry.returnPressed.connect(self._submit)
        layout.addWidget(self.entry)
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        layout.addWidget(self.hint)
        self.set_style(self.style, self.animate)

    def set_style(self, style: styles.Style, animate: bool) -> None:
        self.style, self.animate = style, animate
        m = style.reach(animate)
        self._margins = m
        self.setFixedWidth(self.WIDTH + round(m.left() + m.right()))
        pad, self._tail = styles.padding(style), styles.tail_height(style)
        side, top = round(pad), round(max(12, pad - 4))
        self.layout().setContentsMargins(side + round(m.left()), top + round(m.top()), side + round(m.right()), top + 2 + round(self._tail + m.bottom()))
        self._rim = None
        self._style()
        if self.isVisible():
            self._fit()
            self._run_frames()

    def _run_frames(self) -> None:
        if self.isVisible() and self.animate and (self.style.effect or time.monotonic() - self._opened_at < styles.POP):
            self._frames.start()
        else:
            self._frames.stop()

    def open(self, anchor: QPoint, title: str, hint: str, placeholder: str, text: str = "", prefill: str = "") -> None:
        self.title.setText(title)
        self.hint.setText(QFontMetricsF(self.hint.font()).elidedText(hint, Qt.TextElideMode.ElideRight, self.WIDTH - 34))
        self.entry.setPlaceholderText(placeholder)
        self.entry.setText(prefill)
        self.reset_button.hide()
        self._anchor = QPoint(anchor)
        self.set_answer(text)
        if not self.isVisible():
            self._opened_at = time.monotonic()
        self.show()
        self._run_frames()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()
        self.entry.end(False)

    def set_answer(self, markdown: str) -> None:
        if markdown:
            self.answer.setMarkdown(markdown)
            doc = self.answer.document()
            doc.setTextWidth(self.WIDTH - 32 - 10)
            self.answer.setFixedHeight(min(int(doc.size().height()) + 4, self.MAX_ANSWER))
            self.answer.show()
        else:
            self.answer.clear()
            self.answer.hide()
        self._fit()
        self.answer.verticalScrollBar().setValue(0)

    def set_resettable(self, on: bool) -> None:
        self.reset_button.setVisible(on)

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
        m = self._margins
        left, top, bottom = round(m.left()), round(m.top()), round(m.bottom())
        # The bubble stays on screen and its tail's tip on the anchor; the
        # rim's effect may run off the screen's edge.
        x = min(max(self._anchor.x() - self.WIDTH // 2, geo.left() + 4), geo.right() - self.WIDTH - 4)
        y = max(self._anchor.y() - height + bottom, geo.top() + 4 - top)
        self._tail_x = min(max(self._anchor.x() - x, RADIUS + 24), self.WIDTH - RADIUS - 24)
        self.setGeometry(x - left, y, self.width(), height)
        self.update()

    def _submit(self) -> None:
        text = self.entry.text().strip()
        if text:
            self.entry.clear()
            self.submitted.emit(text)

    def _style(self) -> None:
        bottom, text = self.style.colours()
        accent = self.style.accent
        dim = QColor(text)
        dim.setAlpha(170)
        if not self.style.fill:
            base = QApplication.palette().color(QPalette.ColorRole.Base)
            link = QApplication.palette().color(QPalette.ColorRole.Link)
        else:
            base = QColor(bottom).lighter(140) if self.style.dark() else QColor("#ffffff")
            link = QColor(accent)
        self.answer.document().setDefaultStyleSheet(f"a {{ color: {link.name()}; }}")
        self.setStyleSheet(
            f"""
            QLabel, QTextBrowser {{ color: {text.name()}; background: transparent; font-size: 10.5pt; }}
            QLabel#title {{ font-weight: 600; }}
            QLabel#hint {{ color: {dim.name(QColor.NameFormat.HexArgb)}; font-size: 9pt; }}
            QLineEdit {{ border: 1px solid {accent}; border-radius: 8px; padding: 6px 8px;
                         background: {base.name()}; color: {text.name()}; font-size: 10.5pt;
                         selection-background-color: {accent}; selection-color: {self.style.on_accent}; }}
            QToolButton {{ color: {text.name()}; border: none; padding: 2px 6px; }}
            QToolButton:hover {{ color: {accent}; }}
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

    def paintEvent(self, _event) -> None:
        age = time.monotonic() - self._opened_at
        if self._frames.isActive() and not self.style.effect and age >= styles.POP:
            self._frames.stop()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).marginsRemoved(self._margins)
        box = area.adjusted(1, 1, -1, -1 - self._tail)
        if self.animate:  # pop up from the tail's tip
            scale = styles.pop_scale(age)
            tip = QPointF(area.left() + self._tail_x, area.bottom())
            p.translate(tip)
            p.scale(scale, scale)
            p.translate(-tip)
        if self._rim is None or self._rim.box != box:
            self._rim = styles.Rim(box, RADIUS)
        styles.paint_under(p, self.style, self._rim, age, self.animate)
        styles.paint_body(p, self.style, box, area.left() + self._tail_x)
        styles.paint_over(p, self.style, self._rim, age, self.animate)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(event)
