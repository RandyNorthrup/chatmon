#!/bin/bash
# A red check on sway 1.9: the drag and "nothing anywhere else" tests against two defects, each in a copy of the
# worktree (the worktree itself untouched): content drawn at the wrong offset, and the whole stage taking clicks.
set -e
src=/mnt/c/Users/Randy/Coding/chatmon-wt/sway-ci
here=$(dirname "$0")
for drill in ${DRILLS:-placed fill}; do
  copy=/var/tmp/sway19-red-$drill
  rm -rf "$copy"; mkdir -p "$copy"
  (cd "$src" && tar --exclude=./art --exclude=./docs -cf - .) | tar -xf - -C "$copy"
  python3 - "$copy" "$drill" <<'EOF'
import sys
root, drill = sys.argv[1], sys.argv[2]
rel, find, replace = {
    "placed": ("chatmon/layer.py", "        p.translate(-QPointF(covered.topLeft()))  # the stage draws in its own coordinates",
               "        pass  # red: drawn as if the subsurface were at the corner"),
    "fill": ("chatmon/penguin.py", "        p.fillRect(region.boundingRect(), Qt.GlobalColor.transparent)  # the surface clips it to the region",
             "        p.fillRect(region.boundingRect(), Qt.GlobalColor.darkRed)  # red: what's drawn again is red, not see-through"),
}[drill]
path = f"{root}/{rel}"
data = open(path, "rb").read().decode()
assert data.count(find) == 1, (drill, data.count(find))
open(path, "wb").write(data.replace(find, replace).encode())
EOF
  echo "== red: $drill"
  bash "$here/run.sh" "$copy" -q "tests/test_sway.py::test_dragged_across_the_screen_it_is_drawn_once_where_it_is_and_nowhere_else" \
    "tests/test_sway.py::test_the_overlay_is_a_layer_surface_sway_draws_and_keeps_out_of_its_windows" 2>&1 | grep -E "${SHOW:-passed|failed|^E  }" | head -${LINES_:-6} || true
  [ -n "$KEEP" ] || rm -rf "$copy"
done
