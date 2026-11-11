"""Build Chatmon's installers and packages, and check an installed one works.

  python packaging/build.py windows   dist/Chatmon-<v>-windows-x64-setup.exe     PyInstaller, then Inno Setup 6
  python packaging/build.py macos     dist/Chatmon-<v>-macos-<arch>.pkg, .dmg    PyInstaller, pkgbuild, hdiutil
  python packaging/build.py linux     dist/chatmon_<v>-1_all.deb, -1.noarch.rpm nfpm, for the system's Python and PyQt6
  python packaging/build.py version   the version they're built as (chatmon/__init__.py's)
  python packaging/build.py smoke CLI APP [--version V]
      Start an installed Chatmon (APP), talk to it with its command line (CLI), and quit it, in a scratch
      home of its own and without a screen (Qt's offscreen platform).

Needs PyInstaller (windows, macos), Inno Setup 6's ISCC (windows: on PATH, in its usual folders, or $ISCC)
and nfpm (linux: on PATH or $NFPM). Only the standard library here, so smoke runs on any Python.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
BUNDLE_ID = "io.github.randynorthrup.chatmon"


def version() -> str:
    text = (ROOT / "chatmon" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def run(*argv, **kwargs) -> subprocess.CompletedProcess:
    print("+", " ".join(str(a) for a in argv), flush=True)
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def pyinstaller() -> Path:
    """Freeze Chatmon with PyInstaller; returns where it put it."""
    out = BUILD / "pyinstaller"
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", out, "--workpath", BUILD / "pyinstaller-work", PACKAGING / "chatmon.spec")
    return out


# -- Windows


def _version_info(v: str) -> None:
    """The version, name and maker that Explorer and Task Manager show for chatmon.exe and chatmonw.exe."""
    numbers = (tuple(int(n) for n in re.findall(r"\d+", v)[:3]) + (0, 0, 0, 0))[:4]
    strings = {
        "CompanyName": "Randy Northrup",
        "FileDescription": "Chatmon",
        "FileVersion": v,
        "InternalName": "chatmon",
        "LegalCopyright": "Copyright (c) 2026 Randy Northrup. MIT License.",
        "ProductName": "Chatmon",
        "ProductVersion": v,
    }
    table = ",\n          ".join(f"StringStruct({k!r}, {s!r})" for k, s in strings.items())
    BUILD.mkdir(exist_ok=True)
    (BUILD / "version_info.txt").write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
          {table}])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )


def _iscc() -> str:
    found = os.environ.get("ISCC") or shutil.which("iscc")
    if found:
        return found
    # Where its installer puts it: for you alone, or for everyone.
    for base, sub in (("LOCALAPPDATA", "Programs"), ("ProgramFiles(x86)", ""), ("ProgramFiles", "")):
        if os.environ.get(base) and (candidate := Path(os.environ[base], sub, "Inno Setup 6", "ISCC.exe")).exists():
            return str(candidate)
    sys.exit("Inno Setup 6 isn't installed (or set ISCC to its ISCC.exe).")


def windows() -> Path:
    v = version()
    _version_info(v)
    frozen = pyinstaller() / "Chatmon"
    for program in ("chatmon.exe", "chatmonw.exe"):
        if not (frozen / program).exists():
            sys.exit(f"PyInstaller made no {program}")
    DIST.mkdir(exist_ok=True)
    run(_iscc(), f"/DAppVersion={v}", f"/DSourceDir={frozen}", f"/DOutputDir={DIST}", PACKAGING / "windows" / "chatmon.iss")
    setup = DIST / f"Chatmon-{v}-windows-x64-setup.exe"
    print(f"\n{setup}  {setup.stat().st_size // 2**20} MB")
    return setup


# -- macOS


def macos() -> list[Path]:
    v = version()
    arch = {"x86_64": "intel", "arm64": "arm64"}.get(platform.machine(), platform.machine())
    app = pyinstaller() / "Chatmon.app"
    run("codesign", "--force", "--deep", "--sign", "-", app)  # ad hoc: Apple silicon runs nothing unsigned
    work = BUILD / "macos"
    shutil.rmtree(work, ignore_errors=True)
    (work / "root" / "Applications").mkdir(parents=True)
    run("ditto", app, work / "root" / "Applications" / "Chatmon.app")  # ditto keeps the bundle's links and signature
    scripts = work / "scripts"
    shutil.copytree(PACKAGING / "macos" / "scripts", scripts)
    for script in scripts.iterdir():
        script.chmod(0o755)
    # Installed where it belongs, never "relocated" to wherever another copy of the app happens to be.
    run("pkgbuild", "--analyze", "--root", work / "root", work / "component.plist")
    run("plutil", "-replace", "0.BundleIsRelocatable", "-bool", "NO", work / "component.plist")
    run("pkgbuild", "--root", work / "root", "--component-plist", work / "component.plist", "--identifier", BUNDLE_ID, "--version", v,
        "--install-location", "/", "--scripts", scripts, work / "Chatmon.pkg")
    run("productbuild", "--synthesize", "--package", work / "Chatmon.pkg", work / "distribution.xml")
    distribution = (work / "distribution.xml").read_text(encoding="utf-8")  # the installer's window says "Chatmon"
    (work / "distribution.xml").write_text(distribution.replace("<options ", "<title>Chatmon</title>\n    <options ", 1), encoding="utf-8")
    DIST.mkdir(exist_ok=True)
    pkg = DIST / f"Chatmon-{v}-macos-{arch}.pkg"
    run("productbuild", "--distribution", work / "distribution.xml", "--package-path", work, pkg)
    dmg_root = work / "dmg"
    dmg_root.mkdir()
    run("ditto", app, dmg_root / "Chatmon.app")
    (dmg_root / "Applications").symlink_to("/Applications")
    dmg = DIST / f"Chatmon-{v}-macos-{arch}.dmg"
    dmg.unlink(missing_ok=True)
    run("hdiutil", "create", "-volname", "Chatmon", "-srcfolder", dmg_root, "-ov", "-format", "UDZO", dmg)
    for out in (pkg, dmg):
        print(f"{out}  {out.stat().st_size // 2**20} MB")
    return [pkg, dmg]


# -- Linux


def _stage_package() -> None:
    """The chatmon package as the deb and rpm install it: its modules (with Unix line endings, whatever
    the checkout had) and its data, no caches."""
    out = BUILD / "linux" / "chatmon"
    shutil.rmtree(out.parent, ignore_errors=True)
    for path in sorted((ROOT / "chatmon").rglob("*")):
        rel = path.relative_to(ROOT / "chatmon")
        if path.is_dir() or "__pycache__" in rel.parts or path.suffix in (".pyc", ".pyo"):
            continue
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in (".py", ".json", ".toml", ".txt", ".md"):
            target.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        else:
            shutil.copyfile(path, target)
        target.chmod(0o644)
    for folder in [out, *(p for p in out.rglob("*") if p.is_dir())]:
        folder.chmod(0o755)  # whatever the umask or the checkout's own modes


def linux() -> list[Path]:
    nfpm = os.environ.get("NFPM") or shutil.which("nfpm")
    if not nfpm:
        sys.exit("nfpm isn't installed (https://nfpm.goreleaser.com), or set NFPM to it.")
    _stage_package()
    DIST.mkdir(exist_ok=True)
    env = dict(os.environ, CHATMON_VERSION=version())
    made = []
    for packager in ("deb", "rpm"):
        before = set(DIST.iterdir())
        run(nfpm, "package", "--config", PACKAGING / "linux" / "nfpm.yaml", "--packager", packager, "--target", DIST, cwd=ROOT, env=env)
        made += sorted(set(DIST.iterdir()) - before)
    for out in made:
        print(f"{out}  {out.stat().st_size // 2**20} MB")
    return made


# -- checking an installed one


def smoke(cli: str, app: str, expected: str | None = None) -> None:
    cli, app = (shutil.which(p) or str(Path(p).resolve()) for p in (cli, app))  # a command's name, or a path to it
    home =Path(tempfile.mkdtemp(prefix="cm-", dir=None if sys.platform == "win32" else "/tmp"))  # a short path: macOS caps socket paths
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "AppData"),
               XDG_CONFIG_HOME=str(home / ".config"), XDG_STATE_HOME=str(home / ".state"), XDG_RUNTIME_DIR=str(home))
    if sys.platform == "win32":
        env["USERNAME"] = f"chatmon-smoke-{os.getpid()}"  # a pipe of its own, whatever Chatmon you have running
    env.pop("CHATMON_INTERNAL", None)

    def say(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
        return subprocess.run([cli, *args], env=env, capture_output=True, text=True, timeout=timeout)

    shown = say("--version").stdout.strip()
    print(f"{cli} --version: {shown}")
    if expected and shown != expected:
        sys.exit(f"expected version {expected}")
    log = home / "app-output.txt"
    with open(log, "w") as out:
        running = subprocess.Popen([app], env=env, stdout=out, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if running.poll() is not None:
                break
            if say("say", "hello from the smoke test").returncode == 0:
                break
            time.sleep(1)
        else:
            running.poll()
        if running.returncode is not None:
            sys.exit(f"the app stopped (exit {running.returncode}) before it answered:\n{_output(home, log)}")
        if say("say", "still here").returncode != 0:
            sys.exit(f"the app never answered:\n{_output(home, log)}")
        print("it answered")
        asked = say("quit")
        if asked.returncode != 0:  # the request itself didn't get there: say why, not just that it's still running
            sys.exit(f"`quit` didn't reach it (exit {asked.returncode}): {asked.stderr.strip()}\n{_output(home, log)}")
        try:
            code = running.wait(30)
        except subprocess.TimeoutExpired:
            sys.exit(f"it was asked to quit and didn't, in 30 s:\n{_stack(running.pid)}\n{_output(home, log)}")
        if code != 0:
            sys.exit(f"it quit with exit code {code}:\n{_output(home, log)}")
        print("it quit when asked: all good")
    finally:
        if running.poll() is None:
            running.kill()
        shutil.rmtree(home, ignore_errors=True)


def _stack(pid: int) -> str:
    """Where a process that won't quit is stuck, as far as the system can show without a debugger: macOS's
    `sample` (native stacks of every thread), else nothing."""
    if sys.platform == "darwin" and shutil.which("sample"):
        try:
            shown = subprocess.run(["sample", str(pid), "3"], capture_output=True, text=True, timeout=60)
            return "where it was:\n" + (shown.stdout or shown.stderr)[-12000:]
        except (OSError, subprocess.SubprocessError) as exc:
            return f"(couldn't sample it: {exc})"
    return ""


def _output(home: Path, log: Path) -> str:
    texts = [p.read_text(errors="replace") for p in [log, *home.rglob("chatmon.log")] if p.exists()]
    return "\n".join(t for t in texts if t.strip()) or "(it printed nothing)"


def main(argv: list[str]) -> None:
    if argv == ["version"]:
        print(version())
        return
    if not argv or argv[0] not in ("windows", "macos", "linux", "smoke"):
        sys.exit(__doc__)
    if argv[0] == "smoke":
        args = argv[1:]
        expected = None
        if "--version" in args:
            i = args.index("--version")
            expected = args[i + 1]
            del args[i : i + 2]
        if len(args) != 2:
            sys.exit(__doc__)
        smoke(*args, expected=expected)
        return
    {"windows": windows, "macos": macos, "linux": linux}[argv[0]]()


if __name__ == "__main__":
    main(sys.argv[1:])
