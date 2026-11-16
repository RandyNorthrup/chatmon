"""The plans round for v0.10.0 (7816159): a plan's wave5/extra.json from its last round's: python extra6.py ID.

Every receipt is the last round's check, run again or read again: the receipt ids become W5-, the commit 7816159, the
CI logs main's run 43778643147's for the same jobs (wave5/ci/), the round folders wave5/. What a check observed this
time (counts, sizes, skip reasons) is not carried over: each such text is written again from this round's logs, in
OVERRIDES, and the script refuses to write a plan whose method still names an old count it hasn't been told about
(CHECK). M6A's extra.json is written by hand (its requirements changed). Nothing here runs a check.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
REPORTS = ROOT / "docs/delivery/reports"
LAST = {"m0": "wave4e", "m2": "wave4c", "m3": "wave4e", "m4a": "wave4c", "m6b": "wave4f", "m7": "wave4e", "m8": "wave4e", "m10": "wave4f"}
JOBS = {  # this round's job log for each job name the earlier logs were saved under
    re.sub(r"^ci-\d+-", "", p.name): p.name for p in (REPORTS / "wave5/ci").glob("ci-*-*.log")
}
TEXT = [
    (r"CI run 4374380466[2] on 45a17b3", "main's CI run 43778643147 on 7816159"),
    (r"CI run 43729628408 on 3586a0d", "main's CI run 43778643147 on 7816159"),
    (r"CI run 43729628408", "main's CI run 43778643147"),
    (r"\b(45a17b3|3586a0d)\b", "7816159"),
    (r"\bW4[CEF]-", "W5-"),
    (r"\bwave4[cef]/", "wave5/"),
    (r"chatmon-wt/(plans-final|plans3)\b", "chatmon-wt/measure"),
    (r"plans(final4f|final|3)-mypy-", "plans5-mypy-"),
]
CHECK = re.compile(r"\b\d+ (passed|skipped|deselected|tests)\b|\b\d+x\d+\b|\b\d+(\.\d+)? MB\b")


def text(value: str) -> str:
    for pattern, replacement in TEXT:
        value = re.sub(pattern, replacement, value)
    return value


def walk(value):
    if isinstance(value, str):
        return text(value)
    if isinstance(value, list):
        return [walk(v) for v in value]
    if isinstance(value, dict):
        return {k: walk(v) for k, v in value.items()}
    return value


def main() -> int:
    plan = sys.argv[1]
    old = json.loads((REPORTS / plan / LAST[plan] / "extra.json").read_text(encoding="utf-8"))
    new = walk(old)
    for ci in new.get("ci", []):
        ci["log"] = JOBS[re.sub(r"^ci-\d+-", "", ci["log"])]
    overrides = json.loads((REPORTS / plan / "wave5" / "overrides.json").read_text(encoding="utf-8"))
    for key, value in overrides.items():
        if key in ("ci", "receipts"):
            items = {item["id"]: item for item in new.get(key, [])}
            for rid, fields in value.items():
                if fields is None:
                    new[key] = [item for item in new[key] if item["id"] != rid]
                elif rid in items:
                    items[rid].update(fields)
                else:
                    new.setdefault(key, []).append(fields)
        else:
            new[key] = value
    stale_counts = [(item["id"], m.group(0)) for key in ("ci", "receipts") for item in new.get(key, [])
                    for m in CHECK.finditer(item["method"]) if item["id"] not in overrides.get(key, {})]
    if stale_counts:
        raise SystemExit(f"{plan}: these methods still carry the last round's observations: {stale_counts}")
    (REPORTS / plan / "wave5" / "extra.json").write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{plan}: wave5/extra.json written ({len(new.get('ci', []))} CI receipts, {len(new.get('receipts', []))} others)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
