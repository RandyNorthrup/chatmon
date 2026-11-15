"""The final round, M6A's section: a plan's wave4f/extra.json from an earlier round's, by the same rules for each plan.

usage (from the worktree root): python docs/delivery/reports/wave4/extra5.py SOURCE ID...

SOURCE is the folder the extras come from: wave4c (M6A, last bound in full in round three) or wave4e (M6B and M10,
bound earlier in this round). Receipt names become W4F-, 3586a0d becomes 45a17b3, round three's CI and Packages runs
and their jobs (matched by job name) become 45a17b3's, and the plan's own evidence folder becomes wave4f/. CI's logs,
the merge record and the repository's settings stay in the round's shared wave4e/. Anything else is edited by hand.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
R = ROOT / "docs/delivery/reports"
OLD_CI, NEW_CI = R / "wave4c/ci/ci-43729628408.json", R / "wave4e/ci/ci-43743804662.json"
OLD_PKG, NEW_PKG = R / "wave4c/ci/packages-43729628343.json", R / "wave4e/ci/packages-43743804716.json"


def jobs(path: Path) -> dict[str, int]:
    return {j["name"]: j["id"] for j in json.loads(path.read_text(encoding="utf-8"))["jobs"]}


def main() -> int:
    source, plans = sys.argv[1], sys.argv[2:]
    ids = {}
    for old, new in ((OLD_CI, NEW_CI), (OLD_PKG, NEW_PKG)):
        now = jobs(new)
        ids.update({str(i): str(now[name]) for name, i in jobs(old).items() if name in now})
    plain = [("W4C-", "W4F-"), ("W4E-", "W4F-"), ("3586a0d", "45a17b3"), ("43729628408", "43743804662"),
             ("43729628343", "43743804716"), ("docs/delivery/reports/wave4c/ci/", "docs/delivery/reports/wave4e/ci/"),
             ("reports/wave4c/ci/", "reports/wave4e/ci/"), ("reports/wave4c/github-settings.txt", "reports/wave4e/github-settings.txt")]
    for plan in plans:
        text = (R / plan / source / "extra.json").read_text(encoding="utf-8")
        for a, b in plain:
            text = text.replace(a, b)
        text = re.sub(r"\b(ci|pkg)-(\d{12})-", lambda m: f"{m.group(1)}-{ids.get(m.group(2), m.group(2))}-", text)
        text = re.sub(r"docs/delivery/reports/(m[0-9]+[a-z]?)/wave4[ce]/", lambda m: f"docs/delivery/reports/{m.group(1)}/wave4f/", text)
        json.loads(text)
        (R / plan / "wave4f/extra.json").write_text(text, encoding="utf-8", newline="\n")
        left = sorted(set(re.findall(r"[^\s\"]*wave4[ce][^\s\"]*|round three|1328\d+", text)))
        print(f"{plan}: written; still naming an earlier round: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
