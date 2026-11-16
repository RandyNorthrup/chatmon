"""The plans round for v0.10.0, bound again at 56caddd: a plan's wave5b/readiness.md and wave5b/section.md:
python section7.py ID...

As section5.py did for the final round's second binding: the round's first texts (wave5/) stay, as the record of the
binding at 7816159, and a paragraph says why the plan was bound again and what changed. The section keeps the round's
heading, so it replaces wave5/'s in the plan rather than adding a second one; its closing "Receipts." paragraph is
written again. Counts are read from this binding's logs and results files. Run it before binding: it reads the plan.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
CHANGES = (
    "- **df3e93c** (the coordinator's): `chatmon/layer.py`'s two `app = QGuiApplication.instance()` lines are\n"
    "  `app: QCoreApplication | None = QGuiApplication.instance()`, CONTRIBUTING.md's second workaround for 6.12.1's\n"
    "  stubs, with no change at run time; CONTRIBUTING.md's opt-in table names `CHATMON_PINS_NETWORK=1`.\n"
    "- **56caddd** (the coordinator's): `tests/test_app_smoke.py::test_hide_menu_and_reload` waits for the greeting\n"
    "  before it hides the chatmon, and expects the \"Recent messages\" entry the greeting adds. The greeting could land\n"
    "  inside the test's one-second spin when the companion was slow to start: the WSL failure of this round's first\n"
    "  binding. The coordinator's drill ([reports/wave5/flaky-hide-menu/drill.py.txt](reports/wave5/flaky-hide-menu/drill.py.txt)),\n"
    "  run again here, fails the old body with the start slowed by 0.6 s and passes the new one at 0, 0.6, 1.4 and 2 s\n"
    "  ([reports/wave5b/flaky-hide-menu-drill-windows.log](reports/wave5b/flaky-hide-menu-drill-windows.log), and in WSL\n"
    "  [reports/wave5b/flaky-hide-menu-drill-wsl.log](reports/wave5b/flaky-hide-menu-drill-wsl.log)).\n"
)
WHY = {
    "m0": "56caddd changed `tests/test_app_smoke.py`, which M0's tasks own",
    "m3": "df3e93c changed `chatmon/layer.py`, which M3's overlay tasks own",
    "m6a": "df3e93c changed CONTRIBUTING.md, which T7B owns",
    "m6b": "df3e93c changed `chatmon/layer.py` and 56caddd `tests/test_app_smoke.py`, which its tasks own, and it binds the M6A and M8 plans",
    "m7": "56caddd changed `tests/test_app_smoke.py`, which M7's tasks bind",
    "m8": "df3e93c changed CONTRIBUTING.md, which T2-template owns, and it binds the M0 and M7 plans",
    "m10": "df3e93c changed CONTRIBUTING.md, which T3-qt612-types owns, and it binds the M4A, M6A, M6B and M8 plans",
}
FIXED = {
    "m6a": (
        "**M6A-10.A1 passes now.** With df3e93c, mypy 2.4.1 with PyQt6 6.12.1's stubs finds no issues on linux, win32\n"
        "and darwin, in WSL ([wave5b/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log), `-win32`,\n"
        "`-darwin`) and here ([reports/m10/wave5b/mypy-6121.log](reports/m10/wave5b/mypy-6121.log)). So CONTRIBUTING.md's\n"
        "\"It also passes with the next PyQt6's stubs (6.12.1)\" is true again, and its opt-in table now names\n"
        "`CHATMON_PINS_NETWORK` ([wave5b/docs-review.md](reports/m6a/wave5b/docs-review.md)). T7B is verified. W5-MAN-DOCS,\n"
        "the failed review at 7816159, stays as history."
    ),
    "m6b": (
        "**M6B-02.A1's 6.12 half passes now.** With df3e93c, mypy 2.4.1 with PyQt6 6.12.1's stubs finds no issues on\n"
        "linux, win32 and darwin, in WSL ([reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log](reports/m6a/wave5b/mypy-pyqt6-6.12.1-linux.log),\n"
        "`-win32`, `-darwin`) and here ([reports/m10/wave5b/mypy-6121.log](reports/m10/wave5b/mypy-6121.log)). T4-mypy is\n"
        "verified, and with it T6-phase-b and T7-leftovers. W5-BEH-WSL-MYPY-6121, the failed run at 7816159, stays as\n"
        "history."
    ),
    "m10": (
        "**M10-03.A1 and M10-03.A3 pass now.** With df3e93c:\n\n"
        "- mypy with PyQt6 6.12.1's stubs finds no issues on linux, win32 and darwin\n"
        "  ([wave5b/mypy-6121.log](reports/m10/wave5b/mypy-6121.log)), as with 6.11's ([wave5b/mypy-611.log](reports/m10/wave5b/mypy-611.log));\n"
        "- the five gate drills went green, red and green again ([wave5b/gate-drills.log](reports/m10/wave5b/gate-drills.log));\n"
        "- the how-to's replay in WSL finds nothing ([wave5b/howto-review.md](reports/m10/wave5b/howto-review.md)).\n\n"
        "T3-qt612-types is verified. The failed receipts at 7816159 stay as history."
    ),
}
CLOSED = {
    "m0": "M0 is closed on 56caddd.", "m3": "M3 is closed on 56caddd.", "m6a": "M6A is closed on 56caddd.",
    "m6b": "M6B is closed on 56caddd.", "m7": "M7 is closed on 56caddd.", "m8": "M8 is closed on 56caddd.",
    "m10": "M10 stops only on P-CI-NEXT-STUBS, from 2026-11-28, not a criterion.",
}


def text(name: str) -> str:
    return (REPORTS / name).read_text(encoding="utf-8", errors="replace")


def summary(name: str) -> str:
    return re.findall(r"(\d+ passed(?:, \d+ skipped)?(?:, \d+ deselected)?)", text(name))[-1]


def drills(plan: str) -> tuple[int, int, int]:
    seen: dict[str, tuple[str, str]] = {}
    for path in sorted((REPORTS / plan / "wave5b").glob("*-results.json")):
        if path.name.startswith("gate-") or path.name.startswith("distro-"):
            continue
        for rec in json.loads(path.read_text(encoding="utf-8")):
            seen.setdefault(rec["id"], (path.name, rec.get("status")))
    win = sum(1 for name, s in seen.values() if s == "pass" and "linux" not in name)
    linux = sum(1 for name, s in seen.values() if s == "pass" and "linux" in name)
    return win, linux, sum(1 for _, s in seen.values() if s != "pass")


def gates(plan: str) -> int:
    path = REPORTS / plan / "wave5b" / "gate-drills-results.json"
    return sum(r.get("status") == "pass" for r in json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else 0


def extra_paragraphs(plan: str) -> str:
    if plan == "m6b":
        return (
            "**Archived history, a third time.** This binding's 56 receipts would have taken the plan past the 4 MiB limit\n"
            "again, so round three's 56 `W4C-` receipts (55 stale, 1 failed) were moved out first, byte for byte, to\n"
            "[reports/m6b/history/w4c-round-three.json](reports/m6b/history/README.md). Nothing else in the ledger changed\n"
            "with them."
        )
    if plan == "m3":
        suite = re.findall(r"(\d+ passed, \d+ skipped|\d+ failed, \d+ passed, \d+ skipped(?:, \d+ errors?)?)", text("wave5b/suite-linux.log"))[-1]
        return (
            f"In WSL, M3's own test files ([wave5b/m3-tests-linux.log](reports/m3/wave5b/m3-tests-linux.log): {summary('m3/wave5b/m3-tests-linux.log')}),\n"
            f"the real sway ([wave5b/sway-tests-linux.log](reports/m3/wave5b/sway-tests-linux.log): {summary('m3/wave5b/sway-tests-linux.log')}) and the\n"
            "memory check ([wave5b/memory-after--window.json](reports/m3/wave5b/memory-after--window.json)) ran again. The\n"
            "Wayland drills ran with M3-RC-clipboard-v3 in -v2's place. **The whole suite in WSL**, retried at 56caddd on\n"
            f"a quiet machine, gave {suite} ([reports/wave5b/suite-linux.log](reports/wave5b/suite-linux.log)). The two failed\n"
            "runs at 7816159 stay as history."
        )
    return ""


def section(plan: str) -> str:
    old = (REPORTS / plan / "wave5" / "section.md").read_text(encoding="utf-8")
    head = old.split("\n**Receipts.**", 1)[0].rstrip("\n")
    win, linux, bad = drills(plan)
    gate = gates(plan)
    if bad:
        raise SystemExit(f"{plan}: {bad} drills didn't go green, red and green")
    ran = f"{win} Windows drills" + (f" and {linux} Linux ones (in WSL)" if linux else "") + (f", and {gate} gate drills" if gate else "")
    if (REPORTS / plan / "wave5b" / "distro-drill-results.json").is_file():
        ran += ", and the distro drill under podman in WSL"
    again = (
        "**Bound again at 56caddd.** The coordinator's two commits on this branch, after this section's first binding:\n\n"
        + CHANGES + "\n"
        + f"{WHY[plan]}, so its receipts went stale ([reports/wave5b/stale-at-56caddd.md](reports/wave5b/stale-at-56caddd.md)),\n"
        "and this paragraph changes the plan's prose, which every receipt's scope includes. Every check ran again on\n"
        f"56caddd: the whole suite on Windows ([reports/wave5b/suite-windows.log](reports/wave5b/suite-windows.log): "
        f"{summary('wave5b/suite-windows.log')}), then {ran}, every one green, red and green again. PR #24's CI run\n"
        "43794815103 on 56caddd (all 19 jobs green; its test merge has 56caddd's own tree:\n"
        "[reports/wave5b/ci/merge-tree.txt](reports/wave5b/ci/merge-tree.txt)) was read again\n"
        f"([reports/{plan}/ci/observed-56caddd.txt](reports/{plan}/ci/observed-56caddd.txt)), and the requirements were\n"
        f"reviewed again ([wave5b/readiness.md](reports/{plan}/wave5b/readiness.md))."
    )
    parts = [head, "", again]
    for extra in (extra_paragraphs(plan), FIXED.get(plan, "")):
        if extra:
            parts += ["", extra]
    parts += ["", "**Receipts.** The stale ones are kept as history, with their hashes untouched, and so are the failed ones;\n"
              f"the W5B- receipts replace them. {CLOSED[plan]}"]
    return "\n".join(parts) + "\n"


def readiness(plan: str) -> str:
    old = (REPORTS / plan / "wave5" / "readiness.md").read_text(encoding="utf-8")
    title = old.splitlines()[0] + ", bound again at 56caddd"
    body = old.split("\n", 1)[1]
    body = body.replace("Result: ready.", "Result, at 7816159: ready.")
    for name in ("stub-report.log", "outcomes.log", "readiness.md"):  # the first review's own folder's files
        body = body.replace(f"]({name})", f"](../wave5/{name})")
    return (
        f"{title}\n\n"
        "This review is the round's first ([../wave5/readiness.md](../wave5/readiness.md), at 7816159), read again at\n"
        "56caddd. Its receipt went stale with the plan's new paragraph and the files below. It is a requirements review,\n"
        "not proof that the code works: the behavior and red receipts are.\n\n"
        "## Since 7816159\n\n"
        + CHANGES.replace("](reports/", "](../../") + "\n"
        f"For this plan: {WHY[plan]}. Neither commit changes what a criterion asks or what Chatmon does: one is two type\n"
        "annotations and a documentation row, the other a test's wait. Each requirement still maps both ways to its\n"
        "criteria.\n\n"
        "Result: ready. No requirement is unclear, conflicting or missing failure behavior.\n\n"
        "## The review at 7816159\n"
        + body
    )


def main() -> int:
    for plan in sys.argv[1:]:
        out = REPORTS / plan / "wave5b"
        (out / "readiness.md").write_text(readiness(plan), encoding="utf-8", newline="\n")
        (out / "section.md").write_text(section(plan), encoding="utf-8", newline="\n")
        print(f"{plan}: drills {drills(plan)}, gates {gates(plan)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
