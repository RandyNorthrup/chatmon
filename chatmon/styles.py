"""Chat bubble styles: which painted bubble, and the text and button colours that go on it.

The bubbles themselves are painted art (chatmon/bubbles, drawn by bubbleart.py); the plain
style has none and uses the desktop's own colours.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

DEFAULT = "electric"


@dataclass(frozen=True)
class Button:
    fill: str  # empty: no fill
    outline: str
    text: str  # empty: the body colour


@dataclass(frozen=True)
class Style:
    name: str
    label: str
    title: str  # empty: the desktop's own colours (the plain style)
    body: str
    primary: Button  # the first button (the one that does something)
    other: Button
    entry: str  # the ask box's text field; empty: the desktop's
    accent: str  # the entry's border, links, scroll bars

    def text_colours(self) -> tuple[QColor, QColor]:
        """Title and body colours."""
        if not self.title:
            text = QColor(QApplication.palette().color(QPalette.ColorRole.Text))
            return text, text
        return QColor(self.title), QColor(self.body)

    def entry_colour(self) -> QColor:
        return QColor(self.entry) if self.entry else QColor(QApplication.palette().color(QPalette.ColorRole.Base))


PLAIN_ACCENT = "#26b8d9"  # the penguin's glowing cyan nodes

# Colours matched to the approved mock-ups (art/bubbles/README.md).
STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style("electric", "Electric", "#ffffff", "#d6ecff", Button("#0e2a55", "#45d3f7", "#ffffff"), Button("#0b1d3d", "#2fa9cf", "#ffffff"), "#0a1a36", "#45d3f7"),
        Style("fire", "Fire", "#fff4ea", "#f3dccd", Button("#2a130c", "#ff8a2a", "#ffffff"), Button("#1f0e0a", "#d9661f", "#ffffff"), "#170907", "#ff8a2a"),
        Style("ghost", "Ghost", "#ffffff", "#e2ddf0", Button("#33313f", "#ddd2f7", "#ffffff"), Button("#2b2a35", "#b9afd6", "#ffffff"), "#24232c", "#c9bdf0"),
        Style("fairy", "Fairy", "#402238", "#4a2b40", Button("#f6a2bf", "#f6a2bf", "#402238"), Button("#fff4f7", "#f0b5ca", "#402238"), "#fff4f7", "#d4658f"),
        Style("leaf", "Leaf", "#1f3d1c", "#2d4a2a", Button("#fbf7ec", "#24461f", "#1f3d1c"), Button("#fbf7ec", "#24461f", "#1f3d1c"), "#fffdf6", "#2f6a2a"),
        Style("plain", "Plain (desktop colours)", "", "", Button(PLAIN_ACCENT, PLAIN_ACCENT, "#ffffff"), Button("", PLAIN_ACCENT, ""), "", PLAIN_ACCENT),
    )
}


def get(name: str | None) -> Style:
    return STYLES.get((name or "").strip().lower(), STYLES[DEFAULT])
