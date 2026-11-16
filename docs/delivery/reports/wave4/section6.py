"""The plans round for v0.10.0 (7816159): write a plan's wave5/readiness.md and wave5/section.md: python section6.py ID...

As section4.py, for this round: the shared parts are written once and each plan's own paragraphs are in PLANS. The
drill counts are read from the plan's wave5/*-results.json, and how many receipts went stale, and on which files, from
wave5/stale-at-7816159.md (stale_report.py at 7816159, before any plan was bound). M6A's section is its own
(m6a/wave5/section.md, written by hand), as are its readiness and reviews.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
STALE = REPORTS / "wave5/stale-at-7816159.md"
SLUGS = {"m0": "m0-app-core", "m2": "m2-bubbles-askbox", "m3": "m3-stage-overlay", "m4a": "m4a-platform-awareness",
         "m6b": "m6b-static-analysis-logging", "m7": "m7-integration", "m8": "m8-translation", "m10": "m10-followups"}
CHANGES = (
    "- **The KDE and Hyprland overlay fixes** (`wave5/compositors`, evidence in\n"
    "  [reports/release/compositors/](../../release/compositors/README.md)). `chatmon/layer.py`: when KWin keeps the\n"
    "  keyboard after the overlay lets it go, the surface is made again; what the overlay copies goes on Qt's clipboard\n"
    "  again once one of Qt's windows has the keyboard (KWin refuses Qt's first copy). `chatmon/penguin.py`: while a\n"
    "  button is held on the chatmon or its bubble the whole stage takes the pointer (Hyprland ended a quick drag), and\n"
    "  a screen that moves under the stage is covered where it is now. Their tests are in `tests/test_wayland.py`,\n"
    "  `tests/test_overlay_stage.py` and `tests/test_stage_screens.py`; `tests/test_stage_features.py`'s pretend screen\n"
    "  gains `geometryChanged`. `tests/test_compositors.py` (on `tests/compositor_session.py`) runs sway's checks on a\n"
    "  headless KWin and Hyprland where they're installed, and skips with its reason elsewhere.\n"
    "- **The screen-reader fixes** (`wave5/screen-readers`, evidence in\n"
    "  [reports/release/screen-readers/](../../release/screen-readers/fixes/README.md)). `chatmon/a11y.py`: VoiceOver\n"
    "  is handed what was held, and what is said in Chatmon's first 2.5 s in front, 2.5 s after Chatmon becomes active\n"
    "  (`SETTLE_MS`), because it drops what is posted at that moment. `chatmon/bubble.py`: the ask box's title hands the\n"
    "  keyboard to its field (`setFocusProxy`). `chatmon/clickthrough.py`: the stage's native window is marked\n"
    "  `NonRudeHWND`, so Windows no longer takes Chatmon's own stage for a full-screen app. `chatmon/cli.py` and\n"
    "  `chatmon/macnative.py`: on macOS 14 and later, `chatmon ask` asks for Chatmon to be made the active app once the\n"
    "  box is open. Their tests are in `tests/test_platform_events.py`, `tests/test_ask_box.py`,\n"
    "  `tests/test_clickthrough.py`, `tests/test_presence.py`, `tests/test_cli.py` and `tests/test_macnative.py`.\n"
    "- **The Dependabot replacement** (`wave5/pins`, evidence in [reports/m6a/pins/](../../m6a/pins/README.md)).\n"
    "  `.github/dependabot.yml` keeps only github-actions; `packaging/pins.py`, run each week by\n"
    "  `.github/workflows/pins.yml`, proposes the Python pins' moves; `packaging/requirements-pins.in` and `.txt` lock\n"
    "  the uv it runs; `tests/test_pins.py` (on `tests/fake_uv.py`) tests it, and `tests/test_requirements.py` checks the\n"
    "  new lock too. CONTRIBUTING.md's Dependencies section says so.\n"
    "- **The 0.10.0 notes**: README.md and `chatmon/changelog.md`.\n"
)

PLANS: dict[str, dict[str, str]] = {
    "m0": {
        "name": "M0",
        "ready": (
            "M0-01 to M0-13 and M0-CLI still map both ways to their criteria. T-M0-11, T-M0-12 and T-M0-CLI own\n"
            "`chatmon/cli.py` and `tests/test_cli.py`. `chatmon ask` now keeps `_send`'s answer and, on macOS only, asks\n"
            "for Chatmon to be made active once the box is open; M0-12.A1 (the box opens with the text typed in and the\n"
            "keyboard on it) and M0-12.A2 (Windows' AllowSetForegroundWindow first) ask the same as before, and the macOS\n"
            "step serves A1's \"the keyboard on it\". One drill's line moved with it: M0-12-ask-sent took out the old\n"
            "`return _send(...)`; M0-12-ask-sent-v2 sends the same wrong message type from the new line."
        ),
        "middle": (
            "**One drill re-aimed.** `chatmon ask` keeps `_send`'s answer now (`sent = _send(...)`), so M0-12-ask-sent's\n"
            "text no longer occurs ([wave5/drills-left-out.txt](reports/m0/wave5/drills-left-out.txt)). M0-12-ask-sent-v2\n"
            "makes the same defect in the new line, and the same test fails, so M0-12.A1 keeps its red receipt."
        ),
        "closed": "M0 is closed on 7816159.",
    },
    "m2": {
        "name": "M2",
        "ready": (
            "R-M2-01 to R-M2-20 still map both ways to their 20 criteria. Every task owns `chatmon/bubble.py`, and\n"
            "T-M2-05 to T-M2-07 `tests/test_ask_box.py`. The ask box's title now hands the keyboard to its field\n"
            "(`setFocusProxy`), so a screen reader that moves focus to the title leaves typing in the field. No criterion\n"
            "is about where the title's focus goes; AC-M2-06's outline is drawn round each control that takes the focus,\n"
            "as before, and the title isn't one."
        ),
        "closed": "M2 is closed on 7816159.",
    },
    "m3": {
        "name": "M3",
        "ready": (
            "M3's 28 criteria (scope revision 3) map as in the final round. Ten tasks own the overlay's changed files\n"
            "(`chatmon/layer.py`, `chatmon/penguin.py`, `chatmon/clickthrough.py` and their tests). The KDE and Hyprland\n"
            "fixes add behaviour on compositors no criterion names, and change none of what the criteria ask on sway, on\n"
            "the pretend compositor or on Windows; the `NonRudeHWND` mark changes what Windows reports about Chatmon's\n"
            "stage, not its click-through shape (AC-M3-10-shape). One drill's line moved: M3-RC-clipboard took out\n"
            "`board.setText(text)`, which now occurs twice; M3-RC-clipboard-v2 takes out the same line in `copy()`."
        ),
        "middle_fn": "m3_middle",
        "closed": "M3 is closed on 7816159.",
    },
    "m4a": {
        "name": "M4A",
        "ready": (
            "M4A-01 to M4A-12 still map both ways to their 23 criteria. T-07 and T-10 own `chatmon/a11y.py`, T-04\n"
            "`chatmon/macnative.py`, and T-01, T-03, T-04, T-06, T-07 and T-09 the changed tests. AC-08 (VoiceOver running,\n"
            "Chatmon not the active app: an announcement is held and posted when Chatmon becomes active; with the speech\n"
            "fallback on, spoken at once) still holds as worded: what is held is posted on activation, now after a 2.5 s\n"
            "settle, because the release probe heard VoiceOver drop what is posted at that very moment\n"
            "([reports/release/screen-readers/](../../release/screen-readers/README.md), problem 1). The fallback is\n"
            "unchanged. `macnative.activate_app` is new and serves `chatmon ask` (M0-12), not an M4A criterion."
        ),
        "middle_fn": "m4a_middle",
        "closed": "M4A is closed on 7816159.",
    },
    "m6b": {
        "name": "M6B",
        "ready": (
            "M6B-01 to M6B-03, M6B-RW and M6B-LEFT still map both ways to their 17 criteria. T1-ruff, T3-loggers,\n"
            "T4-mypy, T5-leaks, T6-phase-b and T7-leftovers own the changed files. The new code passes ruff (CI's lint job)\n"
            "and mypy on linux, win32 and darwin with PyQt6 6.11's stubs (CI's types jobs) and 6.12.1's (here and in WSL),\n"
            "with no new `type: ignore` or `noqa` in `chatmon/`; its new loggers' messages follow M6B-03. The M6A and M8\n"
            "plans this plan takes as inputs are re-bound in this round before M6B."
        ),
        "middle": "",
        "closed": "M6B is closed on 7816159.",
    },
    "m7": {
        "name": "M7",
        "ready": (
            "M7-CI, M7-01 to M7-13 and the five INT- requirements still map both ways to their 52 criteria. Seven tasks own\n"
            "changed files (`chatmon/bubble.py`, `chatmon/cli.py`, `chatmon/penguin.py`, `tests/test_cli.py`). AC-11-5's\n"
            "unhosted ask box is now also checked on a headless KWin and Hyprland by `tests/test_compositors.py`, where\n"
            "they're installed (the release's compositor round: 39 passed); the criterion and its sway receipts are as\n"
            "before. AC-M0-10 (only Chatmon's own process allowed to come forward on Windows) is unchanged by the macOS\n"
            "activation step, which runs on macOS only."
        ),
        "closed": "M7 is closed on 7816159.",
    },
    "m8": {
        "name": "M8",
        "ready": (
            "M8-01 still maps to M8-01.A1 through A10. T3-wrap-a and T4-wrap-b own the changed modules; the fixes add no\n"
            "string anyone sees, and `packaging/extract_strings.py --check` finds the template current\n"
            "([reports/wave5/extract-strings-check.log](../../wave5/extract-strings-check.log)). T2-template owns\n"
            "CONTRIBUTING.md, whose translation section is unchanged (only its Dependencies section moved). The M0 and M7\n"
            "plans this plan takes as inputs are re-bound in this round before M8."
        ),
        "closed": "M8 is closed on 7816159.",
    },
    "m10": {
        "name": "M10",
        "ready": (
            "M10-01 to M10-03 still map both ways to their seven criteria. T3-qt612-types owns `chatmon/a11y.py`,\n"
            "`chatmon/bubble.py`, `chatmon/macnative.py` and CONTRIBUTING.md; their new code passes mypy with 6.11's and\n"
            "6.12.1's stubs on every platform, and CONTRIBUTING.md's how-to for the next stubs is unchanged (only its\n"
            "Dependencies section moved). T1-comtypes owns `tests/test_requirements.py`, which now checks the pins lock too.\n"
            "Integration note 2's CI check is the coordinator's from 2026-11-28 (P-CI-NEXT-STUBS) and note 4's upstream\n"
            "report the owner's: neither is a criterion. The M4A, M6A, M6B and M8 plans this plan takes as inputs are\n"
            "re-bound in this round before M10."
        ),
        "middle": (
            "**M10-03.A1 holds on the new code.** mypy with PyQt6 6.12.1's stubs finds no issues on linux, win32 and darwin\n"
            "([wave5/mypy-6121.log](reports/m10/wave5/mypy-6121.log)), and with 6.11's none either\n"
            "([wave5/mypy-611.log](reports/m10/wave5/mypy-611.log)). All five gate drills went green, red and green again\n"
            "([wave5/gate-drills.log](reports/m10/wave5/gate-drills.log)). The how-to was reviewed and replayed in WSL\n"
            "again ([wave5/howto-review.md](reports/m10/wave5/howto-review.md)). The locks (locked again, byte for byte the\n"
            "committed ones), the UI Automation test in the CI-shaped venv and its red drill ran again too, and passed\n"
            "([wave5/locks.log](reports/m10/wave5/locks.log), [wave5/uia-ci-venv.log](reports/m10/wave5/uia-ci-venv.log))."
        ),
        "remains": (
            "**What remains, outside the criteria.** From 2026-11-28, when 6.12.1 can be hash-locked, the `types` job's check\n"
            "against the next stubs (P-CI-NEXT-STUBS, integration note 2): the coordinator. The pins check proposes 6.12.1\n"
            "from that day too (reports/m6a/pins/skip-check.log). The upstream report on PyQt6's stubs (note 4): the owner,\n"
            "with the owner's PyQt mailing-list account."
        ),
        "closed": "",
    },
}


def summary(log: Path) -> str:
    text = log.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"(\d+ passed(?:, \d+ skipped)?(?:, \d+ deselected)?)", text)[-1]


def m3_middle() -> str:
    return (
        "**Linux.** The whole suite in WSL ([wave5/suite-linux.log](reports/wave5/suite-linux.log): "
        + summary(REPORTS / "wave5/suite-linux.log") + ", exit 0), M3's own test files\n"
        "([wave5/m3-tests-linux.log](reports/m3/wave5/m3-tests-linux.log): " + summary(REPORTS / "m3/wave5/m3-tests-linux.log")
        + ") and the real sway's tests\n([wave5/sway-tests-linux.log](reports/m3/wave5/sway-tests-linux.log): "
        + summary(REPORTS / "m3/wave5/sway-tests-linux.log") + ") passed again, as did the overlay's memory\n"
        "check ([wave5/memory-after--window.json](reports/m3/wave5/memory-after--window.json)) and CI's sway job.\n\n"
        "**One drill re-aimed.** The KWin clipboard fix put a second `board.setText(text)` in `chatmon/layer.py`, so\n"
        "M3-RC-clipboard's text occurs twice ([wave5/drills-left-out.txt](reports/m3/wave5/drills-left-out.txt)).\n"
        "M3-RC-clipboard-v2 takes out the same line in `copy()`, found by the comment that follows it, and the same\n"
        "tests fail, so AC-M3-RC-sway keeps its red receipt."
    )


def m4a_middle() -> str:
    return (
        "**Linux and the real readers.** M4A's tests in WSL with PyQt6 6.12.1\n"
        "([wave5/suite-linux-qt612.log](reports/m4a/wave5/suite-linux-qt612.log): " + summary(REPORTS / "m4a/wave5/suite-linux-qt612.log")
        + ") and the real sway's screen-reader\ntests with Orca ([reports/wave5/sway-readers.log](reports/wave5/sway-readers.log): "
        + summary(REPORTS / "wave5/sway-readers.log") + ") passed again. CI's macOS,\nLinux, Windows and GNOME legs were read again."
        " The release round heard the real readers too, which no criterion\nasks: VoiceOver with the fixes on GitHub's macOS"
        " runner, NVDA, and Narrator on testpc2, heard by the owner\n([reports/release/screen-readers/](reports/release/screen-readers/README.md))."
    )


def results(plan: str) -> tuple[int, int, int]:
    win = linux = bad = 0
    for path in sorted((REPORTS / plan / "wave5").glob("*-results.json")):
        if path.name.startswith("gate-") or path.name.startswith("distro-"):
            continue
        for rec in json.loads(path.read_text(encoding="utf-8")):
            if rec.get("status") != "pass":
                bad += 1
            elif "linux" in path.name or "wsl" in path.name:
                linux += 1
            else:
                win += 1
    return win, linux, bad


def gates(plan: str) -> int:
    path = REPORTS / plan / "wave5" / "gate-drills-results.json"
    return sum(r.get("status") == "pass" for r in json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else 0


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
    gate = gates(plan)
    n, of, files = stale(plan)
    suite = summary(REPORTS / "wave5/suite-windows.log")
    parts = ["## Reconciliation, the plans round for v0.10.0 (2026-11-15)", ""]
    parts.append(
        "This round re-bound the plan at **7816159**, v0.10.0's commit: `main` with PR #22 merged (the KDE and Hyprland\n"
        "overlay fixes, the screen-reader fixes and the Dependabot replacement). "
        + f"{n} of its {of} passing receipts went stale, on " + ", ".join(f"`{f}`" for f in files)
        + " ([reports/wave5/stale-at-7816159.md](reports/wave5/stale-at-7816159.md)). Writing this section into the\n"
        "plan changes its prose, which every receipt's scope includes, so the others went stale with it: every check\n"
        "was run again on 7816159 or read from main's CI run of it."
    )
    parts.append("")
    drills = f"{win} Windows drills" + (f" and {linux} Linux ones (in WSL)" if linux else "") + (f", and {gate} gate drills" if gate else "")
    verdict = "Every one went green, red and green again." if not bad else f"{bad} did not: see below."
    parts.append(
        f"**What was re-run.** The whole suite on Windows ([wave5/suite-windows.log](reports/wave5/suite-windows.log): {suite}),\n"
        f"then {drills}. {verdict} main's CI run 43778643147 on 7816159 (all 19 jobs green; each\n"
        "checked out 7816159 itself: [reports/wave5/ci/checkout.txt](reports/wave5/ci/checkout.txt)) was read again\n"
        f"([reports/{plan}/ci/observed-7816159.txt](reports/{plan}/ci/observed-7816159.txt)). The requirements were\n"
        f"reviewed again ([wave5/readiness.md](reports/{plan}/wave5/readiness.md))."
    )
    middle = globals()[info["middle_fn"]]() if info.get("middle_fn") else info.get("middle", "")
    for text in (middle, info.get("remains", "")):
        if text:
            parts += ["", text]
    parts.append("")
    parts.append("**Receipts.** The stale ones are kept as history, with their hashes untouched; the W5- receipts replace\n"
                 f"them. {info['closed']}".rstrip())
    return "\n".join(parts) + "\n"


def readiness(plan: str) -> str:
    info = PLANS[plan]
    return (
        f"# {info['name']} readiness, the plans round for v0.10.0 at 7816159 (2026-11-15)\n\n"
        "The final round's review is in this plan's wave4e/ or wave4f/ folder (at 45a17b3), or round three's in wave4c/\n"
        "(at 3586a0d). Its receipt went stale because files the plan's criteria bind changed. This review re-reads the\n"
        "plan's obligations against the brief and rules as they are now. It is a requirements review, not proof that the\n"
        "code works: the behavior and red receipts are.\n\n"
        "## Inputs read\n\n"
        "- [ASSESSMENT.md](../../../ASSESSMENT.md), [ROADMAP.md](../../../ROADMAP.md) and `pyproject.toml`: unchanged\n"
        "  since round three. The status is in [OUTCOME.md](../../../OUTCOME.md), which no plan binds.\n"
        "- The code and tests, changed from 45a17b3 to 7816159 by PR #18's merge (no file outside docs/) and PR #22's:\n"
        f"{CHANGES}\n"
        "## This plan\n\n"
        f"{info['ready']}\n\n"
        "Result: ready. No requirement is unclear, conflicting or missing failure behavior.\n"
    )


def main() -> int:
    for plan in sys.argv[1:]:
        out = REPORTS / plan / "wave5"
        (out / "readiness.md").write_text(readiness(plan), encoding="utf-8", newline="\n")
        (out / "section.md").write_text(section(plan), encoding="utf-8", newline="\n")
        print(f"{plan}: drills {results(plan)}, gates {gates(plan)}, stale {stale(plan)[:2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
