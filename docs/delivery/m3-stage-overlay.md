# M3: the stage, sprites and the overlay

Milestone M3 of the [roadmap](ROADMAP.md): items M3-01 to M3-15 of the [assessment](ASSESSMENT.md). Branch
`wave1/m3`, worktree `chatmon-wt/m3`, from `improve/assessment-fixes` at `5346385`.

## Rationale

The stage (`penguin.py`) draws the chatmon, its bubbles, its overlay menus and the hosted ask box on one
see-through surface. Most of M3 is in that one loop and the two things it draws on the overlay (`stagemenu.py`,
`layer.py`), plus the frames it draws (`sprites.py`) and what decides them (`behavior.py`).

**One owner per change path.** This milestone owns every file it changes (ROADMAP "File ownership in wave 1"). The
ask box (`bubble.py`) is M2's: the stage uses only what it already used (`anim_key`, `paint_art`, `input_rects`,
`wants_keyboard`, `paste_overlay`, `entry`, `stage_draws_art`), and reads `SpeechBubble._expires` only through
`getattr`, with the one-second floor as the fallback (see Integration notes).

**Reuse decisions.**

- The stage's own drawing key (what looks different, part by part) stays the way it decides what to redraw. The
  idle timer (M3-01) adds when the next change is due: `Behavior.next_change(now)` (pure, no Qt) for the creature,
  the bubble's fade, animation and expiry, the sleeping z's, the menu's pending submenu, and a one-second floor
  for whatever changes without saying so (a screen's geometry, a setting the app writes straight into the
  behaviour).
- Wake-ups come from what already exists: the surface's input calls into the stage, `Behavior` (which now says
  when the app changes it), the hosted scene's `changed` signal and its proxy's `visibleChanged`.
- `StageMenu` stays a plain object without a QObject or timer of its own; its submenu delay and scroll repeat are
  due times the stage's timer serves (`tick`, `next_change`), so the menu stays testable without an event loop.
- The X input shape (M3-10) reuses `clickthrough._key`; scaling is a pure function shared with its X11 test.
- The Latin fallback (M3-09) follows Qt's own `QXkbCommon::lookupLatinKeysym`: the first other layout whose
  symbol at the key's level is Latin-1, unless a key of an earlier layout already gives that symbol.

**New code.** No new module. New responsibilities live in their owners: `Behavior.next_change` and
`set_reduced_motion`; `Stage.set_badge`, `set_reduced_motion`, `set_hosting`, `follow_pointer_screen`;
`StageMenu.key`; `sprites` keeps the previous scale's frames in a two-entry cache; `clickthrough.device_rects`.

**Non-goals.** Wiring the new stage APIs into `app.py` and `settingswin.py` (M7). Bubble and ask-box internals
(M2). Translation of the few new strings (M8).

**M3-04, the part that is deferred.** A layer surface anchored to the whole output must be given a buffer the
size of the output; the protocol has no way to give it a smaller one at an offset. Buffers sized to what is shown
need either a layer surface that moves with the chatmon (the compositor then moves it a frame late, the lag and
trail the one-surface design exists to avoid) or a content subsurface positioned under a 1x1 viewported layer
surface, which changes where pointer, drag-and-drop and text-input events land. That has to be tried on real
compositors (Hyprland, Sway, KDE), which this worker can't run; the pretend compositor in `tests/test_wayland.py`
can't show how a compositor treats a synced subsurface under a layer surface. M3 delivers the part that is safe
everywhere: at most two buffers, and the second one dropped when the stage goes idle, so a quiet stage holds one.
The subsurface design is in the checkpoint as the next safe action.

**Verification environments.** Windows 11 (the gates). Linux code runs in WSL (Arch, Python 3.14.9, PyQt6
6.12.1, libxkbcommon 1.13, Xvfb): `tests/test_wayland.py`, `tests/test_xkb.py`, the X11 shape test. CI on Linux
and macOS stays the authority for those platforms and is a pending operation in the checkpoint.

## Integration notes

Written as delivered; the closing checkpoint repeats any change.

## Changelog notes

Written as delivered.

## README notes

Written as delivered.

```quality-ledger
{
  "schema_version": 1,
  "work": {
    "id": "M3",
    "title": "The stage, sprites and the overlay",
    "scope_revision": 1,
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
        }
      ],
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
          "path": "tests/test_anim_strips.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
          "path": "tests/test_stage_timer.py",
          "action": "modify"
        },
        {
          "path": "tests/test_overlay_stage.py",
          "action": "modify"
        }
      ],
      "status": "planned",
      "evidence": [],
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
      "status": "planned",
      "evidence": [],
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
      "status": "pass",
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
      "reason": null
    }
  ],
  "checkpoint": null
}
```
