"""Round three: each plan's wave4c/extra.json from its wave4b/extra.json, by the same rules for every plan.

usage (from the worktree root): python docs/delivery/reports/wave4/extra3.py ID...

Earlier rounds' warnings about merges still to come are dropped (all merged now), receipt names W4B- become
W4C-, bf9d8ac becomes 3586a0d, the CI and Packages runs and their jobs (matched by job
name) become 3586a0d's, round two's shared evidence in wave4b/ becomes round three's in wave4c/, and the Windows
suite's count is 3586a0d's. Anything a plan needs beyond that is edited in its wave4c/extra.json by hand afterwards.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
R = ROOT / "docs/delivery/reports"
OLD_CI, NEW_CI = R / "wave4b/ci/ci-43701523023.json", R / "wave4c/ci/ci-43729628408.json"
OLD_PKG, NEW_PKG = R / "wave4b/ci/packages-43701523037.json", R / "wave4c/ci/packages-43729628343.json"


def jobs(path: Path) -> dict[str, int]:
    return {j["name"]: j["id"] for j in json.loads(path.read_text(encoding="utf-8"))["jobs"]}


def main() -> int:
    ids = {}
    for old, new in ((OLD_CI, NEW_CI), (OLD_PKG, NEW_PKG)):
        now = jobs(new)
        ids.update({str(i): str(now[name]) for name, i in jobs(old).items() if name in now})
    dropped = [  # earlier rounds' warnings about merges still to come: all of them are merged at 3586a0d
        " Evidence for bf9d8ac: another worker (wave4/crash) may change code for an intermittent Qt crash, so its merge will need this re-checked.",
        " Evidence for fb19cb9; two other workers are changing code at the same time, so their merges will need this re-checked, since any new string must be in the template.",
        " Evidence for fb19cb9; two other workers are changing code at the same time, so their merges will need this re-checked.",
        " Evidence for fb19cb9: two other workers are changing code at the same time, so their merges will need this re-checked.",
    ]
    plain = [("Packages run 43675230966", "Packages run 43729628343"), ("W4B-", "W4C-"), ("bf9d8ac", "3586a0d"), ("43701523023", "43729628408"), ("43701523037", "43729628343"),
             ("docs/delivery/reports/wave4b/", "docs/delivery/reports/wave4c/"), ("1256 passed, 178 skipped", "1259 passed, 178 skipped")]
    for plan in sys.argv[1:]:
        text = (R / plan / "wave4b/extra.json").read_text(encoding="utf-8")
        for phrase in dropped:
            text = text.replace(phrase, "")
        for a, b in plain:
            text = text.replace(a, b)
        text = re.sub(r"\b(ci|pkg)-(\d{12})-", lambda m: f"{m.group(1)}-{ids[m.group(2)]}-", text)
        text = re.sub(rf"docs/delivery/reports/{plan}/wave4b/", f"docs/delivery/reports/{plan}/wave4c/", text)
        json.loads(text)
        (R / plan / "wave4c/extra.json").write_text(text, encoding="utf-8", newline="\n")
        left = sorted(set(re.findall(r"[^\s\"]*wave4b[^\s\"]*|round two", text)))
        print(f"{plan}: written; still naming round two: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
