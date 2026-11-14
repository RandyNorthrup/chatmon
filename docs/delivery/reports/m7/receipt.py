"""Add a receipt to receipts.json, bound to the validator's snapshot of the criteria it covers as they are now.

usage: python receipt.py ID KIND ARTIFACT --acceptance AC... [--command ARG...] [--exit N] [--method TEXT]
                         [--red-drill DRILL_ID --red-results RESULTS.json] [--status pass|fail|deferred|stale --reason TEXT]

KIND is readiness, behavior or red. A red receipt reads its drill's record from the drill harness's results file
(the same run's log is the artifact). Nothing here runs a check: it records one that ran, with the fingerprints the
snapshot gives (an observation of the files, not proof of anything).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # docs/delivery/reports/m7 -> the repository
PLAN = "docs/delivery/m7-integration.md"
VALIDATOR = Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(acceptance: list[str]) -> dict:
    out = subprocess.run([sys.executable, str(VALIDATOR), "--root", ".", "--plan", PLAN, "--snapshot", "--acceptance", *acceptance],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def red_record(results: Path, drill: str) -> dict:
    """The drill's record in the harness's results file (a list of drills)."""
    for record in json.loads(results.read_text(encoding="utf-8")):
        if record.get("id") == drill:
            if record.get("status") != "pass":
                raise SystemExit(f"{drill} didn't go green, red, green: {record.get('reason')}")
            return record
    raise SystemExit(f"{drill} isn't in {results}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("kind", choices=["readiness", "behavior", "red"])
    ap.add_argument("artifact")
    ap.add_argument("--acceptance", nargs="+", required=True)
    ap.add_argument("--command", nargs=argparse.REMAINDER, default=[])
    ap.add_argument("--exit", type=int, default=None)
    ap.add_argument("--method", default="")
    ap.add_argument("--red-drill")
    ap.add_argument("--red-results")
    ap.add_argument("--status", default="pass")
    ap.add_argument("--reason", default=None)
    a = ap.parse_args()
    snap = snapshot(a.acceptance)
    artifact = ROOT / a.artifact
    receipt = {
        "id": a.id, "acceptance": a.acceptance, "kind": a.kind, "status": a.status,
        "command": a.command if a.kind != "readiness" else [], "method": a.method,
        "environment": snap["declared_environment"],
        "exit_code": None if a.kind == "readiness" else (a.exit if a.exit is not None else 0),
        "artifact": {"path": a.artifact, "sha256": digest(artifact)},
        "inputs": snap["inputs"]["readiness" if a.kind == "readiness" else "behavior"],
        "scope_sha256": snap["scope_sha256"], "red": None, "reason": a.reason,
    }
    if a.kind == "red":
        rec = red_record(ROOT / a.red_results, a.red_drill)
        drilled = rec["file"]
        receipt["command"] = rec["command"]
        receipt["red"] = {
            "mutation": f"{rec['id']}: in {drilled}, {rec['mutation']['find']!r} became {rec['mutation']['replace']!r}",
            "baseline_exit": rec["baseline_exit"], "mutated_exit": rec["mutated_exit"], "restored_exit": rec["restored_exit"],
            "expected_diagnostic": "; ".join(rec["expected"]), "observed_diagnostic": rec["observed"],
            "before": [{"path": drilled, "sha256": rec["before_sha256"]}],
            "mutated": [{"path": drilled, "sha256": rec["mutated_sha256"]}],
            "after": [{"path": drilled, "sha256": rec["after_sha256"]}],
        }
    state_file = HERE / "receipts.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    receipts = [r for r in state.get("receipts", []) if r["id"] != a.id]
    receipts.append(receipt)
    state["receipts"] = receipts
    state_file.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{a.id}: {a.kind} {a.status} for {', '.join(a.acceptance)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
