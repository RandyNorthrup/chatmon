"""Red drills for Linux-only tests, run in WSL with tests/drills/run.py's own drill() step.

usage (in WSL, from any folder): python wsl_drills.py WORKTREE SPEC LOG FILES

run.py copies the tree with git, which WSL's git can't do from this Windows worktree (its .git file names a
Windows path). FILES is that copy's list, made on Windows by `git ls-files -co --exclude-standard -z` (the same
call run.py makes); this copies those files, apart from art/ and docs/ as run.py does, into a temporary folder,
then hands each drill to run.drill(): green, red (the mutation must make the named tests fail with pytest's
tests-failed exit and print what's expected), restored (byte for byte, checked by SHA-256), green again. The
log and a JSON summary (LOG's name with -results.json) are written as run.py writes them. Adapted from
docs/delivery/reports/m4b/wsl-drills.py, which copied only chatmon/, tests/ and pyproject.toml.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

root, spec, log_path, listing = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(root / "tests" / "drills"))
import run  # noqa: E402  (tests/drills/run.py)

copy = Path(tempfile.mkdtemp(prefix="chatmon-wsl-drill-", dir="/var/tmp"))
log = [f"red drills from {spec}", f"python: {sys.executable}", f"copy: {copy}"]
results = []
try:
    copied = 0
    for rel in listing.read_bytes().decode("utf-8").split("\0"):
        if not rel or rel.startswith(run.EXCLUDED_TOP) or not (root / rel).is_file():
            continue
        (copy / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, copy / rel)
        copied += 1
    log.append(f"copied {copied} files")
    for d in run.load_spec(spec):
        results.append(run.drill(d, root, copy, sys.executable, log))
finally:
    shutil.rmtree(copy, ignore_errors=True)
log.append("\n=== summary")
for r in results:
    log.append(f"{r['status'].upper():4} {r['id']}" + (f": {r['reason']}" if r["reason"] else ""))
log_path.write_text("\n".join(log) + "\n", encoding="utf-8")
log_path.with_name(log_path.stem + "-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
print("\n".join(log[-len(results) - 1:]))
sys.exit(1 if any(r["status"] != "pass" for r in results) else 0)
