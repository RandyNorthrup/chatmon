"""packaging/pins.py, the weekly check that keeps the Python pins moving where Dependabot can't (it can't lock uv's
universal lists): what it reads from the .in files and the locks' headers, how it loosens the pins, the cooldown's
cutoff, the skip list, PyQt6 and its Qt moving together, one version per package across the locks, its report, and
--apply. Each runs on a small copy of packaging/ with tests/fake_uv.py as uv, over a made-up index, so it's the
same every time and reaches no network. The last test runs the real uv on the real lists, when asked to."""

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FAKE_UV = Path(__file__).resolve().parent / "fake_uv.py"
NOW = dt.datetime(2026, 11, 15, 20, 26, 50, tzinfo=dt.UTC)
CUTOFF = "2026-11-01T20:26:00Z"  # NOW, 14 days back, to the minute


def load_pins():
    spec = importlib.util.spec_from_file_location("chatmon_pins", REPO / "packaging" / "pins.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while it loads
    spec.loader.exec_module(module)
    return module


pins = load_pins()


def release(version, uploaded, requires=(), python=""):
    return {"version": version, "uploaded": uploaded if "T" in uploaded else uploaded + "T00:00:00Z", "requires": list(requires), "python": python}


QT_611 = ["PyQt6-Qt6>=6.11.0,<6.12.0", "PyQt6-sip>=13.8,<14"]
QT_612 = ["PyQt6-Qt6>=6.12.0,<6.13.0", "PyQt6-sip>=13.8,<14"]
INDEX = {
    "nuitka": [release("4.3.1", "2026-09-20"), release("4.3.3", "2026-10-25"), release("4.3.4", "2026-11-01T07:44:15Z"),
               release("4.3.5", "2026-11-08T13:01:00Z")],
    "pyinstaller": [release("6.22.3", "2026-09-01", ["altgraph", "macholib>=1.8"])],
    "altgraph": [release("0.17.5", "2025-11-01")],
    "macholib": [release("1.16.4", "2025-12-01", ["altgraph>=0.17"])],
    "PyQt6": [release("6.11.0", "2026-07-01", QT_611), release("6.12.0", "2026-10-10", QT_612), release("6.12.1", "2026-11-05", QT_612)],
    "PyQt6-Qt6": [release("6.11.2", "2026-08-01"), release("6.11.3", "2026-10-01"), release("6.12.0", "2026-10-10"), release("6.12.1", "2026-11-05")],
    "PyQt6-sip": [release("13.13.0", "2026-06-01")],
    "psutil": [release("7.2.2", "2026-06-01")],
    "pytest": [release("9.2.0", "2026-08-01", ["pluggy>=1.5"])],
    "pluggy": [release("1.6.0", "2025-05-15")],
    "comtypes": [release("1.4.17", "2026-05-01")],
    "ruff": [release("0.17.3", "2026-10-20"), release("0.17.4", "2026-10-28")],
}

IN_FILES = {
    "requirements.in": """# What the installers are built with.
nuitka==4.3.1; sys_platform == 'win32'  # Windows: compiles Chatmon
pyinstaller==6.22.3; sys_platform == 'darwin'  # macOS
PyQt6==6.11.0  # the Qt that ships
PyQt6-Qt6==6.11.2
psutil==7.2.2  # battery levels
""",
    "requirements-test.in": """# What CI's tests run with.
PyQt6==6.11.0
PyQt6-Qt6==6.11.2
psutil==7.2.2
pytest==9.2.0
comtypes==1.4.17; sys_platform == 'win32'  # the UI Automation client
""",
    "requirements-dev.in": """# Everything CI runs.
-r requirements-test.in
ruff==0.17.3
""",
}
# Each list's command, as the real headers have them: requirements.txt without a cutoff, the others with one.
COMMANDS = {
    "requirements": "requirements.in -o requirements.txt --universal --python-version 3.14 --generate-hashes",
    "requirements-test": "requirements-test.in -o requirements-test.txt --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31",
    "requirements-dev": "requirements-dev.in -o requirements-dev.txt --universal --python-version 3.11 --generate-hashes --exclude-newer 2026-10-31",
}
PYPROJECT = """[project]
name = "fixture"
version = "0"
dependencies = ["PyQt6>=6.5"]  # a floor for the distributions' own PyQt6: never raised just because a newer one is out

[project.optional-dependencies]
dev = [
    "PyQt6==6.11.0",
    "PyQt6-Qt6==6.11.2",
    "psutil==7.2.2",
    "pytest==9.2.0",
    "comtypes==1.4.17; sys_platform == 'win32'",  # the screen-reader test's client
    "ruff==0.17.3",
]
"""


class Repo:
    """A copy of packaging/'s lists, locked by the fake uv over an index of the test's own."""

    def __init__(self, root: Path, index: dict, in_files: dict | None = None):
        self.root, self.packaging, self.index_path, self.log = root, root / "packaging", root / "index.json", root / "uv.log"
        self.packaging.mkdir(parents=True)
        self.write_index(index)
        for name, text in (in_files or IN_FILES).items():
            (self.packaging / name).write_text(text, encoding="utf-8", newline="\n")
        (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8", newline="\n")
        for command in COMMANDS.values():
            subprocess.run([sys.executable, str(FAKE_UV), "pip", "compile", *command.split()], cwd=self.packaging, check=True, capture_output=True)
        self.log.unlink()

    def write_index(self, index):
        self.index_path.write_text(json.dumps(index), encoding="utf-8")

    def run(self, capsys, *args, now=NOW):
        code = pins.main(list(args), uv=[sys.executable, str(FAKE_UV)], root=self.root, now=now)
        out = capsys.readouterr()
        return code, out.out, out.err

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def locked(self, stem):
        return pins.read_lock((self.packaging / f"{stem}.txt").read_text(encoding="utf-8"))

    def text(self, name):
        return (self.packaging / name).read_text(encoding="utf-8")

    def hashes(self):
        files = [*sorted(self.packaging.iterdir()), self.root / "pyproject.toml"]
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_UV_INDEX", str(tmp_path / "index.json"))
    monkeypatch.setenv("FAKE_UV_LOG", str(tmp_path / "uv.log"))
    monkeypatch.delenv("FAKE_UV_FAIL", raising=False)
    return Repo(tmp_path, INDEX)


def rows(report, name):
    """The report's table rows for one package."""
    return [line for line in report.splitlines() if line.startswith(f"| {name} |")]


def with_release(index, package, *releases):
    changed = json.loads(json.dumps(index))
    changed[package] = changed[package] + list(releases)
    return changed


# -- reading the lists


def test_reads_each_pin_with_its_marker_and_the_files_a_list_includes(repo):
    infile = pins.read_in(repo.packaging / "requirements.in")
    assert [(pin.name, pin.version, pin.marker) for pin in infile.pins] == [
        ("nuitka", "4.3.1", "sys_platform == 'win32'"), ("pyinstaller", "6.22.3", "sys_platform == 'darwin'"),
        ("PyQt6", "6.11.0", ""), ("PyQt6-Qt6", "6.11.2", ""), ("psutil", "7.2.2", "")]
    assert [pin.key for pin in infile.pins][2:4] == ["pyqt6", "pyqt6-qt6"]
    dev = pins.read_in(repo.packaging / "requirements-dev.in")
    assert dev.includes == ("requirements-test.in",)
    assert [pin.name for pin in dev.pins] == ["ruff"]
    (repo.packaging / "requirements.in").write_text("nuitka>=4.3\n", encoding="utf-8")
    with pytest.raises(pins.PinsError, match="pinned with =="):
        pins.read_in(repo.packaging / "requirements.in")


def test_reads_the_real_lists():
    lists = {lst.stem: lst for lst in pins.read_lists(REPO / "packaging")}
    assert set(lists) == {"requirements", "requirements-build", "requirements-test", "requirements-dev", "requirements-pins"}
    nuitka = next(pin for pin in lists["requirements"].infile.pins if pin.key == "nuitka")
    assert nuitka.marker == "sys_platform == 'win32'"
    assert lists["requirements-dev"].infile.includes == ("requirements-test.in",)
    for lst in lists.values():
        assert set(lst.header.args) >= {"--universal", "--generate-hashes"}, lst.txt.name
        assert pins.output_of(lst.header.args) == lst.txt.name
        assert {pin.key for pin in lst.infile.pins} <= set(lst.current), f"{lst.txt.name} doesn't lock every pin of {lst.infile.path.name}"


def test_refuses_a_lock_that_isnt_uvs_universal_one(repo):
    """Dependabot's own locks were plain pip-compile ones: one platform's packages, the others' dropped."""
    txt = repo.packaging / "requirements.txt"
    body = txt.read_text(encoding="utf-8").split("\n", 2)[2]
    for header, says in [
        ("# This file is autogenerated by pip-compile with Python 3.14\n#    pip-compile --generate-hashes requirements.in\n", "no uv header"),
        (pins.HEADER + "\n#    uv pip compile requirements.in -o requirements.txt --python-version 3.14 --generate-hashes\n", "no --universal"),
        (pins.HEADER + "\n#    uv pip compile requirements.in -o requirements.txt --universal --python-version 3.14\n", "no --generate-hashes"),
        (pins.HEADER + "\n#    uv pip compile other.in -o requirements.txt --universal --generate-hashes\n", "doesn't lock requirements.in"),
    ]:
        txt.write_text(header + body, encoding="utf-8")
        with pytest.raises(pins.PinsError, match=says):
            pins.read_header(txt, "requirements.in")


def test_loosening_takes_each_version_off_and_keeps_its_marker(repo):
    assert pins.loosen(pins.read_in(repo.packaging / "requirements.in")) == """# What the installers are built with.
nuitka ; sys_platform == 'win32'
pyinstaller ; sys_platform == 'darwin'
PyQt6
PyQt6-Qt6
psutil
"""
    assert pins.loosen(pins.read_in(repo.packaging / "requirements-dev.in")) == "# Everything CI runs.\n-r requirements-test.in\nruff\n"


def test_versions_compare_as_pep_440_orders_them():
    ordered = ["1.0.dev1", "1.0a1", "1.0b2", "1.0rc1", "1.0", "1.0.post1", "1.0.1", "1.10", "2026.9", "1!0.1"]
    assert sorted((ordered[i] for i in (4, 9, 0, 7, 2, 5, 8, 1, 6, 3)), key=pins.version_key) == ordered
    assert pins.version_key("6.11") == pins.version_key("6.11.0")
    assert pins.release_line("6.11.2") == (6, 11) and pins.release_line("7") == (7, 0)
    assert pins.older(["6.12.1", "6.9.3", "6.11.0"]) == "6.9.3"


# -- the cooldown


def test_the_cutoff_is_fourteen_days_back():
    assert pins.COOLDOWN == dt.timedelta(days=14)
    assert pins.cutoff_for(NOW) == CUTOFF
    assert pins.cutoff_for(NOW.astimezone(dt.timezone(dt.timedelta(hours=-8)))) == CUTOFF
    assert pins.parse_cutoff("2026-11-01", NOW) == "2026-11-01T00:00:00Z"
    assert pins.parse_cutoff(CUTOFF, NOW) == CUTOFF
    with pytest.raises(pins.PinsError, match="less than 14 days back"):
        pins.parse_cutoff("2026-11-02T00:00:00Z", NOW)


def test_a_cutoff_less_than_two_weeks_back_is_refused(repo, capsys):
    before = repo.hashes()
    code, _, err = repo.run(capsys, "--apply", "--cutoff", "2026-11-10")
    assert code == pins.EXIT_ERROR
    assert "less than 14 days back" in err
    assert repo.hashes() == before and not repo.calls()


def test_each_lock_is_made_with_its_headers_command_and_the_cutoff_in_place_of_its_own(repo):
    header = pins.read_header(repo.packaging / "requirements-test.txt", "requirements-test.in")
    assert pins.compile_args(header, CUTOFF) == ["pip", "compile", *COMMANDS["requirements-test"].split()[:-2], "--exclude-newer", CUTOFF]
    assert pins.compile_args(header, CUTOFF, ["nuitka"])[-2:] == ["--exclude-newer-package", "nuitka=false"]
    header = pins.read_header(repo.packaging / "requirements.txt", "requirements.in")
    assert pins.compile_args(header, CUTOFF) == ["pip", "compile", *COMMANDS["requirements"].split(), "--exclude-newer", CUTOFF]


def test_each_pin_moves_to_its_newest_release_two_weeks_old(repo, capsys):
    """nuitka 4.3.5 is a week old, so 4.3.4 is the newest it moves to."""
    before = repo.hashes()
    code, out, _ = repo.run(capsys)
    assert code == pins.EXIT_MOVABLE
    assert rows(out, "nuitka") == ["| nuitka | 4.3.1 | 4.3.4 | requirements.txt | requirements.in |"]
    assert rows(out, "ruff") == ["| ruff | 0.17.3 | 0.17.4 | requirements-dev.txt | requirements-dev.in, pyproject.toml (dev) |"]
    calls = repo.calls()
    assert len(calls) == 3  # one round settled it: a lock per list
    for call in calls:
        assert call["argv"][call["argv"].index("--exclude-newer") + 1] == CUTOFF
        assert call["argv"].count("--exclude-newer") == 1
        assert Path(call["cwd"]) != repo.packaging  # a scratch folder: the lists themselves stay as they are
    loosened = next(call for call in calls if "requirements.in" in call["argv"])["read"]["requirements.in"]
    assert "nuitka ; sys_platform == 'win32'\n" in loosened
    assert not [line for line in loosened.splitlines() if pins.PIN.fullmatch(line)]
    assert repo.hashes() == before


# -- the rules


def test_the_skip_list_holds_pyqt6_6_12_0_back_and_says_why(repo, capsys):
    """6.12.0 is two weeks old and newer than the 6.11.0 that ships, but its own stubs stop mypy."""
    code, out, _ = repo.run(capsys)
    assert code == pins.EXIT_MOVABLE
    assert not rows(out, "PyQt6"), "PyQt6 moved, though 6.12.0 is skipped"  # it stays at 6.11.0
    assert "| PyQt6-Qt6 | 6.11.2 | 6.11.3 |" in out  # Qt's own fix on the 6.11 line still comes
    assert "PyQt6 6.12.0 is skipped: its own QtDBus.pyi" in out
    constraints = repo.calls()[0]["read"][pins.CONSTRAINTS]
    assert "PyQt6!=6.12.0" in constraints.splitlines()
    skips = {(pins.canonical(skip.package), skip.version): skip.reason for skip in pins.SKIP}
    assert "mypy" in skips.get(("pyqt6", "6.12.0"), "")


def test_no_skip_names_the_version_pinned_now():
    pinned = {(pin.key, pin.version) for lst in pins.read_lists(REPO / "packaging") for pin in lst.infile.pins}
    for skip in pins.SKIP:
        assert skip.reason.strip(), skip
        assert (pins.canonical(skip.package), skip.version) not in pinned, f"{skip.package} {skip.version} is skipped but pinned now"


def test_pyqt6_and_its_qt_stay_on_one_release_line(repo, capsys):
    """Should PyQt6 6.11.0 let PyQt6-Qt6 6.12.0 in, the Qt group still moves together: Qt stays on the 6.11 line."""
    loose = json.loads(json.dumps(INDEX))
    loose["PyQt6"][0]["requires"] = ["PyQt6-Qt6>=6.11.0", "PyQt6-sip>=13.8,<14"]
    repo.write_index(loose)
    code, out, _ = repo.run(capsys)
    assert code == pins.EXIT_MOVABLE
    assert [row.split(" | ")[2] for row in rows(out, "PyQt6-Qt6")] == ["6.11.3"], f"the Qt group split: {rows(out, 'PyQt6-Qt6')}"
    assert not rows(out, "PyQt6")
    assert "PyQt6-Qt6 stays on the 6.11 line with the rest of the Qt group" in out
    assert "pyqt6-qt6==6.11.*" in repo.calls()[-1]["read"][pins.CONSTRAINTS].splitlines()


def test_pyqt6_and_its_qt_move_onto_a_new_line_together(repo, capsys):
    """Two weeks on, 6.12.1 is old enough: PyQt6 and PyQt6-Qt6 both move to it, in every lock and the dev extra."""
    later = NOW + dt.timedelta(days=14)
    code, out, _ = repo.run(capsys, "--apply", now=later)
    assert code == pins.EXIT_NOTHING, out
    for stem in ("requirements", "requirements-test", "requirements-dev"):
        lock = repo.locked(stem)
        assert (lock["pyqt6"], lock["pyqt6-qt6"]) == ("6.12.1", "6.12.1"), stem
    pyproject = (repo.root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"PyQt6==6.12.1",\n    "PyQt6-Qt6==6.12.1",' in pyproject
    assert 'dependencies = ["PyQt6>=6.5"]' in pyproject  # the floor stays: only the dev extra moves


def test_the_real_lists_pin_pyqt6_and_its_qt_together():
    lists = pins.read_lists(REPO / "packaging")
    for lst in lists:
        group = {pin.key for pin in lst.infile.pins} & set(pins.QT_GROUP)
        assert group in (set(), set(pins.QT_GROUP)), f"{lst.infile.path.name} pins {group} without the rest of the Qt group"
    assert set(pins.QT_GROUP) <= set(pins.dev_extra(REPO / "pyproject.toml"))


def test_a_package_in_more_than_one_lock_stays_at_one_version(repo, capsys):
    """psutil 7.3.0 needs Python 3.12: the 3.14 lock could take it, the 3.11 ones can't, so none does."""
    repo.write_index(with_release(INDEX, "psutil", release("7.3.0", "2026-10-01", python=">=3.12")))
    code, out, _ = repo.run(capsys)
    assert code == pins.EXIT_MOVABLE
    assert not rows(out, "psutil"), "psutil would be at two versions"
    assert "psutil held at 7.2.2 in every lock" in out
    assert "psutil==7.2.2" in repo.calls()[-1]["read"][pins.CONSTRAINTS].splitlines()


def test_nothing_moves_backwards(repo, capsys, tmp_path):
    """A pin moved by hand to a release newer than the cutoff (a security fix) stays there."""
    newer = dict(IN_FILES, **{"requirements.in": IN_FILES["requirements.in"].replace("nuitka==4.3.1", "nuitka==4.3.5")})
    shutil.rmtree(repo.packaging)
    repo.log.unlink(missing_ok=True)
    (repo.root / "pyproject.toml").unlink()
    repo = Repo(tmp_path, INDEX, newer)
    code, out, _ = repo.run(capsys)
    assert code == pins.EXIT_MOVABLE  # the rest still moves
    assert not rows(out, "nuitka"), "nuitka went backwards"
    assert "nuitka stays at 4.3.5, which is newer than the cutoff (the newest before it is 4.3.4)" in out
    last = repo.calls()[-1]["argv"]
    assert last[last.index("--exclude-newer-package") + 1] == "nuitka=false"


# -- the report


def test_the_report_names_each_change_its_locks_and_the_commands_that_make_it(repo, capsys, tmp_path):
    report = tmp_path / "report.md"
    code, out, _ = repo.run(capsys, "--report", str(report))
    assert code == pins.EXIT_MOVABLE
    assert report.read_text(encoding="utf-8") == out
    assert out.startswith("# Python pins ready to move\n")
    assert f"taking only releases uploaded before {CUTOFF}, 14 days back" in out
    assert out.count("| Package |") == 1 and "## Locked with them" not in out  # only pins move: nothing else does
    assert ("| PyQt6-Qt6 | 6.11.2 | 6.11.3 | requirements-dev.txt, requirements-test.txt, requirements.txt | "
            "requirements-test.in, requirements.in, pyproject.toml (dev) |") in out
    assert f"python packaging/pins.py --apply --cutoff {CUTOFF}" in out
    for stem, command in COMMANDS.items():
        cut = command.replace(" --exclude-newer 2026-10-31", "")
        assert f"uv pip compile {cut} --exclude-newer {CUTOFF}\n" in out, stem


def test_the_report_lists_what_the_locks_alone_would_move(repo, capsys):
    repo.write_index(with_release(INDEX, "pluggy", release("1.7.0", "2026-10-02")))
    _, out, _ = repo.run(capsys)
    assert "## Locked with them" in out
    assert "| pluggy | 1.6.0 | 1.7.0 | requirements-dev.txt, requirements-test.txt |" in out


def test_nothing_to_move_says_so(repo, capsys):
    assert repo.run(capsys, "--apply", "--cutoff", CUTOFF)[0] == pins.EXIT_NOTHING
    code, out, _ = repo.run(capsys, "--cutoff", CUTOFF)
    assert code == pins.EXIT_NOTHING
    assert out.startswith("# Python pins: nothing to move\n")
    assert "## Moving them" not in out and "PyQt6 6.12.0 is skipped" in out


# -- moving them


def test_apply_moves_the_pins_and_locks_each_list_with_its_own_command(repo, capsys):
    code, out, err = repo.run(capsys, "--apply", "--cutoff", CUTOFF)
    assert code == pins.EXIT_NOTHING, err
    assert "Moved: packaging/requirements-dev.in, packaging/requirements-dev.txt" in out
    assert "nuitka==4.3.4; sys_platform == 'win32'  # Windows: compiles Chatmon\n" in repo.text("requirements.in")
    assert "PyQt6==6.11.0  # the Qt that ships\nPyQt6-Qt6==6.11.3\n" in repo.text("requirements.in")
    assert repo.text("requirements-test.in") == IN_FILES["requirements-test.in"].replace("PyQt6-Qt6==6.11.2", "PyQt6-Qt6==6.11.3")
    assert repo.text("requirements-dev.in") == IN_FILES["requirements-dev.in"].replace("0.17.3", "0.17.4")
    assert (repo.root / "pyproject.toml").read_text(encoding="utf-8") == PYPROJECT.replace("Qt6==6.11.2", "Qt6==6.11.3").replace("0.17.3", "0.17.4")
    moving = [call for call in repo.calls() if Path(call["cwd"]) == repo.packaging]
    assert [call["argv"][2] for call in moving] == ["requirements-dev.in", "requirements-test.in", "requirements.in"]
    for call in moving:
        stem = call["argv"][2].removesuffix(".in")
        command = COMMANDS[stem].replace(" --exclude-newer 2026-10-31", "")
        assert call["argv"] == ["pip", "compile", *command.split(), "--exclude-newer", CUTOFF, "--quiet"]
        assert call["preferences"] == repo.locked(stem)  # uv was handed the report's versions first
        assert repo.text(f"{stem}.txt").split("\n")[1] == f"#    uv pip compile {command} --exclude-newer {CUTOFF}"
    lock = repo.locked("requirements")
    assert (lock["nuitka"], lock["pyqt6"], lock["pyqt6-qt6"]) == ("4.3.4", "6.11.0", "6.11.3")
    built = repo.text("requirements.txt")
    for line in ("nuitka==4.3.4 ; sys_platform == 'win32' \\", "pyinstaller==6.22.3 ; sys_platform == 'darwin' \\",
                 "altgraph==0.17.5 ; sys_platform == 'darwin' \\", "macholib==1.16.4 ; sys_platform == 'darwin' \\"):
        assert line in built.splitlines()
    assert repo.locked("requirements-dev")["ruff"] == "0.17.4"


def test_after_apply_the_lists_agree_as_tests_test_requirements_wants(repo, capsys):
    assert repo.run(capsys, "--apply", "--cutoff", CUTOFF)[0] == pins.EXIT_NOTHING
    lists = pins.read_lists(repo.packaging)
    by_name = {lst.infile.path.name: lst for lst in lists}
    for lst in lists:
        wanted = {pin.key: pin.version for name in (lst.infile.path.name, *lst.infile.includes) for pin in by_name[name].infile.pins}
        assert {key: lst.current[key] for key in wanted} == wanted, lst.txt.name
    dev = by_name["requirements-dev.in"]
    pinned = {pin.key: pin.version for name in ("requirements-dev.in", "requirements-test.in") for pin in by_name[name].infile.pins}
    assert pins.dev_extra(repo.root / "pyproject.toml") == pinned
    seen = {}
    for lst in lists:
        for name, version in lst.current.items():
            assert seen.setdefault(name, version) == version, f"{name} locked at {seen[name]} and {version}"
    assert dev.current["ruff"] == "0.17.4"


def test_apply_puts_every_file_back_when_a_lock_fails(repo, capsys, monkeypatch):
    before = repo.hashes()
    monkeypatch.setenv("FAKE_UV_FAIL", "requirements.txt")
    code, _, err = repo.run(capsys, "--apply", "--cutoff", CUTOFF)
    assert code == pins.EXIT_ERROR
    assert "failed" in err
    assert repo.hashes() == before


# -- the real thing


@pytest.mark.skipif(os.environ.get("CHATMON_PINS_NETWORK") != "1", reason="runs the real uv against PyPI: set CHATMON_PINS_NETWORK=1 to run it")
def test_the_real_lists_with_the_real_uv(capsys):
    uv = shutil.which("uv")
    assert uv, "no uv on PATH: pip install --require-hashes -r packaging/requirements-pins.txt"
    before = {path.name: path.read_bytes() for path in (REPO / "packaging").glob("requirements*")}
    code = pins.main([], uv=[uv])
    out = capsys.readouterr().out
    assert code in (pins.EXIT_NOTHING, pins.EXIT_MOVABLE), out
    assert out.startswith("# Python pins")
    assert {path.name: path.read_bytes() for path in (REPO / "packaging").glob("requirements*")} == before
