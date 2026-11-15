"""The final round (45a17b3): write a plan's wave4e/readiness.md and wave4e/section.md: python section4.py ID...

The shared parts are written once; each plan's own paragraphs are in PLANS. The drill counts are read from the plan's
wave4e/*-results.json, and how many receipts went stale, and on which files, from wave4e/stale-at-45a17b3.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
STALE = REPORTS / "wave4e/stale-at-45a17b3.md"
SLUGS = {"m0": "m0-app-core", "m3": "m3-stage-overlay", "m6a": "m6a-ci-tooling", "m6b": "m6b-static-analysis-logging",
         "m7": "m7-integration", "m8": "m8-translation", "m10": "m10-followups"}
CHANGES = (
    "- The quit guard (`86e84e0`): every system watcher's callback (the lock, sleep, power and settings watchers on\n"
    "  each OS) goes through `Companion._heard`, which does nothing once the Companion has quit and holds it only\n"
    "  weakly, as `_later` does for its one-off waits. While Chatmon runs, each callback is called as before. The line\n"
    "  round three found failing with PyQt6 6.12.1's stubs, `widget.removeEventFilter(self)`, now carries\n"
    "  `# type: ignore[arg-type]` with its reason, as CONTRIBUTING.md says. `tests/test_app_smoke.py` gives its\n"
    "  stand-in Companion a `_heard`, and its quit test no longer counts the guard itself as something that ran.\n"
    "- The toast fix (`8c24b1c`): `tests/test_wintoast.py` waits for a hidden toast to leave Action Center, rather than\n"
    "  taking `hide()`'s True for it.\n"
    "- The macOS owner test (`3bcd857`): `tests/test_install_update.py` gains\n"
    "  `test_mac_an_app_that_isnt_roots_is_never_run_as_root`, with the macOS fixture split so both tests share it.\n"
)

PLANS: dict[str, dict[str, str]] = {
    "m0": {
        "name": "M0",
        "ready": (
            "M0-01 to M0-13 and M0-CLI still map both ways to their criteria. Twelve tasks own `chatmon/app.py` or\n"
            "`tests/test_app_smoke.py`. The quit guard changes what a system watcher's late callback does after quit\n"
            "(nothing), not what Chatmon does while it runs, and no criterion is about after quit."
        ),
        "closed": "M0 is closed on 45a17b3.",
    },
    "m3": {
        "name": "M3",
        "ready": (
            "M3's 28 criteria map as in round three. No task owns a changed file; every receipt bound `chatmon/app.py`\n"
            "through the plan's inputs, so all of them were renewed."
        ),
        "middle": (
            "**The whole suite in WSL passes again** ([wave4e/suite-linux.log](reports/wave4e/suite-linux.log): 1316 passed,\n"
            "122 skipped, exit 0, with UPower on the system bus). Round three's one failure there, the crash fix's quit test,\n"
            "passes since the quit guard sends the power watcher's late answer through `Companion._heard`. It also passed five\n"
            "runs in five on its own ([reports/wave4e/crash-test-wsl.log](reports/wave4e/crash-test-wsl.log)). So W4E-BEH-WSL-SUITE\n"
            "passes, and M3's own test files ran too ([wave4e/m3-tests-linux.log](reports/m3/wave4e/m3-tests-linux.log): 145\n"
            "passed, 4 skipped), as in round three."
        ),
        "closed": "M3 is closed on 45a17b3.",
    },
    "m6a": {"name": "M6A", "ready": "", "closed": ""},
    "m6b": {
        "name": "M6B",
        "ready": (
            "M6B-01 to M6B-03, M6B-RW and M6B-LEFT still map both ways to their 17 criteria. The quit guard's new ignore\n"
            "names its error code and says why, as M6B-02 asks of every ignore, and the new code passes ruff (CI's lint\n"
            "job). `tests/test_install_update.py`, one of T1-ruff's files and so bound by the tasks that depend on it, gains\n"
            "a macOS test and keeps every earlier one. M6B-02.A1's 6.12 half, failing in round three on that line, is checked again."
        ),
        "middle": (
            "**M6B-02.A1's 6.12 half passes again.** mypy 2.4.1 with PyQt6 6.12.1's stubs finds no issues on linux, win32 and\n"
            "darwin, in WSL ([reports/m6a/wave4e/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave4e/mypy-pyqt6-6.12.1-linux.log),\n"
            "`-win32`, `-darwin`) and here ([reports/m10/wave4e/mypy-6121.log](reports/m10/wave4e/mypy-6121.log)). The quit\n"
            "guard gave `chatmon/app.py`'s `removeEventFilter(self)` the `# type: ignore[arg-type]` with its reason. T4-mypy\n"
            "is verified again, and with it T6-phase-b and T7-leftovers, which depend on it and were blocked only by it."
        ),
        "closed": "M6B is closed on 45a17b3.",
    },
    "m7": {
        "name": "M7",
        "ready": (
            "M7-CI, M7-01 to M7-13 and the five INT- requirements still map both ways to their 52 criteria. The toast\n"
            "test's new wait is on its notifications-on branch; this workstation's notifications are off, so here it takes\n"
            "the other branch, as before (CI's Windows runners take the notifications-on one). Two drills' lines moved\n"
            "with the quit guard: M4A-desk-changes-unheard and M4A-mac-sleep-unheard took out a `connect` line that now\n"
            "passes its method through `_heard`. W4-M7-desk-changes-unheard-v2 and W4-M7-mac-sleep-unheard-v2 take out\n"
            "the new lines, for the same tests."
        ),
        "middle": (
            "**Two drills re-aimed.** The quit guard put `self._heard(...)` around the methods M4A-desk-changes-unheard\n"
            "and M4A-mac-sleep-unheard took the `connect` lines of, so their texts no longer occur\n"
            "([wave4e/drills-left-out.txt](reports/m7/wave4e/drills-left-out.txt)). W4-M7-desk-changes-unheard-v2 and\n"
            "W4-M7-mac-sleep-unheard-v2 take out the new lines, and the same tests fail, so AC-11-7 keeps its red receipts."
        ),
        "closed": "M7 is closed on 45a17b3.",
    },
    "m8": {
        "name": "M8",
        "ready": (
            "M8-01 still maps to M8-01.A1 through A10. T3-wrap-a and T4-wrap-b own `chatmon/app.py`; the quit guard adds\n"
            "no string anyone sees, and `packaging/extract_strings.py --check` finds the template current\n"
            "([reports/wave4e/extract-strings-check.log](../../wave4e/extract-strings-check.log)). The M0 and M7 plans this\n"
            "plan takes as inputs are re-bound in this round before M8."
        ),
        "closed": "M8 is closed on 45a17b3.",
    },
    "m10": {
        "name": "M10",
        "ready": (
            "M10-01 to M10-03 still map both ways to their seven criteria. T3-qt612-types owns `chatmon/app.py`, where the\n"
            "line round three found failing now carries the plan's own workaround. Integration note 2's CI check is the\n"
            "coordinator's from 2026-11-28 (P-CI-NEXT-STUBS) and note 4's upstream report the owner's: neither is a\n"
            "criterion. The M6B plan this plan takes as an input is re-bound in this round before M10."
        ),
        "middle": (
            "**M10-03.A1's 6.12.1 half passes again.** mypy with PyQt6 6.12.1's stubs on the tree finds no issues on linux,\n"
            "win32 and darwin ([wave4e/mypy-6121.log](reports/m10/wave4e/mypy-6121.log)), and with 6.11's none either\n"
            "([wave4e/mypy-611.log](reports/m10/wave4e/mypy-611.log)). All five gate drills went green, red and green again\n"
            "([wave4e/gate-drills.log](reports/m10/wave4e/gate-drills.log)); in round three four of them couldn't start. The\n"
            "how-to was reviewed and replayed in WSL again ([wave4e/howto-review.md](reports/m10/wave4e/howto-review.md)).\n"
            "T3-qt612-types is verified. The locks (locked again, byte for byte the committed ones), the UI Automation test\n"
            "in the CI-shaped venv and its red drill ran again too, and passed ([wave4e/locks.log](reports/m10/wave4e/locks.log),\n"
            "[wave4e/uia-ci-venv.log](reports/m10/wave4e/uia-ci-venv.log))."
        ),
        "remains": (
            "**What remains, outside the criteria.** From 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check\n"
            "against the next stubs (P-CI-NEXT-STUBS, integration note 2): the coordinator. The upstream report on PyQt6's\n"
            "stubs (note 4): the owner, with the owner's PyQt mailing-list account."
        ),
        "closed": "",
    },
}


def results(plan: str) -> tuple[int, int, int]:
    win = linux = bad = 0
    for path in sorted((REPORTS / plan / "wave4e").glob("*-results.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")):
            if rec.get("status") != "pass":
                bad += 1
            elif "linux" in path.name or "wsl" in path.name:
                linux += 1
            else:
                win += 1
    return win, linux, bad


def stale(plan: str) -> tuple[int, int, list[str]]:
    text = STALE.read_text(encoding="utf-8")
    part = text.split(f"## docs/delivery/{SLUGS[plan]}.md: ")[1].split("\n## ")[0]
    rows = [line for line in part.splitlines() if line.startswith("| ") and not line.startswith("| Receipt")]
    files = sorted({f for row in rows for f in re.findall(r"`([^`]+)`", row.split(" | ")[2])})
    ledger = json.loads(re.search(r"```quality-ledger\n(.*?)\n```", (ROOT / "docs/delivery" / f"{SLUGS[plan]}.md").read_text(encoding="utf-8"), re.S).group(1))
    passing = sum(e["status"] == "pass" for e in ledger["evidence"])
    return len(rows), passing, files


def section(plan: str) -> str:
    info = PLANS[plan]
    win, linux, bad = results(plan)
    n, of, files = stale(plan)
    parts = ["## Reconciliation, wave 4, final round (2026-11-15)", ""]
    parts.append(
        "The final round re-bound this plan at **45a17b3**: `improve/assessment-fixes` with the quit guard\n"
        "(`86e84e0`), the toast fix (`8c24b1c`), wave4/mac-drills and wave4/mac-owner merged. "
        + (f"{n} of its {of} passing receipts went stale, on " + ", ".join(f"`{f}`" for f in files)
           + " ([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)). Writing this section into the\n"
           "plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check\n"
           "was run again on 45a17b3 or read from its CI run." if n else
           "None of its receipts went stale ([reports/wave4e/stale-at-45a17b3.md](reports/wave4e/stale-at-45a17b3.md)).")
    )
    parts.append("")
    if win or linux:
        drills = f"{win} Windows drills" + (f" and {linux} Linux ones (in WSL)" if linux else "")
        verdict = "Every one went green, red and green again." if not bad else f"{bad} did not: see below."
        parts.append(
            "**What was re-run.** The whole suite on Windows ([wave4e/suite-windows.log](reports/wave4e/suite-windows.log)),\n"
            f"then {drills}. {verdict} CI run 43743804662 (PR #18 at 45a17b3, all 19 jobs green, its test merge `eb8a996`\n"
            "with 45a17b3's own tree: [reports/wave4e/ci/merge-tree.txt](reports/wave4e/ci/merge-tree.txt)) was read again\n"
            f"([reports/{plan}/ci/observed-45a17b3.txt](reports/{plan}/ci/observed-45a17b3.txt)). The requirements were\n"
            f"reviewed again ([wave4e/readiness.md](reports/{plan}/wave4e/readiness.md))."
        )
    for key in ("middle", "remains"):
        if info.get(key):
            parts += ["", info[key]]
    parts.append("")
    parts.append(f"**Receipts.** The stale ones are kept as history, with their hashes untouched; the W4E- receipts replace\n"
                 f"them. {info['closed']}".rstrip())
    return "\n".join(parts) + "\n"


def readiness(plan: str) -> str:
    info = PLANS[plan]
    return (
        f"# {info['name']} readiness, the final round at 45a17b3 (wave 4, 2026-11-15)\n\n"
        "Round three's review is [../wave4c/readiness.md](../wave4c/readiness.md) (at 3586a0d). Its receipt went stale\n"
        "because files the plan's criteria bind changed. This review re-reads the plan's obligations against the brief\n"
        "and rules as they are now. It is a requirements review, not proof that the code works: the behavior and red\n"
        "receipts are.\n\n"
        "## Inputs read\n\n"
        "- [ASSESSMENT.md](../../../ASSESSMENT.md), [ROADMAP.md](../../../ROADMAP.md) and `pyproject.toml`: unchanged\n"
        "  since round three. The final status is in [OUTCOME.md](../../../OUTCOME.md), which no plan binds.\n"
        "- The code and tests, changed since 3586a0d in four files:\n"
        f"{CHANGES}\n"
        "## This plan\n\n"
        f"{info['ready']}\n\n"
        "Result: ready. No requirement is unclear, conflicting or missing failure behavior.\n"
    )


def main() -> int:
    for plan in sys.argv[1:]:
        out = REPORTS / plan / "wave4e"
        if PLANS[plan]["ready"]:
            (out / "readiness.md").write_text(readiness(plan), encoding="utf-8", newline="\n")
        (out / "section.md").write_text(section(plan), encoding="utf-8", newline="\n")
        print(f"{plan}: drills {results(plan)}, stale {stale(plan)[:2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
