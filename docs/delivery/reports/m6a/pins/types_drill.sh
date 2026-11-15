#!/bin/bash
# Red drill for pins.yml's types job: the job's own mypy step (its run: block, read out of pins.yml), on a copy of
# HEAD's packaging/ and pyproject.toml. Green; then red, with a type broken in packaging/pins.py (release_line hands
# back a str where its signature promises an int); then green again, the file's bytes put back and checked by SHA-256.
#
# usage, from the repository's root: bash docs/delivery/reports/m6a/pins/types_drill.sh BIN
#   BIN: the folder holding the mypy that packaging/requirements-dev.txt installs (a venv's bin/ or Scripts/)
set -u
export PATH="$1:$PATH"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git archive HEAD packaging pyproject.toml | tar -x -C "$work"
awk '/name: mypy --strict on pins.py/ {found=1}
     found && /run: \|/ {inside=1; next}
     inside && /^      - / {exit}
     inside {sub(/^          /, ""); print}' .github/workflows/pins.yml > "$work/step.sh"
pins="$work/packaging/pins.py"
find='    return parts[0], parts[1]'
broken='    return parts[0], str(parts[1])'

echo "# HEAD $(git rev-parse HEAD); mypy $(mypy --version)"
echo "## the step, as pins.yml's types job runs it (bash -eo pipefail, as Actions does)"
cat "$work/step.sh"
step() { (cd "$work" && bash --noprofile --norc -eo pipefail step.sh 2>&1); }
sha() { sha256sum "$pins" | cut -c1-64; }

before=$(sha)
echo "## green: packaging/pins.py at sha256 $before"
step; green=$?
echo "exit $green"

[ "$(grep -cxF "$find" "$pins")" = 1 ] || { echo "the mutation's text isn't in pins.py exactly once"; exit 2; }
cp "$pins" "$work/pins.py.orig"
python - "$pins" "$find" "$broken" <<'EOF'
import sys
path, find, broken = sys.argv[1:]
text = open(path, encoding="utf-8", newline="").read()
open(path, "w", encoding="utf-8", newline="").write(text.replace(find, broken))
EOF
echo "## red: '$find' -> '$broken' (sha256 $(sha))"
red_out=$(step); red=$?
echo "$red_out"
echo "exit $red"

cp "$work/pins.py.orig" "$pins"
after=$(sha)
echo "## restored: sha256 $after ($([ "$after" = "$before" ] && echo same || echo DIFFERENT) as before)"
step; restored=$?
echo "exit $restored"

errors=$(grep -c 'error: Incompatible return value type' <<<"$red_out")
if [ "$green" = 0 ] && [ "$red" != 0 ] && [ "$errors" = 3 ] && [ "$after" = "$before" ] && [ "$restored" = 0 ]; then
    echo "PASS: green, red on each of linux, win32 and darwin ($errors errors), green again"
    exit 0
fi
echo "FAIL: green $green, red $red with $errors errors, restored $restored"
exit 1
