"""What changed in each version (changelog.md, shipped with Chatmon): shown after an update, and each
release's notes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS = ("New", "Changes", "Fixes")
_VERSION = re.compile(r"^## (\d+(?:\.\d+)*)\s*$")
_SECTION = re.compile(r"^### (.+?)\s*$")


def version_key(version: str) -> tuple[int, ...]:
    """"0.10.1" sorts after "0.9.3": numbers, not text. Anything after a number (a "rc1") is ignored."""
    parts = []
    for part in version.strip().lstrip("v").split("."):
        digits = re.match(r"\d+", part)
        parts.append(int(digits.group()) if digits else 0)
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


@dataclass
class Release:
    version: str
    sections: dict[str, list[str]] = field(default_factory=dict)  # "New": its items, as Markdown

    def markdown(self, heading: str = "###") -> str:
        out = []
        for name in [*SECTIONS, *(s for s in self.sections if s not in SECTIONS)]:
            items = self.sections.get(name)
            if items:
                out.append(f"{heading} {name}\n" + "\n".join(f"- {item}" for item in items))
        return "\n\n".join(out)


def path() -> Path:
    return Path(__file__).resolve().parent / "changelog.md"


def parse(text: str) -> list[Release]:
    """Each version's sections, in the file's order (newest first). An item may run over several lines."""
    releases: list[Release] = []
    section: list[str] | None = None
    for line in text.splitlines():
        if m := _VERSION.match(line):
            releases.append(Release(m.group(1)))
            section = None
        elif (m := _SECTION.match(line)) and releases:
            section = releases[-1].sections.setdefault(m.group(1), [])
        elif section is not None and line.startswith("- "):
            section.append(line[2:].strip())
        elif section is not None and section and line.startswith("  ") and line.strip():
            section[-1] += " " + line.strip()
    return releases


def load() -> list[Release]:
    try:
        return parse(path().read_text(encoding="utf-8"))
    except OSError:
        return []


def find(version: str, releases: list[Release] | None = None) -> Release | None:
    key = version_key(version)
    return next((r for r in (load() if releases is None else releases) if version_key(r.version) == key), None)


def since(seen: str, current: str, releases: list[Release] | None = None) -> list[Release]:
    """The releases after `seen`, up to and including `current`, newest first: what an update brought."""
    low, high = version_key(seen), version_key(current)
    return [r for r in (load() if releases is None else releases) if low < version_key(r.version) <= high]


def notes(releases: list[Release]) -> str:
    """Markdown for what's new: one release as its sections; several, each under its version."""
    if len(releases) == 1:
        return releases[0].markdown()
    return "\n\n".join(f"**{r.version}**\n\n" + r.markdown("####") for r in releases if r.sections)
