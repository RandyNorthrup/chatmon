"""Every module of Chatmon imports on the OS the tests run on, in a fresh interpreter: what only one platform has
(Windows' WINFUNCTYPE and DLLs, macOS's frameworks, Linux's libraries) is reached when it's used, never on import.
CI runs this on Linux, Windows and macOS, so a module that imports only where it was written fails somewhere."""

import json
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

import chatmon

ROOT = Path(__file__).resolve().parent.parent
NOT_IMPORTED = {"__main__"}  # it runs the command line as it's imported; cli is imported instead

IMPORT_EACH = """
import importlib, json, sys, traceback
failed = {}
for name in sys.argv[1:]:
    try:
        importlib.import_module("chatmon." + name)
    except BaseException:
        failed[name] = traceback.format_exc(limit=3)
print(json.dumps(failed))
"""


def test_every_module_imports_here():
    names = sorted(m.name for m in pkgutil.iter_modules(chatmon.__path__) if m.name not in NOT_IMPORTED)
    assert len(names) > 60 and "cli" in names and "winuia" in names and "macnative" in names  # every module was found
    env = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", IMPORT_EACH, *names], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    failed = json.loads(out.stdout.strip().splitlines()[-1])
    assert not failed, "\n".join(f"chatmon.{name} doesn't import on {sys.platform}:\n{why}" for name, why in failed.items())
