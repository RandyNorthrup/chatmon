"""Bind wave 4's re-runs and CI observations to one plan, through update-delivery.py.

usage: python bind.py BINDINGS.json [--apply]

BINDINGS.json (one per plan, kept beside its reports as the record of what was bound):

    {"plan": "docs/delivery/m0-app-core.md",
     "section": "docs/delivery/reports/m0/wave4/section.md",    the prose put in before the ledger
     "rules": {"docs/delivery/ROADMAP.md": "<new revision>"},   work.rules revisions, by path
     "inputs_add": ["docs/delivery/reports/wave4/cilog.py"],     more work.inputs
     "task_changes_add": {"T-M0-13": [{"path": "chatmon/log.py", "action": "modify"}]},
     "stale_reason": "why an earlier passing receipt no longer counts",
     "receipts": [ {...}, ... ],                                 new receipts, see below
     "tasks": {"T-X": {"status": "implemented", "blocker": null}},   overrides of the computed status
     "pending": [{"id": ..., "description": ..., "next_action": ...}],
     "next_action": "...",
     "source_revision": "fb19cb9..."}

A receipt is {"id", "kind" (readiness|behavior|red|manual), "acceptance", "artifact", "method"} plus, for behavior,
"command" and "exit_code"; for red, "results" (the drill harness's -results.json) and "drill" (its id), from which
the command, exits, diagnostics and the drilled file's three fingerprints are taken as the harness recorded them;
for a non-passing one, "status" and "reason". Its scope and inputs are the validator's own fingerprints of the
candidate plan and today's files (the functions --snapshot uses); its environment is the plan's profile.

Every earlier passing receipt the validator now finds stale is marked "stale" with stale_reason and the
validator's finding codes, its hashes untouched (history, never refreshed). A task is verified when every check
its criteria ask for has a passing receipt that validates, among the task's own evidence; a verified task that
no longer has that goes back to implemented. The checkpoint is made afresh from the candidate. Without --apply,
the candidate is written and checked but the plan is left as it is. Nothing here runs a check.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path.cwd()
SCRIPTS = Path(os.environ.get("DELIVERY_SCRIPTS", Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts"))
sys.path.insert(0, str(SCRIPTS))

from delivery.checks import check_receipt  # noqa: E402
from delivery.model import EvidenceKind  # noqa: E402
from delivery.reader import parse_plan  # noqa: E402
from delivery.snapshot import current_inputs, input_paths, semantic_digest  # noqa: E402

FENCE = "```quality-ledger\n"
LF = "\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split(text: str) -> tuple[str, dict, str]:
    start = text.index(FENCE)
    body = start + len(FENCE)
    end = text.index(LF + "```", body)
    return text[:start], json.loads(text[body:end]), text[end + 1:]


def join(prose: str, ledger: dict, tail: str) -> str:
    return prose + FENCE + json.dumps(ledger, indent=2, ensure_ascii=False) + LF + tail


def red_block(results: Path, drill: str) -> tuple[list[str], dict]:
    for record in json.loads(results.read_text(encoding="utf-8")):
        if record.get("id") != drill:
            continue
        if record.get("status") != "pass":
            raise SystemExit(f"{drill} didn't go green, red, green: {record.get('reason')}")
        drilled = record["file"]
        wanted = record["expected"] if isinstance(record["expected"], list) else [record["expected"]]
        expected = next((e for e in wanted if e in record["observed"]), wanted[0])
        change = record["mutation"]  # run.py records the find and replace texts; the gate drills, a sentence
        said = f"{change['find']!r} became {change['replace']!r}" if isinstance(change, dict) else change
        return record["command"], {
            "mutation": f"{drill}: in {drilled}, {said}",
            "baseline_exit": record["baseline_exit"], "mutated_exit": record["mutated_exit"],
            "restored_exit": record["restored_exit"],
            "expected_diagnostic": expected, "observed_diagnostic": record["observed"],
            "before": [{"path": drilled, "sha256": record["before_sha256"]}],
            "mutated": [{"path": drilled, "sha256": record["mutated_sha256"]}],
            "after": [{"path": drilled, "sha256": record["after_sha256"]}],
        }
    raise SystemExit(f"{drill} isn't in {results}")


def build(spec: dict, ledger_obj, candidate_ledger) -> dict:
    kind = spec["kind"]
    status = spec.get("status", "pass")
    acceptance = tuple(spec["acceptance"])
    paths = input_paths(candidate_ledger, acceptance, EvidenceKind(kind))
    artifact = spec.get("artifact")
    receipt = {
        "id": spec["id"], "acceptance": list(acceptance), "kind": kind, "status": status,
        "command": [], "method": spec["method"], "environment": ledger_obj["work"]["environment"],
        "exit_code": None,
        "artifact": {"path": artifact, "sha256": sha(ROOT / artifact)} if artifact else None,
        "inputs": [asdict(item) for item in current_inputs(ROOT, paths)],
        "scope_sha256": semantic_digest(candidate_ledger, acceptance), "red": None,
        "reason": spec.get("reason"),
    }
    if kind == "behavior":
        receipt["command"], receipt["exit_code"] = spec["command"], spec.get("exit_code", 0)
    elif kind == "red" and status == "pass":
        receipt["command"], receipt["red"] = red_block(ROOT / spec["results"], spec["drill"])
        receipt["exit_code"] = 0
    elif kind == "red" and spec.get("results"):  # a drill that didn't go green, red, green: its command and exit, as history
        record = next(r for r in json.loads((ROOT / spec["results"]).read_text(encoding="utf-8")) if r["id"] == spec["drill"])
        receipt["command"], receipt["exit_code"] = record["command"], record.get("mutated_exit", record.get("baseline_exit"))
    elif kind == "manual" and spec.get("command"):
        raise SystemExit(f"{spec['id']}: a manual receipt has no command")
    return receipt


def main() -> int:
    config_path = Path(sys.argv[1])
    apply = "--apply" in sys.argv
    config = json.loads(config_path.read_text(encoding="utf-8"))
    plan = ROOT / config["plan"]
    original = plan.read_bytes()
    prose, ledger, tail = split(original.decode("utf-8"))

    section = (ROOT / config["section"]).read_text(encoding="utf-8") if config.get("section") else ""
    if section:
        heading = section.split(LF, 1)[0]
        if heading in prose:  # a second run replaces its own section, which is the last before the ledger
            prose = prose[: prose.index(heading)]
        prose = prose.rstrip(LF) + LF + LF + section.rstrip(LF) + LF + LF
    for rule in ledger["work"]["rules"]:
        rule["revision"] = config.get("rules", {}).get(rule["path"], rule["revision"])
    for path in config.get("inputs_add", []):
        if path not in ledger["work"]["inputs"]:
            ledger["work"]["inputs"].append(path)
    tasks = {task["id"]: task for task in ledger["tasks"]}
    for task_id, changes in config.get("task_changes_add", {}).items():
        for change in changes:
            if change not in tasks[task_id]["changes"]:
                tasks[task_id]["changes"].append(change)

    # The semantic content is final now: every fingerprint below is taken against it.
    _, semantic = parse_plan(join(prose, ledger, tail).encode("utf-8"), config["plan"])

    findings: dict[str, list[str]] = {}
    for old in semantic.evidence:
        if old.status != "pass":
            continue
        codes = sorted({f.code for f in check_receipt(semantic, ROOT, old)})
        if codes:
            findings[old.id] = codes
    for receipt in ledger["evidence"]:
        if receipt["id"] in findings:
            receipt["status"] = "stale"
            receipt["reason"] = f"{config['stale_reason']} (the validator's findings: {', '.join(findings[receipt['id']])})"

    known = {receipt["id"] for receipt in ledger["evidence"]}
    added = []
    for spec in config["receipts"]:
        if spec["id"] in known:
            raise SystemExit(f"{spec['id']} is already a receipt")
        added.append(build(spec, ledger, semantic))
        known.add(spec["id"])
    ledger["evidence"].extend(added)
    for receipt in added:
        for task in ledger["tasks"]:
            if task["status"] != "superseded" and set(task["acceptance"]) & set(receipt["acceptance"]) and receipt["id"] not in task["evidence"]:
                task["evidence"].append(receipt["id"])

    _, bound = parse_plan(join(prose, ledger, tail).encode("utf-8"), config["plan"])
    receipts = {r.id: r for r in bound.evidence}
    problems = {r.id: sorted({f.code for f in check_receipt(bound, ROOT, r)}) for r in bound.evidence if r.id in {a["id"] for a in added} and r.status == "pass"}
    problems = {k: v for k, v in problems.items() if v}
    checks = {a.id: a.checks for a in bound.acceptance}
    good = {r.id for r in bound.evidence if r.status == "pass" and not check_receipt(bound, ROOT, r)}
    overrides = config.get("tasks", {})
    status_report = []
    for task in ledger["tasks"]:
        if task["status"] == "superseded":
            continue
        missing = [f"{a}:{k}" for a in task["acceptance"] for k in checks[a]
                   if not any(e in good and a in receipts[e].acceptance and receipts[e].kind == k for e in task["evidence"])]
        computed = "verified" if not missing else ("implemented" if task["status"] in ("verified", "implemented") else task["status"])
        override = overrides.get(task["id"], {})
        task["status"] = override.get("status", computed)
        if "blocker" in override:
            task["blocker"] = override["blocker"]
        elif task["status"] != "blocked":
            task["blocker"] = None
        status_report.append(f"{task['id']}: {task['status']}" + (f" (missing {', '.join(missing)})" if missing else ""))

    next_action = config["next_action"]
    watch = config.get("watch_paths", [])  # files another worker is changing: which new receipts bind them
    if watch:
        hit = [r["id"] for r in added if r["status"] == "pass" and any(i["path"] in watch for i in r["inputs"])]
        named = sorted({i["path"] for r in added for i in r["inputs"] if i["path"] in watch})
        next_action += (f" {config.get('watch_who', 'Another branch')} changes {', '.join(named)}: once it merges, these receipts bind "
                        f"what it changed and need a refresh, {', '.join(hit)} ({len(hit)} of {len(added)}); the others stay fresh."
                        if hit else f" {config.get('watch_who', 'Another branch')} changes none of the files this plan's receipts bind.")
    _, final = parse_plan(join(prose, ledger, tail).encode("utf-8"), config["plan"])
    active = tuple(a.id for a in final.acceptance if not next(r for r in final.requirements if r.id == a.requirement).superseded_by)
    ledger["checkpoint"] = {
        "scope_sha256": semantic_digest(final, active),
        "inputs": [asdict(item) for item in current_inputs(ROOT, input_paths(final, active, EvidenceKind.BEHAVIOR))],
        "environment": ledger["work"]["environment"],
        "verified_tasks": [t["id"] for t in ledger["tasks"] if t["status"] == "verified"],
        "pending_operations": config.get("pending", []),
        "next_action": next_action,
        "source_revision": config.get("source_revision"),
    }
    candidate = join(prose, ledger, tail).encode("utf-8")
    out = ROOT / "docs/delivery/reports/wave4/candidates" / plan.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(candidate)
    print(f"{config['plan']}: {len(findings)} earlier receipts marked stale, {len(added)} added")
    print(LF.join(status_report))
    if problems:
        print(f"NEW RECEIPTS THAT DON'T VALIDATE: {problems}")
        return 1
    if not apply:
        print(f"candidate written to {out.relative_to(ROOT).as_posix()}; the plan is unchanged")
        return 0
    expected = hashlib.sha256(original).hexdigest()
    done = subprocess.run([sys.executable, str(SCRIPTS / "update-delivery.py"), "--root", ".", "--plan", config["plan"],
                           "--candidate", out.relative_to(ROOT).as_posix(), "--expected-sha256", expected],
                          capture_output=True, text=True, cwd=ROOT)
    print(done.stdout.strip() or done.stderr.strip())
    if done.returncode == 0:
        out.unlink()
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
