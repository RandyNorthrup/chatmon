"""Chat bubble styles: which painted bubble, and the text and button colours that go on it.

The bubbles themselves are painted art (chatmon/bubbles, drawn by bubbleart.py); the plain
style has none and uses the desktop's own colours, high contrast themes included.

Every colour a style puts text in is chosen to be read: 4.5:1 against what it sits on (WCAG AA for
text), and 3:1 for outlines that show where a control is. The painted styles' colours are fixed and
checked by the tests against their art; the plain style's come from the desktop's palette, and any pair
the palette leaves short of that is darkened or lightened until it reads (`readable`).
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

DEFAULT = "electric"
TEXT_CONTRAST = 4.5  # WCAG AA, normal-size text
OUTLINE_CONTRAST = 3.0  # WCAG 1.4.11: a control's outline, a focus ring
DIM_ALPHA = 165  # hints are the body colour, this see-through, unless that reads too faintly
ART_MARGIN = 0.5  # painted fills aren't flat: hints keep this much past 4.5:1 to read on all of one
CODE_TINT = 0.09  # how far a code block's background leans from the fill toward the text colour


@dataclass(frozen=True)
class Button:
    fill: str  # empty: no fill
    outline: str
    text: str  # empty: the body colour
    hover_text: str  # the label while it's lit up (filled with its outline colour); empty: the desktop's


@dataclass(frozen=True)
class ButtonLook:
    """A button's colours, resolved: what is drawn."""

    fill: QColor | None
    outline: QColor
    text: QColor
    hover_fill: QColor
    hover_text: QColor


@dataclass(frozen=True)
class Colours:
    """Everything a bubble is drawn in, resolved for this style (and, for the plain one, this palette)."""

    fill: QColor  # what the text sits on
    title: QColor
    body: QColor
    dim: QColor  # hints and the field's placeholder: opaque, already blended onto the fill
    link: QColor
    accent: QColor  # the field's border, focus outlines, rules between turns, scroll bars
    selection: QColor
    selection_text: QColor
    entry: QColor  # the field's background
    entry_text: QColor
    placeholder: QColor  # the field's hint while it's empty
    code_fill: QColor  # a code block's background
    primary: ButtonLook
    other: ButtonLook


@dataclass(frozen=True)
class Style:
    name: str
    label: str
    title: str  # empty: the desktop's own colours (the plain style)
    body: str
    primary: Button  # the first button (the one that does something)
    other: Button
    entry: str  # the ask box's text field; empty: the desktop's
    accent: str  # the entry's border, focus outlines, scroll bars
    fill: str = ""  # the painted bubble's fill under the text, measured from its art; empty: the desktop's
    link: str = ""  # links; empty: the desktop's
    selection: str = ""  # selected text's background; empty: the desktop's
    selection_text: str = ""

    def text_colours(self) -> tuple[QColor, QColor]:
        """Title and body colours."""
        c = self.colours()
        return c.title, c.body

    def entry_colour(self) -> QColor:
        return self.colours().entry

    def colours(self, palette: QPalette | None = None) -> Colours:
        """This style's colours. The plain style reads them from `palette` (the app's, by default)."""
        if self.title:
            return self._painted()
        return _plain(palette if palette is not None else QApplication.palette())

    def _painted(self) -> Colours:
        fill, body = QColor(self.fill), QColor(self.body)
        return Colours(
            fill=fill,
            title=QColor(self.title),
            body=body,
            dim=readable(blend(body, fill, DIM_ALPHA), fill, TEXT_CONTRAST + ART_MARGIN),
            link=QColor(self.link),
            accent=QColor(self.accent),
            selection=QColor(self.selection),
            selection_text=QColor(self.selection_text),
            entry=QColor(self.entry),
            entry_text=body,
            placeholder=readable(blend(body, QColor(self.entry), DIM_ALPHA), QColor(self.entry)),
            code_fill=mix(fill, body, CODE_TINT),
            primary=_button(self.primary, body),
            other=_button(self.other, body),
        )


def _button(b: Button, body: QColor) -> ButtonLook:
    outline = QColor(b.outline)
    return ButtonLook(QColor(b.fill) if b.fill else None, outline, QColor(b.text) if b.text else QColor(body), outline, QColor(b.hover_text))


def _plain(pal: QPalette) -> Colours:
    """The desktop's own colours, each pair made to read: a high contrast theme's pass as they are."""

    def role(r: QPalette.ColorRole) -> QColor:
        c = QColor(pal.color(QPalette.ColorGroup.Active, r))
        c.setAlpha(255)
        return c

    fill = role(QPalette.ColorRole.Base)
    code_fill = mix(fill, role(QPalette.ColorRole.Text), CODE_TINT)
    text = readable(role(QPalette.ColorRole.Text), code_fill)  # on the code panel too, a shade nearer the text than the fill
    highlight = readable(role(QPalette.ColorRole.Highlight), fill, OUTLINE_CONTRAST)
    highlighted = readable(role(QPalette.ColorRole.HighlightedText), highlight)
    button = role(QPalette.ColorRole.Button)
    button_text = readable(role(QPalette.ColorRole.ButtonText), button)
    pressed = highlight.darker(125) if luminance(highlight) > 0.18 else highlight.lighter(130)  # lit up: a shade off the plain one
    return Colours(
        fill=fill,
        title=text,
        body=text,
        dim=readable(blend(text, fill, DIM_ALPHA), fill),
        link=readable(role(QPalette.ColorRole.Link), code_fill),
        accent=highlight,
        selection=highlight,
        selection_text=highlighted,
        entry=fill,
        entry_text=text,
        placeholder=readable(blend(text, fill, DIM_ALPHA), fill),
        code_fill=code_fill,
        primary=ButtonLook(highlight, highlight, highlighted, pressed, readable(highlighted, pressed)),
        other=ButtonLook(button, highlight, button_text, highlight, highlighted),
    )


# -- contrast (WCAG 2.x relative luminance and contrast ratio)


def luminance(c: QColor) -> float:
    def channel(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(c.red()) + 0.7152 * channel(c.green()) + 0.0722 * channel(c.blue())


def contrast(a: QColor, b: QColor) -> float:
    """WCAG contrast ratio of two opaque colours, 1 to 21."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mix(a: QColor, b: QColor, share: float) -> QColor:
    """`a` moved `share` (0..1) of the way to `b`, opaque."""
    return QColor(*(round(x + (y - x) * share) for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))))


def blend(fg: QColor, bg: QColor, alpha: int) -> QColor:
    """`fg` at `alpha` (0..255) laid over an opaque `bg`: the colour you see."""
    return mix(bg, fg, alpha / 255)


def readable(fg: QColor, bg: QColor, ratio: float = TEXT_CONTRAST) -> QColor:
    """`fg`, or the nearest shade of it toward black or white (whichever the background is further from)
    that reaches `ratio` against `bg`."""
    if contrast(fg, bg) >= ratio:
        return QColor(fg)
    black, white = QColor(0, 0, 0), QColor(255, 255, 255)
    target = black if contrast(black, bg) >= contrast(white, bg) else white
    for step in range(1, 21):
        c = mix(fg, target, step / 20)
        if contrast(c, bg) >= ratio:
            return c
    return target


PLAIN_ACCENT = "#26b8d9"  # the penguin's glowing cyan nodes (the stage's menus still wear it)

# Colours matched to the approved mock-ups (art/bubbles/README.md); `fill` is measured from each style's art
# (tests/test_contrast.py checks it), and links, selections and lit-up buttons were set to read on it.
STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style(
            "electric", "Electric", "#ffffff", "#d6ecff",
            Button("#0e2a55", "#45d3f7", "#ffffff", "#0e2a55"), Button("#0b1d3d", "#2fa9cf", "#ffffff", "#0b1d3d"),
            "#0a1a36", "#45d3f7", fill="#072449", link="#45d3f7", selection="#45d3f7", selection_text="#0a1a36",
        ),
        Style(
            "fire", "Fire", "#fff4ea", "#f3dccd",
            Button("#2a130c", "#ff8a2a", "#ffffff", "#2a130c"), Button("#1f0e0a", "#d9661f", "#ffffff", "#1f0e0a"),
            "#170907", "#ff8a2a", fill="#310d05", link="#ff8a2a", selection="#ff8a2a", selection_text="#170907",
        ),
        Style(
            "ghost", "Ghost", "#ffffff", "#e2ddf0",
            Button("#33313f", "#ddd2f7", "#ffffff", "#33313f"), Button("#2b2a35", "#b9afd6", "#ffffff", "#2b2a35"),
            "#24232c", "#c9bdf0", fill="#343744", link="#c9bdf0", selection="#c9bdf0", selection_text="#24232c",
        ),
        Style(
            "fairy", "Fairy", "#402238", "#4a2b40",
            Button("#f6a2bf", "#9c2f5b", "#402238", "#fff4f7"), Button("#fff4f7", "#9c2f5b", "#402238", "#fff4f7"),
            "#fff4f7", "#9c2f5b", fill="#fad7e3", link="#9c2f5b", selection="#9c2f5b", selection_text="#fff4f7",
        ),
        Style(
            "leaf", "Leaf", "#1f3d1c", "#2d4a2a",
            Button("#fbf7ec", "#24461f", "#1f3d1c", "#fbf7ec"), Button("#fbf7ec", "#24461f", "#1f3d1c", "#fbf7ec"),
            "#fffdf6", "#2f6a2a", fill="#f5ebd8", link="#2f6a2a", selection="#2f6a2a", selection_text="#fffdf6",
        ),
        Style("plain", "Plain (desktop colours)", "", "", Button("", "", "", ""), Button("", "", "", ""), "", ""),
    )
}


def get(name: str | None) -> Style:
    return STYLES.get((name or "").strip().lower(), STYLES[DEFAULT])
