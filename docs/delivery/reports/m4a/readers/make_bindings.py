"""Write readers/bindings.json for docs/delivery/reports/wave4/bind.py: T-10's receipts, and the re-run of every M4A
check whose receipt the change made stale. Run from the worktree's root after the checks have run.

usage: python docs/delivery/reports/m4a/readers/make_bindings.py HEAD_SHA
"""

import json
import sys
from pathlib import Path

HERE = Path("docs/delivery/reports/m4a/readers")
HEAD = sys.argv[1]
SHORT = HEAD[:7]
WIN_PY = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
TESTS = ["tests/test_screen_readers.py", "tests/test_a11y.py", "tests/test_presence.py", "tests/test_linuxsession.py", "tests/test_winlock.py",
         "tests/test_heads_up.py", "tests/test_platform_events.py", "tests/test_macnative.py", "tests/test_portal_bus.py"]
ALL = ["AC-01a", "AC-01b", "AC-01c", "AC-02", "AC-03", "AC-04a", "AC-04b", "AC-04c", "AC-05", "AC-06a", "AC-06b", "AC-07a", "AC-07b", "AC-08",
       "AC-09a", "AC-09b", "AC-10", "AC-11", "AC-12a", "AC-12b", "AC-12c", "AC-12d", "AC-12e"]
ON_WINDOWS = [a for a in ALL if a != "AC-04b"]  # Qt's contrast signal: PyQt6 6.11 has it as a method, so it skips here
ON_LINUX = [a for a in ALL if a not in ("AC-01c", "AC-09a")]  # macOS's AppKit, Windows' UI Automation
WSL = ["wsl.exe", "-d", "archlinux", "--", "bash", "/mnt/c/Users/Randy/Coding/chatmon-wt/a11y/docs/delivery/reports/m4a/readers/wsl_batch_2.sh"]
T10_DRILL_AC = {"AC-12e-orca-speaks": "AC-12b", "AC-12f-desk-signal": "AC-12e"}


def counts(log: str) -> str:
    import re

    found = re.findall(r"(\d+) passed(?:, (\d+) skipped)?", (HERE / log).read_text(encoding="utf-8"))
    passed, skipped = found[-1]
    return f"{passed} passed, {skipped or 0} skipped"


def ac_of(drill: str) -> str:
    if drill in T10_DRILL_AC:
        return T10_DRILL_AC[drill]
    name = drill.removeprefix("W4-").removeprefix("L-")
    return name[:6].rstrip("-")


def reds(results: str, where: str, prefix: str) -> list[dict]:
    path = (HERE / results).as_posix()
    method = (f"{where}: green, then the mutation made the named test fail with pytest's tests-failed exit, then the drilled "
              "file's own bytes back (SHA-256) and green again. The results file has each run's exit and the failing test; the log "
              "beside it, each run's output.")
    return [{"id": f"R10-RED-{prefix}{record['id']}", "kind": "red", "acceptance": [ac_of(record["id"])], "artifact": path, "results": path,
             "drill": record["id"], "method": f"Red drill {record['id']} {method}"}
            for record in json.loads((HERE / results).read_text(encoding="utf-8"))]


receipts = [
    {"id": "R10-READY", "kind": "readiness", "acceptance": ALL, "artifact": (HERE / "readiness.md").as_posix(),
     "method": "Requirements review for the reopening (readiness.md): M4A-12 from the wayland worker's finding, at-spi2-core 2.62's D-Bus API "
               "as observed in WSL and its NEWS, checked for coverage, conflicts (IsEnabled alone not counted), failure behavior, "
               "non-blocking, ownership and its effect on the closed tasks."},
    {"id": "R10-BEH-WINDOWS-TESTS", "kind": "behavior", "acceptance": ON_WINDOWS, "artifact": (HERE / "m4a-tests-windows.log").as_posix(),
     "command": [WIN_PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rA", *TESTS], "exit_code": 0,
     "method": f"M4A's tests on this Windows 11 workstation (offscreen Qt, the shared venv, PyQt6 6.11) at {SHORT}: {counts('m4a-tests-windows.log')}, "
               "every skip with its reason (the other platforms' end-to-end tests, and Qt's contrast signal, which 6.11 wraps as a method). "
               "tests/test_screen_readers.py checks each Linux source with real D-Bus messages and /proc as a folder; the UI Automation client "
               "test ran, with comtypes 1.5.0."},
    {"id": "R10-BEH-WINDOWS-SUITE", "kind": "behavior", "acceptance": ON_WINDOWS, "artifact": (HERE / "suite-windows.log").as_posix(),
     "command": [WIN_PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], "exit_code": 0,
     "method": f"The whole suite on Windows at {SHORT}: {counts('suite-windows.log')}, exit 0."},
    {"id": "R10-BEH-WSL-TESTS", "kind": "behavior", "acceptance": ON_LINUX, "artifact": (HERE / "suite-linux.log").as_posix(),
     "command": WSL, "exit_code": 0,
     "method": f"M4A's tests in WSL (Arch: at-spi2-core 2.62.1, Orca 51.1, PyQt6 6.12.1 in /var/tmp/m4a-venv) under xvfb-run -a, on the "
               f"worktree's files at {SHORT}: {counts('suite-linux.log')} (the other platforms'). Among them, on private session buses: at-spi2-core's "
               "own launcher with a reader's process starting as IsEnabled turns on (the launcher never started by asking), a pretend "
               "launcher before 2.62, GNOME's setting through gsettings on a keyfile, Orca's remote controller coming and going, and "
               "the portal, notification servers and UPower tests."},
    {"id": "R10-BEH-WSL-SWAY", "kind": "behavior", "acceptance": ["AC-12b", "AC-12e"], "artifact": (HERE / "sway-readers.log").as_posix(),
     "command": WSL, "exit_code": 0,
     "method": f"The real-sway screen-reader tests in WSL (/var/tmp/wayland-venv, PyQt6 6.11) at {SHORT}, with the real Orca 51.1 and "
               f"at-spi2-core 2.62.1: {counts('sway-readers.log')}. Chatmon, started before the reader's remote controller comes up, finds Orca and "
               "speaks through it, and moves the ask box to a window (screen_reader_changed)."},
]
receipts += reds("drills-results.json", f"on Windows at {SHORT} (tests/drills/run.py, in a temporary copy)", "")
receipts += reds("drills-linux-results.json", f"in WSL at {SHORT} (docs/delivery/reports/wave4/wsl_drills.py, under xvfb-run -a)", "")
receipts += reds("drills-w4-results.json", "on Windows at b5d018a (tests/drills/run.py, wave4/drill-spec.json; its drilled files and tests are "
                                           f"unchanged since, to {SHORT})", "W4-")
receipts += reds("drills-w4-linux-results.json", "in WSL at b5d018a (wsl_drills.py, wave4/drill-spec-linux.json, under xvfb-run -a; its files "
                                                 f"are unchanged since, to {SHORT})", "W4-")
receipts += reds("drills-w4-linux-qt612-results.json", "in WSL at b5d018a on PyQt6 6.12.1 (wsl_drills.py, wave4/drill-spec-linux-qt612.json; "
                                                       f"its files are unchanged since, to {SHORT})", "")
bindings = {
    "plan": "docs/delivery/m4a-platform-awareness.md",
    "section": (HERE / "section.md").as_posix(),
    "rules": {"docs/delivery/ROADMAP.md": SHORT, "pyproject.toml": SHORT},
    "inputs_add": [],
    "task_changes_add": {},
    "stale_reason": "Stale at M4A's reopening for M4A-12 (2026-11-15, wave4/a11y): a11y.py, linuxsession.py and presence.py changed, "
                    "later merges changed ROADMAP.md, pyproject.toml, macnative.py and wave 4's scripts, and the plan gained a requirement; "
                    "the R10- receipts re-ran its check on the changed files",
    "receipts": receipts,
    "tasks": {"T-04": {"status": "implemented"}, "T-09": {"status": "implemented"}},
    "pending": [
        {"id": "CI-macos",
         "description": "T-04 and T-09's end-to-end checks run on macOS only: CI's macOS legs. Their files changed since CI last ran them "
                        "(macnative.py in another worker's merge, presence.py here), so they wait for the next CI run.",
         "next_action": "Read tests/test_macnative.py::test_sleep_wake_displays_accessibility_and_low_power_are_heard and "
                        "tests/test_presence.py::test_macos_reads_increase_contrast from the next CI run on the merged tree; on a pass, "
                        "T-04 and T-09 are verified."},
        {"id": "CI-linux",
         "description": "tests/test_screen_readers.py's bus tests ran in WSL against at-spi2-core 2.62.1. CI's Ubuntu 24.04 legs and the "
                        "distribution containers have an older at-spi2-core (2.52 keeps ScreenReaderEnabled), or none.",
         "next_action": "Read tests/test_screen_readers.py and tests/test_a11y.py from the next CI run: each runs, or skips with its "
                        "reason (no at-spi2-core, no gsettings schema), and passes."},
    ],
    "next_action": "Merge wave4/a11y; read the next CI run for CI-macos and CI-linux.",
    "source_revision": HEAD,
}
(HERE / "bindings.json").write_text(json.dumps(bindings, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(len(receipts), "receipts for", SHORT)
