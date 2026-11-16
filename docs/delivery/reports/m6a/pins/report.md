# Python pins ready to move

uv 0.13.6 locked each list in packaging/ again with every pin set free (its environment marker kept), taking only releases uploaded before 2026-11-01T20:47:00Z, 14 days back. This is what would change.

## Pins

| Package | Now | Proposed | Locks | Pinned in |
| --- | --- | --- | --- | --- |
| nuitka | 4.3.1 | 4.3.4 | requirements.txt | requirements.in |

## Held back

- PyQt6 6.12.0 is skipped: its own QtDBus.pyi has a syntax error that stops mypy before it reads anything, so every types job would fail; 6.12.1 fixes it (docs/delivery/m10-followups.md).

## Moving them

Run this from the repository's root, then review the diff and commit it:

```sh
python packaging/pins.py --apply --cutoff 2026-11-01T20:47:00Z
```

That moves each pin above in packaging/requirements*.in (and pyproject.toml's dev extra), then locks each list again in packaging/ with the command at the top of its .txt, the cutoff set:

```sh
cd packaging
uv pip compile requirements.in -o requirements.txt --universal --python-version 3.14 --generate-hashes --exclude-newer 2026-11-01T20:47:00Z
```

Run by hand after moving the pins, these commands move only what the new pins need; --apply first hands uv the versions above, so it locks exactly this report.

_packaging/pins.py wrote this; .github/workflows/pins.yml runs it every week and keeps one issue with its report while something can move._
