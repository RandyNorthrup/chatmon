# M0 readiness, the plans round for v0.10.0 at 7816159 (2026-11-15)

The final round's review is in this plan's wave4e/ or wave4f/ folder (at 45a17b3), or round three's in wave4c/
(at 3586a0d). Its receipt went stale because files the plan's criteria bind changed. This review re-reads the
plan's obligations against the brief and rules as they are now. It is a requirements review, not proof that the
code works: the behavior and red receipts are.

## Inputs read

- [ASSESSMENT.md](../../../ASSESSMENT.md), [ROADMAP.md](../../../ROADMAP.md) and `pyproject.toml`: unchanged
  since round three. The status is in [OUTCOME.md](../../../OUTCOME.md), which no plan binds.
- The code and tests, changed from 45a17b3 to 7816159 by PR #18's merge (no file outside docs/) and PR #22's:
- **The KDE and Hyprland overlay fixes** (`wave5/compositors`, evidence in
  [reports/release/compositors/](../../release/compositors/README.md)). `chatmon/layer.py`: when KWin keeps the
  keyboard after the overlay lets it go, the surface is made again; what the overlay copies goes on Qt's clipboard
  again once one of Qt's windows has the keyboard (KWin refuses Qt's first copy). `chatmon/penguin.py`: while a
  button is held on the chatmon or its bubble the whole stage takes the pointer (Hyprland ended a quick drag), and
  a screen that moves under the stage is covered where it is now. Their tests are in `tests/test_wayland.py`,
  `tests/test_overlay_stage.py` and `tests/test_stage_screens.py`; `tests/test_stage_features.py`'s pretend screen
  gains `geometryChanged`. `tests/test_compositors.py` (on `tests/compositor_session.py`) runs sway's checks on a
  headless KWin and Hyprland where they're installed, and skips with its reason elsewhere.
- **The screen-reader fixes** (`wave5/screen-readers`, evidence in
  [reports/release/screen-readers/](../../release/screen-readers/fixes/README.md)). `chatmon/a11y.py`: VoiceOver
  is handed what was held, and what is said in Chatmon's first 2.5 s in front, 2.5 s after Chatmon becomes active
  (`SETTLE_MS`), because it drops what is posted at that moment. `chatmon/bubble.py`: the ask box's title hands the
  keyboard to its field (`setFocusProxy`). `chatmon/clickthrough.py`: the stage's native window is marked
  `NonRudeHWND`, so Windows no longer takes Chatmon's own stage for a full-screen app. `chatmon/cli.py` and
  `chatmon/macnative.py`: on macOS 14 and later, `chatmon ask` asks for Chatmon to be made the active app once the
  box is open. Their tests are in `tests/test_platform_events.py`, `tests/test_ask_box.py`,
  `tests/test_clickthrough.py`, `tests/test_presence.py`, `tests/test_cli.py` and `tests/test_macnative.py`.
- **The Dependabot replacement** (`wave5/pins`, evidence in [reports/m6a/pins/](../../m6a/pins/README.md)).
  `.github/dependabot.yml` keeps only github-actions; `packaging/pins.py`, run each week by
  `.github/workflows/pins.yml`, proposes the Python pins' moves; `packaging/requirements-pins.in` and `.txt` lock
  the uv it runs; `tests/test_pins.py` (on `tests/fake_uv.py`) tests it, and `tests/test_requirements.py` checks the
  new lock too. CONTRIBUTING.md's Dependencies section says so.
- **The 0.10.0 notes**: README.md and `chatmon/changelog.md`.

## This plan

M0-01 to M0-13 and M0-CLI still map both ways to their criteria. T-M0-11, T-M0-12 and T-M0-CLI own
`chatmon/cli.py` and `tests/test_cli.py`. `chatmon ask` now keeps `_send`'s answer and, on macOS only, asks
for Chatmon to be made active once the box is open; M0-12.A1 (the box opens with the text typed in and the
keyboard on it) and M0-12.A2 (Windows' AllowSetForegroundWindow first) ask the same as before, and the macOS
step serves A1's "the keyboard on it". One drill's line moved with it: M0-12-ask-sent took out the old
`return _send(...)`; M0-12-ask-sent-v2 sends the same wrong message type from the new line.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.
