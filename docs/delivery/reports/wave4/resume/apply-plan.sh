#!/bin/bash
# usage: apply-plan.sh ID PLANSLUG
set -e
cd /c/Users/Randy/Coding/chatmon-wt/plans
W=C:/Users/Randy/AppData/Local/Temp/claude/7c6ca09538d30e43/c556eb9f-f3e9-4bef-aa5d-6224074a51c8/scratchpad
V=/c/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py
id=$1; slug=$2; D=docs/delivery/reports/$id/wave4
python docs/delivery/reports/wave4/mkbind.py "$id"
python docs/delivery/reports/wave4/bind.py "$D/bindings.json" --apply
test -f "$D/context.json"
set +e
for st in resume closure; do
  { echo "\$ python verify-delivery.py --root . --plan docs/delivery/$slug.md --stage $st --context $D/context.json"; python $V --root . --plan docs/delivery/$slug.md --stage $st --context "$D/context.json"; echo "exit $?"; } > "$D/validate-$st.txt" 2>&1
  head -1 "$D/validate-$st.txt" >/dev/null; sed -n 2p "$D/validate-$st.txt"; grep -v "^Checked\|^Structural\|^\$" "$D/validate-$st.txt" | tail -12
done
