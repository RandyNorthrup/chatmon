#!/bin/bash
# Red drill on .github/scripts/distro-tests.sh, as CI's distro jobs run it: does a failing test fail the script, and so
# the job? Green, red and restored green, each a fresh debian:trixie container on its own PyQt6, run against a copy of
# the tree (the files git lists, LF as git stores them; art/ and docs/ left out as the drill harness leaves them out).
# usage (in WSL): bash distro_drill.sh WORKTREE FILES OUTDIR   (FILES: git ls-files -co --exclude-standard -z, from Windows)
set -u
root=$1; files=$2; out=$3
work=$(mktemp -d /var/tmp/chatmon-distro-drill-XXXXXX)
trap 'rm -rf "$work"' EXIT
(cd "$root" && tr '\0' '\n' < "$files" | grep -v -e '^art/' -e '^docs/' | while IFS= read -r f; do [ -f "$f" ] && mkdir -p "$work/src/$(dirname "$f")" && cp -p "$f" "$work/src/$f"; done)
target=tests/test_cli.py
find='    assert cli.main(["--help"]) == 0'
replace='    assert cli.main(["--help"]) == 1'
summary=$out/distro-drill.log
run() {  # $1: green, red or restored
    podman run --rm -v "$work/src:/src:ro" debian:trixie sh /src/.github/scripts/distro-tests.sh > "$out/distro-drill-$1.log" 2>&1
    code=$?
    echo "$1: exit $code, $(tail -1 "$out/distro-drill-$1.log")" >> "$summary"
    return $code
}
{
    echo "# Red drill on .github/scripts/distro-tests.sh in debian:trixie (podman $(podman --version | cut -d' ' -f3)), $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# copy: $work/src, $(find "$work/src" -type f | wc -l) files"
    echo "# $target sha256 before: $(sha256sum "$work/src/$target" | cut -d' ' -f1)"
} > "$summary"
before=$(sha256sum "$work/src/$target" | cut -d' ' -f1)
run green; green=$?
count=$(grep -cF "$find" "$work/src/$target")
echo "# mutation: in the copy, '$find' (found $count time) made '$replace'" >> "$summary"
cp -p "$work/src/$target" "$work/original.py"
python3 - "$work/src/$target" "$find" "$replace" <<'PY'
import sys
path, find, replace = sys.argv[1:]
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8", newline="").write(text.replace(find, replace, 1))
PY
mutated=$(sha256sum "$work/src/$target" | cut -d' ' -f1)
echo "# $target sha256 mutated: $mutated" >> "$summary"
run red; red=$?
grep -m1 -E "^_+ test_help_version" "$out/distro-drill-red.log" >> "$summary"
grep -m1 -E "^E +AssertionError" "$out/distro-drill-red.log" >> "$summary"
cp -p "$work/original.py" "$work/src/$target"
after=$(sha256sum "$work/src/$target" | cut -d' ' -f1)
echo "# $target sha256 restored: $after ($([ "$after" = "$before" ] && echo same as before || echo DIFFERENT))" >> "$summary"
run restored; restored=$?
echo "# exits: green $green, red $red, restored $restored" >> "$summary"
[ "$green" = 0 ] && [ "$red" != 0 ] && [ "$restored" = 0 ] && [ "$after" = "$before" ] && [ "$count" = 1 ]
ok=$?
echo "# drill $([ $ok = 0 ] && echo PASS || echo FAIL)" >> "$summary"
# The same record tests/drills/run.py writes for a drill, so a receipt reads this drill the way it reads the others.
python3 - "$out/distro-drill-results.json" "$ok" "$green" "$red" "$restored" "$before" "$mutated" "$after" "$target" "$find" "$replace" "$out/distro-drill-red.log" <<'PY'
import json, sys
out, ok, green, red, restored, before, mutated, after, target, find, replace, red_log = sys.argv[1:]
expected = "test_help_version_and_what_it_doesnt_know"
observed = next((line.strip() for line in open(red_log, encoding="utf-8", errors="replace") if expected in line), "")
record = {"id": "W4-M6A-03-distro-fails-on-a-failed-test", "requirement": "M6A-03.A1", "file": target,
          "mutation": {"find": find, "replace": replace},
          "command": ["podman", "run", "--rm", "-v", "<copy>:/src:ro", "debian:trixie", "sh", "/src/.github/scripts/distro-tests.sh"],
          "expected": [expected], "status": "pass" if ok == "0" else "fail", "reason": None if ok == "0" else "see distro-drill.log",
          "before_sha256": before, "baseline_exit": int(green), "mutated_sha256": mutated, "mutated_exit": int(red),
          "observed": observed, "after_sha256": after, "restored_exit": int(restored)}
open(out, "w", encoding="utf-8").write(json.dumps([record], indent=2) + chr(10))
PY
exit $ok
