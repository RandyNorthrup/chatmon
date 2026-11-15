"""Bind M10's runs to its ledger: python docs/delivery/reports/m10/bind.py [--final] (from the worktree root)

Builds the receipts from logs of real runs, each bound to the validator's snapshot of the criteria it covers as they
are now, for every log that exists: the readiness review, the lock tests, the UI Automation test in a CI-shaped venv,
the Qt translation tests, mypy with each stub, the whole suite, the how-to review, the pytest drills and the gate
drills. Marks verified each task whose criteria all have their declared kinds of passing receipt; with --final,
writes the checkpoint. Writes the candidate plan (reports/m10/candidate.md) for update-delivery.py. Nothing is run
here but the validator's snapshot: each log must come from the command its receipt names.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
REL = "docs/delivery/reports/m10"
PLAN = "docs/delivery/m10-followups.md"
VALIDATOR = Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py"
PY = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
NEXT = "%TEMP%/m10-qt6121/Scripts/python.exe"  # the throwaway venv with PyQt6 6.12.1's stubs
CI_VENV = "%TEMP%/m10-ci-test/Scripts/python.exe"  # the throwaway venv installed as CI's Windows legs install


def digest(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def snapshot(acceptance: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(VALIDATOR), "--root", ".", "--plan", PLAN, "--snapshot"] + (["--acceptance", *acceptance] if acceptance else [])
    return json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)  # noqa: S603 - the validator, fixed


def receipt(ident: str, kind: str, acceptance: list[str], artifact: str, method: str, command: list[str] | None = None, red: dict | None = None) -> dict:
    snap = snapshot(acceptance)
    static = kind in ("readiness", "manual")
    return {
        "id": ident, "acceptance": acceptance, "kind": kind, "status": "pass",
        "command": [] if static else command, "method": method,
        "environment": snap["declared_environment"], "exit_code": None if static else 0,
        "artifact": {"path": artifact, "sha256": digest(artifact)},
        "inputs": snap["inputs"]["readiness" if kind == "readiness" else "behavior"],
        "scope_sha256": snap["scope_sha256"], "red": red, "reason": None,
    }


def red_from(record: dict, expected: str, mutation: str) -> dict:
    drilled = record["file"]
    return {
        "mutation": mutation,
        "baseline_exit": record["baseline_exit"], "mutated_exit": record["mutated_exit"], "restored_exit": record["restored_exit"],
        "expected_diagnostic": expected, "observed_diagnostic": record["observed"],
        "before": [{"path": drilled, "sha256": record["before_sha256"]}],
        "mutated": [{"path": drilled, "sha256": record["mutated_sha256"]}],
        "after": [{"path": drilled, "sha256": record["after_sha256"]}],
    }


def drill_receipts(spec_name: str, results_name: str, log_name: str) -> list[dict]:
    """A red receipt for each drill of one harness run that went green, red and green."""
    if not (HERE / results_name).exists():
        return []
    spec = {d["id"]: d for d in json.loads((HERE / spec_name).read_text(encoding="utf-8"))["drills"]}
    out = []
    for record in json.loads((HERE / results_name).read_text(encoding="utf-8")):
        if record["status"] != "pass":
            continue
        drill = spec[record["id"]]
        expected = next((e for e in drill["expect"] if e in record["observed"]), drill["expect"][0])
        out.append(receipt(
            f"E-red-{record['id']}", "red", [drill["requirement"]], f"{REL}/{log_name}",
            f"Red drill {record['id']} through tests/drills/run.py in a temporary copy: green, {drill['file']} mutated once and the named "
            "tests failed with pytest's tests-failed exit for the intended reason (the log shows the assertion), the file's bytes put back "
            "(SHA-256 checked) and green again.",
            record["command"],
            red_from(record, expected, f"{record['id']}: in {drill['file']}, {drill['find']!r} became {drill['replace']!r}"),
        ))
    return out


def gate_receipts() -> list[dict]:
    if not (HERE / "gate-drills-results.json").exists():
        return []
    out = []
    for record in json.loads((HERE / "gate-drills-results.json").read_text(encoding="utf-8")):
        if record["status"] != "pass":
            continue
        out.append(receipt(
            f"E-red-gate-{record['id']}", "red", ["M10-03.A1"], f"{REL}/gate-drills.log",
            f"Gate drill {record['id']} (gate_drills.py) in a temporary copy of chatmon/ and pyproject.toml: mypy with {record['stubs']} "
            f"green, then failing on one change and naming {record['expected']}, then green again with the file's bytes put back.",
            [PY, f"{REL}/gate_drills.py"],
            red_from(record, record["expected"], f"{record['id']}: in {record['file']}, {record['mutation']}"),
        ))
    return out


# (id, kind, acceptance, log, method, command): included once the log exists.
RUNS = [
    ("E-readiness", "readiness", None, "readiness.md",
     "Requirements review of the three follow-ups against M4A's, M6B's and M8's notes, the roadmap's rules and the wave-4 brief: each "
     "re-checked on fb19cb9 (the locked Nuitka's and PyInstaller's sources read, mypy run with 6.12.0's and 6.12.1's stubs), decisions "
     "D1-D19, failure behaviour, terms, coverage and the files left to the wayland worker (readiness.md).", None),
    ("E-locks", "behavior", ["M10-01.A1"], "locks.log",
     "The lock tests on the final tree, after locking the test and dev lists again with the documented uv command: every lock pinned and "
     "hashed, at its .in file's versions, one version per package, the dev extra in step, and comtypes for Windows alone; the log also "
     "shows the relock's diff against fb19cb9 (comtypes and its header line only).",
     [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_requirements.py"]),
    ("E-uia-ci-venv", "behavior", ["M10-01.A2"], "uia-ci-venv.log",
     "A fresh venv from C:\\Python314, installed from packaging/requirements-test.txt with --require-hashes as CI's Windows legs install "
     "it (comtypes 1.4.17 among them), runs the UI Automation end-to-end test on the final tree with -rs: it runs, not skipped, and passes.",
     [CI_VENV, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "tests/test_platform_events.py::test_a_ui_automation_client_hears_the_announcement"]),
    ("E-qt-translations", "behavior", ["M10-02.A1", "M10-02.A2"], "qt-translations.log",
     "The build's and i18n's tests on the final tree, real Qt (6.11.2) offscreen: build.py's Nuitka options and PyInstaller data files for a "
     "temporary locale folder, English alone and with throwaway de.po and pt.po, and i18n.setup in a frozen app's layout, frozen and not.",
     [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_packaging.py", "tests/test_i18n.py"]),
    ("E-mypy-611", "behavior", ["M10-03.A1"], "mypy-611.log",
     "mypy for linux, win32 and darwin on the final tree with the shared venv's PyQt6 6.11.0 stubs (CI's lock) and pyproject.toml's settings, "
     "no module exempted: no issues in 70 files on each.",
     [PY, f"{REL}/mypy_runs.py", PY, f"{REL}/mypy-611.log"]),
    ("E-mypy-6121", "behavior", ["M10-03.A1"], "mypy-6121.log",
     "mypy for linux, win32 and darwin on the final tree with the throwaway venv's PyQt6 6.12.1 stubs: the only errors left are in the "
     "wayland worker's layer.py and penguin.py (integration note), none in any other module.",
     [PY, f"{REL}/mypy_runs.py", NEXT, f"{REL}/mypy-6121.log"]),
    ("E-mypy-6121-copy", "behavior", ["M10-03.A1"], "mypy-6121-wayland-copy.log",
     "The same mypy runs with PyQt6 6.12.1's stubs on a scratch copy of the final tree with the integration note's changes to layer.py and "
     "penguin.py applied (wayland-files-qt6121.diff): no issues on any platform; and with 6.11's stubs on that copy, none either.",
     [PY, f"{REL}/mypy_runs.py", NEXT, f"{REL}/mypy-6121-wayland-copy.log", "--root", "<scratch copy>"]),
    ("E-suite", "behavior", ["M10-01.A1", "M10-02.A1", "M10-02.A2", "M10-03.A2"], "suite-final.log",
     "The whole suite on the final tree in the shared venv (real Qt objects offscreen, every warning an error): it runs the lock tests, the "
     "build's and i18n's new tests, and every test of a module whose signals moved to chatmon/qtsignal.py.",
     [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
    ("E-howto", "manual", ["M10-03.A3"], "howto-review.md",
     "Review of CONTRIBUTING.md's how-to for the next stubs and of the integration note's CI entry, line by line against the commands this "
     "work ran (mypy_runs.py with the throwaway venv; uv's compile with and without --exclude-newer) and the logs they wrote.", None),
]


def main() -> int:
    final = "--final" in sys.argv[1:]
    text = (ROOT / PLAN).read_text(encoding="utf-8")
    match = re.search(r"```quality-ledger\n(.*?)\n```", text, re.S)
    ledger = json.loads(match.group(1))
    every = [a["id"] for a in ledger["acceptance"]]
    receipts = [
        receipt(ident, kind, acceptance or every, f"{REL}/{log}", method, command)
        for ident, kind, acceptance, log, method, command in RUNS if (HERE / log).exists()
    ]
    receipts += drill_receipts("drill-spec.json", "drills-results.json", "drills.log")
    receipts += drill_receipts("drill-spec-ci-venv.json", "drills-ci-venv-results.json", "drills-ci-venv.log")
    receipts += gate_receipts()
    # A passing receipt already in the ledger that this run binds again to a changed scope stays, as stale history.
    fresh = {r["id"]: r for r in receipts}
    history = [r for r in ledger["evidence"] if r["status"] == "stale"]
    for old in ledger["evidence"]:
        new = fresh.get(old["id"])
        if old["status"] == "pass" and new is not None and new["scope_sha256"] != old["scope_sha256"]:
            history.append(dict(old, id=f"{old['id']}.{old['scope_sha256'][:8]}", status="stale",
                                reason="Bound to an earlier scope (the plan or a file it covers changed since); the check was run or "
                                       f"reviewed again on the current scope as {old['id']}. Next action: none."))
    by_ac: dict[str, set[str]] = {}
    for r in receipts:
        for a in r["acceptance"]:
            by_ac.setdefault(a, set()).add(r["kind"])
    checks = {a["id"]: set(a["checks"]) for a in ledger["acceptance"]}
    for task in ledger["tasks"]:
        task["evidence"] = sorted({r["id"] for r in receipts if set(r["acceptance"]) & set(task["acceptance"]) and r["kind"] != "readiness"})
        if all(checks[a] <= by_ac.get(a, set()) for a in task["acceptance"]):
            task["status"] = "verified"
        elif task["evidence"]:
            task["status"] = "implemented"
    ledger["evidence"] = receipts + [r for r in history if r["id"] not in fresh]
    if final:
        snap = snapshot()
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None  # noqa: S607 - git, fixed
        ledger["checkpoint"] = {
            "scope_sha256": snap["scope_sha256"], "inputs": snap["inputs"]["behavior"], "environment": snap["declared_environment"],
            "verified_tasks": sorted(t["id"] for t in ledger["tasks"] if t["status"] == "verified"),
            "pending_operations": [],
            "next_action": "Coordinator: apply the layer.py and penguin.py changes in the integration note after the wayland worker merges, "
                           "and add the 6.12.1 types entry to ci.yml once 6.12.1 is two weeks old (2026-11-28).",
            "source_revision": revision,
        }
    out = text[: match.start(1)] + json.dumps(ledger, indent=2, ensure_ascii=False) + text[match.end(1):]
    (HERE / "candidate.md").write_text(out, encoding="utf-8", newline="\n")
    print(f"{len(receipts)} receipts; tasks: " + ", ".join(f"{t['id']} {t['status']}" for t in ledger["tasks"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
