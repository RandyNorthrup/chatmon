"""The companions you can pick: the electric penguin and its four siblings.

Each has the same twelve animation strips. The penguin's are in anim/, where they have always
been; the others' are in anim/<id>/ (cut by art/tools/creature-cut.py). Only the chosen one's
strips are loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths
from .i18n import N_, _

DEFAULT = "penguin"


@dataclass(frozen=True)
class Companion:
    id: str
    label_en: str  # its name in menus, in English: `label` is in the person's language
    nickname_en: str
    bubble_style: str  # the bubble style that matches it (styles.STYLES)

    @property
    def label(self) -> str:
        return _(self.label_en)

    @property
    def nickname(self) -> str:
        """What it answers to until you name it."""
        return _(self.nickname_en)

    def anim_dir(self) -> Path:
        base = paths.anim_dir()
        return base if self.id == DEFAULT else base / self.id


COMPANIONS: dict[str, Companion] = {
    c.id: c
    for c in (
        Companion("penguin", N_("Electric penguin"), N_("Penguin"), "electric"),
        Companion("fire-red-panda", N_("Fire red panda"), N_("Panda"), "fire"),
        Companion("ghost-rabbit", N_("Ghost rabbit"), N_("Rabbit"), "ghost"),
        Companion("fairy-axolotl", N_("Fairy axolotl"), N_("Axolotl"), "fairy"),
        Companion("leaf-pangolin", N_("Leaf pangolin"), N_("Pangolin"), "leaf"),
    )
}


def get(name: str | None) -> Companion:
    """The companion called `name`; the penguin for a name that isn't one, or whose strips are missing."""
    companion = COMPANIONS.get((name or "").strip().lower(), COMPANIONS[DEFAULT])
    if not (companion.anim_dir() / "manifest.json").exists():
        return COMPANIONS[DEFAULT]
    return companion
