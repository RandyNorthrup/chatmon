# M3 follow-up (wave4/wayland): pause checkpoint, 2026-11-14

Paused at the owner's request (resumed 2026-11-15 00:20; the plan's own checkpoint supersedes this note). HEAD
before the WIP commit: `fb19cb9` (branch `wave4/wayland`, worktree `chatmon-wt/wayland`). The WIP commit holds everything below; nothing is pushed.

## What's in the WIP commit

- `tests/sway_session.py` (new): the real-compositor test bed. A private session bus, a headless sway
  (`WLR_BACKENDS=headless`, pixman, no input devices, its own `WAYLAND_DISPLAY` by full path), optional AT-SPI
  (activated through the bus) and Orca (`--debug-file`); a virtual pointer and keyboard over chatmon's own
  `wayland.Connection`; grim screenshots; `Probe`, a whole Chatmon (`app_harness.make_companion`) on that sway in
  its own process, driven with Python over stdin/stdout; `atspi_tree`/`AtspiEvents` read through libatspi in the
  system's Python, as a screen reader does.
- `tests/test_sway.py` (new): 19 tests (overlay maps, input region, keyboard only while the box is open, menus,
  clipboard both ways, full-screen windows, a screen unplugged, buffers at 4K/2x and 1.5x, drag with no trail,
  the unhosted box floated/centred/focused, the penguin's menu with the box a window, the box's Qt popups, AT-SPI
  tree and events, Orca speaking a bubble and echoing typing in the window but not in the hosted box).
- `chatmon/layer.py`:
  - M3-04: what's drawn is on a synchronized subsurface the size of what's shown (plus a 32 px margin, on whole
    device pixels), over a layer surface holding one stretched see-through pixel; a move sends position and pixels
    in one parent commit and waits for a free buffer; at most 2 content buffers; full-output fallback without
    `wl_subcompositor` + `wp_viewporter`.
  - Found on sway 1.12: an `exclusive` -> `on_demand` handover loses the keyboard at once (sway's
    `arrange_layers` unfocuses any non-exclusive layer). The overlay now takes it back and keeps grabs exclusive.
  - Found on sway: after the overlay copied, Chatmon's own Qt windows froze 2 s and pasted nothing (Qt reads the
    clipboard through the compositor, which asks the overlay's connection on the blocked thread). Copies now go
    on Qt's clipboard too.
- `chatmon/penguin.py`: `Stage._extent` / `set_extent` for the subsurface; the penguin's menu takes the keyboard
  even with the box unhosted (it didn't: keys went to the box, Esc closed the box); a bubble no longer keeps
  "clear" of an unhosted box on Wayland (its geometry there is fiction: the bubble was drawn over the real box).
- `tests/test_wayland.py`: pretend-compositor tests for the subsurface, the move waiting for a buffer, the grid,
  the handover drop, a later leave. `tests/test_overlay_stage.py`: menu keyboard and bubble placement tests.
- `.github/workflows/ci.yml`: new job `sway` (ubuntu-24.04, apt sway/grim/wl-clipboard/dbus/at-spi2-core/
  python3-gi/gir1.2-atspi-2.0 and Qt's Wayland libs, hash-locked `requirements-test.txt`, `CHATMON_SWAY=1`).
- `docs/delivery/reports/m3/memory.py`: the before/after measurement script.

## Verified so far (WSL, Arch, sway 1.12, Python 3.14.9, PyQt6 6.11 from requirements-test.txt)

- `tests/test_wayland.py`: 32 passed. `tests/test_overlay_stage.py`: 25 passed.
- `tests/test_sway.py`: every test passed in runs during the work (17 in one run, then the 5 rewritten AT-SPI/
  Orca tests in a second); not yet one clean full run after the last edits.
- Memory at 3840x2160, scale 2 (`/var/tmp/mem-*.json` in WSL, from the script before its last edit): before, two
  3840x2160 buffers, 63.3 MB resident in Chatmon at every moment; after, 0.6 to 7.4 MB (two buffers of
  384x384 to 896x1088). With a window under the overlay, sway's resident shared memory 94-157 MB before and
  94-101 MB after.

## Not done yet

- Windows gates (full pytest, ruff, mypy linux/win32/darwin, extract_strings) not run on these changes.
- The full Linux suite in WSL; one clean full `tests/test_sway.py` run; the memory script re-run (it now stops
  the walking and waits for the greeting) with its JSON saved under `reports/m3/`.
- Red drills (Windows and Linux specs) for the new behaviour; the plan (`m3-stage-overlay.md`) reopened as scope
  revision 3 with requirements/acceptance/tasks/evidence, readiness review, closure validation.
- Separate commits in logical steps (the WIP commit will be split or followed by proper commits).

## Next safe step

Re-run `tests/test_sway.py` and `tests/test_wayland.py` in WSL with `/var/tmp/wayland-venv`, then the Windows
gates, then the plan update and drills.

## Environment left behind (WSL `archlinux`)

- Packages installed with pacman: `sway` (1.12, with `wlroots0.20`), `python-gobject`, `orca` (51.1, with
  `speech-dispatcher`; `gst-plugins-bad-libs` upgraded to 1.28.9 in the same transaction to keep gstreamer
  consistent), `wlr-protocols`. Already present: `grim`, `wl-clipboard`, `at-spi2-core`, `dbus`.
- Throwaway venv: `/var/tmp/wayland-venv` (from `packaging/requirements-test.txt`). The "before" checkout for the
  memory comparison: `/var/tmp/chatmon-before` (`git archive fb19cb9`). Measurement output: `/var/tmp/mem-*.json`.
- Sessions use `/tmp/sway-*` (removed on close) and pytest's `/tmp/pytest-of-randy`. No sway, at-spi, Orca,
  speech-dispatcher or pytest process of this work is running. An `at-spi-bus-launcher` on the user's own
  session bus (started 21:52) was stopped. An `Xvfb :99` (started 22:06 from `/var/tmp`, not by this work) is
  still running and was left alone.
