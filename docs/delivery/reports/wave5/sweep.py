"""Validate every plan at resume and closure, as the last round's validation-sweep.txt: python sweep.py OUT.

Each plan is checked with the context.json of its latest round (wave5/ for the nine re-bound in this round; the
newest folder that has one for the four that weren't), which must equal the plan's own profile. One line per plan
and stage: PASS, or FAIL with the validator's finding codes and their locations. The validator's JSON report for
each is kept in OUT's folder, as validate-sweep.json. Nothing is changed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
PY = "C:/Users/Randy/Coding/chatmon/.venv/Scripts/python.exe"
V = "C:/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py"
PLANS = ["m0", "m1a", "m1b", "m2", "m3", "m4a", "m4b", "m5", "m6a", "m6b", "m7", "m8", "m10"]
ORDER = ["wave5", "w4d", "wave4f", "wave4e", "wave4c", "wave4b", "wave4"]


def context(plan: str, profile: dict) -> Path:
    base = ROOT / "docs/delivery/reports" / plan
    for folder in ORDER:
        path = base / folder / "context.json"
        if path.is_file() and json.loads(path.read_text(encoding="utf-8")) == profile:
            return path
    raise SystemExit(f"{plan}: no context.json matches the plan's profile")


def main() -> int:
    out = Path(sys.argv[1])
    lines, reports = [], {}
    for plan in PLANS:
        slug = next(p for p in (ROOT / "docs/delivery").glob(f"{plan}-*.md"))
        text = slug.read_text(encoding="utf-8")
        profile = json.loads(re.search(r"```quality-ledger\n(.*?)\n```", text, re.S).group(1))["work"]["environment"]
        ctx = context(plan, profile)
        for stage in ("resume", "closure"):
            command = [PY, V, "--root", ".", "--plan", slug.relative_to(ROOT).as_posix(), "--stage", stage,
                       "--context", ctx.relative_to(ROOT).as_posix(), "--format", "json"]
            done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)  # noqa: S603 - the skill's own validator, fixed
            report = json.loads(done.stdout)
            reports[f"{plan} {stage}"] = {"context": ctx.relative_to(ROOT).as_posix(), "exit": done.returncode, "report": report}
            findings = report.get("findings", [])
            verdict = "PASS" if done.returncode == 0 else "FAIL"
            lines.append(f"{plan} {stage}: {verdict} " + " ".join(f"{f['code']}:{f['location']}" for f in findings))
            print(lines[-1])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out.parent / "validate-sweep.json").write_text(json.dumps(reports, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
