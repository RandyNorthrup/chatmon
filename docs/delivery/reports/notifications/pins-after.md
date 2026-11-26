# Python pins: nothing to move

uv 0.13.6 locked each list in packaging/ again with every pin set free (its environment marker kept), taking only releases uploaded before 2026-11-09T06:54:00Z, 14 days back. Every lock already holds what it would pick.

## Held back

- PyQt6 6.12.0 is skipped: its own QtDBus.pyi has a syntax error that stops mypy before it reads anything, so every types job would fail; 6.12.1 fixes it (docs/delivery/m10-followups.md).


_packaging/pins.py wrote this; .github/workflows/pins.yml runs it every week and keeps one issue with its report while something can move._
