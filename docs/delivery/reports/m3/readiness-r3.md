# M3 readiness review, scope revision 3 (2026-11-14 to 15)

Requirements review of the reopened part of `docs/delivery/m3-stage-overlay.md`: M3-04's deferred half (buffers
sized to what's shown), M3-14 on a real compositor (the unhosted ask box with a screen reader), and the new M3-RC
(the overlay proven on a real compositor, with a test bed that also runs in CI). Against the brief
(`docs/delivery/ASSESSMENT.md`, M3-04 and M3-14), the rules (`docs/delivery/ROADMAP.md`, `pyproject.toml`), the
owner's direction for this revision ("use WSL on this PC and fix everything") and the coordinator's scope (four
items, file ownership, gates). It reviews the requirements, not the code; it proves nothing about behaviour.

Read before changing anything: the M3 plan (its deferral note and its caveat on `set_hosting(False)`), M7's plan
(how the app calls `set_hosting` and keeps the penguin's menu on the stage), `chatmon/layer.py`, `wayland.py`,
`penguin.py` (hosting, menus, bubble placement), the hosting decision in `chatmon/app.py` (`_ask_box_as_window`,
`_check_hosting`, `show_menu`, `_popup`), `chatmon/a11y.py` (how a screen reader is found and spoken to),
`bubble.py`'s `AskBox` (flags, fixed width, accessible names), `tests/test_wayland.py` (the pretend compositor),
`tests/app_harness.py`, `tests/fake_orca.py`, `tests/gnome-session.sh` and CI's `gnome` job (the pattern for a real
compositor in CI).

## Clarity and conflicts

1. **"Sized to what's shown" and "lag-free".** A layer surface anchored to every edge is the output's size; a
   smaller one moved each frame is placed by the compositor a frame late. Read together: the buffers holding pixels
   must be about the size of what's drawn, and a move must show the new place and pixels in the same frame. A
   synchronized subsurface does both (position and buffer apply with the parent's commit). Resolved in
   AC-M3-04-content: at most 2 content buffers, plus the layer surface's one stretched pixel, which holds no
   drawing; "at most 2 buffers" in the brief is read as the drawing buffers.
2. **"If an approach doesn't work on sway, say why".** The subsurface was tried first and works on sway 1.12;
   the moving layer surface was not built (its frame of lag is the reason the overlay is one surface). Recorded so,
   not as a comparison that wasn't made.
3. **"Placed sensibly".** On Wayland a client can't place a window; the compositor does (sway floats the box, as
   its width is fixed, and centres it). Read as: floating (not tiled over your windows), wholly on the output,
   focused, and not covered by Chatmon's own overlay. The last part found a defect (a bubble kept "clear" of the
   box's asked-for place, which on Wayland is fiction, landed on the real box).
4. **"Exposed with names and roles" vs "a bubble's announcement reaches AT-SPI".** Chatmon's bubbles are drawn on
   the overlay, not widgets, and PyQt6 has no QAccessible API to announce through (a11y.py). What a screen reader
   can be given: the box's own widgets (its field, buttons and conversation, whose text includes answers) through
   Qt's AT-SPI bridge, and a bubble's words through Orca's remote controller (PresentMessage). Read as: the box's
   tree with names and roles and its changes heard as AT-SPI events; a bubble said through Orca where Orca 49+
   runs. The penguin's own menu is drawn on the stage and isn't in AT-SPI's tree: recorded as a gap, not claimed.

## Missing failure behaviour, now specified

- A compositor without `wl_subcompositor` or `wp_viewporter`: full-output buffers, as before (the pretend
  compositor's existing tests keep that path).
- A move when both buffers are held by the compositor: it waits for a release; old pixels are never shown at the
  new place.
- Nothing drawn at all (hidden chatmon): the subsurface is unmapped.
- A compositor that takes the keyboard away on the handover to `on_demand` (found on sway): the overlay takes it
  back and keeps grabs exclusive.
- Chatmon's own windows pasting what the overlay copied (found on sway): served from Qt's clipboard, not a
  blocking round trip to the overlay's own connection.
- Tests where sway, grim, dbus or AT-SPI are missing: skip with the reason; in CI's `sway` job a missing piece
  fails (Orca aside: Ubuntu 24.04's is 46, without the remote controller).

## Scope

In: `chatmon/layer.py`, `wayland.py`, `penguin.py`, the hosting decision in `app.py` (unchanged in the end),
their tests, `tests/sway_session.py`, `tests/test_sway.py`, the new CI job, this plan and `reports/m3/`. Out, and
noted for their owners: `a11y.py` (at-spi2-core 2.62 no longer has `ScreenReaderEnabled`), `menus.py` ("Help &
updates" shows its ampersand as a mnemonic), speaking the drawn penguin menu's items (a feature for M7's owner).

## Terminology

"Content subsurface", "backdrop pixel" (the layer surface's one stretched pixel), "handover" (exclusive to
on_demand), "unhosted box" (`set_hosting(False)`), "test bed" (`tests/sway_session.py`), "probe" (the Chatmon the
test bed runs). Used the same way in the plan, the code's comments and the tests.

## Rules

ROADMAP rules 1-8 apply as written; the coordinator's message replaces the wave-1 file table for this work (the
files above). No new runtime dependency (the test bed uses chatmon's own Wayland client; sway, grim,
wl-clipboard, dbus, AT-SPI, python3-gi and Orca are test-only system packages). Gates: the whole Windows suite,
ruff, mypy on three platforms (no exemptions), the string template unchanged unless strings are added (none were:
every new string is a comment, docstring or log message), the Linux suite and the real-compositor tests in WSL,
red drills on both.

## Coverage and order

- AC-M3-04-content: T-M3-content (layer.py, penguin.py's extent; pretend-compositor tests; sway at 4K/2x and 1.5x,
  the drag; `memory.py`).
- AC-M3-14-sway: T-M3-unhosted-sway (penguin.py's menu keyboard and bubble placement; unit tests; sway tests).
- AC-M3-14-atspi: T-M3-unhosted-sway with T-M3-sway-bed (AT-SPI tree and events, Orca).
- AC-M3-RC-sway: T-M3-sway-fixes (layer.py's handover and clipboard) and T-M3-sway-bed (the test bed, the CI job).
- Order: the test bed first (it found the defects), then the fixes, then content-sized buffers, measured last.
- Every earlier M3 criterion is re-proved on the current source (its receipts went stale as later milestones and
  this revision changed the files): the Windows and Linux suites, and the earlier drill specs re-run as
  `drill-spec-r3.json` and `drill-spec-linux-r3.json` (two `find` strings updated where M6B moved the code).
