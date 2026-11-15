# The Wayland overlay on KWin and Hyprland, before v0.10.0

2026-11-15, branch `wave5/compositors` from `main` at **65ed989** (PR #18 merged). This closes the gap
[OUTCOME.md](../../../OUTCOME.md) names: "Hyprland and KDE: the overlay and the unhosted ask box have only been
tried on sway". Every check of [tests/test_sway.py](../../../../../tests/test_sway.py) now also runs on a headless
KWin and a headless Hyprland ([tests/test_compositors.py](../../../../../tests/test_compositors.py), on
[tests/compositor_session.py](../../../../../tests/compositor_session.py)), in WSL Arch, with the real Orca.
No product file was changed; three product problems were found, each with a proposed fix below, checked but not
committed.

## Versions

| | |
|---|---|
| KWin | 6.8.2 (`kwin 6.8.2-2`, virtual backend), libkscreen 6.8.2, plasma-wayland-protocols 1.23.0 |
| Hyprland | 0.57.0 (commit 0aa6745), Aquamarine 0.15.1, hyprutils 0.14.3 (Lua config) |
| sway, for comparison | 1.12 (wlroots 0.20.2), grim 1.5.0 |
| Rendering | Mesa 26.2.6 llvmpipe (software), on WSL's vgem DRM device |
| Accessibility | Orca 51.1, at-spi2-core 2.62.1, python-gobject 3.58.1 |
| Chatmon's side | Python 3.14.9, PyQt6 6.11.0 / Qt 6.11.2 (`/var/tmp/plans-venv`, packaging/requirements-test.txt); the system's Qt 6.12.0 runs KWin |
| Host | WSL 2, Arch Linux, kernel 6.18.58.1-microsoft-standard-WSL2 |

All of it, and what was installed for this work, is in [versions.txt](versions.txt) ([versions.sh](versions.sh)).
Installed with pacman: `kwin` (and 69 dependencies) and `plasma-wayland-protocols`. kwin pulled in `karchive
6.31.0-2`, built for OpenSSL 4, which this system (OpenSSL 3.6.5) doesn't have yet; its OpenSSL 3 build `6.31.0-1`
came from the Arch archive instead of a full system upgrade on the shared WSL. Hyprland 0.57.0 was already there.

## How each runs headless

**KWin**: `kwin_wayland --virtual --width W --height H --output-count N --no-lockscreen --no-global-shortcuts`,
with Mesa's llvmpipe (`LIBGL_ALWAYS_SOFTWARE=1`), on a session bus of the test's own. The size is in device pixels;
the scale is set afterwards with `kscreen-doctor output.Virtual-0.scale.S`, as Plasma's display settings set it
(`--scale` multiplies the mode and leaves the output at scale 1). KWin logs "Failed to find a working output layer
configuration" each frame: its virtual output's buffers can't be allocated on vgem. It still composites what the
screenshot service captures, and still sends clients their frame callbacks; nothing below depends on that output.

**Hyprland**: Aquamarine has no headless-only mode. It needs a KMS device or a Wayland compositor to run in, for
the device its buffers come from; WSL's only DRM device is vgem, with no KMS
([logs/probe-hyprland-headless.log](logs/probe-hyprland-headless.log), first attempt: "Cannot open backend: no
allocator available", then `CBackend::create() failed!`). So:

- Hyprland runs in a headless KWin of its own (64x64, on a second, private session bus), through Aquamarine's
  Wayland backend. sway 1.12 can't be that host: Aquamarine 0.15.1 binds `xdg_wm_base` version 6, sway offers 5, a
  protocol error (the same log, third attempt: `invalid version for global xdg_wm_base (12): expected at most 5,
  got 6`).
- The test's output is one Aquamarine's headless backend makes, `hyprctl output create headless CHATMON-1`, set by
  a monitor rule (`hl.monitor`); the output the nesting makes, `WAYLAND-1`, is turned off.
- Mesa's software GBM allocates dumb buffers, which vgem's render node refuses (the same log, second attempt: `KMS:
  DRM_IOCTL_MODE_CREATE_DUMB failed: Permission denied`, every mode `REJECTED`). A small preload library, built by
  the test bed with `cc`, has Hyprland open vgem's primary node (`/dev/dri/card0`) where it asks for the render
  node. Only Hyprland gets it, and only where the render node is vgem's.
- `LIBSEAT_BACKEND=noop`, and `HYPRLAND_NO_SD_VARS=1 HYPRLAND_NO_SD_TARGET=1 HYPRLAND_NO_SD_NOTIFY=1`: nothing goes
  to the desktop's systemd user manager (the journal shows nothing from the runs).

Config: Hyprland's defaults (tiling, gaps, borders, `follow_mouse = 1`) except no animations, wallpaper, logo,
Xwayland, scale notice or not-responding dialog, and a black background.

## What stands in for sway's tools

| sway's test bed uses | KWin | Hyprland |
|---|---|---|
| grim (wlr-screencopy) | KWin's screenshot service, `org.kde.KWin.ScreenShot2.CaptureScreen`, its pixels read from a pipe by the system's Python (Gio) | grim, as on sway (Hyprland's cursor shows in its screenshots, as sway 1.9's does) |
| wlr virtual pointer and keyboard | `org_kde_kwin_fake_input` v6 (`KWinInput`: absolute motion, buttons, evdev keys), as KDE Connect and remote desktops drive KWin | sway_session's `Input`, unchanged |
| `swaymsg -t get_tree` | a KWin script loaded through `org.kde.kwin.Scripting`, printing `workspace.windowList()` and `workspace.screens` as JSON into KWin's log | `hyprctl -j clients`, `hyprctl -j monitors` |
| `swaymsg create_output`, `output X disable` | `--output-count 2`, the second turned off at the start and on in the test, with `kscreen-doctor output.Virtual-1.enable` / `.disable` | `hyprctl output create headless CHATMON-2` and `hl.monitor({ output = ..., disabled = true })` through `hyprctl eval` |

KWin lists the overlay's layer surface as a "normal" window to its scripts (its namespace is none of KWin's own);
the test bed tells it apart by what a layer surface can't be (moved, resized, minimized, in the task switcher).

## Results

KWin and Hyprland: [logs/kwin-hyprland.log](logs/kwin-hyprland.log), `CHATMON_COMPOSITORS=1` (a missing piece fails),
**34 passed, 5 xfailed** (the three problems below), 6 min 40 s. The same checks on sway, to compare:
[logs/sway-parametrized.log](logs/sway-parametrized.log), 19 passed. sway's own tests/test_sway.py, whole, with the
real Orca, and tests/test_wayland.py, as CI's sway job runs them: [logs/sway-test_sway.log](logs/sway-test_sway.log),
**52 passed**, none skipped. Screenshots of every check, by compositor: [shots/](shots/).

| Check (tests/test_compositors.py; test_sway.py's of the same name) | sway 1.12 | KWin 6.8.2 | Hyprland 0.57.0 |
|---|---|---|---|
| The overlay is a layer surface the compositor draws, the size of the output (1280x800), with its content subsurface, not a window; the chatmon drawn and nothing else | pass | pass | pass |
| Clicks land on the chatmon (the ask box opens) and pass through its see-through parts and everywhere else to the window under it | pass | pass | pass |
| The keyboard is the overlay's only while the ask box is open: typing reaches the box, and after Esc the window again | pass | **fail**: after Esc the keyboard stays on the overlay; 'c' typed is lost (problem 1) | pass |
| The penguin's menu opens on the overlay, works from the keyboard (Down, Return: the ask box) and the pointer; a click elsewhere closes it and goes no further | pass | pass | pass |
| The clipboard both ways: another app's copy pasted in the box, the box's copy pasted by another app, and by Chatmon's own window | pass | **fail**: the last: Chatmon's window never gets the keyboard back (problem 1) and reads nothing; with that fixed, it reads nothing after a 2 s freeze (problem 3) | pass |
| Under a full-screen window (the top layer), above it while the ask box is open, under it again after | pass | **fail**: the last: the chatmon stays over the full-screen window (problem 1) | pass |
| When its screen is unplugged, it comes back on the one left, a layer surface configured to it, drawn | pass | pass (the output left moves to 0,0; see observations) | pass |
| Buffers the size of what's shown at 3840x2160 scale 2 and 2560x1440 scale 1.5: a one-pixel backdrop, at most two content buffers of a tenth of the output or less, on whole device pixels, drawn | pass | pass | pass (at 1.6: Hyprland's own choice for 1.5) |
| Dragged across the screen in 110 px steps, drawn once where it is, no trail | pass | pass | **fail**: the chatmon doesn't follow: Hyprland releases the button on the first step (problem 2) |
| With a screen reader, the ask box is a window: floating, all on screen, focused; typing reaches it; a bubble then stays off it; it's drawn | pass (centred) | pass (centred) | pass (centred) |
| With the box a window, the penguin's menu (on the overlay) takes the keys and gives them back to the box | pass | **fail**: the keyboard doesn't go back to the box (problem 1) | pass |
| With the box a window, its own context menu is Qt's popup beside it | pass | pass | pass |
| AT-SPI, as a screen reader reads it: the box window, its field (name, hint, text, focus), its buttons, its check box, the conversation as words | pass | pass | pass |
| Only as a window of its own is the box an active window to AT-SPI (`window:activate`), setting auto and off; its field focused either way | pass | pass | pass |
| The conversation's change reaches AT-SPI listeners (`object:text-changed:insert`) | pass | pass | pass |
| Orca 51: a bubble said through its remote controller and spoken; the box as a window announced, then its field and hint; typing echoed | pass | pass | pass |
| Orca 51: the box drawn on the overlay is never announced as a window | pass (no keys echoed) | pass (keys echoed: see observations) | pass (no keys echoed) |
| The test bed's own: KWin's fake-input opcodes match plasma-wayland-protocols' fake-input.xml | n/a | pass | n/a |

Nothing in either compositor's column was "not checkable": every check of test_sway.py ran on both, with each
compositor's own stand-ins for grim, the virtual pointer and the window tree. What the runs can't say about a real
desktop is under "What couldn't be checked".

## Product problems found

Each is a strict xfail in tests/test_compositors.py, on its compositor only, naming this section: the check passes
the day the product is fixed, and then fails until the mark is taken away. The three fixes together are in
[proposed-fixes.diff](proposed-fixes.diff) (86 lines, `chatmon/layer.py` and `chatmon/penguin.py`), **not
committed**. With them applied to the working tree, the five affected checks pass on both compositors
([logs/proposed-fixes-applied.log](logs/proposed-fixes-applied.log), `--runxfail`: 10 passed), and sway's whole
test_sway.py, test_wayland.py and the stage's tests still pass on sway
([logs/proposed-fixes-applied-sway-and-stage.log](logs/proposed-fixes-applied-sway-and-stage.log): 106 passed).
Those two logs' header says HEAD 65ed989: the fixes were uncommitted changes on top of it, taken away after.

### 1. KWin: after the ask box closes, the keyboard goes nowhere

**What happens.** You type in a window, click the chatmon, the ask box opens and has the keyboard. Esc closes it.
On sway and Hyprland the keyboard goes back to the window. On KWin 6.8.2 it stays on the overlay: KWin keeps the
overlay's layer surface as its active window, sends it no `wl_keyboard.leave`, and activates no other window. What
you type next goes to the overlay, which drops it (the box is closed). Three more symptoms follow:

- the penguin's menu opened over the unhosted box (with a screen reader) doesn't give the keyboard back to the box;
- a full-screen window (a video, a game, slides), no longer KWin's active window, goes under the top layer, so
  the chatmon stays drawn over it after the box closes (screenshots
  [under](shots/kwin/it_gives_way_to_a_full_screen_window_and_comes_above_it_for_the_ask_box-under.png),
  [above](shots/kwin/it_gives_way_to_a_full_screen_window_and_comes_above_it_for_the_ask_box-above.png), [under-again](shots/kwin/it_gives_way_to_a_full_screen_window_and_comes_above_it_for_the_ask_box-under-again.png));
- it's half of problem 3.

It doesn't matter whether the overlay had the keyboard `on_demand` (as KWin lets it keep it) or `exclusive` (as
on sway). Unmapping the layer surface, or making it again, makes KWin give the keyboard back to the window
([logs/probe-kwin-keyboard-*.log](logs/): `as-is`, `exclusive`, `remap`, `recreate`).

**Cause in the code.** `LayerSurface.focus_keyboard(False)` → `_set_keyboard_mode(KEYBOARD_NONE)`
(chatmon/layer.py) sets `keyboard_interactivity` to none and commits, and counts on the compositor to move the
keyboard away, as layer-shell says it should ("the compositor should never assign it the keyboard focus"). KWin
6.8.2 doesn't. `_kb_focus` stays True, `_keyboard_event` keeps passing keys to `Stage.key`.

**Proposed fix** (`chatmon/layer.py`): when the overlay lets the keyboard go and still has it 0.3 s later
(`KEPT_GRACE`), `_keyboard_kept` makes the layer surface again, as a change of screen already does
(`_destroy_surface()` + `_create_surface()`), and tells the stage the keyboard has gone. The chatmon is back a frame
later. Nothing changes where the compositor sends the `leave` (sway, Hyprland).

### 2. Hyprland: a quick drag drops the chatmon, or opens the ask box

**What happens.** Press on the chatmon and move. Wayland keeps a pressed button with the surface it went down on
(an implicit grab) until it's let go, wherever the pointer goes. Hyprland 0.57 doesn't, for the overlay: as soon
as the pointer is outside the overlay's input region (the chatmon's own pixels), Hyprland sends the overlay a
button release, then a `leave`, while the button is still down. A drag that gets ahead of the chatmon by a frame
drops it where it is; a press that leaves the chatmon before the 6 px a drag needs is taken as a click, and opens
the ask box. In [logs/probe-drag-hyprland-*.log](logs/), pressing then moving 330 px left in steps 1/60 s apart:

- 110 px steps: release and `leave` on the first step, before any motion reached the overlay; a click: the ask box
  opens and the chatmon stays where it was ([probe-drag-hyprland-110.log](logs/probe-drag-hyprland-110.log));
- 40 px steps: the drag starts, and is released on the second step; the chatmon drops 40 px along
  ([probe-drag-hyprland-40.log](logs/probe-drag-hyprland-40.log));
- 20 px and 5 px steps: it follows to the end in these runs (an earlier trial of 20 px steps dropped it on the third).

On sway and KWin it follows at every step size ([probe-drag-sway-*.log](logs/), [probe-drag-kwin-*.log](logs/)):
the overlay gets motion events wherever the pointer goes, until the button goes up.

**Cause in the code.** `Stage._tick` (chatmon/penguin.py) rebuilds the input region each frame from the sprite's
pixels, the bubble, the z's and the hosted box; only an open menu makes it the whole stage. During a drag it is
the chatmon's pixels where the chatmon was last drawn. `LayerSurface._pointer_event` turns Hyprland's release into
`Stage.release`: a drop, or a click.

**Proposed fix** (`chatmon/penguin.py`): while a button is held on the overlay (`self._press is not None`), the
input region is the whole stage, as for an open menu. The press itself still lands only on the chatmon's pixels
(the region changes on the next tick, a frame after the press), and the region is the chatmon's again on release.

### 3. KWin: what the ask box copies can't be pasted in Chatmon's own windows

**What happens.** Copy in the ask box on the overlay (Ctrl+C). Other apps paste it (wl-paste: "mine"). Chatmon's
own windows (Settings, Chats, the desk window here) read Qt's clipboard: on KWin it is empty
([logs/probe-kwin-qt-clipboard.log](logs/probe-kwin-qt-clipboard.log); problem 1 keeps the window from ever
having the keyboard there). With fix 1 applied, the window gets the keyboard back, and its first read of the
clipboard freezes Chatmon for 2.01 s and returns "" ([logs/probe-kwin-qt-clipboard-with-fix-1-only.log](logs/probe-kwin-qt-clipboard-with-fix-1-only.log)).
With fixes 1 and 3 it reads "mine" at once ([logs/probe-kwin-qt-clipboard-with-fixes-1-3.log](logs/probe-kwin-qt-clipboard-with-fixes-1-3.log)).
Those two runs had the fixes as uncommitted changes, applied for the run and taken away after.

**Cause in the code.** `LayerSurface.copy` (chatmon/layer.py) puts the text on Qt's clipboard too, so Chatmon's
windows paste from Qt's memory rather than from the overlay's own connection, which is serviced on the same thread
(the freeze its docstring describes). KWin, by what it does, takes a selection only from the client with the
keyboard: Qt's copy, made while the overlay's connection has it, never becomes the clipboard; made again once a Qt
window has the keyboard (fix 3), it does. So when a Qt window gets the keyboard, KWin offers it the overlay's
selection, and Qt reads it through a pipe the overlay can't fill while Qt waits on the same thread.

**Proposed fix** (`chatmon/layer.py`): remember what was copied; when one of Qt's windows gets the keyboard
(`QGuiApplication.focusWindowChanged`) and the overlay's selection is still the clipboard, put it on Qt's clipboard
again. KWin takes it then. Needs fix 1 on KWin, for a window to get the keyboard at all.

### The diff

```diff
diff --git a/chatmon/layer.py b/chatmon/layer.py
index d41a3fa..2b8c4f1 100644
--- a/chatmon/layer.py
+++ b/chatmon/layer.py
@@ -122,6 +122,7 @@ IDLE_AFTER_MS = 300_000
 ANCHOR_ALL = 1 | 2 | 4 | 8  # top, bottom, left, right: the whole output
 KEYBOARD_NONE, KEYBOARD_EXCLUSIVE, KEYBOARD_ON_DEMAND = 0, 1, 2  # on_demand: layer-shell version 4
 HANDOVER_GRACE = 0.5  # s: the keyboard gone this soon after a handover to on_demand was the compositor's doing
+KEPT_GRACE = 0.3  # s: the keyboard still here this long after the overlay let it go: the compositor kept it (KWin)
 KEYMAP_XKB_V1 = 1
 SHM_ARGB8888 = 0  # premultiplied, byte order B G R A: QImage's ARGB32_Premultiplied on little-endian
 CAP_POINTER, CAP_KEYBOARD = 1, 2
@@ -635,6 +636,10 @@ class LayerSurface(QObject):
             "primary": Selection(self, PRIMARY),
         }
         self._text_state: TextState | None = None  # the focused text field, as the stage last said
+        self._qt_clipboard: str | None = None  # copied on the overlay, for Qt's clipboard once a Qt window has the keyboard
+        app = QGuiApplication.instance()
+        if isinstance(app, QGuiApplication):
+            app.focusWindowChanged.connect(self._qt_window_focused)
         self._seat_versions: dict[int, int] = {}
         self._registry = conn.new_id(self._registry_event)
         conn.request(DISPLAY_ID, 1, "n", self._registry)  # wl_display.get_registry
@@ -804,6 +809,15 @@ class LayerSurface(QObject):
         board = QGuiApplication.clipboard() if which == "clipboard" and text else None
         if board is not None:
             board.setText(text)
+            # KWin takes a selection only from the client with the keyboard: the overlay's connection has it now, so
+            # KWin refuses Qt's, and Chatmon's windows would read the overlay's instead (the freeze above). Qt's
+            # again when one of them has the keyboard.
+            self._qt_clipboard = text
+
+    def _qt_window_focused(self, window) -> None:
+        text, self._qt_clipboard = self._qt_clipboard, None
+        if window is not None and text is not None and self.selections["clipboard"].source is not None:  # still ours
+            QGuiApplication.clipboard().setText(text)
 
     def set_text_input(self, state: TextState | None) -> None:
         """The text field that has the focus on the stage (None: none does),
@@ -1146,6 +1160,22 @@ class LayerSurface(QObject):
         self.conn.request(self._layer, LAYER_SURFACE_SET_KEYBOARD_INTERACTIVITY, "u", mode)
         self.conn.request(self._surface, SURFACE_COMMIT)
         self._flush()
+        if mode == KEYBOARD_NONE and self._kb_focus:
+            QTimer.singleShot(round(KEPT_GRACE * 1000), self._keyboard_kept)
+
+    def _keyboard_kept(self) -> None:
+        """KWin (6.8) leaves the keyboard on a layer surface that has let it go, and gives it to no window: what you
+        type next goes nowhere, and a full-screen window, no longer the active one, stays under the chatmon. A
+        layer surface unmapped loses the keyboard, and KWin gives it back to the window it came from: so the
+        surface is made again, as for a new screen (the chatmon is back a frame later)."""
+        if self._closing or self._kb_wanted or not self._kb_focus or self._surface is None:
+            return
+        logger.debug("the compositor kept the keyboard on the overlay after it was let go; making the surface again")
+        self._kb_focus = False
+        self._stop_repeat()
+        self.stage.keyboard_focus(False)
+        self._destroy_surface()
+        self._create_surface()
 
 
     # -- away from the desk (ext-idle-notify-v1)
diff --git a/chatmon/penguin.py b/chatmon/penguin.py
index 1df5d8b..7bd5cf4 100644
--- a/chatmon/penguin.py
+++ b/chatmon/penguin.py
@@ -1063,7 +1063,7 @@ class Stage(QObject):
             (bubble_rect.x(), bubble_rect.y(), bubble_rect.width(), bubble_rect.height()) if bubble_rect is not None else None,
             (zs.x(), zs.y(), zs.width(), zs.height()) if zs.isValid() else None,
             hosted_rects,
-            (self._geo.width(), self._geo.height()) if self.menu.is_open() else None,
+            (self._geo.width(), self._geo.height()) if self.menu.is_open() or self._press is not None else None,
         )
         if parts != self._input_parts:
             self._take_input(parts)
@@ -1164,7 +1164,9 @@ class Stage(QObject):
 
     def _take_input(self, parts: tuple) -> None:
         """Take clicks where `parts` (plain numbers) says: the whole stage while the menu is open, as any popup menu
-        does (a click anywhere else closes it), else the sprite, the bubble, the z's and the hosted scene."""
+        does (a click anywhere else closes it), and while a button is held on the chatmon or its bubble (a drag:
+        Hyprland ends a press as soon as the pointer leaves the input region, though Wayland keeps it with the
+        surface it began on), else the sprite, the bubble, the z's and the hosted scene."""
         self._input_parts = parts
         rects, (px, py), bubble_t, zs_t, hosted_t, menu = parts
         if menu is not None:
```

## What couldn't be checked, and why

- **A real KDE Plasma or Hyprland desktop.** These are the compositors alone, headless, in WSL, with no GPU (Mesa's
  llvmpipe), no real input devices and no real monitors. Not checked: plasmashell's panels and their exclusive
  zones under the overlay, KDE's own window rules and focus-stealing settings beyond KWin's defaults, Hyprland
  under a user's config, hardware cursors, real hotplug, and either compositor on DRM/KMS. A person on each
  desktop should still try the chatmon, the ask box, a drag and a full-screen video (OUTCOME.md's "for a person").
- **Hyprland on its own.** It ran inside a headless KWin (the only way Aquamarine runs without KMS), on a headless
  output of its own, with vgem's primary node for its render node. The overlay talks to Hyprland alone; KWin only
  hosts Hyprland's buffers. Nothing seen depends on the nesting, but it isn't Hyprland on a desktop's GPU.
- **Pointer input as a mouse gives it.** KWin is driven through its fake-input protocol, Hyprland and sway
  through the wlr virtual pointer and keyboard: events through each compositor's own seat, not libinput devices.
- **Hearing Orca.** Orca 51 runs and its debug log has every `SPEECH OUTPUT`; no audio was listened to.
- **What sway's tests don't check either**: input methods (text-input-v3), files dropped on the overlay, idle and
  lock notices (ext-idle-notify, Hyprland's lock notify), the GlobalShortcuts portal's hotkey.
- **sway in CI** is unchanged: its job runs tests/test_sway.py and tests/test_wayland.py only, and
  tests/test_compositors.py skips wherever KWin or Hyprland isn't installed (CI's other Linux jobs), with the reason.

## Observations (not problems)

From [observed.jsonl](observed.jsonl), what each compositor did where the checks allow more than one way:

| | sway 1.12 | KWin 6.8.2 | Hyprland 0.57.0 |
|---|---|---|---|
| layer-shell version Chatmon binds (min of the compositor's and 4) | 4 | 4 (KWin offers 5) | 4 (offers 5) |
| Keyboard while the hosted box is open | exclusive (sway takes it back from on_demand) | on_demand, kept | on_demand, kept |
| The unhosted ask box (a screen reader on) | floated, centred, at 450,311 | placed centred (KWin's default placement), at 450,311 | floated, centred, at 450,312 |
| A bubble while the unhosted box is open | over the chatmon's head, clear of the box | the same | the same |
| The second output, once the first is unplugged | moved to 0,0 (sway's own layout; its new output is 1920x1080, sway's default); the chatmon comes back at x 1272 | moved to 0,0; the chatmon comes back at x 1172 | stays at x 1280 (its monitor rule's place); the chatmon where it was, x 542 |
| 2560x1440 at scale 1.5 | 1.5 (1706x960) | 1.5 (1707x960) | Hyprland makes it **1.6** (1600x900): 1.5 doesn't divide 2560 evenly; buffers follow 1.6 |
| Orca, the box hosted on the overlay (setting off) | no window announced, no keys echoed | no window announced; **keys echoed**: KWin tells Orca of every key (it registers `org.freedesktop.a11y.Manager`, the keyboard monitor) | no window announced, no keys echoed |
| Orca, the unhosted box | window, then field, then keys | the same | the same. In the first run, keys typed 1 s after the box opened were echoed before Orca said the field ([first-run log](logs/first-run-before-test-bed-fixes.log)): the check now waits for Orca to say where you are, as a user would (0.2 s more, on both, in the evidence run) |

The overlay's buffers at 4K and scale 2 are for 1920x1080 logical and a tenth or less of the output's pixels on
all three, as M3-04 has it.

**A remaining output moved to 0,0 (sway and KWin), more closely.** The stage moves to the output left while Qt
still has it at x 1280 (`Stage._screen_removed`), and keeps that origin until a later tick finds the chatmon's x on
the moved screen (`Stage._tick` asks `screenAt(behavior.x)`; nothing listens to a screen's geometry changing). On
KWin, with the chatmon still, that was about a second: the stage's origin still 1280 and the chatmon at x -108 in
its own coordinates 1 s after ([logs/probe-kwin-output-relayout.log](logs/probe-kwin-output-relayout.log)), then
right; within 5 s in the check, on both. Not counted as a problem here (it puts itself right), but a place to look
if a person sees the chatmon vanish for a moment when a monitor is unplugged: waking the stage on
`QScreen.geometryChanged` would close it.

## The commands

In WSL (`wsl.exe -d archlinux -- ...`), from the worktree's `/mnt/c/...` path, every run through [run.sh](run.sh):
nice 10, the venv first on PATH, `QT_QPA_PLATFORM=offscreen`, a `CHATMON_INSTANCE` of the run's own, and a header
with the versions and the worktree's HEAD. Every compositor, bus, AT-SPI registry and Orca is started by the test
bed in a runtime folder of the test's own and stopped by it (`Session.close`); nothing runs on a display of the
desktop's.

```sh
R=docs/delivery/reports/release/compositors
# KWin and Hyprland; a missing piece fails rather than skips
bash $R/run.sh $R/logs/kwin-hyprland.log env CHATMON_COMPOSITORS=1 CHATMON_COMPOSITORS_NOTES=... CHATMON_COMPOSITORS_SHOTS=... \
  python -m pytest -p no:cacheprovider -v -rxXs --tb=short tests/test_compositors.py --basetemp=/var/tmp/compositors-tmp/final
# the same checks on sway, to compare (sway only: -k sway)
bash $R/run.sh $R/logs/sway-parametrized.log env CHATMON_COMPOSITORS=1 CHATMON_COMPOSITORS_SWAY=1 \
  python -m pytest -p no:cacheprovider -v -rxXs --tb=short tests/test_compositors.py -k sway --basetemp=/var/tmp/compositors-tmp/sway
# sway's own checks, whole, as CI's sway job runs them (and with Orca, which CI hasn't)
bash $R/run.sh $R/logs/sway-test_sway.log env CHATMON_SWAY=1 \
  python -m pytest -p no:cacheprovider -v -rxXs tests/test_sway.py tests/test_wayland.py --basetemp=/var/tmp/compositors-tmp/sway-own
# the probes behind the problems
bash $R/probes.sh
# the fixes, applied to the working tree for the run only (git apply $R/proposed-fixes.diff; git checkout -- chatmon/ after)
bash $R/run.sh $R/logs/proposed-fixes-applied.log python -m pytest -p no:cacheprovider -v --tb=short --runxfail \
  tests/test_compositors.py::<the five checks> --basetemp=/var/tmp/compositors-tmp/fixes
bash $R/run.sh $R/logs/proposed-fixes-applied-sway-and-stage.log env CHATMON_SWAY=1 python -m pytest -p no:cacheprovider -q \
  tests/test_sway.py tests/test_wayland.py tests/test_overlay_stage.py tests/test_stage_features.py tests/test_stage_screens.py \
  tests/test_stage_timer.py tests/test_stagemenu.py --basetemp=/var/tmp/compositors-tmp/fixes-sway
bash $R/run.sh $R/logs/probe-kwin-qt-clipboard-with-fixes-1-3.log python $R/probes/kwin_qt_clipboard.py /var/tmp/compositors-probes/clip-fixes
# ... and fix 3's lines taken back out of chatmon/layer.py, for fix 1 alone
bash $R/run.sh $R/logs/probe-kwin-qt-clipboard-with-fix-1-only.log python $R/probes/kwin_qt_clipboard.py /var/tmp/compositors-probes/clip-fix1
# the evidence into this folder; the versions
bash $R/collect.sh /var/tmp/compositors-evidence /var/tmp/compositors-evidence-sway
bash $R/versions.sh
```

On Windows, with `C:\Users\Randy\Coding\chatmon\.venv`: `python -m ruff check .` (all checks passed) and `python -m
mypy --platform linux chatmon tests/compositor_session.py tests/test_compositors.py`: no issues in the new files
(`--follow-imports=silent`: "Success: no issues found in 2 source files"); followed into the unchanged
tests/sway_session.py it reports that file's own 4 errors, the same as `mypy --platform linux chatmon
tests/sway_session.py` on `main` ([logs/lint.log](logs/lint.log)).

## Files

| | |
|---|---|
| [tests/compositor_session.py](../../../../../tests/compositor_session.py) | KWin and Hyprland sessions on sway_session's (`unavailable`, `start`, `devices`), KWin's fake-input `KWinInput`, sway's for comparison |
| [tests/test_compositors.py](../../../../../tests/test_compositors.py) | test_sway.py's checks, parametrized over KWin and Hyprland (and sway with `CHATMON_COMPOSITORS_SWAY=1`), and a check of the fake-input opcodes against plasma-wayland-protocols' XML |
| [logs/](logs/) | every run's log; `first-run-before-test-bed-fixes.log` is the first full run, before the test bed knew KWin's layer windows, scale and output relayout and Hyprland's cursor (its failures there are the test bed's, but for the problems above) |
| [shots/](shots/) | screenshots each compositor took during the checks, by compositor and check |
| [observed.jsonl](observed.jsonl) | what each compositor did where the checks allow more than one way |
| [probes/](probes/), [probes.sh](probes.sh) | the scripts behind the problems' evidence |
| [collect.sh](collect.sh) | copies a run's notes and screenshots here |
| [proposed-fixes.diff](proposed-fixes.diff) | the three fixes, not committed |
| [versions.txt](versions.txt), [versions.sh](versions.sh), [run.sh](run.sh) | versions, and how every run was made |
