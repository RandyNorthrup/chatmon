# M3 readiness review, 2026-11-14

Requirements review of `docs/delivery/m3-stage-overlay.md` against the brief (`docs/delivery/ASSESSMENT.md`, M3
section) and the rules (`docs/delivery/ROADMAP.md`, `pyproject.toml`). It reviews the requirements, not the code;
it proves nothing about behaviour.

Source read before planning: `chatmon/penguin.py`, `sprites.py`, `behavior.py`, `stagemenu.py`,
`clickthrough.py`, `layer.py` (all of it), `wayland.py` (wire format), `xkb.py`, `companions.py`; the callers in
`chatmon/app.py` (stage set-up, `_set_sprite_scale`, `_power_saving`, `_seen`, menus, direct writes to
`behavior.sleep_after`, `speed`, `anims`); the M2-owned `SpeechBubble` and `AskBox` interfaces the stage uses;
their tests; `.github/workflows/ci.yml` (Linux installs `libxkbcommon0`, no X server).

Baseline: `python -m pytest -q -p no:cacheprovider` 514 passed, 59 skipped (`baseline-tests.log`). In WSL (Arch,
Python 3.14.9, PyQt6 6.12.1), the Linux-only `test_wayland.py`, `test_xkb.py`, `test_overlay_stage.py` and
`test_stagemenu.py` pass, 45 of 45, none skipped.

## Clarity and conflicts

1. **M3-01 "about 1 Hz" and "the next actual change".** Read together: the timer sleeps until the next change it
   can see, never longer than 1 s (a floor for what changes without telling the stage: a screen's geometry, the
   app writing `behavior.sleep_after` or `speed` directly, a bubble restyled). Covered or hidden: at least 1 s.
   Not drawing: stopped, as now. Resolved in AC-M3-01-idle and AC-M3-01-quiet.
2. **M3-01 and M3-02.** The refresh rate is the shortest interval, used only while something moves continuously
   (a walk, a fall, a fade, an animated bubble). Not a conflict once the interval is a minimum, not a period.
3. **"Keep behaviour identical" (coordinator).** Ticking less often must not change what is drawn when. Two
   places in `Behavior.tick` depend on tick spacing: the hovered walk's clock shift uses the clamped `dt` (0.25 s
   at most) and would drift on 1 s ticks; the fall's Euler steps use `dt`. The first must use the unclamped time;
   the second only runs while falling, which is continuous (full rate). Covered by AC-M3-01-idle's reference
   comparison and AC-M3-12-hold.
4. **The contract name `StageMenu.key(event) -> bool`** clashes with today's `StageMenu.key()` (the drawing key).
   The drawing key is renamed `look()`; only `penguin.py` calls it.
5. **M3-11 and walking.** The app already stills walking under reduced motion unless you chose to walk. The
   behaviour must not override that choice: reduced motion stills moods and reactions, not a walk you asked for.
6. **M3-12 "the current walk frame holds, or the turn plays."** Either satisfies it; holding is chosen (no frame
   swap, nothing to undo when the pointer leaves).

## Missing failure behaviour, now specified

- `QScreen.refreshRate()` can be 0 or nonsense on virtual or offscreen screens: clamp to 24-500 Hz, 60 when unknown.
- An old libxkbcommon without `xkb_keymap_key_get_syms_by_level` (before 0.4): no fallback, keys as today.
- `SpeechBubble` is M2's and changing: its expiry is read with `getattr` (`_expires`) and the 1 s floor covers a
  bubble without it. Integration note asks M2 for `next_change(now)`.
- The pointer's screen (M3-15) is unknown on native Wayland (`QCursor.pos()` only knows Qt's own surfaces): the
  option then does nothing. Stated in the README notes.
- An X server without SHAPE keeps the existing `MaskInput` fallback.

## Scope

- M3-04 is partly deferred: buffers "sized to what's shown" need a subsurface design that must be tried on real
  compositors. Recorded in the plan's rationale and checkpoint; the two-buffer limit and idle release are in scope.
- Wiring (who calls `set_badge`, `set_reduced_motion`, `set_hosting`, `follow_pointer_screen`) is M7's.
- `companions.py` is owned but has no M3 finding; it is not changed.

## Terminology

"Stage" (the surface's owner, `penguin.Stage`), "surface" (overlay `LayerSurface` or `StageWindow`), "hosted"
(the ask box drawn on the overlay), "frame interval" (1/refresh rate), "idle floor" (1 s) are used consistently in
the plan and the tests.

## Rules

ROADMAP rules 2-8 apply. Tests use real Qt objects offscreen and the `qapp` fixture; the surfaces in the stage tests
are recording fakes for the compositor or window only (as `tests/test_overlay_stage.py` already does), never for
the stage, behaviour, menu or sprites under test. Linux-only tests skip elsewhere with a reason.

## Coverage and order

Every requirement M3-01 to M3-15 has at least one acceptance criterion with behaviour and red checks, and every
criterion has an owning task. Order: the independent tasks (xkb, shape, sprites, behaviour, buffers) first; the
stage timer after the behaviour (it needs `next_change`); the menu and stage features after the timer (they add
due times and wake-ups to it).

Verdict: ready, with the M3-04 partial deferral recorded.
