# M3: the stage, sprites and the overlay

Milestone M3 of the [roadmap](ROADMAP.md): items M3-01 to M3-15 of the [assessment](ASSESSMENT.md), plus the
stage-side calls M2 handed over (M3-M2). Branch `wave1/m3`, worktree `chatmon-wt/m3`, from
`improve/assessment-fixes` at `5346385`; `improve/assessment-fixes` at `4827b0c` (M0, M1A, M1B, M2, M5) merged in
at `1fd1342`.

## Rationale

The stage (`penguin.py`) draws the chatmon, its bubbles, its overlay menus and the hosted ask box on one
see-through surface. Most of M3 is in that one loop and the two things it draws on the overlay (`stagemenu.py`,
`layer.py`), plus the frames it draws (`sprites.py`) and what decides them (`behavior.py`).

**One owner per change path.** This milestone changes only files it owns (ROADMAP "File ownership in wave 1") and
its new tests. The ask box and speech bubbles (`bubble.py`) are M2's: the stage uses their public calls
(`expires()`, `set_hovered()`, `hit()`/`open_link_at()`, `max_height`, `SCREEN_SHARE`, `anim_key`, `paint_art`,
`input_rects`, `wants_keyboard`, `paste_overlay`, `entry`, `stage_draws_art`) and the ask box's layout margins
(public Qt) for its painted border.

**Scope revision 2 (2026-11-14).** The coordinator merged M2 and asked M3 to make the stage-side calls M2 handed
over (requirement M3-M2): pause a bubble while pointed at, open a bubble's links on a click with a hand cursor,
hold a bubble to its share of the stage's screen, let the multi-line field keep its line breaks, and repaint only
the ask box's border as its art moves. New tests went into new files (`tests/test_sprites.py`,
`tests/test_stage_features.py`) rather than the files first named.

**Reuse decisions.**

- The stage's drawing key (what looks different, part by part) still decides what is drawn again. The idle clock
  (M3-01) adds when the next change is due: `Behavior.next_change(now)` (pure, no Qt) for the creature, the
  bubble's fade, animation and `expires()`, the sleeping z's, the needs-you ring, the menu's pending submenu, and a
  one-second floor for what changes without saying so (a screen's geometry, a setting written straight into the
  behaviour, a bubble restyled).
- Wake-ups come from what already exists: the surface's input calls into the stage, `Behavior.on_change` (the
  behaviour now says when it's told something), the hosted scene's `changed` signal and its proxy's
  `visibleChanged`.
- `StageMenu` stays a plain object without a QObject or timer; its submenu delay and scroll repeat are due times
  the stage's clock serves (`tick`, `next_change`), so the menu is tested without an event loop.
- The X input shape (M3-10) keeps `clickthrough._key`; the scaling is a pure function, also read back from a real
  X server in its test.
- The Latin fallback (M3-09) follows Qt's own `QXkbCommon::lookupLatinKeysym`: the first other layout whose
  symbol at the key's level is Latin-1, unless a key of an earlier layout already types it.

**New code.** No new module. New responsibilities live in their owners: `Behavior.next_change`, `on_change` and
`set_reduced_motion`; `Stage.set_badge`, `badge_description`, `set_reduced_motion`, `set_hosting`,
`follow_pointer_screen`; `Hosted.unhost` and `ring`; `StageMenu.key`, `wheel`, `tick`, `next_change`, `look`;
`sprites._CUT` (the last two sets of frames); `clickthrough.device_rects`; `StageWindow.set_cursor` and
`polls_pointer`; `LayerSurface._trim`.

**Non-goals.** Wiring the new stage calls into the app and Settings (M7). Bubble and ask-box internals (M2).
Translating the few new strings (M8).

**M3-04, the part that is deferred.** A layer surface anchored to the whole output must be given a buffer the
size of the output; the protocol has no way to give it a smaller one at an offset. Buffers sized to what is shown
need either a layer surface that moves with the chatmon (the compositor then moves it a frame late: the lag and
trail the one-surface design exists to avoid) or a content subsurface positioned under a 1x1 viewported layer
surface, which changes where pointer, drag-and-drop and text-input events land. That has to be tried on real
compositors (Hyprland, Sway, KDE); the pretend compositor in `tests/test_wayland.py` can't show how a compositor
treats a synced subsurface under a layer surface. M3 delivers the part that is safe everywhere: at most two
buffers, and the spare destroyed once the stage has been still for 2 s, so a quiet stage holds one. The
subsurface design is the checkpoint's next safe action for this item.

**Verification environments.** Windows 11 (the gates: the whole suite and ruff). Linux code also runs here, in WSL
(Arch, Python 3.14.9, PyQt6 6.12.1, libxkbcommon 1.13, WSLg's X server): `tests/test_wayland.py`,
`tests/test_xkb.py`, the X11 shape test and the Linux red drills (through `reports/m3/wslpy.py`). CI on Linux
and macOS stays the authority for those platforms and is a pending operation in the checkpoint.

**A test this milestone can't change.** `tests/test_app_smoke.py::test_in_power_saver_mode_the_stage_draws_less_often`
(M0's file) asserts the stage's old fixed intervals (`penguin.FPS`, `SLOW_FPS`, `SAVER_SLOW_FPS`), which M3-01
replaces by design; it fails on this branch until its owner takes the replacement in the Integration notes.
`tests/test_stage_timer.py::test_while_it_moves_it_ticks_at_the_screens_refresh_rate` covers the same promise.

## Integration notes

APIs delivered (all on `penguin.Stage` unless named):

- `set_badge(working: int = 0, needs_you: int = 0)`: the agents badge (needs-you an amber diamond with a pulsing
  ring, working a blue circle, counts over 9 shown as "9+"). `badge_description() -> str`: it in words ("1 agent
  needs you, 2 agents working"), for the stage window's accessible description and the tray tooltip (M7-07).
- `set_reduced_motion(on: bool)`: calls `Behavior.set_reduced_motion` and stills the z's and the ring. The app
  still decides walking (`app._walks()`); M7-11 should call this from the reduced-motion change events too.
- `set_drawing(on)`, `set_covered(on)`: as before, and now slow or stop the stage's clock and the pointer polling.
  M7-11 (Linux lock, macOS sleep) calls `set_drawing(False)`.
- `follow_pointer_screen(on: bool) -> bool`: off by default; returns False (and stays off) where apps aren't told
  where the pointer is (Wayland, including XWayland under a Wayland session). M7-11's "Follow me" setting.
- `set_hosting(on: bool)`: off leaves the ask box a normal window and makes `hosts_windows()` and `draws_menus()`
  False, so the app must check `draws_menus()` each time it opens a menu (it does in `show_menu`) rather than
  once. M7-11 ("with a screen reader, the overlay's ask box runs as a window") calls `set_hosting(False)` when a
  screen reader runs or the accessible ask-box setting is on. Two things to try on a real compositor first: where
  the overlay runs, Qt runs on Wayland itself, so the compositor places the unhosted box (`move()` is ignored)
  rather than above the chatmon; and a `QMenu.popup` needs a Qt window to belong to, which the penguin's own menu
  (opened from the overlay) hasn't. With hosting off, `show_menu` may need to keep drawing the penguin's menu on
  the stage there (`stage.open_menu`) and give Qt only the ask box's menus, which belong to the box's window.
- `StageMenu.key(event: QKeyEvent) -> bool`: routed by `Stage.key` already; nothing to wire.
- `power_saving` is still a plain attribute the app sets; the new frame interval reads it.
- The ask box's power saving (`AskBox.set_power_saving`) is M2's and M7's to wire (M7-11 "power saving reaches the
  ask box").

For M0 (owner of `tests/test_app_smoke.py`), replace the body of `test_in_power_saver_mode_the_stage_draws_less_often`:

```python
    c = companion
    c._power_saving(True)
    assert c.stage._frame_interval() == pytest.approx(1 / min(c.stage._refresh_hz(), penguin.SAVER_FPS))
    c._power_saving(False)
    assert c.stage._frame_interval() == pytest.approx(1 / c.stage._refresh_hz())
```

For M6A (owner of `.github/**`): Linux CI has no X server, so
`tests/test_clickthrough.py::test_the_x_server_gets_the_shape_in_device_pixels` skips there. Installing `xvfb`
and running the Linux job under `xvfb-run -a` would run it (it needs `libx11-6` and `libxext6`, already pulled
in by Qt).

For M2: nothing further. The stage now reads `SpeechBubble.expires()` and calls `set_hovered(on, now)`; a bubble
restyled with `set_style` while it shows is drawn again within a second (the stage's floor), which is fine for a
settings change.

## Changelog notes

- The chatmon uses far less power when it isn't doing anything: its clock sleeps until the next thing it will
  show changes (about 100 wake-ups a minute standing idle, down from 1,800), once a second while a full-screen
  window covers it, and not at all while the screen is locked or off.
- Smoother movement on fast displays: the chatmon moves at your screen's own refresh rate, on half pixels on a
  2x screen, and follows the pointer at once when you drag it.
- Each animation frame is kept once in memory instead of twice, and moving the chatmon back to a monitor it was
  on before no longer cuts its animations again.
- On the Wayland overlay: the penguin's menu and the ask box's right-click menu work from the keyboard (Esc,
  arrows, Home/End, Page Up/Down, Left/Right for submenus, Enter, and a letter to jump); long menus scroll; a
  submenu waits a quarter of a second before switching, so moving diagonally into it works; headers and
  shortcuts are easier to read, the highlighted row is solid and outlined, and rows grow with your font size.
  Esc with a menu open closes only the menu, and closing the ask box closes its menu.
- Shortcuts in the ask box (Ctrl+V, Ctrl+C, Ctrl+X, Ctrl+A, Ctrl+Z) work under Russian, Greek and other
  non-Latin keyboard layouts on the overlay.
- On X11 with display scaling, the chatmon takes clicks exactly where it's drawn.
- Hovering over a walking chatmon now stops it mid-step instead of snapping it to face you.
- With reduced motion, the chatmon holds still poses, skips waves, hops and peeks, and lands at once when
  dropped.
- A bubble waits while you point at it, and links in it open in your browser on a click.
- On the overlay the ask box can now be a normal window that screen readers can read (to be switched on in
  Settings, M7).
- The stage can show how many agents are working or need you, and follow you to the screen you're using (both
  to be switched on in Settings, M7).
- The Wayland overlay keeps at most two drawing buffers, and only one once the chatmon is still.

## README notes

- Power use: the chatmon's drawing clock sleeps while nothing on it changes, and stops while the screen is
  locked or off.
- Accessibility: overlay menus are fully keyboard-operable (Esc, arrows, Home/End, Page Up/Down, Left/Right,
  Enter, letters); menu text meets WCAG AA contrast and follows the system font size; reduced motion stills
  the chatmon's poses and skips its waves, hops and peeks; on the Wayland overlay the ask box can be a normal
  window for screen readers.
- Keyboard layouts: shortcuts in the ask box work on non-Latin layouts (Russian, Greek, ...) when a Latin layout
  is also configured, as in other Qt apps.
- Multiple monitors: the chatmon can follow the pointer to another screen (an option). It isn't available on
  Wayland desktops, which don't tell apps where the pointer is.
- Agents: an optional badge by the chatmon counts agents working (blue circle) and needing you (amber diamond).

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M3",
    "title": "The stage, sprites and the overlay",
    "scope_revision": 2,
    "brief": "docs/delivery/ASSESSMENT.md",
    "brief_reason": null,
    "rules": [
      {
        "path": "docs/delivery/ROADMAP.md",
        "revision": "5346385"
      },
      {
        "path": "pyproject.toml",
        "revision": "5346385"
      }
    ],
    "inputs": [
      "tests/conftest.py",
      "tests/drills/run.py"
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    }
  },
  "requirements": [
    {
      "id": "M3-01",
      "statement": "The stage timer sleeps until the next actual change, slows to about 1 Hz or stops while covered, hidden or not drawing, and polls the pointer at full rate only near the chatmon",
      "priority": "critical",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-02",
      "statement": "The frame interval follows the screen's refresh rate, positions are in device pixels, and drags redraw on pointer moves",
      "priority": "normal",
      "acceptance": [
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-03",
      "statement": "Frames are stored once, hit tests use an alpha mask, and the previous scale's frames are kept",
      "priority": "normal",
      "acceptance": [
        "AC-M3-03-once",
        "AC-M3-03-cache"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-04",
      "statement": "The overlay uses at most 2 buffers, sized to what is shown where the protocol allows",
      "priority": "normal",
      "acceptance": [
        "AC-M3-04-buffers"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-05",
      "statement": "Overlay menus take the keyboard: Esc, arrows, Home/End, Left/Right for submenus, Enter, letters; the highlighted row is outlined",
      "priority": "critical",
      "acceptance": [
        "AC-M3-05-keys",
        "AC-M3-05-focus"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-06",
      "statement": "Long overlay menus are capped with scroll arrows and the wheel; submenus open after a 250 ms hover; the menu rebuilds only when the hovered item changes",
      "priority": "normal",
      "acceptance": [
        "AC-M3-06-scroll",
        "AC-M3-06-hover"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-07",
      "statement": "Overlay menu headers reach 4.5:1 contrast and hover and focus are solid",
      "priority": "normal",
      "acceptance": [
        "AC-M3-07-contrast"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-08",
      "statement": "Overlay menu rows follow the font size",
      "priority": "normal",
      "acceptance": [
        "AC-M3-08-rows"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-09",
      "statement": "Shortcuts work on non-Latin layouts on the overlay through the key's Latin symbol from another layout",
      "priority": "critical",
      "acceptance": [
        "AC-M3-09-latin",
        "AC-M3-09-overlay"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-10",
      "statement": "The X11 input shape is scaled by the device pixel ratio and rounded outward",
      "priority": "normal",
      "acceptance": [
        "AC-M3-10-shape"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-11",
      "statement": "Reduced motion holds looping moods still, skips waves, hops and peeks, lands drops at once, and keeps needs-you still with a static badge",
      "priority": "normal",
      "acceptance": [
        "AC-M3-11-still"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-12",
      "statement": "Hovering mid-walk holds the current walk frame",
      "priority": "low",
      "acceptance": [
        "AC-M3-12-hold"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-13",
      "statement": "The stage can draw a badge with the number of agents working or needing you, coloured by state with a shape cue",
      "priority": "normal",
      "acceptance": [
        "AC-M3-13-badge"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-14",
      "statement": "The stage can run unhosted, with the ask box as a normal Qt window and real menus, for a screen reader",
      "priority": "normal",
      "acceptance": [
        "AC-M3-14-unhosted"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-15",
      "statement": "The stage can follow the pointer's screen, as an option",
      "priority": "low",
      "acceptance": [
        "AC-M3-15-follow"
      ],
      "superseded_by": null
    },
    {
      "id": "M3-M2",
      "statement": "The stage makes the bubble calls M2 handed over: a bubble pauses while pointed at, its links open on a click with a hand cursor, it is held to its share of the stage's screen, the multi-line field keeps its line breaks, and only the ask box's border is drawn again as its art moves",
      "priority": "normal",
      "acceptance": [
        "AC-M3-M2-stage"
      ],
      "superseded_by": null
    }
  ],
  "acceptance": [
    {
      "id": "AC-M3-01-idle",
      "requirement": "M3-01",
      "given": "A stage whose creature stands idle (walking off, no bubble) on a fake clock",
      "when": "60 s of stage time pass, each tick at the delay the stage's own single-shot timer was given",
      "then": "It ticks no more than about once a second plus once per visible frame change, far below the old 30 Hz, and every frame change a 240 Hz reference behaviour shows is drawn within one frame interval of it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-01-quiet",
      "requirement": "M3-01",
      "given": "A stage that is covered, whose creature is hidden, or that is told not to draw",
      "when": "It ticks, and then input or the app changes the behaviour",
      "then": "Covered or hidden waits at least 1 s between ticks, not drawing stops the timer, and a press, a pointer move or a behaviour change brings the next tick within one frame",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-01-pointer",
      "requirement": "M3-01",
      "given": "A surface that has to poll the pointer to let clicks through (Windows, macOS)",
      "when": "The pointer is near the chatmon, far from it, or the stage is covered",
      "then": "It is polled at the frame interval near the chatmon, at the slow interval far from it, and not at all while covered or not drawing",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-02-refresh",
      "requirement": "M3-02",
      "given": "A stage on a 144 Hz screen, and one on a 50 Hz screen",
      "when": "The creature walks, with and without power saving",
      "then": "The frame interval is 1000/144 and 1000/50 ms (rounded), and power saving caps it at 30 frames a second",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-02-pixels",
      "requirement": "M3-02",
      "given": "A surface with 2 device pixels per stage pixel and the creature at a fractional x",
      "when": "The stage places the sprite",
      "then": "Its position is on the half-pixel device grid, not rounded to whole logical pixels, and the input region still covers it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-02-drag",
      "requirement": "M3-02",
      "given": "The creature held by a drag, the timer otherwise idle",
      "when": "The pointer moves",
      "then": "The sprite is drawn at the new place on the next event-loop turn after the move, not on a fixed tick",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-03-once",
      "requirement": "M3-03",
      "given": "Sprites cut at scale 2",
      "when": "A frame is made",
      "then": "The pixmap has the ratio, no full-colour QImage copy is kept, and the mask's hit test agrees with the pixmap's own alpha at every pixel",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-03-cache",
      "requirement": "M3-03",
      "given": "Sprites cut at scale 1, then at scale 2",
      "when": "Sprites at scale 1 are made again (a drag back to the first monitor)",
      "then": "They reuse the frames already cut instead of cutting the strips again; a third scale drops the oldest",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-04-buffers",
      "requirement": "M3-04",
      "given": "A configured layer surface against the pretend compositor",
      "when": "Frames are presented while the compositor holds buffers, and then the stage goes idle",
      "then": "No more than 2 buffers ever exist, a third frame waits for a release, and the spare buffer is destroyed once idle",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-05-keys",
      "requirement": "M3-05",
      "given": "An overlay menu open (with a submenu, a section, a disabled item), the ask box open behind it",
      "when": "Keys arrive: Down, Up, Home, End, Right, Left, a letter, Enter, Esc",
      "then": "The highlight moves over enabled items only, Right opens and Left closes the submenu, a letter jumps to the next item starting with it, Enter runs the item after the menu closes, and Esc closes the menu while the ask box stays open",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-05-focus",
      "requirement": "M3-05",
      "given": "The overlay with the ask box closed",
      "when": "A menu opens and later closes",
      "then": "The stage asks for the keyboard as the menu opens and gives it back as it closes, and the highlighted row is drawn with an outline",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-06-scroll",
      "requirement": "M3-06",
      "given": "A menu with more items than fit the screen",
      "when": "It opens, and the wheel, a scroll arrow and End are used",
      "then": "Its height stays within the screen, scroll arrows show, and each scrolls the hidden items into view",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-06-hover",
      "requirement": "M3-06",
      "given": "A menu with a submenu",
      "when": "The pointer rests on the submenu's item, then crosses a sibling on its way into the open submenu",
      "then": "The submenu opens 250 ms after the hover, not before; it stays open across the diagonal move; and moving within the hovered item does not rebuild it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-07-contrast",
      "requirement": "M3-07",
      "given": "The menu's colours for a light and a dark palette",
      "when": "Headers, shortcuts and the hovered row are drawn",
      "then": "Headers and shortcuts have at least 4.5:1 contrast with the fill, the hovered row's fill is opaque, and its text has at least 4.5:1 on it",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-08-rows",
      "requirement": "M3-08",
      "given": "The application font at its default size and at 24 pt",
      "when": "A menu is laid out",
      "then": "Each row is max(26, font height + 8) pixels high",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-09-latin",
      "requirement": "M3-09",
      "given": "A us,ru keymap with Russian active",
      "when": "V, C, X, A and Z are pressed with Ctrl, or with Alt, or with neither",
      "then": "With Ctrl or Alt they are Key_V, Key_C, Key_X, Key_A, Key_Z; with neither they stay Cyrillic; a Russian-only keymap has nothing to fall back to",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-09-overlay",
      "requirement": "M3-09",
      "given": "The layer surface against the pretend compositor with the us,ru keymap, Russian active, and the stage with the ask box open",
      "when": "Ctrl and the V key are pressed",
      "then": "The stage receives Key_V with Ctrl, and the ask box pastes the overlay's clipboard",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-10-shape",
      "requirement": "M3-10",
      "given": "Input rectangles in logical pixels and a device pixel ratio of 1.5 or 2",
      "when": "The X input shape is set",
      "then": "Each rectangle is scaled by the ratio and rounded outward, and the X server reports those rectangles where an X server is available",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-11-still",
      "requirement": "M3-11",
      "given": "A behaviour with reduced motion on",
      "when": "Alert, talk, think, sleep and idle play, a wave or hop is asked for, it hides and comes back, and it is dropped from a height",
      "then": "Each looping mood holds one pose, waves, hops and peeks don't play, a drop lands at once, and the stage's needs-you badge and sleeping z's don't animate",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-12-hold",
      "requirement": "M3-12",
      "given": "The creature walking",
      "when": "The pointer rests on it, then leaves",
      "then": "The current walk frame holds, facing the way it walked, and the walk carries on from there",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-13-badge",
      "requirement": "M3-13",
      "given": "A stage with the creature drawn",
      "when": "set_badge is given agents working and needing you, then cleared",
      "then": "A badge is drawn beside the creature: needs-you as an amber diamond, working as a blue circle, each with its count; its description names the states; clearing redraws the place it was",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-14-unhosted",
      "requirement": "M3-14",
      "given": "The overlay stage hosting the ask box",
      "when": "Hosting is turned off, and on again",
      "then": "Off: the ask box is a top-level window outside any scene, with Qt's own context menus, and the stage says it neither hosts windows nor draws menus; on: it is hosted again",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-15-follow",
      "requirement": "M3-15",
      "given": "Two screens and the pointer on the one the stage isn't on",
      "when": "Following is off; then on, for less than and more than 1 s; and while dragging",
      "then": "Off or under 1 s it stays; on and over 1 s it moves to the pointer's screen with the creature on that floor; never during a drag",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    },
    {
      "id": "AC-M3-M2-stage",
      "requirement": "M3-M2",
      "given": "The overlay stage with M2's speech bubble and ask box",
      "when": "The pointer rests on a bubble past its time and leaves; a link in a bubble is pointed at and clicked; the stage's screen is set; the ask box's art moves a frame",
      "then": "The bubble stays while pointed at and goes after the rest of its time; the cursor is a hand over the link and the link opens without dismissing the bubble; the bubble's max height is 40% of the screen's; only the box's border is damaged, not its text area",
      "checks": [
        "behavior",
        "red"
      ],
      "manual_reason": null
    }
  ],
  "tasks": [
    {
      "id": "T-M3-xkb",
      "purpose": "Latin fallback for Ctrl and Alt shortcuts in xkb.Keyboard, with tests through the keyboard and the overlay",
      "acceptance": [
        "AC-M3-09-latin",
        "AC-M3-09-overlay"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/xkb.py",
          "action": "modify"
        },
        {
          "path": "tests/test_xkb.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wayland.py",
          "action": "modify"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-linux",
        "EV-red-09-latin",
        "EV-red-09-overlay"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-shape",
      "purpose": "Scale the X input shape to device pixels, rounding outward",
      "acceptance": [
        "AC-M3-10-shape"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/clickthrough.py",
          "action": "modify"
        },
        {
          "path": "tests/test_clickthrough.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-10-shape"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-sprites",
      "purpose": "Store frames once with an alpha mask, the ratio set before fromImage, and keep the previous scale's frames",
      "acceptance": [
        "AC-M3-03-once",
        "AC-M3-03-cache"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/sprites.py",
          "action": "modify"
        },
        {
          "path": "tests/test_sprites.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-03-once",
        "EV-red-03-cache"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-behavior",
      "purpose": "Behavior.next_change, change notification, reduced motion and the held walk frame",
      "acceptance": [
        "AC-M3-11-still",
        "AC-M3-12-hold"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/behavior.py",
          "action": "modify"
        },
        {
          "path": "tests/test_behavior.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-11-still",
        "EV-red-12-hold"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-timer",
      "purpose": "The stage's single-shot timer, refresh-rate frames, device-pixel positions, drag redraws and pointer polling",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer",
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag"
      ],
      "depends_on": [
        "T-M3-behavior"
      ],
      "changes": [
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stage_timer.py",
          "action": "create"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-01-idle",
        "EV-red-01-quiet",
        "EV-red-01-pointer",
        "EV-red-02-refresh",
        "EV-red-02-pixels",
        "EV-red-02-drag"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-menu",
      "purpose": "StageMenu keyboard, scrolling, hover delay, contrast and font-sized rows, and the stage routing keys and the keyboard to it",
      "acceptance": [
        "AC-M3-05-keys",
        "AC-M3-05-focus",
        "AC-M3-06-scroll",
        "AC-M3-06-hover",
        "AC-M3-07-contrast",
        "AC-M3-08-rows"
      ],
      "depends_on": [
        "T-M3-timer"
      ],
      "changes": [
        {
          "path": "chatmon/stagemenu.py",
          "action": "modify"
        },
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stagemenu.py",
          "action": "modify"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-05-keys",
        "EV-red-05-focus",
        "EV-red-06-scroll",
        "EV-red-06-hover",
        "EV-red-07-contrast",
        "EV-red-08-rows"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-stage-features",
      "purpose": "The agent badge, reduced motion on the stage, the unhosted mode and following the pointer's screen",
      "acceptance": [
        "AC-M3-11-still",
        "AC-M3-13-badge",
        "AC-M3-14-unhosted",
        "AC-M3-15-follow"
      ],
      "depends_on": [
        "T-M3-timer",
        "T-M3-behavior"
      ],
      "changes": [
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_stage_features.py",
          "action": "create"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-11-still",
        "EV-red-13-badge",
        "EV-red-14-unhosted",
        "EV-red-15-follow"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-buffers",
      "purpose": "At most two overlay buffers, the spare dropped when idle",
      "acceptance": [
        "AC-M3-04-buffers"
      ],
      "depends_on": [],
      "changes": [
        {
          "path": "chatmon/layer.py",
          "action": "modify"
        },
        {
          "path": "tests/test_wayland.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-linux",
        "EV-red-04-buffers"
      ],
      "blocker": null,
      "superseded_by": null
    },
    {
      "id": "T-M3-m2",
      "purpose": "The stage-side bubble calls M2 handed over: hover pause, links, max height per screen, the multi-line field, the border-only repaint",
      "acceptance": [
        "AC-M3-M2-stage"
      ],
      "depends_on": [
        "T-M3-timer"
      ],
      "changes": [
        {
          "path": "chatmon/penguin.py",
          "action": "modify"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        }
      ],
      "status": "verified",
      "evidence": [
        "EV-tests-windows",
        "EV-tests-linux",
        "EV-red-m2-stage"
      ],
      "blocker": null,
      "superseded_by": null
    }
  ],
  "evidence": [
    {
      "id": "EV-readiness-1",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer",
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag",
        "AC-M3-03-once",
        "AC-M3-03-cache",
        "AC-M3-04-buffers",
        "AC-M3-05-keys",
        "AC-M3-05-focus",
        "AC-M3-06-scroll",
        "AC-M3-06-hover",
        "AC-M3-07-contrast",
        "AC-M3-08-rows",
        "AC-M3-09-latin",
        "AC-M3-09-overlay",
        "AC-M3-10-shape",
        "AC-M3-11-still",
        "AC-M3-12-hold",
        "AC-M3-13-badge",
        "AC-M3-14-unhosted",
        "AC-M3-15-follow"
      ],
      "kind": "readiness",
      "status": "stale",
      "command": [],
      "method": "Requirements review of every M3 criterion against the brief, the rules and the source it changes: clarity, conflicts, failure behaviour, scope, terminology, rules, coverage and order (reports/m3/readiness.md)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m3/readiness.md",
        "sha256": "20c0a41af631164ddb477e6f0ae5c203fabc54d6aa71e685ee2e3671c90edcc7"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "0124fee38622d8b1ec37924591db63326fb776de87b58dde6a09dbeb1f4b704f"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d0ae7f3f3cfaf55d605832df85b4863a8fe93a746e52d8d27621f2f9892da222"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "33a9c9cbbbb675d33bac9603122b65cc2e31ffb942d9be57fe2d65bf7ef3e43c"
        }
      ],
      "scope_sha256": "804d65f6e557d1bee11b7227edef524e42579b59b81a0b17402f56af7a6a0c24",
      "red": null,
      "reason": "Scope revision 2 added M3-M2 and moved tests to new files; re-reviewed in EV-readiness-2 (readiness.md, addendum)"
    },
    {
      "id": "EV-readiness-2",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer",
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag",
        "AC-M3-03-once",
        "AC-M3-03-cache",
        "AC-M3-04-buffers",
        "AC-M3-05-keys",
        "AC-M3-05-focus",
        "AC-M3-06-scroll",
        "AC-M3-06-hover",
        "AC-M3-07-contrast",
        "AC-M3-08-rows",
        "AC-M3-09-latin",
        "AC-M3-09-overlay",
        "AC-M3-10-shape",
        "AC-M3-11-still",
        "AC-M3-12-hold",
        "AC-M3-13-badge",
        "AC-M3-14-unhosted",
        "AC-M3-15-follow",
        "AC-M3-M2-stage"
      ],
      "kind": "readiness",
      "status": "pass",
      "command": [],
      "method": "Requirements review of every M3 criterion against the brief, the rules and the source, with the scope revision 2 addendum for M3-M2, the moved test files and the closing Integration notes (reports/m3/readiness.md)",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": null,
      "artifact": {
        "path": "docs/delivery/reports/m3/readiness.md",
        "sha256": "ef384467ca605d2e8396f9d867489f7ee317ccbd46de3feb564f11f41f8963fc"
      },
      "inputs": [
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        }
      ],
      "scope_sha256": "0260c6f79183687e380fb3e14605a351d8d6f622a28b23ea18487cfe1f04a8c1",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-tests-windows",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer",
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag",
        "AC-M3-03-once",
        "AC-M3-03-cache",
        "AC-M3-05-keys",
        "AC-M3-05-focus",
        "AC-M3-06-scroll",
        "AC-M3-06-hover",
        "AC-M3-07-contrast",
        "AC-M3-08-rows",
        "AC-M3-10-shape",
        "AC-M3-11-still",
        "AC-M3-12-hold",
        "AC-M3-13-badge",
        "AC-M3-14-unhosted",
        "AC-M3-15-follow",
        "AC-M3-M2-stage"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_stage_timer.py",
        "tests/test_stage_features.py",
        "tests/test_stagemenu.py",
        "tests/test_overlay_stage.py",
        "tests/test_behavior.py",
        "tests/test_sprites.py",
        "tests/test_clickthrough.py",
        "tests/test_stage_screens.py",
        "tests/test_xkb.py",
        "tests/test_wayland.py"
      ],
      "method": "M3's test files on Windows 11 offscreen: 89 passed; the Linux-only overlay, xkb and X server tests skip here and are covered by EV-tests-linux",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/gates/m3-tests-windows.log",
        "sha256": "345857d7d4a4b9648e7ff696e7f2c39e074a73737a40d71b3a94ca5e5d5f9558"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "0386ad57af0750a3d098b44cf38b169f3a7e75be902baf1c1d0ba75d5ae4bf06"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "62aeea9561822ef440c72b95e311971ee1f5f143cc1bccb1767581dc57ac4c5a"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "df313ca5e71ba0d5ecf24c7107ae1a970895fe0566a4019f0e5b0817f51918f5",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-tests-linux",
      "acceptance": [
        "AC-M3-01-idle",
        "AC-M3-01-quiet",
        "AC-M3-01-pointer",
        "AC-M3-02-refresh",
        "AC-M3-02-pixels",
        "AC-M3-02-drag",
        "AC-M3-03-once",
        "AC-M3-03-cache",
        "AC-M3-04-buffers",
        "AC-M3-05-keys",
        "AC-M3-05-focus",
        "AC-M3-06-scroll",
        "AC-M3-06-hover",
        "AC-M3-07-contrast",
        "AC-M3-08-rows",
        "AC-M3-09-latin",
        "AC-M3-09-overlay",
        "AC-M3-10-shape",
        "AC-M3-11-still",
        "AC-M3-12-hold",
        "AC-M3-13-badge",
        "AC-M3-14-unhosted",
        "AC-M3-15-follow",
        "AC-M3-M2-stage"
      ],
      "kind": "behavior",
      "status": "pass",
      "command": [
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rs",
        "tests/test_stage_timer.py",
        "tests/test_stage_features.py",
        "tests/test_stagemenu.py",
        "tests/test_overlay_stage.py",
        "tests/test_behavior.py",
        "tests/test_sprites.py",
        "tests/test_clickthrough.py",
        "tests/test_stage_screens.py",
        "tests/test_xkb.py",
        "tests/test_wayland.py"
      ],
      "method": "M3's test files on Linux (WSL Arch, PyQt6 6.12.1, libxkbcommon, WSLg X server): 117 passed, the 4 Windows-only click-through tests skipped",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/gates/m3-tests-linux.log",
        "sha256": "87c824b4edf74470742b3d0dfa6ac9153f280b8510971485b3c05684df691eec"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
        },
        {
          "path": "chatmon/layer.py",
          "sha256": "90deeb65c322cd2a9b867f0b48f64d4eb2f39382e9345eee6848735ed6455d9d"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/sprites.py",
          "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "chatmon/xkb.py",
          "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "0386ad57af0750a3d098b44cf38b169f3a7e75be902baf1c1d0ba75d5ae4bf06"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "62aeea9561822ef440c72b95e311971ee1f5f143cc1bccb1767581dc57ac4c5a"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "067fcbe7f54d541a1c0265fc894901abf6b1b996574063ddbd2282f98765e07a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c4cd00772fcf1545497c6a4e0c624ab4d005dfe190799c70e507a3a1ab8d9586"
        }
      ],
      "scope_sha256": "0260c6f79183687e380fb3e14605a351d8d6f622a28b23ea18487cfe1f04a8c1",
      "red": null,
      "reason": null
    },
    {
      "id": "EV-red-01-idle",
      "acceptance": [
        "AC-M3-01-idle"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_standing_idle_it_sleeps_until_the_next_frame_and_misses_none"
      ],
      "method": "tests/drills/run.py drill M3-01-idle on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '        return min(max(min(due) - now, self._frame_interval()), IDLE_FLOOR)' -> '        return self._frame_interval()'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_standing_idle_it_sleeps_until_the_next_frame_and_misses_none",
        "observed_diagnostic": "______ test_standing_idle_it_sleeps_until_the_next_frame_and_misses_none ______",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "16afdaedbe2b418fa2e208fd72ad6508b74b8e8d3aec36d70e467e03a4e4a66a"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-01-quiet",
      "acceptance": [
        "AC-M3-01-quiet"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_covered_hidden_or_not_drawing_it_hardly_ticks_or_stops"
      ],
      "method": "tests/drills/run.py drill M3-01-quiet on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '        if not self.drawing:\\n            return\\n        self._schedule(self._last_tick' -> '        self._schedule(self._last_tick'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_covered_hidden_or_not_drawing_it_hardly_ticks_or_stops",
        "observed_diagnostic": "_________ test_covered_hidden_or_not_drawing_it_hardly_ticks_or_stops _________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "43ceda768745db34aff222b25f71273ff54ce25f15579c988dcf592856bbddc8"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-01-pointer",
      "acceptance": [
        "AC-M3-01-pointer"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_the_pointer_is_polled_every_frame_only_near_the_chatmon"
      ],
      "method": "tests/drills/run.py drill M3-01-pointer on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '(self._frame_interval() if near else FAR_POLL)' -> '(self._frame_interval())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_pointer_is_polled_every_frame_only_near_the_chatmon",
        "observed_diagnostic": "________ test_the_pointer_is_polled_every_frame_only_near_the_chatmon _________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "be0bea88638a979f6990abe510c880368109936d0614d0ab817be5c3d663b840"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-02-refresh",
      "acceptance": [
        "AC-M3-02-refresh"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_while_it_moves_it_ticks_at_the_screens_refresh_rate"
      ],
      "method": "tests/drills/run.py drill M3-02-refresh on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '        return min(max(rate, MIN_HZ), MAX_HZ) if rate > 0 else DEFAULT_HZ' -> '        return DEFAULT_HZ'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_while_it_moves_it_ticks_at_the_screens_refresh_rate",
        "observed_diagnostic": "__________ test_while_it_moves_it_ticks_at_the_screens_refresh_rate ___________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "e1fb5c0520606f88147fb25e97d4f58cdb9974083ba7f2d60a3e10b537f26917"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-02-pixels",
      "acceptance": [
        "AC-M3-02-pixels"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_the_sprite_sits_on_the_device_pixel_grid"
      ],
      "method": "tests/drills/run.py drill M3-02-pixels on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '            left = round((f.x - origin.x() - sprite.anchor) * k) / k' -> '            left = round(f.x - origin.x() - sprite.anchor)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert halves >= 2",
        "observed_diagnostic": ">       assert halves >= 2  # not rounded to whole stage pixels",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "d229cfe338b4fdc0ab52f767557f9c8c5376eec6b74e5ea93a5d24c507ef00cd"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-02-drag",
      "acceptance": [
        "AC-M3-02-drag"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_timer.py::test_a_drag_redraws_on_the_pointer_moving_not_on_a_clock"
      ],
      "method": "tests/drills/run.py drill M3-02-drag on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "c034e5199b2a374a63ba3201f9dee8f9d76f5c2b205355e47b6af72aaed1f08b",
      "red": {
        "mutation": "in chatmon/penguin.py: '        self._schedule(self._last_tick + self._frame_interval() - self._clock())' -> '        self._schedule(IDLE_FLOOR)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_drag_redraws_on_the_pointer_moving_not_on_a_clock",
        "observed_diagnostic": "__________ test_a_drag_redraws_on_the_pointer_moving_not_on_a_clock ___________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "d1aa553033a17c310a5e755b350eb8d1f3906098e8ef863096eef1788a031338"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-03-once",
      "acceptance": [
        "AC-M3-03-once"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_sprites.py::test_a_frame_is_kept_once_with_a_mask_that_agrees_with_its_pixels"
      ],
      "method": "tests/drills/run.py drill M3-03-once on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/sprites.py",
          "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "62aeea9561822ef440c72b95e311971ee1f5f143cc1bccb1767581dc57ac4c5a"
        }
      ],
      "scope_sha256": "413b27b0f35769f0fe8a89b5663557a63d1fbd1ee6965fad5494ea42b661b35d",
      "red": {
        "mutation": "in chatmon/sprites.py: \"    img.setDevicePixelRatio(scale)  # before the pixmap is made: changing a pixmap's ratio afterwards can copy it\" -> '    pass  # drill: no ratio before the pixmap is made'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "devicePixelRatio() == 2.0",
        "observed_diagnostic": ">       assert frame.pixmap.devicePixelRatio() == 2.0",
        "before": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "4cc849a2ebd15f29fad77e8dacc761d97292113689fd133b7ad232c5e51fbddc"
          }
        ],
        "after": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-03-cache",
      "acceptance": [
        "AC-M3-03-cache"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_sprites.py::test_the_previous_screens_frames_are_kept_for_a_drag_back"
      ],
      "method": "tests/drills/run.py drill M3-03-cache on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/sprites.py",
          "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_sprites.py",
          "sha256": "62aeea9561822ef440c72b95e311971ee1f5f143cc1bccb1767581dc57ac4c5a"
        }
      ],
      "scope_sha256": "413b27b0f35769f0fe8a89b5663557a63d1fbd1ee6965fad5494ea42b661b35d",
      "red": {
        "mutation": "in chatmon/sprites.py: '        _CUT.move_to_end(key)' -> '        pass  # drill: the newest is not moved to the end'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_previous_screens_frames_are_kept_for_a_drag_back",
        "observed_diagnostic": "__________ test_the_previous_screens_frames_are_kept_for_a_drag_back __________",
        "before": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "0d00a53258f7a64629396dfab310624bc422bf1544b8f0a2237802d0164ef23f"
          }
        ],
        "after": [
          {
            "path": "chatmon/sprites.py",
            "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-04-buffers",
      "acceptance": [
        "AC-M3-04-buffers"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon-wt/m3/docs/delivery/reports/m3/wslpy.bat",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wayland.py::test_it_keeps_two_buffers_at_most_and_lets_the_spare_go_once_still"
      ],
      "method": "tests/drills/run.py drill M3-04-buffers on a temporary copy (Linux, WSL Arch through reports/m3/wslpy.bat): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills-linux.log",
        "sha256": "db9fe3d7a9a6baac88006ecd78c9a2f1cb1cc9e6e6012c622713564e36de97c7"
      },
      "inputs": [
        {
          "path": "chatmon/layer.py",
          "sha256": "90deeb65c322cd2a9b867f0b48f64d4eb2f39382e9345eee6848735ed6455d9d"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "067fcbe7f54d541a1c0265fc894901abf6b1b996574063ddbd2282f98765e07a"
        }
      ],
      "scope_sha256": "281d6bd0f96ae0a6d7337877bc6def9518d6d7d165c35ba69c17b1761360eb09",
      "red": {
        "mutation": "in chatmon/layer.py: 'MAX_BUFFERS = 2' -> 'MAX_BUFFERS = 3'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_keeps_two_buffers_at_most_and_lets_the_spare_go_once_still",
        "observed_diagnostic": "______ test_it_keeps_two_buffers_at_most_and_lets_the_spare_go_once_still ______",
        "before": [
          {
            "path": "chatmon/layer.py",
            "sha256": "90deeb65c322cd2a9b867f0b48f64d4eb2f39382e9345eee6848735ed6455d9d"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/layer.py",
            "sha256": "9805393e904c578fb4c9b67099e8377269a0483045fe6b325f516db1922a0225"
          }
        ],
        "after": [
          {
            "path": "chatmon/layer.py",
            "sha256": "90deeb65c322cd2a9b867f0b48f64d4eb2f39382e9345eee6848735ed6455d9d"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-05-keys",
      "acceptance": [
        "AC-M3-05-keys"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_the_keyboard_moves_opens_picks_and_closes"
      ],
      "method": "tests/drills/run.py drill M3-05-keys on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/stagemenu.py: '            else:\\n                self.close()\\n        elif key in (Qt.Key.Key_Down' -> '            else:\\n                pass\\n        elif key in (Qt.Key.Key_Down'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_keyboard_moves_opens_picks_and_closes",
        "observed_diagnostic": "_______________ test_the_keyboard_moves_opens_picks_and_closes ________________",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "1de852c7068752c1d32ed8196ed89adedb011f7a56062303237c505830f72c2e"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-05-focus",
      "acceptance": [
        "AC-M3-05-focus"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_overlay_stage.py::test_the_keyboard_picks_from_the_penguins_menu_and_the_overlay_takes_it_while_open"
      ],
      "method": "tests/drills/run.py drill M3-05-focus on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/penguin.py: '            focus(on, on)\\n' -> '            pass\\n'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "assert s.surface.focus == [(True, True)]",
        "observed_diagnostic": ">       assert s.surface.focus == [(True, True)]  # a popup menu takes the keyboard",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "ccda529bfbd2047c6d96594605705ab29d8440dcbd8dc6403bf3b9e782d7b69c"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-06-scroll",
      "acceptance": [
        "AC-M3-06-scroll"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_a_menu_taller_than_the_screen_scrolls"
      ],
      "method": "tests/drills/run.py drill M3-06-scroll on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/stagemenu.py: '        size = QRect(0, 0, width, min(content, max(row + 2 * SCROLLER, area.height())))' -> '        size = QRect(0, 0, width, content)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_menu_taller_than_the_screen_scrolls",
        "observed_diagnostic": "_________________ test_a_menu_taller_than_the_screen_scrolls __________________",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "8b0ae54159b5fd671cf4ee17c771c477baadc67b68594126d0c85df086ca2332"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-06-hover",
      "acceptance": [
        "AC-M3-06-hover"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_submenus_open_after_the_pointer_rests_and_actions_run_after_it_closes"
      ],
      "method": "tests/drills/run.py drill M3-06-hover on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/stagemenu.py: '            self._pending = (pi, ii, self._clock() + SUBMENU_DELAY)' -> '            self._pending = (pi, ii, self._clock())'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_submenus_open_after_the_pointer_rests_and_actions_run_after_it_closes",
        "observed_diagnostic": "_ test_submenus_open_after_the_pointer_rests_and_actions_run_after_it_closes __",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "0eadbed64a33c8908550425104ac0a39972ef24fda2aed1ce6dba9de1533707f"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-07-contrast",
      "acceptance": [
        "AC-M3-07-contrast"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_headers_and_shortcuts_read_well_and_the_lit_row_is_solid"
      ],
      "method": "tests/drills/run.py drill M3-07-contrast on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/stagemenu.py: 'MUTED_AIM = 5.0' -> 'MUTED_AIM = 2.5'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_headers_and_shortcuts_read_well_and_the_lit_row_is_solid",
        "observed_diagnostic": "________ test_headers_and_shortcuts_read_well_and_the_lit_row_is_solid ________",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "b0b23139f9005f4b037ab2fe1089d7ef91a81010d9687a599d521de4b2739a1e"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-08-rows",
      "acceptance": [
        "AC-M3-08-rows"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stagemenu.py::test_rows_grow_with_the_font"
      ],
      "method": "tests/drills/run.py drill M3-08-rows on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "chatmon/stagemenu.py",
          "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        },
        {
          "path": "tests/test_stagemenu.py",
          "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
        }
      ],
      "scope_sha256": "401bbe77c8bc1bd671d68aab390df4ff7f39cc74ebb0c8642a87a8043f6f2590",
      "red": {
        "mutation": "in chatmon/stagemenu.py: '        return max(ROW, QFontMetrics(self._font()).height() + ROW_PAD)' -> '        return ROW'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_rows_grow_with_the_font",
        "observed_diagnostic": "________________________ test_rows_grow_with_the_font _________________________",
        "before": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "4759302f3492e9e54d2dbaca718fe76a6264c921e2c3d457be408154e392efaf"
          }
        ],
        "after": [
          {
            "path": "chatmon/stagemenu.py",
            "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-09-latin",
      "acceptance": [
        "AC-M3-09-latin"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon-wt/m3/docs/delivery/reports/m3/wslpy.bat",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_xkb.py::test_shortcuts_on_a_russian_layout_are_the_latin_keys",
        "tests/test_xkb.py::test_the_latin_symbol_comes_from_the_first_layout_that_has_one"
      ],
      "method": "tests/drills/run.py drill M3-09-latin on a temporary copy (Linux, WSL Arch through reports/m3/wslpy.bat): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills-linux.log",
        "sha256": "db9fe3d7a9a6baac88006ecd78c9a2f1cb1cc9e6e6012c622713564e36de97c7"
      },
      "inputs": [
        {
          "path": "chatmon/xkb.py",
          "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "067fcbe7f54d541a1c0265fc894901abf6b1b996574063ddbd2282f98765e07a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c4cd00772fcf1545497c6a4e0c624ab4d005dfe190799c70e507a3a1ab8d9586"
        }
      ],
      "scope_sha256": "9397fcd6f8ed3d65973dffeb93da7620cf25975bba1b9a4a12c83c0078c9e659",
      "red": {
        "mutation": "in chatmon/xkb.py: '            sym = self._latin_sym(xkb_code) or sym' -> '            sym = 0 or sym'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_shortcuts_on_a_russian_layout_are_the_latin_keys",
        "observed_diagnostic": "____________ test_shortcuts_on_a_russian_layout_are_the_latin_keys _____________",
        "before": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "477e4d0f97cf96403b3170c12527ce8e3d15aa19a6b85342ac82e54e9c84bda5"
          }
        ],
        "after": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-09-overlay",
      "acceptance": [
        "AC-M3-09-overlay"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:/Users/Randy/Coding/chatmon-wt/m3/docs/delivery/reports/m3/wslpy.bat",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_wayland.py::test_shortcuts_reach_the_stage_as_latin_keys_on_a_russian_layout",
        "tests/test_overlay_stage.py::test_ctrl_v_pastes_under_a_russian_layout"
      ],
      "method": "tests/drills/run.py drill M3-09-overlay on a temporary copy (Linux, WSL Arch through reports/m3/wslpy.bat): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills-linux.log",
        "sha256": "db9fe3d7a9a6baac88006ecd78c9a2f1cb1cc9e6e6012c622713564e36de97c7"
      },
      "inputs": [
        {
          "path": "chatmon/xkb.py",
          "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_wayland.py",
          "sha256": "067fcbe7f54d541a1c0265fc894901abf6b1b996574063ddbd2282f98765e07a"
        },
        {
          "path": "tests/test_xkb.py",
          "sha256": "c4cd00772fcf1545497c6a4e0c624ab4d005dfe190799c70e507a3a1ab8d9586"
        }
      ],
      "scope_sha256": "9397fcd6f8ed3d65973dffeb93da7620cf25975bba1b9a4a12c83c0078c9e659",
      "red": {
        "mutation": "in chatmon/xkb.py: '            sym = self._latin_sym(xkb_code) or sym' -> '            sym = 0 or sym'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_shortcuts_reach_the_stage_as_latin_keys_on_a_russian_layout",
        "observed_diagnostic": "_______ test_shortcuts_reach_the_stage_as_latin_keys_on_a_russian_layout _______",
        "before": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "477e4d0f97cf96403b3170c12527ce8e3d15aa19a6b85342ac82e54e9c84bda5"
          }
        ],
        "after": [
          {
            "path": "chatmon/xkb.py",
            "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-10-shape",
      "acceptance": [
        "AC-M3-10-shape"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_clickthrough.py::test_the_x_input_shape_is_in_device_pixels_rounded_outward"
      ],
      "method": "tests/drills/run.py drill M3-10-shape on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/clickthrough.py",
          "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_clickthrough.py",
          "sha256": "0386ad57af0750a3d098b44cf38b169f3a7e75be902baf1c1d0ba75d5ae4bf06"
        }
      ],
      "scope_sha256": "f6f89f7341d7c61e71dce2fbfa1a66f1c22563ee80b3fe795b93232084fb37e6",
      "red": {
        "mutation": "in chatmon/clickthrough.py: 'math.ceil((x + w) * ratio) - left' -> 'round((x + w) * ratio) - left'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_x_input_shape_is_in_device_pixels_rounded_outward",
        "observed_diagnostic": "_________ test_the_x_input_shape_is_in_device_pixels_rounded_outward __________",
        "before": [
          {
            "path": "chatmon/clickthrough.py",
            "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/clickthrough.py",
            "sha256": "8cc838f0b4ffc67dc88706105d5b3e6bb4b9a1fcb44316d711459e1b4fdb446c"
          }
        ],
        "after": [
          {
            "path": "chatmon/clickthrough.py",
            "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-11-still",
      "acceptance": [
        "AC-M3-11-still"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_behavior.py::test_reduced_motion_holds_each_looping_mood_still"
      ],
      "method": "tests/drills/run.py drill M3-11-still on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "7fefd3e632a157695123981bcaf221af910909a79591abddb4dfb28da1301d1e",
      "red": {
        "mutation": "in chatmon/behavior.py: '            clips = self._still(clips)' -> '            clips = list(clips)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_reduced_motion_holds_each_looping_mood_still",
        "observed_diagnostic": "______________ test_reduced_motion_holds_each_looping_mood_still ______________",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "f58bbd42092bf6465fb52ffdb31a9d6127b614207e2b5ffbb4118d7e76d827e6"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-12-hold",
      "acceptance": [
        "AC-M3-12-hold"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_behavior.py::test_a_walk_waits_while_the_pointer_is_over_it_and_carries_on_after"
      ],
      "method": "tests/drills/run.py drill M3-12-hold on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        }
      ],
      "scope_sha256": "7c49bbf57305497c1bb4bb7fbe9480f3ed577ae774a526eee678088891dc9d4f",
      "red": {
        "mutation": "in chatmon/behavior.py: '            return Frame(\"walk\", clip.frames[n % len(clip.frames)], clip.mirror, self.x, self.lift)' -> '            return Frame(\"idle\", 0, clip.mirror, self.x, self.lift)'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_walk_waits_while_the_pointer_is_over_it_and_carries_on_after",
        "observed_diagnostic": "_____ test_a_walk_waits_while_the_pointer_is_over_it_and_carries_on_after _____",
        "before": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "6fa36696fe62dba2bf0f53ca7627de70547cfa8067bf965fc94cc83329721329"
          }
        ],
        "after": [
          {
            "path": "chatmon/behavior.py",
            "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-13-badge",
      "acceptance": [
        "AC-M3-13-badge"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_the_badge_counts_agents_by_state_with_a_shape_for_each"
      ],
      "method": "tests/drills/run.py drill M3-13-badge on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "7fefd3e632a157695123981bcaf221af910909a79591abddb4dfb28da1301d1e",
      "red": {
        "mutation": "in chatmon/penguin.py: '        if state == \"needs-you\":  # a diamond: a warning\\'s shape' -> \"        if False:  # a diamond: a warning's shape\"",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_the_badge_counts_agents_by_state_with_a_shape_for_each",
        "observed_diagnostic": "_________ test_the_badge_counts_agents_by_state_with_a_shape_for_each _________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "893a5f5c40cdb35a52a318cfe6934323fd706f722f3299e40fd397575563eae3"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-14-unhosted",
      "acceptance": [
        "AC-M3-14-unhosted"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_overlay_stage.py::test_for_a_screen_reader_the_box_can_be_a_normal_window_with_qts_own_menus"
      ],
      "method": "tests/drills/run.py drill M3-14-unhosted on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "7fefd3e632a157695123981bcaf221af910909a79591abddb4dfb28da1301d1e",
      "red": {
        "mutation": "in chatmon/penguin.py: '        return bool(getattr(self.surface, \"hosts_windows\", False)) and not self._unhosted' -> '        return bool(getattr(self.surface, \"hosts_windows\", False))'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_for_a_screen_reader_the_box_can_be_a_normal_window_with_qts_own_menus",
        "observed_diagnostic": "_ test_for_a_screen_reader_the_box_can_be_a_normal_window_with_qts_own_menus __",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "bfa1f6747c3286e427f0110a0866880b3f7f1611b6d524148c25e7afc995d1ac"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-15-follow",
      "acceptance": [
        "AC-M3-15-follow"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_stage_features.py::test_it_follows_the_pointer_to_its_screen_only_when_asked_and_after_a_second"
      ],
      "method": "tests/drills/run.py drill M3-15-follow on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_features.py",
          "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "7fefd3e632a157695123981bcaf221af910909a79591abddb4dfb28da1301d1e",
      "red": {
        "mutation": "in chatmon/penguin.py: '        if now - self._away[1] < FOLLOW_AFTER:' -> '        if False:'",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_it_follows_the_pointer_to_its_screen_only_when_asked_and_after_a_second",
        "observed_diagnostic": "_ test_it_follows_the_pointer_to_its_screen_only_when_asked_and_after_a_second _",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "bd05d08e846507e92de9ed1f87543da000139d6ffe9ebce6d49d8522ebcdebfe"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    },
    {
      "id": "EV-red-m2-stage",
      "acceptance": [
        "AC-M3-M2-stage"
      ],
      "kind": "red",
      "status": "pass",
      "command": [
        "C:\\Users\\Randy\\Coding\\chatmon\\.venv\\Scripts\\python.exe",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_overlay_stage.py::test_a_bubble_waits_while_the_pointer_is_on_it"
      ],
      "method": "tests/drills/run.py drill M3-M2-hover on a temporary copy (Windows, the worktree's venv): green, mutated red, restored green",
      "environment": {
        "platform": "windows",
        "tools": {
          "python": "3.14.10",
          "pyqt6": "6.11.0",
          "pytest": "9.2.0",
          "ruff": "0.17.4"
        }
      },
      "exit_code": 0,
      "artifact": {
        "path": "docs/delivery/reports/m3/drills.log",
        "sha256": "2de93a05e13f246610571ec3ed4bbab54f95f73b51d80c093506fc06886af03f"
      },
      "inputs": [
        {
          "path": "chatmon/behavior.py",
          "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
        },
        {
          "path": "chatmon/penguin.py",
          "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
        },
        {
          "path": "docs/delivery/ASSESSMENT.md",
          "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
        },
        {
          "path": "docs/delivery/ROADMAP.md",
          "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
        },
        {
          "path": "pyproject.toml",
          "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
        },
        {
          "path": "tests/conftest.py",
          "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
        },
        {
          "path": "tests/drills/run.py",
          "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
        },
        {
          "path": "tests/test_behavior.py",
          "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
        },
        {
          "path": "tests/test_stage_timer.py",
          "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
        }
      ],
      "scope_sha256": "790833fe427597598bdc7b0786a34915a262d0e3810f0aebf2742ad9eb7f2b45",
      "red": {
        "mutation": "in chatmon/penguin.py: '            self._bubble_hovered(hover not in (None, \"penguin\"))\\n' -> ''",
        "baseline_exit": 0,
        "mutated_exit": 1,
        "restored_exit": 0,
        "expected_diagnostic": "test_a_bubble_waits_while_the_pointer_is_on_it",
        "observed_diagnostic": "_______________ test_a_bubble_waits_while_the_pointer_is_on_it ________________",
        "before": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ],
        "mutated": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "1483e9655b66da17d4f55ac414a65d9374e89f494dcd0654b11ac6abbe1cd9f7"
          }
        ],
        "after": [
          {
            "path": "chatmon/penguin.py",
            "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
          }
        ]
      },
      "reason": null
    }
  ],
  "checkpoint": {
    "scope_sha256": "0260c6f79183687e380fb3e14605a351d8d6f622a28b23ea18487cfe1f04a8c1",
    "inputs": [
      {
        "path": "chatmon/behavior.py",
        "sha256": "27b811fdf9cab85bcab9a6e24f639b5d446718d6a61e0b84e42ba5f82cdb7a4b"
      },
      {
        "path": "chatmon/clickthrough.py",
        "sha256": "3163bf87deb2d48820c6621f6608af1c9e114471ba4bf10d19f9c109bf216603"
      },
      {
        "path": "chatmon/layer.py",
        "sha256": "90deeb65c322cd2a9b867f0b48f64d4eb2f39382e9345eee6848735ed6455d9d"
      },
      {
        "path": "chatmon/penguin.py",
        "sha256": "81050433d0e60454ea54bcf01c8f057ce9019ce235fe96b89dd03f8eb97d36cf"
      },
      {
        "path": "chatmon/sprites.py",
        "sha256": "f84720ba58621131d8e82de3f20354c5126dce430e016497f1e1fcc6ee8fd846"
      },
      {
        "path": "chatmon/stagemenu.py",
        "sha256": "59ea9f2ab4bb18741b2f373e2e39affb8839470639b1249cc1e9420e88fcc85f"
      },
      {
        "path": "chatmon/xkb.py",
        "sha256": "4bb5d93133e05ae9239889aad0e86dcb9e45730a9b1833b301af0fe26b7d09d5"
      },
      {
        "path": "docs/delivery/ASSESSMENT.md",
        "sha256": "2977d61a84feb17c49dcef4ef887804a59dc4372fc9b3f57a9d2e0e587131cb5"
      },
      {
        "path": "docs/delivery/ROADMAP.md",
        "sha256": "c46dc262e53927389a2827db514cc78e9cfa7840b549562441cba2c234f9fa1a"
      },
      {
        "path": "pyproject.toml",
        "sha256": "207b2af2544392fa97665d64816729a78e6840c6f6c290a5682b14785b0cf297"
      },
      {
        "path": "tests/conftest.py",
        "sha256": "d7ab148510da9a898f43585921d8f7302655e9134372cf25618ad1fbace53a43"
      },
      {
        "path": "tests/drills/run.py",
        "sha256": "9f7e42e8abf1fdd9190fc9bb5e7576f8b60b5be0310cec38af5e0ac2d7573301"
      },
      {
        "path": "tests/test_behavior.py",
        "sha256": "1e1240c2f299ff68160cfb08ae0953fc4be20a546db175b6cb4968e137fd3322"
      },
      {
        "path": "tests/test_clickthrough.py",
        "sha256": "0386ad57af0750a3d098b44cf38b169f3a7e75be902baf1c1d0ba75d5ae4bf06"
      },
      {
        "path": "tests/test_overlay_stage.py",
        "sha256": "737c29ec32f16a48374bbab377aa53e46f54de5f2c2d550f6a0ea851c1a5a7c2"
      },
      {
        "path": "tests/test_sprites.py",
        "sha256": "62aeea9561822ef440c72b95e311971ee1f5f143cc1bccb1767581dc57ac4c5a"
      },
      {
        "path": "tests/test_stage_features.py",
        "sha256": "e646d90d8430c99cef17c7798c375fbdab66ea53eb45090bac93faf6a3a5ca1c"
      },
      {
        "path": "tests/test_stage_timer.py",
        "sha256": "d738635c9cae37f672fcbdf91858d06ac340771a3a8f3986a9f8e3a63c0e2a19"
      },
      {
        "path": "tests/test_stagemenu.py",
        "sha256": "b3bf900defe7320bc16d1e20d07d5bbdd2d0267854f7058d42cf18845aa24331"
      },
      {
        "path": "tests/test_wayland.py",
        "sha256": "067fcbe7f54d541a1c0265fc894901abf6b1b996574063ddbd2282f98765e07a"
      },
      {
        "path": "tests/test_xkb.py",
        "sha256": "c4cd00772fcf1545497c6a4e0c624ab4d005dfe190799c70e507a3a1ab8d9586"
      }
    ],
    "environment": {
      "platform": "windows",
      "tools": {
        "python": "3.14.10",
        "pyqt6": "6.11.0",
        "pytest": "9.2.0",
        "ruff": "0.17.4"
      }
    },
    "verified_tasks": [
      "T-M3-xkb",
      "T-M3-shape",
      "T-M3-sprites",
      "T-M3-behavior",
      "T-M3-timer",
      "T-M3-menu",
      "T-M3-stage-features",
      "T-M3-buffers",
      "T-M3-m2"
    ],
    "pending_operations": [
      {
        "id": "CI-linux-macos",
        "description": "Linux and macOS CI on wave1/m3: the Wayland overlay, xkb and stage tests on Linux (run here only in WSL), and the stage, sprite and menu tests on macOS (cocoa, not run here)",
        "next_action": "After the coordinator pushes the merged branch, read the Linux and macOS jobs and send any M3 failure back to M3"
      },
      {
        "id": "M0-power-saver-test",
        "description": "tests/test_app_smoke.py::test_in_power_saver_mode_the_stage_draws_less_often (M0's file) asserts the stage's removed fixed intervals and fails on wave1/m3 by design",
        "next_action": "M0 or the coordinator replaces its body with the code in the plan's Integration notes when merging wave1/m3"
      },
      {
        "id": "M3-14-on-wayland",
        "description": "The unhosted ask box (set_hosting(False)) and Qt's menus on a real Wayland compositor where Qt runs natively: the box's placement and the penguin's menu, which has no Qt window to belong to",
        "next_action": "M7 tries it on Hyprland or Sway when wiring the accessible ask-box setting, and keeps the penguin's menu on the stage there if Qt can't show it (Integration notes)"
      },
      {
        "id": "X11-shape-in-CI",
        "description": "tests/test_clickthrough.py::test_the_x_server_gets_the_shape_in_device_pixels skips in Linux CI, which has no X server; it passed here under WSLg's X server",
        "next_action": "M6A adds xvfb and runs the Linux job under xvfb-run -a (Integration notes)"
      }
    ],
    "next_action": "Coordinator merges wave1/m3 and settles the pending operations. M7 wires set_badge, badge_description, set_reduced_motion, set_hosting and follow_pointer_screen (Integration notes). For M3-04's deferred half (buffers sized to what is shown): prototype a content subsurface under a 1x1 viewported layer surface and try it on Hyprland, Sway and KDE before changing the overlay.",
    "source_revision": "a3447706f7636ef052ee91e74c98aa574d1bbd79"
  }
}
```
