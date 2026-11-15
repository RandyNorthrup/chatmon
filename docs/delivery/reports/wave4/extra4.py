"""The final round: each plan's wave4e/extra.json from its wave4c/extra.json, by the same rules for every plan.

usage (from the worktree root): python docs/delivery/reports/wave4/extra4.py ID...

Receipt names W4C- become W4E-, 3586a0d becomes 45a17b3, the CI and Packages runs and their jobs (matched by job name)
become 45a17b3's, and round three's evidence in wave4c/ becomes the final round's in wave4e/. Anything a plan needs
beyond that (round three's failures, now fixed) is edited in its wave4e/extra.json by hand afterwards.
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
    ids = {}
    for old, new in ((OLD_CI, NEW_CI), (OLD_PKG, NEW_PKG)):
        if not new.exists():  # Packages: none of the plans this round binds reads its logs
            continue
        now = jobs(new)
        ids.update({str(i): str(now[name]) for name, i in jobs(old).items() if name in now})
    plain = [("W4C-", "W4E-"), ("3586a0d", "45a17b3"), ("43729628408", "43743804662"), ("43729628343", "43743804716"),
             ("docs/delivery/reports/wave4c/", "docs/delivery/reports/wave4e/")]
    for plan in sys.argv[1:]:
        text = (R / plan / "wave4c/extra.json").read_text(encoding="utf-8")
        for a, b in plain:
            text = text.replace(a, b)
        text = re.sub(r"\b(ci|pkg)-(\d{12})-", lambda m: f"{m.group(1)}-{ids[m.group(2)]}-", text)
        text = re.sub(r"docs/delivery/reports/(m[0-9]+[a-z]?)/wave4c/", lambda m: f"docs/delivery/reports/{m.group(1)}/wave4e/", text)
        json.loads(text)
        (R / plan / "wave4e/extra.json").write_text(text, encoding="utf-8", newline="\n")
        left = sorted(set(re.findall(r"[^\s\"]*wave4c[^\s\"]*|round three", text)))
        print(f"{plan}: written; still naming round three: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
