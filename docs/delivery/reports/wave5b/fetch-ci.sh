#!/bin/bash
# The plans round for v0.10.0, bound again at 56caddd: CI's evidence, read-only. PR #24's ci.yml run on 56caddd (the
# second binding's evidence): every job's log and the run's job list, saved as gh prints them:
#   bash docs/delivery/reports/wave5b/fetch-ci.sh RUN [PREFIX]
# (PREFIX "ci" for ci.yml, "pkg" for packages.yml, "pins" for pins.yml.) Nothing here runs or changes a run.
cd /c/Users/Randy/Coding/chatmon-wt/measure || exit 2
run=$1; prefix=${2:-ci}; out=docs/delivery/reports/wave5b/ci
gh run view "$run" --repo RandyNorthrup/chatmon --json conclusion,createdAt,updatedAt,event,headBranch,headSha,workflowName,status,jobs \
  --jq '{conclusion,createdAt,updatedAt,event,headBranch,headSha,workflowName,status,jobs:[.jobs[]|{completedAt,conclusion,id:.databaseId,name,startedAt}]}' > "$out/$prefix-$run.json" || exit 1
python -c "
import json, re, sys
for j in json.load(open(sys.argv[1], encoding='utf-8'))['jobs']:
    slug = re.sub(r'[^A-Za-z0-9.]+', '-', j['name']).strip('-')
    print(j['id'], slug, j['conclusion'])
" "$out/$prefix-$run.json" | tr -d '\r' | while read -r job slug conclusion; do  # Windows' python ends its lines with CR LF
  if [ "$conclusion" = skipped ]; then echo "$job $slug skipped: no log"; continue; fi
  gh run view "$run" --repo RandyNorthrup/chatmon --job "$job" --log > "$out/$prefix-$job-$slug.log"; echo "$job $slug exit $? $(wc -l < "$out/$prefix-$job-$slug.log") lines"
done
