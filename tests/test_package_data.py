"""What the wheel and sdist ship: every file of the chatmon package that the repository tracks.

setuptools ships the package's Python files and only those other files `[tool.setuptools.package-data]` names by
glob, so a new kind of file under chatmon/ that no glob takes would be missing from every pip and pipx install.
These tests read the globs as setuptools does and hold them against the files git tracks. Given CHATMON_DIST, a
folder holding a built wheel and sdist (CI's packages workflow builds them), they check what's in those too.
"""

import glob
import os
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "chatmon"
DIST = os.environ.get("CHATMON_DIST")
needs_dist = pytest.mark.skipif(not DIST, reason="checks a built wheel and sdist: CHATMON_DIST=<the folder holding them>")


def package_data_globs() -> list[str]:
    with open(REPO / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["setuptools"]["package-data"]["chatmon"]


def tracked_files() -> set[str]:
    """Every file under chatmon/ that git tracks, relative to chatmon/ ("anim/idle.png"). Where there's no git
    repository (an unpacked sdist, or a red drill's copy), every file there but Python's own byte code."""
    git = shutil.which("git")
    if git:
        listed = subprocess.run([git, "ls-files", "-z", "--", "chatmon"], cwd=REPO, capture_output=True)
        if listed.returncode == 0:
            return {p.removeprefix("chatmon/") for p in listed.stdout.decode("utf-8").split("\0") if p}
    return {
        p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def taken_by(pattern: str) -> set[str]:
    """The files one package-data glob takes, found as setuptools' build_py finds them: the standard library's
    glob, recursive, from the package's folder (so `*` takes no name starting with a dot)."""
    return {Path(p).as_posix() for p in glob.glob(pattern, root_dir=PACKAGE, recursive=True) if (PACKAGE / p).is_file()}


def ships_as_python(path: str) -> bool:
    """`packages = ["chatmon"]`: the Python files of the package's own folder ship as code, and nothing below it
    does unless a glob takes it (none of chatmon's folders is a package of its own)."""
    return path.endswith(".py") and "/" not in path


def test_every_tracked_file_of_chatmon_ships():
    tracked = tracked_files()
    assert {"__init__.py", "changelog.md"} <= tracked, "the listing didn't find the package"
    taken = set().union(*(taken_by(p) for p in package_data_globs()))
    left_out = sorted(f for f in tracked if not ships_as_python(f) and f not in taken)
    assert not left_out, f"no package-data glob in pyproject.toml takes these, so pip and pipx installs would lack them: {left_out}"


def test_every_package_data_glob_takes_a_tracked_file():
    """A glob that takes nothing is a file that was renamed or removed, or a typo."""
    tracked = tracked_files()
    unused = [p for p in package_data_globs() if not taken_by(p) & tracked]
    assert not unused, f"these package-data globs take no file the repository tracks: {unused}"


def one(pattern: str) -> Path:
    assert DIST is not None
    found = sorted(Path(DIST).glob(pattern))
    assert len(found) == 1, f"{DIST} should hold exactly one {pattern}, not {[p.name for p in found]}"
    return found[0]


@needs_dist
def test_the_wheel_holds_every_tracked_file_of_chatmon_and_nothing_else():
    with zipfile.ZipFile(one("chatmon-*.whl")) as wheel:
        names = [n for n in wheel.namelist() if not n.endswith("/")]
    shipped = {n.removeprefix("chatmon/") for n in names if n.startswith("chatmon/")}
    tracked = tracked_files()
    assert sorted(tracked - shipped) == [], "left out of the wheel"
    assert sorted(shipped - tracked) == [], "in the wheel, but not tracked by the repository"
    assert [n for n in names if not n.startswith("chatmon/") and ".dist-info/" not in n] == [], "outside the package"


@needs_dist
def test_the_wheel_installs_chatmons_two_commands_and_no_others():
    """`chatmon`, and `chatmonw` (Windows without a console). The old name, penguin-companion, was dropped
    after 0.9; Chatmon still moves over what was set up under it."""
    with zipfile.ZipFile(one("chatmon-*.whl")) as wheel:
        (entry_points,) = [n for n in wheel.namelist() if n.endswith(".dist-info/entry_points.txt")]
        text = wheel.read(entry_points).decode("utf-8")
    commands, section = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.strip("[]")
        elif "=" in line:
            name, target = (part.strip() for part in line.split("=", 1))
            commands[name] = (section, target)
    assert commands == {"chatmon": ("console_scripts", "chatmon.cli:main"), "chatmonw": ("gui_scripts", "chatmon.cli:main")}


@needs_dist
def test_the_sdist_holds_every_tracked_file_of_chatmon():
    """A wheel built from the sdist (as pip does from a source download) can ship only what the sdist holds."""
    with tarfile.open(one("chatmon-*.tar.gz")) as sdist:
        names = [m.name for m in sdist.getmembers() if m.isfile()]
    top = names[0].split("/", 1)[0]
    shipped = {n.removeprefix(f"{top}/chatmon/") for n in names if n.startswith(f"{top}/chatmon/")}
    tracked = tracked_files()
    assert sorted(tracked - shipped) == [], "left out of the sdist"
    assert sorted(shipped - tracked) == [], "in the sdist, but not tracked by the repository"
