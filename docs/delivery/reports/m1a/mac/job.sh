#!/bin/sh
# One step of Chatmon's macOS drills on the owner's Mac, with everything kept in one folder of its own.
#
# usage: sh job.sh STEP [ARGS...]
#
# T (~/chatmon-drills-tmp) holds src/ (`git archive` of the commit drilled), venv/, and this folder (mac/).
# Every step runs with HOME and TMPDIR inside T: what a test writes through Path.home() or a temporary folder
# (Chatmon's settings and state, a login entry, agents' configs) can't reach the owner's own folders, and pip
# reads none of the owner's configuration and keeps no cache.
#
# steps:
#   setup PYTHON        a venv of PYTHON in T/venv with packaging/requirements-test.txt, hash-locked; src/ made a
#                       git work tree of its own with every file in its index (no commit), so tests/drills/run.py
#                       and tests/test_package_data.py list the files a checkout tracks
#   observe             the platform and every version the steps run with
#   drills SPEC LOG     tests/drills/run.py SPEC --log LOG (green, red, green, each in a copy of src/)
#   suite LOG           every test, as CI's "Every test" step does, offscreen
#   macnative LOG       tests/test_macnative.py on Qt's cocoa platform, as CI's last macOS step does
#   hotkeys-free LOG    the combinations the hotkey tests register can each be registered exclusively again
#
# The drills that need the window server (Carbon's hot keys, NSSound) and the last three steps run in the
# signed-in user's Aqua session, through aqua.sh; the others run as they are, over ssh.
set -eu
T="$HOME/chatmon-drills-tmp"
export HOME="$T/home" TMPDIR="$T/tmp/"
export PIP_CONFIG_FILE=/dev/null PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
unset XDG_RUNTIME_DIR XDG_CONFIG_HOME XDG_STATE_HOME XDG_DATA_HOME XDG_CACHE_HOME \
    CLAUDE_CONFIG_DIR CODEX_HOME GEMINI_CLI_HOME GROK_HOME COPILOT_HOME CHATMON_TEST_CLIPBOARD 2>/dev/null || true
mkdir -p "$HOME" "$TMPDIR"
PY="$T/venv/bin/python"
SRC="$T/src"
# The one test left out of the suite: it keeps a key in, and takes it out of, the owner's own login keychain.
KEYCHAIN=tests/test_keychain.py::test_macos_keychain_keeps_replaces_and_forgets_a_key

step=$1
shift
case "$step" in
setup)
    "$1" -m venv "$T/venv"
    "$PY" -m pip install --quiet --require-hashes -r "$SRC/packaging/requirements-test.txt"
    cd "$SRC"
    git -c init.defaultBranch=drills init -q
    git config core.excludesFile /dev/null
    git add -A
    ;;
observe)
    sw_vers
    echo "machine: $(uname -m)"
    echo "kernel: $(uname -r)"
    echo "python: $("$PY" -c 'import sys; print(sys.version.replace(chr(10), " "))')"
    echo "base python: $("$PY" -c 'import sys; print(sys._base_executable)')"
    "$PY" -c 'import PyQt6.QtCore as q; print("pyqt6:", q.PYQT_VERSION_STR, "built for qt:", q.QT_VERSION_STR, "qt:", q.qVersion())'
    "$PY" -m pytest --version
    "$PY" -m pip freeze --all
    git --version
    echo "launchd session: $(launchctl managername)"
    ;;
drills)
    cd "$SRC"
    QT_QPA_PLATFORM=offscreen "$PY" tests/drills/run.py "$1" --log "$2"
    ;;
suite)
    cd "$SRC"
    QT_QPA_PLATFORM=offscreen "$PY" -m pytest -p no:cacheprovider --deselect "$KEYCHAIN" > "$1" 2>&1 || code=$?
    echo "# exit ${code:-0}" >> "$1"
    ;;
macnative)
    cd "$SRC"
    QT_QPA_PLATFORM=cocoa "$PY" -m pytest -p no:cacheprovider tests/test_macnative.py > "$1" 2>&1 || code=$?
    echo "# exit ${code:-0}" >> "$1"
    ;;
hotkeys-free)
    cd "$SRC"
    PYTHONPATH="$SRC" QT_QPA_PLATFORM=offscreen "$PY" - > "$1" 2>&1 <<'EOF'
"""Each combination the hotkey tests and drills register (Command+Option+Shift and F17, F18, F19) can be
registered exclusively by another process now: none is still held."""
import ctypes

from chatmon import hotkey

lib = ctypes.cdll.LoadLibrary(hotkey._Carbon.CARBON)
lib.GetApplicationEventTarget.restype = ctypes.c_void_p
lib.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, hotkey._EventHotKeyID, ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.POINTER(ctypes.c_void_p)]
lib.RegisterEventHotKey.restype = ctypes.c_int32
lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
lib.UnregisterEventHotKey.restype = ctypes.c_int32
flags = hotkey._Carbon.FLAGS
held = 0
for key in ("F17", "F18", "F19"):
    ref = ctypes.c_void_p()
    status = lib.RegisterEventHotKey(hotkey.KEYS[key].mac, flags["ctrl"] | flags["alt"] | flags["shift"], hotkey._EventHotKeyID(hotkey.fourcc("FREE"), 1),
                                     lib.GetApplicationEventTarget(), hotkey._Carbon.EXCLUSIVE, ctypes.byref(ref))
    freed = lib.UnregisterEventHotKey(ref) if status == 0 else None
    print(f"Command+Option+Shift+{key}: exclusive registration {status}, unregistered {freed}")
    held += status != 0
print("all free" if not held else f"{held} still held")
raise SystemExit(1 if held else 0)
EOF
    ;;
*)
    echo "job.sh: no step $step" >&2
    exit 64
    ;;
esac
