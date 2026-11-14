"""Every module the hotkey, sound and toast work added or changed imports on every OS, each in a fresh interpreter:
its platform's libraries are loaded when used, never on import."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MODULES = ["hotkey", "sound", "wintoast", "wincaret", "winrt", "winfocus", "libdbus", "shortcutportal"]


@pytest.mark.parametrize("module", MODULES)
def test_it_imports_here(module):
    env = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", f"import chatmon.{module}"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
