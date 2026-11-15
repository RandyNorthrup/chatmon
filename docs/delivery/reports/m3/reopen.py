"""M3's scope revision 3, written into the plan's quality ledger (docs/delivery/m3-stage-overlay.md).

usage: python docs/delivery/reports/m3/reopen.py structure
       python docs/delivery/reports/m3/reopen.py readiness
       python docs/delivery/reports/m3/reopen.py bind

- structure: the revision's records (M3-RC, four criteria, four tasks, the work's inputs); every earlier receipt that
  still claimed a pass marked stale (later milestones and this revision changed the files they fingerprint), and
  every earlier task back to implemented until it's proved again; no checkpoint.
- readiness: the readiness receipt for readiness-r3.md, bound to the validator's snapshot of every criterion.
- bind: one receipt per run named in RUNS and per drill that went green, red and green in DRILLS, each bound to the
  validator's snapshot of the criteria it covers as they are now; each task verified that has its criteria's
  behavior and red proof; the checkpoint, from the snapshot of everything.

Each step writes a candidate plan next to this script (candidate.md) and applies it with the skill's
update-delivery.py against the digest it read, so a writer that got there first is refused, never overwritten.
Nothing here runs a check: the logs it binds come from real runs of the commands they name.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = "docs/delivery/m3-stage-overlay.md"
REPORTS = "docs/delivery/reports/m3"
SKILL = Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts"
FENCE = "```quality-ledger"
STALE_REASON = ("Its fingerprinted files changed after it ran (M6B, M7, M8, M10 and scope revision 3 edited them): proved again on the "
                "current source by the EV-r3-* receipts")
WSL = ["wsl.exe", "-d", "archlinux", "--", "/var/tmp/wayland-venv/bin/python"]

NEW_REQUIREMENT = {
    "id": "M3-RC",
    "statement": "The overlay is proven on a real compositor, in WSL and in CI, and what that finds broken is fixed: the layer surface maps and draws, takes clicks only where it draws, has the keyboard only while the ask box or its menu is open, its menus work, the clipboard goes both ways, it gives way to full-screen windows and comes back on the screen that's left",
    "priority": "critical",
    "acceptance": ["AC-M3-RC-sway"],
    "superseded_by": None,
}

NEW_ACCEPTANCE = [
    {
        "id": "AC-M3-04-content",
        "requirement": "M3-04",
        "given": "The overlay on a compositor with wl_subcompositor and wp_viewporter: the pretend compositor at a scale of 2, and a headless sway at 3840x2160 and scale 2, and at 2560x1440 and scale 1.5",
        "when": "The stage draws the chatmon, a bubble, the ask box and a menu, moves the chatmon a little and far, and draws nothing; and the chatmon is dragged across sway's output",
        "then": "The layer surface holds one stretched see-through pixel; what's drawn is on a subsurface the size of the stage's extent plus a 32 px margin, on whole device pixels, with no input region; at most 2 content buffers, each a tenth of the output's pixels or less; a far move sends position and repainted pixels in one parent commit and waits for a free buffer; nothing drawn unmaps it; on sway the chatmon is drawn once where the stage put it, with no trail, in every frame of the drag; memory.py measures the buffers before and after at 4K",
        "checks": ["behavior", "red"],
        "manual_reason": None,
    },
    {
        "id": "AC-M3-14-sway",
        "requirement": "M3-14",
        "given": "A whole Chatmon on a headless sway with a screen reader running (Orca's remote controller on the session bus, accessibility on), and the ask box unhosted",
        "when": "The chatmon is clicked, keys are typed, a bubble is shown, the penguin is right-clicked with the box open and its menu driven from the keyboard, and the box's field is right-clicked",
        "then": "The box is a window sway floats, centres on the output and focuses, and the keys go to its field; the bubble stays off the box's real place; the penguin's menu, drawn on the overlay, takes the keyboard (the box gets none of its keys) and gives it back to the box as it closes; the field's own menu is Qt's popup; on Qt's offscreen platform the penguin's menu likewise takes and gives back the keyboard, and a bubble keeps clear of a box only where its geometry is real",
        "checks": ["behavior", "red"],
        "manual_reason": None,
    },
    {
        "id": "AC-M3-14-atspi",
        "requirement": "M3-14",
        "given": "That sway session with AT-SPI's registry (and Orca 51 where it's installed)",
        "when": "The box opens unhosted, and, for contrast, drawn on the overlay (Settings' accessible ask box off); an answer is shown; keys are typed; a bubble is said",
        "then": "Through libatspi: the box window with its title, its field (role text, named for the box, with its hint, its text and focus), its buttons and check box by name, and the conversation's words; window:activate and a focused field when unhosted, no window:activate when drawn on the overlay; the conversation's change heard as object:text-changed:insert; with Orca, the bubble said through PresentMessage and spoken, the unhosted box announced and its typing echoed, the hosted one neither",
        "checks": ["behavior", "red"],
        "manual_reason": None,
    },
    {
        "id": "AC-M3-RC-sway",
        "requirement": "M3-RC",
        "given": "A whole Chatmon on a headless sway of the test's own, with a virtual pointer and keyboard, a plain window under the overlay where a test needs one",
        "when": "It starts; clicks land off the chatmon, on its see-through frame and on it; keys are typed before, while and after the ask box is open; the penguin's menu is opened and driven; text is copied both ways with another app and read by Chatmon's own window; a window goes full screen; a second output is added and the first removed",
        "then": "The overlay is a configured layer surface, not a window in sway's tree, and sway draws the chatmon there and nothing elsewhere; only the click on the chatmon is the overlay's; the keyboard is the overlay's only while the box is open (taken back and kept exclusive where the compositor drops it on the handover to on_demand); the menu is drawn, its keys and Enter work, a click elsewhere closes it and stops there; the clipboard reaches the box and other apps, and Chatmon's own window reads it at once; it's under a full-screen window, above it with the ask box, under it again after; it comes back on the output that's left; in CI's sway job the same tests run, failing on any skip but Orca's",
        "checks": ["behavior", "red"],
        "manual_reason": None,
    },
]

NEW_TASKS = [
    {
        "id": "T-M3-sway-bed",
        "purpose": "The real-compositor test bed (a headless sway, its input devices, a whole Chatmon on it, AT-SPI and Orca) and its CI job",
        "acceptance": ["AC-M3-RC-sway", "AC-M3-14-atspi"],
        "depends_on": [],
        "changes": [
            {"path": "tests/sway_session.py", "action": "create"},
            {"path": "tests/test_sway.py", "action": "create"},
            {"path": ".github/workflows/ci.yml", "action": "modify"},
        ],
    },
    {
        "id": "T-M3-sway-fixes",
        "purpose": "What the test bed found broken in layer.py on sway: the keyboard lost on the handover to on_demand, and a copy that froze Chatmon's own windows",
        "acceptance": ["AC-M3-RC-sway"],
        "depends_on": ["T-M3-sway-bed"],
        "changes": [
            {"path": "chatmon/layer.py", "action": "modify"},
            {"path": "tests/test_wayland.py", "action": "modify"},
        ],
    },
    {
        "id": "T-M3-content",
        "purpose": "M3-04's second half: buffers the size of what's shown, on a synchronized subsurface the stage's extent sizes",
        "acceptance": ["AC-M3-04-content"],
        "depends_on": ["T-M3-buffers", "T-M3-sway-bed"],
        "changes": [
            {"path": "chatmon/layer.py", "action": "modify"},
            {"path": "chatmon/penguin.py", "action": "modify"},
            {"path": "tests/test_wayland.py", "action": "modify"},
            {"path": "tests/test_overlay_stage.py", "action": "modify"},
        ],
    },
    {
        "id": "T-M3-unhosted-sway",
        "purpose": "M3-14 on sway: the penguin's menu takes the keyboard with the box a window, and bubbles keep off a box whose place only the compositor knows",
        "acceptance": ["AC-M3-14-sway", "AC-M3-14-atspi"],
        "depends_on": ["T-M3-stage-features", "T-M3-sway-bed"],
        "changes": [
            {"path": "chatmon/penguin.py", "action": "modify"},
            {"path": "tests/test_overlay_stage.py", "action": "modify"},
        ],
    },
]

NEW_INPUTS = [  # what else these checks depend on: the hosting decision, the test bed's own helpers, the tools that ran them
    "chatmon/app.py", "tests/app_harness.py", "tests/fake_orca.py",
    "docs/delivery/reports/m3/memory.py", "docs/delivery/reports/m3/memory-run.sh",
    "docs/delivery/reports/m3/wslrun.sh", "docs/delivery/reports/m3/wslvenv.py",
]

# The runs bound as behavior receipts: (id, artifact, command, acceptance (None: what the old receipt covered, plus), method).
SUITE = ["-m", "pytest", "-q", "-p", "no:cacheprovider"]
NEW_ACS = [a["id"] for a in NEW_ACCEPTANCE]
RUNS = [
    ("EV-r3-tests-windows", f"{REPORTS}/gates/full-suite-windows-r3.log", ["python", *SUITE], ("EV-tests-windows", []),
     "The whole suite on Windows on the final source (real Qt objects, offscreen; the Linux-only tests skip with their reason), which runs every Windows-side test of these criteria; the log ends with its counts and no failure"),
    ("EV-r3-tests-linux", f"{REPORTS}/gates/full-suite-linux.log", [*WSL, *SUITE], ("EV-tests-linux", NEW_ACS),
     "The whole suite in WSL (Arch, sway 1.12, Python 3.14.9, PyQt6 6.11 from requirements-test.txt, through reports/m3/wslrun.sh) on the final source, test_sway.py's real-compositor tests included and none of them skipped; the log ends with its counts and no failure"),
    ("EV-r3-sway", f"{REPORTS}/gates/sway-tests-linux.log", [*WSL, "-m", "pytest", "-p", "no:cacheprovider", "-v", "-rs", "tests/test_sway.py", "tests/test_wayland.py"], (None, NEW_ACS),
     "test_sway.py and test_wayland.py on their own in WSL, verbose: every real-compositor test by name, each passed, none skipped (Orca 51 installed)"),
    ("EV-r3-memory", f"{REPORTS}/memory-after--window.json", ["wsl.exe", "-d", "archlinux", "--", "bash", f"{REPORTS}/memory-run.sh"], (None, ["AC-M3-04-content"]),
     "memory-run.sh: memory.py on a headless sway at 3840x2160 and scale 2, with a window under the overlay, on this source and on fb19cb9's: "
     "the overlay's buffers at each moment, 1.1 to 7.4 MB in one or two buffers here against one or two of 3840x2160 (31.6 to 63.3 MB) there "
     "(memory-before--window.json, and gates/memory-summary.log for all four runs)"),
]

# Each drill, and the criteria its tests guard (the spec's ids; the earlier ones as revision 2 bound them).
DRILLS = {
    f"{REPORTS}/drills-r3-results.json": {
        "M3-01-idle": ["AC-M3-01-idle"], "M3-01-missed": ["AC-M3-01-idle"], "M3-01-quiet": ["AC-M3-01-quiet"],
        "M3-01-pointer": ["AC-M3-01-pointer"], "M3-02-refresh": ["AC-M3-02-refresh"], "M3-02-pixels": ["AC-M3-02-pixels"],
        "M3-02-drag": ["AC-M3-02-drag"], "M3-03-once": ["AC-M3-03-once"], "M3-03-cache": ["AC-M3-03-cache"],
        "M3-05-keys": ["AC-M3-05-keys"], "M3-05-route": ["AC-M3-05-keys"], "M3-05-focus": ["AC-M3-05-focus"],
        "M3-05-outline": ["AC-M3-05-focus"], "M3-06-scroll": ["AC-M3-06-scroll"], "M3-06-hover": ["AC-M3-06-hover"],
        "M3-07-contrast": ["AC-M3-07-contrast"], "M3-08-rows": ["AC-M3-08-rows"], "M3-10-shape": ["AC-M3-10-shape"],
        "M3-11-still": ["AC-M3-11-still"], "M3-11-zs": ["AC-M3-11-still"], "M3-12-hold": ["AC-M3-12-hold"],
        "M3-13-badge": ["AC-M3-13-badge"], "M3-14-unhosted": ["AC-M3-14-unhosted"], "M3-15-follow": ["AC-M3-15-follow"],
        "M3-M2-hover": ["AC-M3-M2-stage"], "M3-M2-link": ["AC-M3-M2-stage"], "M3-M2-ring": ["AC-M3-M2-stage"],
    },
    f"{REPORTS}/drills-linux-r3-results.json": {
        "M3-04-buffers": ["AC-M3-04-buffers"], "M3-04-trim": ["AC-M3-04-buffers"], "M3-09-latin": ["AC-M3-09-latin"],
        "M3-09-overlay": ["AC-M3-09-overlay"], "M3-10-xserver": ["AC-M3-10-shape"],
    },
    f"{REPORTS}/drills-wayland-results.json": {
        "M3-14-menu-keys": ["AC-M3-14-sway"], "M3-14-bubble-clear": ["AC-M3-14-sway"], "M3-04-extent": ["AC-M3-04-content"],
    },
    f"{REPORTS}/drills-wayland-linux-results.json": {
        "M3-04-content": ["AC-M3-04-content"], "M3-04-move-waits": ["AC-M3-04-content"], "M3-04-placed": ["AC-M3-04-content"],
        "M3-RC-input": ["AC-M3-RC-sway"], "M3-RC-keyboard": ["AC-M3-RC-sway"], "M3-RC-clipboard": ["AC-M3-RC-sway"],
        "M3-14-sway-menu": ["AC-M3-14-sway"], "M3-14-sway-bubble": ["AC-M3-14-sway"], "M3-14-hosting": ["AC-M3-14-sway", "AC-M3-14-atspi"],
    },
}

PENDING = [{
    "id": "CI-sway-job",
    "description": "The new CI job `sway` (ubuntu-24.04: sway 1.9, grim, wl-clipboard, dbus, AT-SPI) has run only here, in WSL with sway 1.12; its first run on GitHub is the coordinator's push away",
    "next_action": "After the coordinator pushes wave4/wayland, read the `sway` job; a failure there (Ubuntu's sway 1.9 or AT-SPI 2.52 behaving otherwise) comes back to M3; once green, add it to main's required checks",
}]


def run(argv: list[str]) -> str:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=True, encoding="utf-8").stdout


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_plan() -> tuple[str, dict, str]:
    text = (ROOT / PLAN).read_text(encoding="utf-8")
    start = text.index(FENCE)
    body_start = text.index("\n", start) + 1
    end = text.index("```", body_start)
    return text[:start], json.loads(text[body_start:end]), text[end + 3 :]


def apply(before: str, ledger: dict, after: str) -> None:
    candidate = HERE / "candidate.md"
    candidate.write_text(f"{before}{FENCE}\n{json.dumps(ledger, indent=2, ensure_ascii=False)}\n```{after}", encoding="utf-8", newline="\n")
    expected = digest(ROOT / PLAN)
    out = subprocess.run([sys.executable, str(SKILL / "update-delivery.py"), "--root", ".", "--plan", PLAN, "--candidate",
                          f"{REPORTS}/candidate.md", "--expected-sha256", expected], cwd=ROOT, capture_output=True, text=True, check=False)
    print(out.stdout + out.stderr)
    candidate.unlink()
    if out.returncode:
        raise SystemExit(out.returncode)


def snapshot(acceptance: list[str] | None = None) -> dict:
    argv = [sys.executable, str(SKILL / "verify-delivery.py"), "--root", ".", "--plan", PLAN, "--snapshot"]
    return json.loads(run(argv + (["--acceptance", *acceptance] if acceptance else [])))


def structure() -> None:
    before, ledger, after = read_plan()
    work = ledger["work"]
    work["scope_revision"] = 3
    revision = run(["git", "rev-parse", "--short", "HEAD"]).strip()
    for rule in work["rules"]:
        rule["revision"] = revision
    work["inputs"] = sorted(set(work["inputs"]) | set(NEW_INPUTS))
    reqs = {r["id"]: r for r in ledger["requirements"]}
    reqs["M3-04"]["acceptance"] = [*reqs["M3-04"]["acceptance"], "AC-M3-04-content"]
    reqs["M3-14"]["acceptance"] = [*reqs["M3-14"]["acceptance"], "AC-M3-14-sway", "AC-M3-14-atspi"]
    if "M3-RC" not in reqs:
        ledger["requirements"].append(NEW_REQUIREMENT)
    known = {a["id"] for a in ledger["acceptance"]}
    ledger["acceptance"] += [a for a in NEW_ACCEPTANCE if a["id"] not in known]
    tasks = {t["id"] for t in ledger["tasks"]}
    ledger["tasks"] += [{**t, "status": "implemented", "evidence": [], "blocker": None, "superseded_by": None} for t in NEW_TASKS if t["id"] not in tasks]
    for task in ledger["tasks"]:
        # Proved again in bind, on the current source; until then a task waiting on another is planned, as the
        # ledger wants a task done only once what it depends on is verified.
        task["status"] = "planned" if task["depends_on"] else "implemented"
    for receipt in ledger["evidence"]:
        if receipt["status"] == "pass":
            receipt["status"], receipt["reason"] = "stale", STALE_REASON
    ledger["checkpoint"] = None
    apply(before, ledger, after)


def receipt(rid: str, kind: str, artifact: str, acceptance: list[str], command: list[str], method: str, red: dict | None = None) -> dict:
    snap = snapshot(acceptance)
    return {
        "id": rid, "acceptance": acceptance, "kind": kind, "status": "pass",
        "command": command if kind != "readiness" else [], "method": method,
        "environment": snap["declared_environment"], "exit_code": None if kind == "readiness" else 0,
        "artifact": {"path": artifact, "sha256": digest(ROOT / artifact)},
        "inputs": snap["inputs"]["readiness" if kind == "readiness" else "behavior"],
        "scope_sha256": snap["scope_sha256"], "red": red, "reason": None,
    }


def add(ledger: dict, new: dict) -> None:
    ledger["evidence"] = [e for e in ledger["evidence"] if e["id"] != new["id"]] + [new]


def readiness() -> None:
    before, ledger, after = read_plan()
    every = [a["id"] for a in ledger["acceptance"]]
    add(ledger, receipt("EV-readiness-3", "readiness", f"{REPORTS}/readiness-r3.md", every, [],
                        "Requirements review of scope revision 3 (M3-04's second half, M3-14 on a real compositor, the new M3-RC) against the brief, "
                        "the rules, the owner's direction and the coordinator's scope, with every earlier criterion re-read for coverage (readiness-r3.md)"))
    apply(before, ledger, after)


def red_receipt(results: str, record: dict, acceptance: list[str]) -> dict:
    drilled = record["file"]
    log = results.replace("-results.json", ".log")
    red = {
        "mutation": f"{record['id']}: in {drilled}, {record['mutation']['find']!r} became {record['mutation']['replace']!r}",
        "baseline_exit": record["baseline_exit"], "mutated_exit": record["mutated_exit"], "restored_exit": record["restored_exit"],
        "expected_diagnostic": next((e for e in record["expected"] if e in record["observed"]), record["expected"][0]),
        "observed_diagnostic": record["observed"],
        "before": [{"path": drilled, "sha256": record["before_sha256"]}],
        "mutated": [{"path": drilled, "sha256": record["mutated_sha256"]}],
        "after": [{"path": drilled, "sha256": record["after_sha256"]}],
    }
    where = "in WSL through reports/m3/wslvenv.bat" if "linux" in results else "on Windows"
    method = (f"Red drill {record['id']} through tests/drills/run.py {where}, in a temporary copy: green, the defect put in, the named tests "
              "failing for that reason, the file's bytes put back and green again")
    return receipt(f"EV-r3-red-{record['id']}", "red", log, acceptance, record["command"], method, red)


def bind() -> None:
    before, ledger, after = read_plan()
    old = {e["id"]: e for e in ledger["evidence"]}
    made: list[dict] = []
    for rid, artifact, command, (like, more), method in RUNS:
        acceptance = sorted(set(old[like]["acceptance"] if like else []) | set(more))
        made.append(receipt(rid, "behavior", artifact, acceptance, command, method))
    for results, mapping in DRILLS.items():
        records = {r["id"]: r for r in json.loads((ROOT / results).read_text(encoding="utf-8"))}
        for drill, acceptance in mapping.items():
            record = records.get(drill)
            if record is None or record.get("status") != "pass":
                raise SystemExit(f"{drill} in {results} didn't go green, red, green: {record and record.get('reason')}")
            made.append(red_receipt(results, record, acceptance))
    for new in made:
        add(ledger, new)
    criteria = {a["id"]: a for a in ledger["acceptance"]}
    verified = []
    for task in ledger["tasks"]:
        mine = [e["id"] for e in made if set(e["acceptance"]) & set(task["acceptance"])]
        task["evidence"] = [*[e for e in task["evidence"] if e not in mine], *mine]
        proved = all(any(e["kind"] == kind and ac in e["acceptance"] for e in made if e["id"] in mine)
                     for ac in task["acceptance"] for kind in criteria[ac]["checks"])
        task["status"] = "verified" if proved else "implemented"
        if proved:
            verified.append(task["id"])
    snap = snapshot()
    ledger["checkpoint"] = {
        "scope_sha256": snap["scope_sha256"], "inputs": snap["inputs"]["behavior"], "environment": snap["declared_environment"],
        "verified_tasks": verified, "pending_operations": PENDING,
        "next_action": "Coordinator: push wave4/wayland and read the new `sway` CI job (pending operation CI-sway-job); add it to main's required checks once green. "
                       "Owners named in the Integration notes: a11y.py (ScreenReaderEnabled gone in at-spi2-core 2.62), menus.py (\"Help && updates\"), "
                       "and speaking the drawn penguin menu's items to a screen reader.",
        "source_revision": run(["git", "rev-parse", "HEAD"]).strip(),
    }
    apply(before, ledger, after)
    unproved = [t["id"] for t in ledger["tasks"] if t["status"] != "verified"]
    print(f"{len(made)} receipts; tasks not verified: {unproved or 'none'}")


if __name__ == "__main__":
    {"structure": structure, "readiness": readiness, "bind": bind}[sys.argv[1]]()
