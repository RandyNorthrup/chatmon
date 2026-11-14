"""Red drills for M4B's Linux-only tests, run in WSL (Arch Linux) with tests/drills/run.py's own drill() step.

run.py copies the tree with git, which can't read this Windows worktree's .git file from WSL, so this copies
chatmon/, tests/ and pyproject.toml itself and then hands each drill to run.drill(): green, red (the mutation must
make the named tests fail and print what's expected), restored (byte for byte, checked by SHA-256), green again.

usage (in WSL): python wsl-drills.py WORKTREE SPEC LOG
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

root, spec, log_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(root / "tests" / "drills"))
import run  # noqa: E402  (tests/drills/run.py)

copy = Path(tempfile.mkdtemp(prefix="chatmon-wsl-drill-", dir="/var/tmp"))
log = [f"red drills from {spec}", f"python: {sys.executable}", f"copy: {copy}"]
results = []
try:
    for part in ("chatmon", "tests"):
        shutil.copytree(root / part, copy / part, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(root / "pyproject.toml", copy / "pyproject.toml")
    for d in run.load_spec(spec):
        results.append(run.drill(d, root, copy, sys.executable, log))
finally:
    shutil.rmtree(copy, ignore_errors=True)
log.append("\n=== summary")
for r in results:
    log.append(f"{r['status'].upper():4} {r['id']}" + (f": {r['reason']}" if r["reason"] else ""))
log_path.write_text("\n".join(log) + "\n", encoding="utf-8")
log_path.with_suffix(".json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print("\n".join(log[-len(results) - 1:]))
sys.exit(1 if any(r["status"] != "pass" for r in results) else 0)
