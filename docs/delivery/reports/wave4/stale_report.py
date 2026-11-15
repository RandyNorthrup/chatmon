"""Every passing receipt of every plan that no longer validates, with the cause: python stale_report.py OUT.

For each plan in docs/delivery/, each receipt whose status is pass is checked with the validator's own check_receipt.
When it fails, the cause is named: the inputs whose bytes changed (recorded and current SHA-256), inputs added to or
dropped from its coverage, a changed artifact, or a changed scope. Nothing is changed. The report is a table per plan,
written to OUT (Markdown), and a one-line count per plan is printed.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
SCRIPTS = Path(os.environ.get("DELIVERY_SCRIPTS", Path.home() / ".claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts"))
sys.path.insert(0, str(SCRIPTS))

from delivery.checks import check_receipt  # noqa: E402
from delivery.model import ResultStatus  # noqa: E402
from delivery.reader import parse_plan  # noqa: E402
from delivery.snapshot import current_inputs, input_paths  # noqa: E402

PLANS = sorted(p for p in (ROOT / "docs/delivery").glob("m*-*.md") if re.match(r"m\d+[a-z]?-", p.name))


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> int:
    out = Path(sys.argv[1])
    lines = ["# Stale receipts, by plan", "", f"Checked against the worktree's files with the validator's check_receipt ({SCRIPTS.name}).", ""]
    for plan in PLANS:
        rel = plan.relative_to(ROOT).as_posix()
        _, ledger = parse_plan(plan.read_bytes(), rel)
        stale = []
        for receipt in ledger.evidence:
            if receipt.status != ResultStatus.SUCCESS:
                continue
            codes = sorted({f.code for f in check_receipt(ledger, ROOT, receipt)})
            if not codes:
                continue
            recorded = {item.path: item.sha256 for item in receipt.inputs}
            expected = {item.path: item.sha256 for item in current_inputs(ROOT, input_paths(ledger, receipt.acceptance, receipt.kind))}
            changed = sorted(p for p in recorded if p in expected and recorded[p] != expected[p])
            added = sorted(set(expected) - set(recorded))
            dropped = sorted(set(recorded) - set(expected))
            causes = []
            if changed:
                causes.append("changed: " + ", ".join(f"`{p}`" for p in changed))
            if added:
                causes.append("now also binds: " + ", ".join(f"`{p}`" for p in added))
            if dropped:
                causes.append("no longer binds: " + ", ".join(f"`{p}`" for p in dropped))
            if receipt.artifact and receipt.artifact.sha256 and sha(ROOT / receipt.artifact.path) != receipt.artifact.sha256:
                causes.append(f"artifact changed: `{receipt.artifact.path}`")
            stale.append((receipt.id, codes, "; ".join(causes) or "-"))
        print(f"{rel}: {len(stale)} stale of {sum(r.status == ResultStatus.SUCCESS for r in ledger.evidence)} passing")
        lines.append(f"## {rel}: {len(stale)} stale")
        lines.append("")
        if stale:
            lines += ["| Receipt | Findings | Cause |", "|---|---|---|"]
            lines += [f"| {rid} | {', '.join(codes)} | {cause} |" for rid, codes, cause in stale]
            lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
