#!/bin/bash
# M3-04's before-and-after measurement, in WSL: memory.py on revision 2's code (fb19cb9, extracted with
#   git archive -o before.tar fb19cb9 chatmon tests pyproject.toml   and untarred to /var/tmp/chatmon-before)
# and on this worktree, each without and with a window under the overlay. The "before" checkout gets this revision's
# tests/sway_session.py (it had none), so both are measured by the same test bed. Output: memory-<which>[--window].json
# beside this script, and their summary on stdout.
#   bash docs/delivery/reports/m3/memory-run.sh
here=/mnt/c/Users/Randy/Coding/chatmon-wt/wayland/docs/delivery/reports/m3
after=/mnt/c/Users/Randy/Coding/chatmon-wt/wayland
py=/var/tmp/wayland-venv/bin/python
cp "$after/tests/sway_session.py" /var/tmp/chatmon-before/tests/
cd /var/tmp || exit 1
for window in "" --window; do
  "$py" "$here/memory.py" /var/tmp/chatmon-before $window > "$here/memory-before$window.json" || exit 1
  "$py" "$here/memory.py" "$after" $window > "$here/memory-after$window.json" || exit 1
done
"$py" - "$here"/memory-before.json "$here"/memory-after.json "$here"/memory-before--window.json "$here"/memory-after--window.json <<'EOF'
import json, sys
for path in sys.argv[1:]:
    d = json.load(open(path))
    print(path.rsplit("/", 1)[-1], "window under it:", d["window_under_it"])
    for r in d["results"]:
        print("  %-42s buffers %-26s %5.1f MB  Chatmon resident %5.1f MB  sway shmem %6.1f MB  frames/2 s %3d" % (
            r["moment"], r["buffers"], r["buffer_bytes"] / 2**20, r["chatmon"]["rss_kb"] / 1024, r["sway"]["rss_shmem_kb"] / 1024, r["frames_last_2s"]))
EOF
