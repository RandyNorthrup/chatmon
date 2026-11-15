"""Bind the final runs to the ledger: python bind.py PYTEST_LOG DRILLS_RESULTS... [--pending ID=TEXT ...]

Adds (to receipts.json) one behavior receipt for every criterion, on the whole suite's log (the one command that runs
every check), one red receipt for each drill that went green, red and green, and a readiness receipt; marks verified
each task whose criteria all have both; and writes the checkpoint from the validator's snapshot. Nothing is run here:
the logs must come from real runs of the commands they name."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PY = sys.executable
sys.path.insert(0, str(HERE))

import ledger  # noqa: E402
import receipt  # noqa: E402

SUITE = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def main() -> int:
    args = sys.argv[1:]
    pending = [a.split("=", 1) for a in args if "=" in a and not a.startswith("--")]
    files = [a for a in args if "=" not in a and not a.startswith("--")]
    suite_log, results = files[0], files[1:]
    every = [c[0] for r in ledger.REQS for c in r[3]]
    state_file = HERE / "receipts.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    state["receipts"] = [r for r in state.get("receipts", []) if r["kind"] == "readiness"]  # fresh runs replace the old receipts
    state_file.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")

    def add(*argv: str) -> None:
        subprocess.run([PY, str(HERE / "receipt.py"), *argv], check=True, cwd=ROOT)

    add("RDY-1", "readiness", "docs/delivery/reports/m7/readiness.md", "--acceptance", *every,
        "--method", "Requirements review of M7-01..M7-13, the CI finding and every integration note addressed to M7 (readiness.md), "
                    "re-read against the merged M3 and M4B notes.")
    add("BEH-SUITE", "behavior", suite_log, "--acceptance", *every, "--exit", "0",
        "--method", "The whole suite on the final source (real Qt objects, offscreen), which runs every criterion's tests; the log names each failure, and had none.",
        "--command", *SUITE)
    drilled: dict[str, int] = {}
    for results_file in results:
        for record in json.loads((ROOT / results_file).read_text(encoding="utf-8")):
            if record.get("status") != "pass":
                continue
            ac = next((d["requirement"] for d in json.loads((HERE / "drill-spec.json").read_text(encoding="utf-8"))["drills"] if d["id"] == record["id"]), None)
            if ac is None:
                continue
            ac = {"M7-CI": None}.get(ac, ac)
            targets = ["AC-CI-1"] if record["id"].startswith("CI-01") else ["AC-CI-2"] if record["id"].startswith(("CI-02", "CI-03")) else \
                ["AC-CI-3"] if record["id"].startswith("CI-0") else [ac]
            log = results_file.replace("-results.json", ".log")
            add(f"RED-{record['id']}", "red", log, "--acceptance", *targets, "--exit", "0", "--red-drill", record["id"], "--red-results", results_file,
                "--method", f"Red drill {record['id']} through tests/drills/run.py in a temporary copy: green, the defect put in, the named "
                            "tests failing for that reason, the file's bytes put back and green again.")
            for t in targets:
                drilled[t] = drilled.get(t, 0) + 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    missing = [a for a in every if not drilled.get(a)]
    status = {}
    for tid, _purpose, acs, _deps, _changes in ledger.TASKS:
        status[tid] = "verified" if not set(acs) & set(missing) else "implemented"
    state["status"] = status
    snap = json.loads(subprocess.run([PY, str(receipt.VALIDATOR), "--root", ".", "--plan", receipt.PLAN, "--snapshot"], cwd=ROOT,
                                     capture_output=True, text=True, check=True).stdout)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    state["checkpoint"] = {
        "scope_sha256": snap["scope_sha256"], "inputs": snap["inputs"]["behavior"], "environment": snap["declared_environment"],
        "verified_tasks": sorted(t for t, s in status.items() if s == "verified"),
        "pending_operations": [{"id": pid, "description": text, "next_action": "Observe the outcome (the coordinator's CI run or merge), then re-run the affected checks."}
                               for pid, text in pending],
        "next_action": "Wire M4A's sleep and live accessibility events once it is merged into improve/assessment-fixes; read the Linux and macOS CI results.",
        "source_revision": revision,
    }
    state_file.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"criteria without a red drill: {missing or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
