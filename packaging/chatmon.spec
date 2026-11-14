# PyInstaller's recipe for the Chatmon the macOS installers carry, a Python of its own included:
# Chatmon.app, its program also the command line (the .pkg puts a `chatmon` that runs it on PATH).
# packaging/build.py runs it: python -m PyInstaller packaging/chatmon.spec
# Windows' is compiled with Nuitka instead (build.py), which doesn't support PyQt6 on macOS; see
# packaging/README.md for why Windows needs it and macOS doesn't.

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
    # macOS's own entry: the chatmon command, and `Chatmon verify-update`, root's check of an update (see there).
    [str(ROOT / "packaging" / "macos" / "entry.py")],
    pathex=[str(ROOT)],
    datas=collect_data_files("chatmon", excludes=["**/__pycache__"]),  # the sprites, bubbles and the Claude Code plugin
    # Imported where they're used, not at the top: named so they're surely in.
    hiddenimports=["chatmon.app", "chatmon.agents", "chatmon.autostart", "chatmon.releasecheck"],
    excludes=["tkinter", "unittest", "pydoc_data", "test"],
)
pyz = PYZ(a.pure)  # noqa: F821

program = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=False, argv_emulation=False, upx=False)  # noqa: F821
files = COLLECT(program, a.binaries, a.datas, name=NAME, upx=False)  # noqa: F821
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
        "LSMinimumSystemVersion": "13.0",  # Qt 6.11's own minimum, and SMAppService's (starting at login)
        "NSHighResolutionCapable": True,
        # What macOS shows when it asks you to let Chatmon reach a model server on another computer.
        "NSLocalNetworkUsageDescription": "Chatmon talks to model servers on your network, such as Ollama or LM Studio on another computer, when you choose one as its brain.",
        "NSHumanReadableCopyright": "Copyright (c) 2026 Randy Northrup. MIT License.",
    },
)
