#!/bin/bash
# Each plan's --snapshot (the validator's own fingerprints of what its receipts bind), reduced to the paths it binds,
# one line per plan and path: used before and after docs/delivery/OUTCOME.md was written, to show no plan binds it.
cd /c/Users/Randy/Coding/chatmon-wt/plans-final || exit 2
V=/c/Users/Randy/.claude/plugins/cache/high-quality-projects-skill/high-quality-projects-skill/0.7.0/scripts/verify-delivery.py
for plan in docs/delivery/m*-*.md; do
  python "$V" --root . --plan "$plan" --snapshot | python -c "
import json, sys
snap = json.load(sys.stdin)
for kind, items in sorted(snap['inputs'].items()):
    for item in items:
        print(sys.argv[1], kind, item['path'], item['sha256'])
" "$plan"
done
