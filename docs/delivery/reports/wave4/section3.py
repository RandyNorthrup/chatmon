"""Round three (3586a0d): write a plan's wave4c/readiness.md and wave4c/section.md: python section3.py ID...

The parts every plan shares are written here once; each plan's own paragraphs are in PLANS. The counts (drills that
went green, red and green, on Windows and in WSL) are read from the plan's wave4c/*-results.json, and which CI legs
were read is taken from round two's section, whose receipts round three renews one for one.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
CRASH_FILES = "`chatmon/app.py`, `chatmon/brains.py`, `tests/app_harness.py` and `tests/test_app_smoke.py`"
LISTED = {"m0", "m1b", "m3", "m6b", "m7", "m8"}  # round two's checkpoints named receipts binding wave4/crash's files
CRASH_CITED = LISTED | {"m10"}

PLANS: dict[str, dict[str, str]] = {
    "m0": {
        "name": "M0",
        "ready": (
            "M0-01 to M0-13 and M0-CLI still map both ways to their criteria. Twelve of its fifteen tasks own\n"
            "`chatmon/app.py` or `tests/test_app_smoke.py`, which the crash fix changed. The fix is about what runs after\n"
            "`quit()`: nothing. While Chatmon runs, each one-off wait still runs its method after the same delay, now\n"
            "through `Companion._later` instead of `QTimer.singleShot`. `chatmon quit` (M0-12) still quits once the sender has\n"
            "heard back (`self._later(0, self.quit)`). No criterion is about what happens after quit, or about how a wait is\n"
            "scheduled."
        ),
        "closed": "M0 is closed on 3586a0d.",
    },
    "m1a": {
        "name": "M1A",
        "ready": (
            "AC-01 to AC-11 and their criteria map as in round two. No task of this plan owns a file the crash fix changed.\n"
            "`chatmon/winpipe.py`, whose docstrings AC-10 is about, is unchanged; the accept path in `chatmon/app.py` they\n"
            "describe moved down but didn't change, and AC-10's review is done again for that. AC-01-MACOS's red drill still\n"
            "needs macOS. That is a place to run it, not a gap in the requirement."
        ),
        "middle": "AC-10's docstrings were read again ([wave4c/review-ac10.md](reports/m1a/wave4c/review-ac10.md)), and they hold.",
        "remains": (
            "**What remains.** AC-01-MACOS's red drill still needs macOS, as in round two. It is recorded again as\n"
            "W4C-RED-AC-01-MACOS, which says how to run it. Owner: Randy on a Mac, or the coordinator with a throwaway drill\n"
            "branch on CI."
        ),
        "closed": "",
    },
    "m1b": {
        "name": "M1B",
        "ready": (
            "M1B-01 to M1B-17 still map one to one to AC-M1B-01 to AC-M1B-17. Eight of its ten tasks own `chatmon/brains.py`,\n"
            "where the crash fix gives `Finder` a `stop()`: once Chatmon quits, a brain found after that is handed to no\n"
            "one. While Chatmon runs, finding a brain is unchanged. No criterion is about what happens after quit."
        ),
        "closed": "M1B is closed on 3586a0d.",
    },
    "m2": {
        "name": "M2",
        "ready": "M2's requirements map to their criteria as in round two. No task of this plan owns a file the crash fix changed.",
        "closed": "M2 is closed on 3586a0d.",
    },
    "m3": {
        "name": "M3",
        "ready": (
            "M3-01 to M3-15, M3-M2 and M3-RC (scope revision 3) map both ways to their 28 criteria, as in round two. No task\n"
            "of this plan owns a file the crash fix changed. Round two's receipts bound `chatmon/app.py` and\n"
            "`tests/app_harness.py` through the plan's inputs, so they had to be renewed. M3-RC's CI half is again the `sway`\n"
            "job, still one of `main`'s 19 required checks ([reports/wave4c/github-settings.txt](../../wave4c/github-settings.txt)).\n"
            "M3-14's real-Orca half is again proven in WSL, because CI has no Orca."
        ),
        "middle": (
            "**The whole suite in WSL fails one test, none of M3's** ([wave4c/suite-linux.log](reports/wave4c/suite-linux.log):\n"
            "1 failed, 1315 passed, 121 skipped). It is the crash fix's own\n"
            "`tests/test_app_smoke.py::test_a_quit_companion_runs_nothing_it_had_waiting`: after quit,\n"
            "`Companion._power_saving` ran. `linuxsession.PowerProfile` asks the system bus for UPower's `OnBattery`, and\n"
            "its answer comes back after quit, which `Companion._stop_for_good` doesn't stop. It fails five runs in five with\n"
            "UPower on WSL's system bus, and passes without a system bus\n"
            "([reports/wave4c/crash-test-wsl.log](reports/wave4c/crash-test-wsl.log)). CI's runners have no such bus, so CI\n"
            "passes it. That is product code, the coordinator's, and is recorded as W4C-BEH-WSL-SUITE, failing. In its place,\n"
            "M3's own test files ran on their own in WSL ([wave4c/m3-tests-linux.log](reports/m3/wave4c/m3-tests-linux.log):\n"
            "145 passed, 4 skipped, exit 0) as W4C-BEH-WSL-M3. Those are every file any of M3's drills runs a test of, the\n"
            "real-compositor and real-Orca tests among them."
        ),
        "closed": "M3 is closed on 3586a0d.",
    },
    "m4a": {
        "name": "M4A",
        "ready": (
            "M4A's requirements map to their criteria as in round two. No task of this plan owns a file the crash fix\n"
            "changed. T-04 and T-09's macOS end-to-end checks are read from CI's macOS legs again, and its screen-reader\n"
            "tests from the Linux legs and WSL."
        ),
        "closed": "M4A is closed on 3586a0d.",
    },
    "m4b": {
        "name": "M4B",
        "ready": (
            "M4B's requirements map to their criteria as in round two. No task of this plan owns a file the crash fix\n"
            "changed. The same four red drills still need somewhere to run: a Mac, or a Windows desktop with notifications\n"
            "on. Those are places to run them, not gaps in the requirements."
        ),
        "remains": (
            "**What remains.** The same four red drills as in round two, each recorded again as a deferred receipt that says\n"
            "how:\n\n"
            "- AC-00C, AC-01D and AC-02F need macOS. Owner: Randy on a Mac, or the coordinator through CI.\n"
            "- AC-03E needs a Windows desktop with notifications on. Owner: Randy (notifications on for one run, or a test PC's\n"
            "  signed-in desktop), or the coordinator through CI."
        ),
        "closed": "",
    },
    "m5": {
        "name": "M5",
        "ready": "M5's requirements map to their criteria as in round two. No task of this plan owns a file the crash fix changed.",
        "closed": "M5 is closed on 3586a0d.",
    },
    "m6a": {
        "name": "M6A",
        "ready": (
            "M6A's requirements map to their criteria as in round two. No task of this plan owns a file the crash fix\n"
            "changed, and `.github/`, `CONTRIBUTING.md`, `packaging/` and `pyproject.toml` are unchanged since bf9d8ac. The\n"
            "0.10.0 tag and Dependabot's first run are still outcomes of a release and a merge, recorded as pending operations."
        ),
        "middle": (
            "**M6A-10.A1 fails again, on one sentence** ([wave4c/docs-review.md](reports/m6a/wave4c/docs-review.md)).\n"
            "CONTRIBUTING.md is unchanged since round two, but its \"It also passes with the next PyQt6's stubs (6.12.1)\" is\n"
            "no longer true at 3586a0d. The crash fix's new `widget.removeEventFilter(self)` in `Companion._stop_for_good`\n"
            "(`chatmon/app.py:3173`) fails mypy with 6.12.1's stubs on linux, win32 and darwin: `Argument 1 to\n"
            "\"removeEventFilter\" of \"QObject\" has incompatible type \"Companion\"; expected \"AskBox\"  [arg-type]`. That was\n"
            "seen here ([reports/m10/wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)) and in WSL\n"
            "([wave4c/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log), `-win32`, `-darwin`).\n"
            "It is the stub bug CONTRIBUTING.md's third workaround covers, and the line lacks the workaround. CI is green\n"
            "because it locks 6.11's stubs. The fix is product code, not this work's: T7 is blocked on it. Round three's\n"
            "other runs passed: the 10 gate drills on CI's combined coverage data for 3586a0d against `fail_under = 84`,\n"
            "the distro drill under podman, the reproducible wheel, the Windows Update opt-in, and Dependabot's schema."
        ),
        "remains": (
            "**What remains.**\n\n"
            "- **M6A-10.A1.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`.\n"
            "  Then M10's `mypy_runs.py` with the 6.12.1 venv runs again, and this review with it.\n"
            "- **P-RELEASE**, a pending operation as in round two: no v0.10.0 tag exists yet\n"
            "  ([reports/wave4c/github-settings.txt](reports/wave4c/github-settings.txt), observed again). Owner: Randy or\n"
            "  the coordinator, at the release.\n"
            "- **P-DEPENDABOT**, as in round two: `.github/dependabot.yml` isn't on `main` yet. Owner: the coordinator, after\n"
            "  the merge."
        ),
        "closed": "",
    },
    "m6b": {
        "name": "M6B",
        "ready": (
            "M6B-01 to M6B-03, M6B-RW and M6B-LEFT still map both ways to their 17 criteria. Seven tasks own files the crash\n"
            "fix changed. The fix adds no `noqa` and no `type: ignore`. ruff and mypy with 6.11's stubs pass on it on every\n"
            "platform (CI's lint and three types jobs at 3586a0d). M6B-02.A1 also asks for mypy to pass with 6.12's stubs.\n"
            "That half now fails, on one line of the fix: the receipts say so, and T4-mypy is blocked on it. The\n"
            "requirement itself is clear. The M6A and M8 plans this plan takes as inputs are re-bound in round three\n"
            "before M6B."
        ),
        "middle": (
            "**M6B-02.A1's 6.12 half fails.** The crash fix's new `widget.removeEventFilter(self)` in\n"
            "`Companion._stop_for_good` (`chatmon/app.py:3173`) fails mypy with PyQt6 6.12.1's stubs on linux, win32 and\n"
            "darwin: `Argument 1 to \"removeEventFilter\" of \"QObject\" has incompatible type \"Companion\"; expected\n"
            "\"AskBox\"  [arg-type]`. That was seen in WSL\n"
            "([reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4c/mypy-pyqt6-6.12.1-linux.log), `-win32`,\n"
            "`-darwin`) and here ([reports/m10/wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)). 6.12.1's stubs type the\n"
            "filter as `Self`, the watched object: the bug the other such lines carry `# type: ignore[arg-type]` for. CI's\n"
            "`types` jobs lock 6.11's stubs and pass, and so does every gate drill. The 6.11 half and the rest of the plan\n"
            "hold."
        ),
        "remains": (
            "**What remains.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`.\n"
            "Then mypy with 6.12.1's stubs runs again, and T4-mypy can be verified. T6-phase-b and T7-leftovers depend on\n"
            "it, so they are blocked with it, though their own receipts pass. It is product code, not this work's to change."
        ),
        "closed": "",
    },
    "m7": {
        "name": "M7",
        "ready": (
            "M7-CI, M7-01 to M7-13 and the five INT- requirements still map both ways to their 52 criteria. Twenty-two tasks\n"
            "own `chatmon/app.py`, `tests/app_harness.py` or `tests/test_app_smoke.py`. One drill's text moved with the fix:\n"
            "M7-11-palette-ignored took out `QTimer.singleShot(0, self._palette_changed)`, which is now\n"
            "`self._later(0, self._palette_changed)` (and the `not self._quitting` test moved into `_later`). Round three's\n"
            "W4-M7-11-palette-ignored-v2 makes the same change on the new line, for the same test. WAYLAND-HOSTING stands as\n"
            "in round two: sway with the real Orca in WSL, sway in CI; Hyprland and KDE themselves not tried."
        ),
        "middle": (
            "**One drill re-aimed.** M7-11-palette-ignored's text no longer occurs (the fix moved the palette's one-off wait\n"
            "to `self._later`), so it is left out of the copy ([wave4c/drills-left-out.txt](reports/m7/wave4c/drills-left-out.txt)).\n"
            "W4-M7-11-palette-ignored-v2 takes the new line out for the same test, which fails, so AC-11-2 keeps its red receipt."
        ),
        "closed": "M7 is closed on 3586a0d.",
    },
    "m8": {
        "name": "M8",
        "ready": (
            "M8-01 still maps to M8-01.A1 through A10. T3-wrap-a and T4-wrap-b own `chatmon/app.py` and `chatmon/brains.py`.\n"
            "The crash fix adds no string anyone sees, and `packaging/extract_strings.py --check` finds the template current\n"
            "([reports/wave4c/extract-strings-check.log](../../wave4c/extract-strings-check.log)). The M0, M5 and M7 plans\n"
            "this plan takes as inputs are re-bound in round three before M8."
        ),
        "closed": "M8 is closed on 3586a0d.",
    },
    "m10": {
        "name": "M10",
        "ready": "",  # its own, written by hand: the plan's first review since fb19cb9
        "middle": (
            "**What failed: M10-03.A1's 6.12.1 half.** Integration note 1 is in the tree, so mypy with PyQt6 6.12.1's\n"
            "stubs was run on the tree itself, not a patched copy. It found one error, the same on linux, win32 and darwin\n"
            "([wave4c/mypy-6121.log](reports/m10/wave4c/mypy-6121.log)). The crash fix's new\n"
            "`widget.removeEventFilter(self)` in `Companion._stop_for_good` (`chatmon/app.py:3173`) gives `Argument 1 to\n"
            "\"removeEventFilter\" of \"QObject\" has incompatible type \"Companion\"; expected \"AskBox\"  [arg-type]`. 6.12.1's\n"
            "stubs type the filter as `Self`, the watched object: the plan's third kind of stub bug, which the line\n"
            "doesn't work around. CI is green because it locks 6.11's stubs, which pass\n"
            "([wave4c/mypy-611.log](reports/m10/wave4c/mypy-611.log), and the three `types` jobs). The four gate drills on\n"
            "6.12.1's stubs couldn't start, because mypy isn't green on the copy. They are recorded as failing\n"
            "([wave4c/gate-drills.log](reports/m10/wave4c/gate-drills.log)). The fifth, on 6.11's, went green, red and\n"
            "green. Everything else passed: the locks, the UI Automation test in the CI-shaped venv and on CI's Windows\n"
            "legs, Qt's translations, the 10 pytest drills, and the how-to, replayed in WSL. The replay reports the same\n"
            "error, which is what the how-to is for."
        ),
        "remains": (
            "**What remains.** The coordinator adds `# type: ignore[arg-type]` with the reason to `chatmon/app.py:3173`,\n"
            "as CONTRIBUTING.md says for an argument the stubs type as `Self`. It is product code, not this work's to\n"
            "change. Then `mypy_runs.py` with the 6.12.1 venv and `wave4c/gate_drills.py` run again, and T3-qt612-types can\n"
            "be verified. After that, from 2026-11-28, the `types` job's check against the next stubs (P-CI-NEXT-STUBS,\n"
            "integration note 2) is the coordinator's too. It is not a criterion, but it would have caught this line in CI."
        ),
        "closed": "",
    },
}


def results(plan: str) -> tuple[int, int, int]:
    """(Windows drills passed, Linux drills passed, drills not passed) in the plan's wave4c/."""
    win = linux = bad = 0
    for path in sorted((REPORTS / plan / "wave4c").glob("*-results.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")):
            if rec.get("status") != "pass":
                bad += 1
            elif "linux" in path.name or "wsl" in path.name or "distro" in path.name:  # M6A's distro drill ran in WSL, under podman
                linux += 1
            else:
                win += 1
    return win, linux, bad


def ci_read(plan: str) -> str:
    old = (REPORTS / plan / "wave4b/section.md").read_text(encoding="utf-8")
    found = re.search(r"was read for (.*?) \(\[reports/", old.replace("\n", " "), re.S)
    text = found.group(1) if found else "its legs"
    return text.replace("43701523037", "43729628343").replace("bf9d8ac", "3586a0d")


def refresh_count(plan: str) -> str:
    slug = next(p for p in (ROOT / "docs/delivery").glob(f"{plan}-*.md"))
    ledger = json.loads(re.search(r"```quality-ledger\n(.*?)\n```", slug.read_text(encoding="utf-8"), re.S).group(1))
    found = re.search(r"need a refresh, .*? \((\d+) of (\d+)\)", ledger["checkpoint"]["next_action"])
    return f"{found.group(1)} of its {found.group(2)} receipts" if found else "some of its receipts"


def section(plan: str) -> str:
    info = PLANS[plan]
    win, linux, bad = results(plan)
    parts = ["## Reconciliation, wave 4, round three (2026-11-15)", ""]
    parts.append(
        "Round three re-bound this plan at **3586a0d**: `improve/assessment-fixes` with wave4/crash and round two merged.\n"
        "wave4/crash frees quit test Companions between tests (CI's fedora:44 crash) and makes sure nothing a quit Chatmon\n"
        f"had waiting runs: its one-off waits, its timers, its threads' answers. It changed {CRASH_FILES}."
    )
    parts.append("")
    if plan == "m10":
        parts.append(
            "**Why every receipt was renewed.** Rounds one and two didn't re-bind this plan, the followups worker's. Its\n"
            "receipts were hashed on a CRLF checkout, against ROADMAP's *Canonical bytes*, and the a11y, wayland and crash\n"
            "merges changed its inputs since. Round three ran every check again on an LF checkout of 3586a0d."
        )
    elif plan in LISTED:
        parts.append(
            f"**Why every receipt was renewed.** Round two's checkpoint named {refresh_count(plan)} as binding those\n"
            "files. ROADMAP.md is a rule of every plan, and round three amends it (the Outcome at 3586a0d), so the others\n"
            "went stale with it. Every check was run again on 3586a0d or read from its CI run, not only those."
        )
    else:
        parts.append(
            "**Why every receipt was renewed.** None of round two's receipts bound those files. But ROADMAP.md is a rule of\n"
            "every plan, and round three amends it (the Outcome at 3586a0d), so every receipt went stale with it. Every\n"
            "check was run again on 3586a0d or read from its CI run."
        )
    parts.append("")
    drills = f"{win} Windows drills" + ((" and one Linux drill (in WSL)" if linux == 1 else f" and {linux} Linux ones (in WSL)") if linux else "")
    verdict = "Every one went green, red and green again." if not bad else f"{bad} did not go green, red and green: see below."
    ci = ("CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:\n"
          f"[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for {ci_read(plan)}"
          if plan != "m10" else
          "CI run 43729628408 (PR #18 at 3586a0d, all 19 jobs green, its test merge `5545f5a` with 3586a0d's own tree:\n"
          "[reports/wave4c/ci/merge-tree.txt](reports/wave4c/ci/merge-tree.txt)) was read for its Windows test legs (the UI\n"
          "Automation test, with comtypes from the test lock) and its three types jobs")
    parts.append(
        "**What was re-run.** The whole suite on Windows ([wave4c/suite-windows.log](reports/wave4c/suite-windows.log):\n"
        f"1259 passed, 178 skipped), then {drills}. {verdict} {ci}\n"
        f"([reports/{plan}/ci/observed-3586a0d.txt](reports/{plan}/ci/observed-3586a0d.txt)). The requirements were reviewed\n"
        f"again ([wave4c/readiness.md](reports/{plan}/wave4c/readiness.md))."
    )
    if plan in CRASH_CITED:
        parts.append("")
        parts.append(
            "**The crash fix's own drills.** CRASH-01 to CRASH-07 (the harness freeing a quit Companion; no look at the\n"
            "agents once quit; `_later`, Background, the Finder, the timers and the event filter each doing nothing once\n"
            "quit) went green, red and green again on 3586a0d here too\n"
            "([reports/wave4c/crash/drills.log](reports/wave4c/crash/drills.log)). They prove wave4/crash's own\n"
            "requirements, which are none of this plan's criteria, so they are cited as context, not bound as receipts."
        )
    for key in ("middle", "remains"):
        if info.get(key):
            parts += ["", info[key]]
    parts.append("")
    old = "Its earlier receipts" if plan == "m10" else "Round two's W4B- receipts"
    parts.append(f"**Receipts.** {old} are now stale history, with their hashes untouched. The W4C- receipts replace\n"
                 f"them. {info['closed']}".rstrip())
    return "\n".join(parts) + "\n"


def readiness(plan: str) -> str:
    info = PLANS[plan]
    name = info["name"]
    return (
        f"# {name} readiness, round three at 3586a0d (wave 4, 2026-11-15)\n\n"
        "Round two's review is [../wave4b/readiness.md](../wave4b/readiness.md) (at bf9d8ac). Its receipt went stale\n"
        "because ROADMAP.md (a rule) is amended for round three, and wave4/crash changed files. This review re-reads the\n"
        "plan's obligations against the brief and rules as they are now. It is a requirements review, not proof that the\n"
        "code works: the behavior and red receipts are.\n\n"
        "## Inputs read\n\n"
        "- [ASSESSMENT.md](../../../ASSESSMENT.md): unchanged since round one.\n"
        "- [ROADMAP.md](../../../ROADMAP.md), amended in round three: the Outcome now reads 3586a0d, and the evidence rules\n"
        "  say how round three binds. No owner decision changed, and `main` still requires the same 19 checks\n"
        "  ([reports/wave4c/github-settings.txt](../../wave4c/github-settings.txt)).\n"
        "- `pyproject.toml`: unchanged since bf9d8ac.\n"
        f"- The code: only wave4/crash's merge changed it, in {CRASH_FILES}, and one\n"
        "  changelog line. A quit Companion runs nothing it had waiting. Its one-off waits go through `Companion._later`,\n"
        "  which holds it weakly and checks it hasn't quit. Its timers are stopped and silenced. `Background` and\n"
        "  `brains.Finder` hand nothing back once stopped, and the agents aren't looked at once it has quit. The tests free\n"
        "  each quit Companion between tests. Nothing changes while Chatmon runs.\n\n"
        "## This plan\n\n"
        f"{info['ready']}\n\n"
        "Result: ready. No requirement is unclear, conflicting or missing failure behavior.\n"
    )


def main() -> int:
    for plan in sys.argv[1:]:
        out = REPORTS / plan / "wave4c"
        if PLANS[plan]["ready"]:
            (out / "readiness.md").write_text(readiness(plan), encoding="utf-8", newline="\n")
        (out / "section.md").write_text(section(plan), encoding="utf-8", newline="\n")
        print(f"{plan}: {results(plan)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
