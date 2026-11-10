# PyInstaller's recipe for the Chatmon the Windows and macOS installers carry, a Python of its own included.
# packaging/build.py runs it: python -m PyInstaller packaging/chatmon.spec
#
# Windows: one folder with two programs on the same files, chatmon.exe (a console program, for hooks
# and the command line) and chatmonw.exe (no console window: the Start menu, the desktop, autostart).
# macOS: Chatmon.app, its program also the command line (the .pkg puts a `chatmon` that runs it on PATH).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is PyInstaller's)
sys.path.insert(0, str(ROOT))
import chatmon  # noqa: E402

NAME = "Chatmon"
VERSION = chatmon.__version__
ICONS = ROOT / "packaging" / "icons"
BUNDLE_ID = "io.github.randynorthrup.chatmon"

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    datas=collect_data_files("chatmon", excludes=["**/__pycache__"]),  # the sprites, bubbles and the Claude Code plugin
    # Imported where they're used, not at the top: named so they're surely in.
    hiddenimports=["chatmon.app", "chatmon.agents", "chatmon.autostart", "chatmon.winpipe", "chatmon.winlock"],
    excludes=["tkinter", "unittest", "pydoc_data", "test"],
)
pyz = PYZ(a.pure)  # noqa: F821

if sys.platform == "win32":
    version_info = ROOT / "build" / "version_info.txt"  # written by packaging/build.py
    programs = [
        EXE(  # noqa: F821
            pyz, a.scripts, [], exclude_binaries=True, name=name, console=console, upx=False,
            icon=str(ICONS / "chatmon.ico"), version=str(version_info) if version_info.exists() else None,
        )
        for name, console in (("chatmon", True), ("chatmonw", False))
    ]
    COLLECT(*programs, a.binaries, a.datas, name=NAME, upx=False)  # noqa: F821
else:
    program = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, argv_emulation=False, upx=False)  # noqa: F821
    files = COLLECT(program, a.binaries, a.datas, name=NAME, upx=False)  # noqa: F821
    if sys.platform == "darwin":
        BUNDLE(  # noqa: F821
            files,
            name=f"{NAME}.app",
            icon=str(ICONS / "chatmon.icns"),
            bundle_identifier=BUNDLE_ID,
            version=VERSION,
            info_plist={
                "CFBundleName": NAME,
                "CFBundleDisplayName": NAME,
                "CFBundleShortVersionString": VERSION,
                "CFBundleVersion": VERSION,
                "LSUIElement": True,  # it lives on the desktop and in the menu bar: no Dock icon
                "NSHighResolutionCapable": True,
                "NSHumanReadableCopyright": "Copyright (c) 2026 Randy Northrup. MIT License.",
            },
        )
