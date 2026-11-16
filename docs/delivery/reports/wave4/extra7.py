"""The plans round for v0.10.0, bound again at 56caddd: a plan's wave5b/extra.json from its wave5/ one: python extra7.py ID.

As extra6.py, one step on: receipt ids become W5B-, the commit 56caddd (the coordinator's df3e93c and 56caddd on
7816159), the CI logs PR #24's run 43794815103's for the same jobs (wave5b/ci/), the folders wave5b/. The wave5/
binding's ledger edits are already in the plan (M6A's M6A-02B), so they aren't carried over. What a check observed
this time is written again in wave5b/overrides.json, which can also drop a receipt (null) or replace one whole, and the
script refuses a plan whose method still names an old count it hasn't been told about. Nothing here runs a check.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
JOBS = {  # each job's log as read: the first attempt's for the 17 that passed there, the re-run's for macOS 3.15 and coverage
    re.sub(r"^ci-\d+-", "", p.name): p.name for p in (REPORTS / "wave5b/ci").glob("ci-*-*.log") if not p.name.startswith("ci-133061193367-")
}
TEXT = [
    (r"main's CI run 43778643147 on 7816159", "PR #24's CI run 43794815103 on 56caddd"),
    (r"main's CI run 43778643147", "PR #24's CI run 43794815103"),
    (r"\b7816159\b", "56caddd"),
    (r"\bW5-", "W5B-"),
    (r"\bwave5/", "wave5b/"),
    (r"plans5-mypy-", "plans5b-mypy-"),
]
CHECK = re.compile(r"\b\d+ (passed|skipped|deselected|tests)\b|\b\d+x\d+\b|\b\d+(\.\d+)? MB\b")


def walk(value):
    if isinstance(value, str):
        for pattern, replacement in TEXT:
            value = re.sub(pattern, replacement, value)
        return value
    if isinstance(value, list):
        return [walk(v) for v in value]
    if isinstance(value, dict):
        return {k: walk(v) for k, v in value.items()}
    return value


def main() -> int:
    plan = sys.argv[1]
    old = json.loads((REPORTS / plan / "wave5" / "extra.json").read_text(encoding="utf-8"))
    old.pop("ledger_edits", None)
    new = walk(old)
    for ci in new.get("ci", []):
        if ci["log"].startswith("ci-"):
            ci["log"] = JOBS[re.sub(r"^ci-\d+-", "", ci["log"])]
    overrides = json.loads((REPORTS / plan / "wave5b" / "overrides.json").read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if key in ("ci", "receipts"):
            items = {item["id"]: item for item in new.get(key, [])}
            for rid, fields in value.items():
                if fields is None:
                    new[key] = [item for item in new[key] if item["id"] != rid]
                elif fields.get("replace"):
                    whole = {k: v for k, v in fields.items() if k != "replace"}
                    new[key] = [whole if item["id"] == rid else item for item in new[key]] if rid in items else new.get(key, []) + [whole]
                elif rid in items:
                    items[rid].update(fields)
                else:
                    new.setdefault(key, []).append(fields)
        else:
            new[key] = value
    for key in ("ci", "receipts"):  # a receipt passing now carries no failure of the last binding's
        for item in new.get(key, []):
            if item.get("status") in (None, "pass"):
                item.pop("status", None)
                item.pop("reason", None)
                if item.get("exit_code") not in (None, 0):
                    item["exit_code"] = 0
    stale_counts = [(item["id"], m.group(0)) for key in ("ci", "receipts") for item in new.get(key, [])
                    for m in CHECK.finditer(item["method"]) if item["id"] not in overrides.get(key, {})]
    if stale_counts:
        raise SystemExit(f"{plan}: these methods still carry the last binding's observations: {stale_counts}")
    (REPORTS / plan / "wave5b" / "extra.json").write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{plan}: wave5b/extra.json written ({len(new.get('ci', []))} CI receipts, {len(new.get('receipts', []))} others)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
