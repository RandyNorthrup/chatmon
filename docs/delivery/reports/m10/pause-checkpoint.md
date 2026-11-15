# M10 pause checkpoint (2026-11-14, paused by the owner overnight)

**Resumed 2026-11-15 and closed.** The WIP commit `098c32b` was folded into M10's closing commit (it was never pushed); the ledger's inputs gained `chatmon/winuia.py`, `tests/test_platform_events.py` and `tests/uia_client.py`, the receipts were bound again, and closure and resume validation pass. What follows is the checkpoint as it was written.

**Branch** `wave4/followups`. Code commits: `983b95c` (comtypes), `7972401` (Qt's translations), `d15d7a9` (PyQt6 6.12.1
stubs). The WIP commit on top holds only evidence and the plan (`docs/delivery/`); no file under `chatmon/`,
`packaging/`, `tests/`, `pyproject.toml` or `CONTRIBUTING.md` has changed since `d15d7a9`. No pytest, mypy, uv or pip
process of this work is running (checked in Windows and WSL).

## Verified (on `d15d7a9`'s code)

- Whole suite 1244 passed, 148 skipped (`suite-final.log`); ruff clean; template current.
- mypy: 6.11 stubs pass linux/win32/darwin (`mypy-611.log`); 6.12.1 stubs: 14 errors, all in the wayland worker's
  `layer.py`/`penguin.py` (`mypy-6121.log`); with `wayland-files-qt6121.diff` applied in a copy, both stubs pass on
  all three (`mypy-6121-wayland-copy.log`), also on Linux via CONTRIBUTING's commands (`howto-replay.log`).
- Red drills: 9/9 (`drills.log`), 1/1 in the CI-shaped venv (`drills-ci-venv.log`), gate drills 5/5 (`gate-drills.log`,
  rerun so the log keeps mypy's error lines; the first run is `gate-drills-first.log`).
- Frozen-app observations: Nuitka (`frozen-nuitka.log`) and PyInstaller (`frozen-pyinstaller.log`) both carry only
  `qtbase_de.qm` with a throwaway `de.po` and show "Abbrechen".

## Not yet done

- **Closure validation fails** (`validate-closure.log`), on bookkeeping only:
  1. `E-red-M10-01-announcement-not-important`: the drilled file `chatmon/winuia.py` isn't among the ledger's inputs.
     Fix: add `chatmon/winuia.py`, `tests/test_platform_events.py` and `tests/uia_client.py` to `work.inputs` in the
     plan's ledger.
  2. Five `E-red-gate-*` receipts: their artifact lacked the diagnostic (the old log's tail was all mypy notes). Fixed
     by the gate-drill rerun now in `gate-drills.log`; needs re-binding.
- Resume validation not run; plan's ledger checkpoint will be rewritten by the re-bind.

## Next safe step

From the worktree root, with `PY=C:\Users\Randy\Coding\chatmon\.venv\Scripts\python.exe`:

1. Edit the ledger's `work.inputs` as in 1 above (the plan file, by hand or a candidate).
2. `PY docs/delivery/reports/m10/bind.py --final`, then `update-delivery.py --candidate
   docs/delivery/reports/m10/candidate.md --expected-sha256 <snapshot's plan_sha256>`, delete `candidate.md`.
3. `verify-delivery.py --stage closure` and `--stage resume` with `docs/delivery/reports/m10/context.json`, into
   `validate-closure.log` and `validate-resume.log`.
4. Commit the evidence ("M10 closed: ..."), then report to the coordinator.

Nothing needs re-running unless a code file changes: if one does, re-run the suite, mypy logs and drills first.

## Throwaway environments (all under `%TEMP%` = `C:\Users\Randy\AppData\Local\Temp`)

| Venv | What |
|---|---|
| `%TEMP%\m10-qt6121` | PyQt6 6.12.1 (Qt 6.12.0), psutil 7.2.2, mypy 2.4.1: the next stubs (hash-installed from `%TEMP%\m10probe\qt6121\types-6121.txt`) |
| `%TEMP%\m10-qt612` | PyQt6 6.12.0, the one whose QtDBus stub doesn't parse |
| `%TEMP%\m10-ci-test` | installed from this branch's `requirements-test.txt` (comtypes 1.4.17) |
| `%TEMP%\m10-ci-before` | installed from fb19cb9's `requirements-test.txt` (no comtypes) |
| `%TEMP%\m10-build` | Nuitka 4.3.1 build venv; `%TEMP%\m10-nuitka-src` is the probe build's copy |
| `%TEMP%\m10-pyi` | PyInstaller 6.22.3; `%TEMP%\m10-pyi-src`, `-old`, `-en` are the probe copies |
| `%TEMP%\m10probe\wcopy` | the tree's `chatmon/` + `pyproject.toml` with the wayland diff applied |
| WSL `/tmp/qt-next`, `/var/tmp/m10-howto` | CONTRIBUTING's how-to replay |
