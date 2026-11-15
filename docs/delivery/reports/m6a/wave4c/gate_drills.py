"""M6A's gate drills: each gate passes on the tree, fails on one deliberate violation, and passes again.

usage (from the worktree root, with the venv's Python, which has mypy, zizmor, coverage and pip):
    python docs/delivery/reports/m6a/gate_drills.py [--only ID ...]

tests/drills/run.py drills pytest assertions; these drill the other gates: zizmor, actionlint, mypy, pytest's own
settings, pip's hash checking, the coverage floor and the checksum job's script. Every mutation is made in a
temporary copy, never in the tree; each drill checks the tree's file still has the bytes it had before. The log
(gate-drills.log) and a JSON summary (gate-drills-results.json) are written beside this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
PY = sys.executable
SCRIPTS = Path(PY).parent
TAIL = 25
CRLF, LF = "\r\n", "\n"
# Git for Windows' own bash and openssl: Windows finds System32's bash.exe (WSL's) before anything on PATH.
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\usr\bin\bash.exe"
OPENSSL = shutil.which("openssl") if os.name != "nt" else r"C:\Program Files\Git\mingw64\bin\openssl.exe"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 900) -> tuple[int, str]:
    full = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    done = subprocess.run(cmd, cwd=cwd, env=full, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return done.returncode, done.stdout + done.stderr


def tail(out: str) -> str:
    return "\n".join(out.rstrip().splitlines()[-TAIL:])


def copy(paths: list[str], dest: Path) -> None:
    for rel in paths:
        src = ROOT / rel
        if src.is_dir():
            shutil.copytree(src, dest / rel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)


class Drill:
    """One gate drill: copy `paths`, run `cmd` (green), apply `mutate` to `file` (red, needs `expect` in the output and a
    non-zero exit), restore its bytes, run again (green)."""

    def __init__(self, id, requirement, paths, file, mutate, cmd, expect, env=None, setup=None, mutation=""):
        self.id, self.requirement, self.paths, self.file = id, requirement, paths, file
        self.mutate, self.cmd, self.expect, self.env, self.setup, self.mutation = mutate, cmd, expect, env, setup, mutation

    def __call__(self, log: list[str]) -> dict:
        tree_bytes = (ROOT / self.file).read_bytes()
        result = {"id": self.id, "requirement": self.requirement, "file": self.file, "mutation": self.mutation,
                  "expected": self.expect, "status": "fail", "reason": None, "before_sha256": sha(tree_bytes)}
        log.append(f"\n=== {self.id} ({self.requirement}) on {self.file}: {self.mutation}")
        with tempfile.TemporaryDirectory(prefix="m6a-gate-") as tmp:
            work = Path(tmp)
            copy(self.paths, work)
            if self.setup:
                self.setup(work)
            cmd = [str(c).format(work=work) for c in self.cmd]
            env = {k: v.format(work=work) for k, v in (self.env or {}).items()}
            result["command"] = [str(c).format(work="<copy>") for c in self.cmd]
            log.append("command: " + " ".join(result["command"]))
            target = work / self.file
            original = target.read_bytes()
            code, out = run(cmd, work, env)
            result["baseline_exit"] = code
            log.append(f"-- green: exit {code}\n{tail(out)}")
            if code != 0:
                result["reason"] = "baseline is not green"
                return result
            try:
                text = original.decode("utf-8")
                crlf = CRLF in text  # a Windows checkout's line ends: mutate the text, keep its line ends
                changed = self.mutate(text.replace(CRLF, LF))
                mutated = (changed.replace(LF, CRLF) if crlf else changed).encode("utf-8")
                if mutated == original:
                    result["reason"] = "the mutation changed nothing"
                    return result
                target.write_bytes(mutated)
                result["mutated_sha256"] = sha(mutated)
                code, out = run(cmd, work, env)
                result["mutated_exit"] = code
                log.append(f"-- red: exit {code}\n{tail(out)}")
                missing = [e for e in self.expect if e not in out]
                result["observed"] = next((ln.strip() for ln in out.splitlines() if self.expect[0] in ln), "")
                if code == 0:
                    result["reason"] = "the violation passed the gate"
                elif missing:
                    result["reason"] = f"the gate failed without saying {missing}"
            except ValueError as exc:
                result["reason"] = f"the mutation couldn't be made: {exc}"
            finally:
                target.write_bytes(original)
            result["after_sha256"] = sha(target.read_bytes())
            if result["reason"]:
                return result
            code, out = run(cmd, work, env)
            result["restored_exit"] = code
            log.append(f"-- restored green: exit {code}\n{tail(out)}")
            if code != 0:
                result["reason"] = "restored run is not green"
                return result
        if (ROOT / self.file).read_bytes() != tree_bytes:
            result["reason"] = "the tree's file changed during the drill"
            return result
        result["status"] = "pass"
        return result


def replace_once(find: str, replace: str):
    def mutate(text: str) -> str:
        n = text.count(find)
        if n != 1:
            raise ValueError(f"{find!r} occurs {n} times")
        return text.replace(find, replace)
    return mutate


def replace_first(find: str, replace: str):
    def mutate(text: str) -> str:
        if find not in text:
            raise ValueError(f"{find!r} isn't there")
        return text.replace(find, replace, 1)
    return mutate


def scramble_hashes_of(package: str):
    """Every hash of one package in a lock, changed: pip must refuse whichever file it downloads."""
    def mutate(text: str) -> str:
        block = re.search(rf"(?ms)^{re.escape(package)}==.*?(?=^\S|\Z)", text)  # up to the next requirement, or the end
        if not block:
            raise ValueError(f"no {package} in the lock")
        changed = re.sub(r"--hash=sha256:[0-9a-f]{64}", "--hash=sha256:" + "f" * 64, block.group(0))
        return text[: block.start()] + changed + text[block.end():]
    return mutate


def append(line: str):
    return lambda text: text.rstrip("\r\n") + "\n" + line + "\n"


# -- the checksum job's script, as packages.yml has it, run with a throwaway release key


def checksum_script(workflow: str) -> str:
    """The `run:` block of packages.yml's "List and sign every file's checksum" step, dedented."""
    lines = workflow.splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.strip() == "- name: List and sign every file's checksum")
    run_at = next(i for i in range(at, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run_at + 1]) - len(lines[run_at + 1].lstrip())
    body = []
    for ln in lines[run_at + 1:]:
        if ln.strip() and len(ln) - len(ln.lstrip()) < indent:
            break
        body.append(ln[indent:])
    return "\n".join(body) + "\n"


def checksum_setup(work: Path) -> None:
    """A throwaway Ed25519 key, chatmon/releasecheck.py trusting only it, a dist folder of two files, and a runner
    script that runs the step's script as the job would (KEY, DIST, RUNNER_TEMP, GITHUB_WORKSPACE)."""
    key = work / "release.pem"
    subprocess.run([OPENSSL, "genpkey", "-algorithm", "ed25519", "-out", str(key)], check=True)
    der = subprocess.run([OPENSSL, "pkey", "-in", str(key), "-pubout", "-outform", "DER"], check=True, capture_output=True).stdout
    public = der[-32:].hex()
    check = work / "chatmon" / "releasecheck.py"
    text = check.read_text(encoding="utf-8")
    check.write_text(re.sub(r'^RELEASE_KEYS = \(.*$', f'RELEASE_KEYS = ("{public}",)', text, count=1, flags=re.M), encoding="utf-8")
    (work / "dist").mkdir()
    (work / "dist" / "chatmon-0.0.0.tar.gz").write_bytes(b"a pretend sdist\n")
    (work / "dist" / "chatmon_0.0.0-1_all.deb").write_bytes(b"a pretend deb\n")
    (work / "temp").mkdir()
    (work / "run-step.sh").write_text(
        "#!/bin/sh\n# Runs the step's script from the copy's packages.yml, each time, so a drill on the workflow reaches it.\n"
        "set -e\n"
        f"rm -f '{(work / 'dist').as_posix()}'/SHA256SUMS.txt*  # each run starts as the job does, from a fresh download\n"
        f"KEY=$(cat '{key.as_posix()}')\nexport KEY\n"
        f"export DIST='{(work / 'dist').as_posix()}' RUNNER_TEMP='{(work / 'temp').as_posix()}' GITHUB_WORKSPACE='{work.as_posix()}'\n"
        f"'{Path(PY).as_posix()}' '{Path(__file__).as_posix()}' --print-checksum-script '{(work / '.github/workflows/packages.yml').as_posix()}' > '{(work / 'step.sh').as_posix()}'\n"
        f"exec bash -e '{(work / 'step.sh').as_posix()}'\n",
        encoding="utf-8", newline="\n",
    )


DRILLS = [
    Drill("G-zizmor-unpinned", "M6A-01", [".github"], ".github/workflows/ci.yml",
          replace_once("      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n        with:\n          persist-credentials: false\n      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n        with:\n          python-version: \"3.14\"\n      - run: python -m pip install --require-hashes -r packaging/requirements-dev.txt\n      - run: ruff check .",
                       "      - uses: actions/checkout@v7\n        with:\n          persist-credentials: false\n      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0 # v7.1.0\n        with:\n          python-version: \"3.14\"\n      - run: python -m pip install --require-hashes -r packaging/requirements-dev.txt\n      - run: ruff check ."),
          [SCRIPTS / "zizmor.exe", "--no-online-audits", ".github"], ["unpinned-uses"],
          mutation="the lint job's checkout pinned to the tag v7 instead of its commit"),
    Drill("G-actionlint-expression", "M6A-12", [".github"], ".github/workflows/ci.yml",
          replace_once('PLATFORM: ${{ matrix.platform }}', 'PLATFORM: ${{ matrix.platfrom }}'),
          ["actionlint", ".github/workflows/ci.yml"], ['property "platfrom" is not defined'],
          mutation="the types job reads matrix.platfrom, a property its matrix doesn't have"),
    Drill("G-mypy-gated", "M6A-13", ["chatmon", "pyproject.toml"], "chatmon/changelog.py",
          append('_DRILL: int = "not a number"'),
          [PY, "-m", "mypy", "--platform", "linux", "--no-incremental", "--cache-dir", "{work}/.mypy"],
          ["chatmon\\changelog.py", "Incompatible types in assignment"],
          mutation="a str assigned to an int in changelog.py, a gated module"),
    Drill("G-pytest-strict-markers", "M6A-01", ["chatmon", "tests", "pyproject.toml"], "tests/test_cli.py",
          replace_first("\ndef test_", "\n@pytest.mark.drillmark\ndef test_"),
          [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_cli.py"],
          ["'drillmark' not found in `markers` configuration option"],
          mutation="an unregistered mark on test_cli.py's first test"),
    Drill("G-pip-hashes", "M6A-06", ["packaging"], "packaging/requirements-build.txt",
          scramble_hashes_of("wheel"),
          [PY, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--no-cache-dir", "--require-hashes", "-r", "packaging/requirements-build.txt"],
          ["THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE"],
          mutation="every hash of wheel 0.48.0 in requirements-build.txt changed"),
    Drill("G-checksums-key", "M6A-I1", [".github", "chatmon/releasecheck.py", "chatmon/updates.py"], ".github/workflows/packages.yml",
          lambda text: replace_once('"$GITHUB_WORKSPACE/chatmon/releasecheck.py"', '"$GITHUB_WORKSPACE/chatmon/updates.py"')(
              replace_once("sparse-checkout: chatmon/releasecheck.py", "sparse-checkout: chatmon/updates.py")(text)),
          [BASH, "{work}/run-step.sh"], ["RELEASE_SIGNING_KEY isn't a key in RELEASE_KEYS"],
          setup=checksum_setup,
          mutation="the checksums job looks for the key in chatmon/updates.py again, where it was before M1A moved it"),
]


def coverage_drill(data_file: str) -> Drill:
    return Drill("G-coverage-floor", "M6A-04", ["chatmon", "pyproject.toml", data_file], "pyproject.toml",
                 lambda text: re.sub(r"^fail_under = \d+", "fail_under = 99", text, count=1, flags=re.M),
                 [PY, "-m", "coverage", "report", "--data-file", data_file],
                 ["Coverage failure: total of", "is less than fail-under=99"],
                 mutation="fail_under raised to 99, above the measured total")


BUILD_TREE = ["chatmon", "tests/conftest.py", "tests/test_package_data.py", "pyproject.toml", "README.md", "LICENSE"]


def build_drills(build_py: str) -> list[Drill]:
    """What packages.yml's wheel job does, on a copy: build the wheel and sdist without isolation (build_py has the
    locked requirements-build.txt), twine check --strict, then the package-data tests on what was built."""
    def job(select: str) -> list:
        py = Path(build_py).as_posix()
        return [BASH, "-ec", f"'{py}' -m build --no-isolation --outdir dist . >build.log 2>&1 || {{{{ tail -20 build.log; exit 1; }}}}; "
                f"'{py}' -m twine check --strict dist/*; "
                f"CHATMON_DIST=dist '{py}' -m pytest -q -p no:cacheprovider tests/test_package_data.py -k '{select}'"]
    return [
        Drill("W-wheel-sounds", "M6A-08", BUILD_TREE, "pyproject.toml",
              replace_once('    "sounds/*.wav",\n', ""), job("wheel_holds"),
              ["AssertionError: left out of the wheel", "first extra item: 'sounds/done.wav'"],
              mutation="the sounds/*.wav package-data glob removed, so the wheel is built without the sounds"),
        Drill("W-entry-points", "M6A-09", BUILD_TREE, "pyproject.toml",
              replace_once('[project.scripts]\nchatmon = "chatmon.cli:main"\n', '[project.scripts]\nchatmon = "chatmon.cli:main"\npenguin-companion = "chatmon.cli:main"\n'),
              job("commands"), ["'penguin-companion': ('console_scripts', 'chatmon.cli:main')"],
              mutation="the penguin-companion console script put back"),
        Drill("W-twine-markup", "M6A-08", BUILD_TREE, "pyproject.toml",
              replace_once('readme = "README.md"', 'readme = { file = "README.md", content-type = "text/x-rst" }'),
              job("wheel_holds"), ["`long_description` has syntax errors in markup"],
              mutation="the README declared as reStructuredText, which its Markdown isn't"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--coverage-data", help="a combined .coverage file, for the coverage floor drill")
    parser.add_argument("--build-python", help="a Python with requirements-build.txt installed, for the wheel job's drills")
    parser.add_argument("--print-checksum-script", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.print_checksum_script:
        sys.stdout.write(checksum_script(Path(args.print_checksum_script).read_text(encoding="utf-8")))
        return 0
    drills = DRILLS + ([coverage_drill(args.coverage_data)] if args.coverage_data else [])
    drills += build_drills(args.build_python) if args.build_python else []
    if args.only:
        drills = [d for d in drills if d.id in args.only]
    log = [f"M6A gate drills, {ROOT}", f"python: {PY}"]
    results = [d(log) for d in drills]
    log.append("\n=== summary")
    log += [f"{r['status'].upper():4} {r['id']}" + (f": {r['reason']}" if r["reason"] else "") for r in results]
    name = "gate-drills" + ("-" + "-".join(args.only) if args.only else "")
    (HERE / f"{name}.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    (HERE / f"{name}-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("\n".join(log[-len(results) - 1:]))
    return 0 if all(r["status"] == "pass" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
