# M8 readiness, the plans round for v0.10.0 at 7816159 (2026-11-15), bound again at 56caddd

This review is the round's first ([../wave5/readiness.md](../wave5/readiness.md), at 7816159), read again at
56caddd. Its receipt went stale with the plan's new paragraph and the files below. It is a requirements review,
not proof that the code works: the behavior and red receipts are.

## Since 7816159

- **df3e93c** (the coordinator's): `chatmon/layer.py`'s two `app = QGuiApplication.instance()` lines are
  `app: QCoreApplication | None = QGuiApplication.instance()`, CONTRIBUTING.md's second workaround for 6.12.1's
  stubs, with no change at run time; CONTRIBUTING.md's opt-in table names `CHATMON_PINS_NETWORK=1`.
- **56caddd** (the coordinator's): `tests/test_app_smoke.py::test_hide_menu_and_reload` waits for the greeting
  before it hides the chatmon, and expects the "Recent messages" entry the greeting adds. The greeting could land
  inside the test's one-second spin when the companion was slow to start: the WSL failure of this round's first
  binding. The coordinator's drill ([reports/wave5/flaky-hide-menu/drill.py.txt](../../wave5/flaky-hide-menu/drill.py.txt)),
  run again here, fails the old body with the start slowed by 0.6 s and passes the new one at 0, 0.6, 1.4 and 2 s
  ([reports/wave5b/flaky-hide-menu-drill-windows.log](../../wave5b/flaky-hide-menu-drill-windows.log), and in WSL
  [reports/wave5b/flaky-hide-menu-drill-wsl.log](../../wave5b/flaky-hide-menu-drill-wsl.log)).

For this plan: df3e93c changed CONTRIBUTING.md, which T2-template owns, and it binds the M0 and M7 plans. Neither commit changes what a criterion asks or what Chatmon does: one is two type
annotations and a documentation row, the other a test's wait. Each requirement still maps both ways to its
criteria.

Result: ready. No requirement is unclear, conflicting or missing failure behavior.

## The review at 7816159

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

M8-01 still maps to M8-01.A1 through A10. T3-wrap-a and T4-wrap-b own the changed modules; the fixes add no
string anyone sees, and `packaging/extract_strings.py --check` finds the template current
([reports/wave5/extract-strings-check.log](../../wave5/extract-strings-check.log)). T2-template owns
CONTRIBUTING.md, whose translation section is unchanged (only its Dependencies section moved). The M0 and M7
plans this plan takes as inputs are re-bound in this round before M8.

Result, at 7816159: ready. No requirement is unclear, conflicting or missing failure behavior.
