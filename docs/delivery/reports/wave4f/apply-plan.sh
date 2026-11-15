#!/bin/bash
# The final round, M6A's section: bind one plan at 45a17b3 and validate it.   bash docs/delivery/reports/wave4f/apply-plan.sh ID SLUG [--dry]
# --dry writes the candidate (docs/delivery/reports/wave4/candidates/) and leaves the plan as it is.
set -e
cd /c/Users/Randy/Coding/chatmon-wt/plans-final
V=/c/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py
id=$1; slug=$2; D=docs/delivery/reports/$id/wave4f
python docs/delivery/reports/wave4/mkbind5.py "$id"
if [ "$3" = --dry ]; then python docs/delivery/reports/wave4/bind.py "$D/bindings.json"; exit $?; fi
python docs/delivery/reports/wave4/bind.py "$D/bindings.json" --apply
test -f "$D/context.json"
set +e
for st in resume closure; do
  { echo "\$ python verify-delivery.py --root . --plan docs/delivery/$slug.md --stage $st --context $D/context.json"; python $V --root . --plan docs/delivery/$slug.md --stage $st --context "$D/context.json"; echo "exit $?"; } > "$D/validate-$st.txt" 2>&1
  sed -n 2p "$D/validate-$st.txt"; grep -v "^Checked\|^Structural\|^\$" "$D/validate-$st.txt" | tail -12
done
