"""What CI and the release builds install, pinned and locked: packaging/requirements*.in name the versions, each
requirements*.txt beside them locks those with every dependency's hashes (pip installs them --require-hashes),
and pyproject.toml's `dev` extra pins what CI runs for anyone working on Chatmon. These tests keep them in step:
a lock left behind its .in file, two lists disagreeing about a version, or a dev extra that drifted from CI."""

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

REPO = Path(__file__).resolve().parent.parent
PACKAGING = REPO / "packaging"
LISTS = ["requirements", "requirements-build", "requirements-test", "requirements-dev"]
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def locked(stem: str) -> dict[str, tuple[str, list[str]]]:
    """A lock file's requirements: name -> (version, hashes)."""
    text = (PACKAGING / f"{stem}.txt").read_text(encoding="utf-8")
    entries = {}
    for line in re.sub(r"\\\r?\n", " ", text).splitlines():  # a requirement and its hashes, as one line
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pin = PIN.match(line)
        assert pin, f"{stem}.txt: not a pinned requirement: {line}"
        entries[canonical(pin[1])] = (pin[2], re.findall(r"--hash=sha256:([0-9a-f]{64})\b", line))
    return entries


def requirement(stem: str, name: str) -> Requirement | None:
    """One of a lock file's requirements as pip reads it, with its environment marker; None when it isn't there."""
    text = (PACKAGING / f"{stem}.txt").read_text(encoding="utf-8")
    for line in re.sub(r"\\\r?\n", " ", text).splitlines():
        line = line.split("#", 1)[0].split("--hash", 1)[0].strip()
        if line and canonical(Requirement(line).name) == name:
            return Requirement(line)
    return None


def pinned(stem: str) -> dict[str, str]:
    """The versions a .in file names, with those of the files it includes (-r)."""
    pins = {}
    for line in (PACKAGING / f"{stem}.in").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("-r "):
            pins.update(pinned(line[3:].strip().removesuffix(".in")))
        elif line:
            pin = PIN.match(line)
            assert pin, f"{stem}.in: every requirement is pinned with ==, not {line}"
            pins[canonical(pin[1])] = pin[2]
    return pins


def pyproject() -> dict:
    with open(REPO / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_every_locked_requirement_is_pinned_and_hashed():
    for stem in LISTS:
        entries = locked(stem)
        assert entries, f"{stem}.txt locks nothing"
        unhashed = sorted(name for name, (_, hashes) in entries.items() if not hashes)
        assert not unhashed, f"{stem}.txt has no hash for {unhashed}: pip --require-hashes would refuse it"


def test_each_lock_holds_the_versions_its_in_file_names():
    """Changing a pin means locking again: the .txt is what CI and the builds install."""
    for stem in LISTS:
        entries = locked(stem)
        stale = {name: version for name, version in pinned(stem).items() if entries.get(name, ("",))[0] != version}
        assert not stale, f"{stem}.txt doesn't lock these at the versions {stem}.in pins: {stale}"


def test_a_package_in_more_than_one_lock_is_the_same_version_in_each():
    """CI's tests run on the Qt that ships, and the wheel is checked with the pytest the tests use."""
    seen: dict[str, dict[str, str]] = {}
    for stem in LISTS:
        for name, (version, _) in locked(stem).items():
            seen.setdefault(name, {})[stem] = version
    assert {"pyqt6", "pyqt6-qt6", "pyqt6-sip", "psutil"} <= {n for n, by in seen.items() if len(by) > 1}
    differ = {name: by for name, by in seen.items() if len(set(by.values())) > 1}
    assert not differ, f"locked at different versions: {differ}"


def test_the_windows_test_legs_install_the_screen_readers_ui_automation_client():
    """tests/uia_client.py listens to UI Automation through comtypes, which only Windows has a use for. Without it in
    the test list, CI's Windows legs would skip the end-to-end screen-reader test instead of running it."""
    for stem in ("requirements-test", "requirements-dev"):
        comtypes = requirement(stem, "comtypes")
        assert comtypes is not None, f"{stem}.txt doesn't lock comtypes"
        where = [p for p in ("win32", "linux", "darwin") if comtypes.marker is None or comtypes.marker.evaluate({"sys_platform": p})]
        assert where == ["win32"], f"{stem}.txt installs comtypes on {where}, not on Windows alone: {comtypes}"


def test_the_dev_extra_pins_what_ci_runs():
    extra = {canonical(r.name): r for r in map(Requirement, pyproject()["project"]["optional-dependencies"]["dev"])}
    wanted = pinned("requirements-dev")
    assert set(extra) == set(wanted), f"the dev extra and requirements-dev.in name different packages: {set(extra) ^ set(wanted)}"
    for name, requirement in extra.items():
        assert str(requirement.specifier) == f"=={wanted[name]}", f"dev extra: {requirement}, but CI runs {name}=={wanted[name]}"


def test_releases_build_with_a_pinned_setuptools_the_project_accepts():
    version, _ = locked("requirements-build")["setuptools"]
    backend = next(Requirement(r) for r in pyproject()["build-system"]["requires"] if canonical(Requirement(r).name) == "setuptools")
    assert Version(version) in backend.specifier, f"setuptools {version} doesn't meet pyproject.toml's {backend}"
