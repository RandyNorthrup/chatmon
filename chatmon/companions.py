"""The companions you can pick: the electric penguin and its four siblings.

Each has the same twelve animation strips. The penguin's are in anim/, where they have always
been; the others' are in anim/<id>/ (cut by art/tools/creature-cut.py). Only the chosen one's
strips are loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths

DEFAULT = "penguin"


@dataclass(frozen=True)
class Companion:
    id: str
    label: str
    nickname: str  # what it answers to until you name it
    bubble_style: str  # the bubble style that matches it (styles.STYLES)

    def anim_dir(self) -> Path:
        base = paths.anim_dir()
        return base if self.id == DEFAULT else base / self.id


COMPANIONS: dict[str, Companion] = {
    c.id: c
    for c in (
        Companion("penguin", "Electric penguin", "Penguin", "electric"),
        Companion("fire-red-panda", "Fire red panda", "Panda", "fire"),
        Companion("ghost-rabbit", "Ghost rabbit", "Rabbit", "ghost"),
        Companion("fairy-axolotl", "Fairy axolotl", "Axolotl", "fairy"),
        Companion("leaf-pangolin", "Leaf pangolin", "Pangolin", "leaf"),
    )
}


def get(name: str | None) -> Companion:
    """The companion called `name`; the penguin for a name that isn't one, or whose strips are missing."""
    companion = COMPANIONS.get((name or "").strip().lower(), COMPANIONS[DEFAULT])
    if not (companion.anim_dir() / "manifest.json").exists():
        return COMPANIONS[DEFAULT]
    return companion
