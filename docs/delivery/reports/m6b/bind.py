"""Bind M6B's runs to its ledger: python docs/delivery/reports/m6b/bind.py (from the worktree root)

Builds the receipts from logs of real runs (the whole suite, ruff, mypy, the template check, the pytest drills and
the gate drills), each bound to the validator's snapshot of the criteria it covers as they are now; marks verified
each phase-A task whose criteria all have passing behaviour and red receipts; writes the checkpoint; and writes the
candidate plan (reports/m6b/candidate.md) for update-delivery.py. Nothing is run here but the validator's snapshot:
the logs must come from the commands they name.
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
REL = "docs/delivery/reports/m6b"
PLAN = "docs/delivery/m6b-static-analysis-logging.md"
VALIDATOR = Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py"
PY = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
TASKS = ["T1-ruff", "T2-log", "T3-loggers", "T4-mypy", "T5-leaks", "T6-phase-b", "T7-leftovers"]
STATIC = {"M6B-01.A1", "M6B-01.A3", "M6B-02.A1", "M6B-02.A3"}  # what ruff and mypy check, not the suite


def digest(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def snapshot(acceptance: list[str] | None = None) -> dict:
    cmd = [sys.executable, str(VALIDATOR), "--root", ".", "--plan", PLAN, "--snapshot"] + (["--acceptance", *acceptance] if acceptance else [])
    return json.loads(subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout)  # noqa: S603 - the validator, fixed


def receipt(ident: str, kind: str, acceptance: list[str], artifact: str, method: str, command: list[str] | None = None, red: dict | None = None) -> dict:
    snap = snapshot(acceptance)
    return {
        "id": ident, "acceptance": acceptance, "kind": kind, "status": "pass",
        "command": [] if kind == "readiness" else command, "method": method,
        "environment": snap["declared_environment"], "exit_code": None if kind == "readiness" else 0,
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


def main() -> int:
    text = (ROOT / PLAN).read_text(encoding="utf-8")
    match = re.search(r"```quality-ledger\n(.*?)\n```", text, re.S)
    ledger = json.loads(match.group(1))
    every = [a["id"] for a in ledger["acceptance"]]
    tested = [a for t in ledger["tasks"] if t["id"] in TASKS for a in t["acceptance"]]
    receipts = [
        receipt("E-readiness", "readiness", every, f"{REL}/readiness.md",
                "Requirements review of M6B-01..03 and M6A's note 4 against the assessment, the roadmap's rules, the wave-3 brief "
                "and the coordinator's two added rules: the findings re-checked on dd2e375, decisions D1-D17, failure behaviour, "
                "terms and coverage; then phase B's and the leftovers' (M6B-LEFT), re-checked on 210c6e0, decisions D18-D23 (readiness.md)."),
        receipt("E-suite", "behavior", sorted(set(tested) - STATIC), f"{REL}/suite-final.log",
                "The whole suite on the final source (exported from the index into a scratch folder, real Qt objects offscreen), every "
                "warning an error, ResourceWarning too: 1241 passed, 148 skipped; it runs test_log.py, test_imports.py and every test the "
                "drills name.",
                [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
        receipt("E-template", "behavior", ["M6B-01.A2"], f"{REL}/template.log",
                "The string extractor's check on the final source: the template is what the code says (phase B's two new sentences in it).",
                [PY, "packaging/extract_strings.py", "--check"]),
        receipt("E-ruff", "behavior", ["M6B-01.A1", "M6B-01.A3"], f"{REL}/ruff.log",
                "ruff with pyproject.toml's eleven families and max-complexity 15 over the whole repository, the hub files without any "
                "exemption: clean; the log also counts the per-line suppressions by code.",
                [PY, "-m", "ruff", "check", "."]),
    ]
    receipts.extend(
        receipt(f"E-mypy-{platform}", "behavior", ["M6B-02.A1", "M6B-02.A3"], f"{REL}/mypy-{platform}.log",
                f"mypy for {platform} on the final source with pyproject.toml's settings and no exemption at all: no issues in 69 files.",
                [PY, "-m", "mypy", "--platform", platform])
        for platform in ("linux", "win32", "darwin")
    )
    for spec_name, results_name, log_name in (("drill-spec.json", "drills-results.json", "drills.log"),
                                              ("drill-spec-b.json", "drills-b-results.json", "drills-b.log")):
        receipts.extend(drill_receipts(spec_name, results_name, log_name))
    for record in json.loads((HERE / "gate-drills-results.json").read_text(encoding="utf-8")):
        if record["status"] != "pass":
            continue
        phase_b = record["id"] in ("ruff-app", "ruff-app-test", "mypy-app", "mypy-menus")  # the hub files, no longer exempt
        target = ("M6B-02.A3" if phase_b else "M6B-02.A1") if record["id"].startswith("mypy") else ("M6B-01.A3" if phase_b else "M6B-01.A1")
        receipts.append(receipt(
            f"E-red-gate-{record['id']}", "red", [target], f"{REL}/gate-drills.log",
            f"Gate drill {record['id']} (gate_drills.py) in a temporary copy of chatmon/, packaging/, tests/ and pyproject.toml: the gate "
            f"({' '.join(Path(a).name if i == 0 else a for i, a in enumerate(record['command']))}) green, then failing on one violation and naming "
            f"{record['expected']}, then green again with the file's bytes put back.",
            [PY, f"{REL}/gate_drills.py"],
            red_from(record, record["expected"], f"{record['id']}: in {record['file']}, {record['mutation']}"),
        ))
    by_ac: dict[str, set[str]] = {}
    for r in receipts:
        for a in r["acceptance"]:
            by_ac.setdefault(a, set()).add(r["kind"])
    for task in ledger["tasks"]:
        if task["id"] not in TASKS:
            continue
        ok = all({"behavior", "red"} <= by_ac.get(a, set()) for a in task["acceptance"])
        task["status"] = "verified" if ok else "implemented"
        task["evidence"] = sorted({r["id"] for r in receipts if set(r["acceptance"]) & set(task["acceptance"]) and r["kind"] != "readiness"})
    ledger["evidence"] = receipts
    snap = snapshot()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None  # noqa: S607 - git, fixed
    ledger["checkpoint"] = {
        "scope_sha256": snap["scope_sha256"], "inputs": snap["inputs"]["behavior"], "environment": snap["declared_environment"],
        "verified_tasks": sorted(t["id"] for t in ledger["tasks"] if t["status"] == "verified"),
        "pending_operations": [],
        "next_action": "None in M6B: the coordinator's CI run of the feature branch (Linux xvfb, the Qt 6.4 containers, macOS) is what's left to see (integration note 1).",
        "source_revision": revision,
    }
    out = text[: match.start(1)] + json.dumps(ledger, indent=2, ensure_ascii=False) + text[match.end(1):]
    (HERE / "candidate.md").write_text(out, encoding="utf-8", newline="\n")
    print(f"{len(receipts)} receipts; tasks: " + ", ".join(f"{t['id']} {t['status']}" for t in ledger["tasks"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
