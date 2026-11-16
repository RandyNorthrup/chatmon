"""Move a plan's oldest stale receipts, byte for byte, out of its ledger into reports/<id>/history/, for the
validator's 4 MiB plan limit, as reports/m6b/history/README.md describes the first such move.

usage: python archive_receipts.py PLAN PREFIX OUT.json [--apply]

Every receipt whose id starts with PREFIX must be stale (history only, the current evidence for nothing). Each is
written to OUT.json exactly as it stands in the ledger: the same text, with the ledger's own indentation, in a JSON
array. They leave the ledger's evidence and every task's evidence list, and nothing else changes: no other receipt,
requirement, criterion, task field or checkpoint. Without --apply the candidate is checked and written to
docs/delivery/reports/wave4/candidates/ and the plan is left alone; with it, update-delivery.py replaces the plan
(checked against the plan's SHA-256 as read). Prints each file's SHA-256 and the plan's size before and after.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path.cwd()
SCRIPTS = Path(os.environ.get("DELIVERY_SCRIPTS", Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts"))
FENCE = "```quality-ledger\n"


def main() -> int:
    plan, prefix, out = ROOT / sys.argv[1], sys.argv[2], ROOT / sys.argv[3]
    original = plan.read_bytes()
    text = original.decode("utf-8")
    start = text.index(FENCE) + len(FENCE)
    end = text.index("\n```", start)
    ledger = json.loads(text[start:end])
    if text[start:end] != json.dumps(ledger, indent=2, ensure_ascii=False):
        raise SystemExit("the ledger isn't in bind.py's form")
    moving = [r for r in ledger["evidence"] if r["id"].startswith(prefix)]
    if not moving or any(r["status"] != "stale" for r in moving):
        raise SystemExit(f"{len(moving)} receipts start with {prefix}; every one must be stale")
    pieces = [textwrap.indent(json.dumps(r, indent=2, ensure_ascii=False), "    ") for r in moving]
    for piece in pieces:
        if piece not in text:
            raise SystemExit("a receipt's text isn't in the plan verbatim")
    ids = {r["id"] for r in moving}
    ledger["evidence"] = [r for r in ledger["evidence"] if r["id"] not in ids]
    for task in ledger["tasks"]:
        task["evidence"] = [e for e in task["evidence"] if e not in ids]
    candidate = (text[:start] + json.dumps(ledger, indent=2, ensure_ascii=False) + text[end:]).encode("utf-8")
    archive = ("[\n" + ",\n".join(pieces) + "\n]\n").encode("utf-8")
    print(f"{len(moving)} receipts ({prefix}*), {len(archive)} bytes; plan {len(original)} -> {len(candidate)} bytes")
    if "--apply" not in sys.argv:
        cand = ROOT / "docs/delivery/reports/wave4/candidates" / plan.name
        cand.parent.mkdir(parents=True, exist_ok=True)
        cand.write_bytes(candidate)
        print(f"candidate written to {cand.relative_to(ROOT).as_posix()}; the plan is unchanged")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(archive)
    print(f"{out.relative_to(ROOT).as_posix()}: sha256 {hashlib.sha256(archive).hexdigest()}")
    cand = ROOT / "docs/delivery/reports/wave4/candidates" / plan.name
    cand.parent.mkdir(parents=True, exist_ok=True)
    cand.write_bytes(candidate)
    command = [sys.executable, str(SCRIPTS / "update-delivery.py"), "--root", ".", "--plan", plan.relative_to(ROOT).as_posix(),
               "--candidate", cand.relative_to(ROOT).as_posix(), "--expected-sha256", hashlib.sha256(original).hexdigest()]
    done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)  # noqa: S603 - the skill's own writer, fixed
    print(done.stdout.strip() or done.stderr.strip())
    if done.returncode == 0:
        cand.unlink()
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
