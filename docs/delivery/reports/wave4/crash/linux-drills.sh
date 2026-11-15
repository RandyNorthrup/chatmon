#!/bin/sh
# The new tests green, each red under its mutation, and green again, in a copy of the container's checkout (fedora:44).
set -u
src=/home/chatmon-tests/chatmon
T1="tests/test_app_smoke.py::test_a_quit_companion_is_freed_between_tests_never_inside_qts_own_loops"
T2="tests/test_app_smoke.py::test_a_quit_companion_never_looks_at_the_agents_again"
work=$(mktemp -d)
cp -R "$src" "$work/c"
cd "$work/c"
run() { python3 -m pytest -q -p no:cacheprovider "$@" > "$work/out.txt" 2>&1; rc=$?; echo "  exit $rc: $(tail -1 "$work/out.txt")"; grep -o "windows freed inside Qt's loop: [0-9]*\|Fatal Python error: [A-Za-z ]*\|0x[0-9a-f]\{8\}'\|QApplicationPrivate::[A-Za-z_]*\|_ZN[0-9]*QApplicationPrivate[0-9]*[A-Za-z_]*" "$work/out.txt" | sort | uniq -c | sed 's/^/    /'; }
echo "green:"; run "$T1" "$T2"
cp tests/app_harness.py "$work/h"; cp chatmon/app.py "$work/a"
python3 - <<'PY'
p = "tests/app_harness.py"; s = open(p, newline="").read()
f = "_QUIT.extend([c, *(w for w in QApplication.topLevelWidgets() if sip.unwrapinstance(w) not in others)])"
assert s.count(f) == 1; open(p, "w", newline="").write(s.replace(f, "pass"))
PY
echo "red (CRASH-01, the harness holds nothing):"; run "$T1"
cp "$work/h" tests/app_harness.py
python3 - <<'PY'
p = "chatmon/app.py"; s = open(p, newline="").read()
f = "        if self._quitting:\r\n            return\r\n        if self._refreshing:"
assert s.count(f) == 1; open(p, "w", newline="").write(s.replace(f, "        if self._refreshing:"))
PY
echo "red (CRASH-02, no guard):"; run "$T2"
cp "$work/a" chatmon/app.py
echo "green again:"; run "$T1" "$T2"
rm -rf "$work"
