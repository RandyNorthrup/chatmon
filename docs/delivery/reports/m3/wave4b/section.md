## Reconciliation, wave 4, round two (2026-11-15)

Round two re-bound this plan at **bf9d8ac**: `improve/assessment-fixes` after the wayland, followups, a11y and
sway-ci merges, and round one's own. Its earlier receipts went stale, because `pyproject.toml` (a rule) and files they
were bound to changed. The evidence is for bf9d8ac only. wave4/crash, not merged yet, fixes an intermittent Qt crash
in `chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`. The checkpoint's next
action names the receipts that bind those files, and only those need a refresh when it merges.

**What was re-run.** The whole suite on Windows ([wave4b/suite-windows.log](reports/wave4b/suite-windows.log): 1256 passed, 178 skipped), then 30 Windows drills and 14 Linux ones (in WSL). Every one went green, red and green again. CI run 43701523023 (PR #18 at bf9d8ac, all 19
jobs green) was read for its `sway` job (49 passed; 3 skipped because CI has no Orca or wlr-protocols) ([reports/m3/ci/observed-bf9d8ac.txt](reports/m3/ci/observed-bf9d8ac.txt)). The
requirements were reviewed again ([wave4b/readiness.md](reports/m3/wave4b/readiness.md)).

**CI-sway-job is answered.** The `sway` job's first run on GitHub is green, and it is one of `main`'s 19 required
checks. Also re-run in WSL on bf9d8ac's files, with sway 1.12, at-spi2-core 2.62.1 and Orca 51.1:

- the whole suite ([wave4b/suite-linux.log](reports/wave4b/suite-linux.log));
- `test_sway.py` and `test_wayland.py`, verbose, the real-Orca tests included
  ([wave4b/sway-tests-linux.log](reports/m3/wave4b/sway-tests-linux.log));
- `memory.py` at 3840x2160 and scale 2 with a window under the overlay
  ([wave4b/memory-after--window.json](reports/m3/wave4b/memory-after--window.json)).

The drills ran through `reports/wave4/wsl_drills.py` and `tests/drills/run.py`, in place of `reports/m3/wslrun.sh` and
`wslvenv.bat`, which name the wayland worker's worktree.

**Receipts.** Round one's W4- receipts are now stale history, with their hashes untouched. The W4B- receipts replace
them. M3 is closed on bf9d8ac.
