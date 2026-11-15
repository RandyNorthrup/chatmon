"""M6A-06.A3 again: is the wheel byte-identical when SOURCE_DATE_EPOCH is set, and different when it isn't?

usage (from the worktree root): python sde_check.py BUILD_PYTHON LOG

BUILD_PYTHON has packaging/requirements-build.txt installed (build, setuptools, wheel). Two copies of the files the
wheel is built from are made, with their files' times set a fortnight apart (2026-11-01 and 2026-11-14), and each is
built with `python -m build --no-isolation --wheel`, first without SOURCE_DATE_EPOCH and then with it set to HEAD's
commit time, as packages.yml's "Date the build by its commit" step sets it. Exit 0 when the two wheels differ without
it and are byte-identical with it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
TREE = ["chatmon", "pyproject.toml", "README.md", "LICENSE"]
TIMES = {"a": 1793491200, "b": 1794614400}  # 2026-11-01 and 2026-11-14, 00:00 UTC


def copy(dest: Path, when: int) -> None:
    listed = subprocess.run(["git", "ls-files", "-z", *TREE], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
    for rel in filter(None, listed):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    for path in [dest, *dest.rglob("*")]:
        os.utime(path, (when, when))


def build(python: str, tree: Path, epoch: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}
    if epoch:
        env["SOURCE_DATE_EPOCH"] = epoch
    out = tree / "dist"
    shutil.rmtree(out, ignore_errors=True)
    for stale in ("build", "chatmon.egg-info"):
        shutil.rmtree(tree / stale, ignore_errors=True)
    subprocess.run([python, "-m", "build", "--no-isolation", "--wheel", "--outdir", str(out), "."], cwd=tree, env=env,
                   check=True, capture_output=True)
    (wheel,) = out.glob("*.whl")
    return hashlib.sha256(wheel.read_bytes()).hexdigest()


def main() -> int:
    python, log = sys.argv[1], Path(sys.argv[2])
    epoch = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    versions = subprocess.run([python, "-c", "import importlib.metadata as m; print(' '.join(f'{d} {m.version(d)}' for d in ('build', 'setuptools', 'wheel')))"],
                              capture_output=True, text=True, check=True).stdout.strip()
    lines = [f"# Two copies of {', '.join(TREE)} at {subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()},",
             "# their files' times set to 2026-11-01 (a) and 2026-11-14 (b), each built with python -m build --no-isolation --wheel",
             f"# and packaging/requirements-build.txt's tools: {versions}"]
    digests = {}
    with tempfile.TemporaryDirectory(prefix="chatmon-sde-") as work:
        for name, when in TIMES.items():
            copy(Path(work) / name, when)
        for label, value in (("no SOURCE_DATE_EPOCH", None), (f"SOURCE_DATE_EPOCH={epoch} (HEAD's commit time)", epoch)):
            for name in TIMES:
                digests[(label, name)] = build(python, Path(work) / name, value)
                lines.append(f"{label}, copy {name}: {digests[(label, name)]}")
    labels = list(dict.fromkeys(label for label, _ in digests))
    differ = digests[(labels[0], "a")] != digests[(labels[0], "b")]
    same = digests[(labels[1], "a")] == digests[(labels[1], "b")]
    lines.append(f"# without it the wheels {'differ' if differ else 'are the same'}; with it they {'are byte-identical' if same else 'differ'}")
    ok = differ and same
    lines.append(f"exit {0 if ok else 1}")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
