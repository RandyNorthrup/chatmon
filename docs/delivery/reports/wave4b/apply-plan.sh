#!/bin/bash
# Round two: bind one plan at bf9d8ac and validate it.   bash docs/delivery/reports/wave4b/apply-plan.sh ID SLUG
set -e
cd /c/Users/Randy/Coding/chatmon-wt/plans2
V=/c/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py
id=$1; slug=$2; D=docs/delivery/reports/$id/wave4b
python docs/delivery/reports/wave4/mkbind2.py "$id"
python docs/delivery/reports/wave4/bind.py "$D/bindings.json" --apply
test -f "$D/context.json"
set +e
for st in resume closure; do
  { echo "\$ python verify-delivery.py --root . --plan docs/delivery/$slug.md --stage $st --context $D/context.json"; python $V --root . --plan docs/delivery/$slug.md --stage $st --context "$D/context.json"; echo "exit $?"; } > "$D/validate-$st.txt" 2>&1
  sed -n 2p "$D/validate-$st.txt"; grep -v "^Checked\|^Structural\|^\$" "$D/validate-$st.txt" | tail -12
done
