#!/bin/bash
# The probes behind the README's problems, each log written to logs/ through run.sh (versions, HEAD, command).
#   bash docs/delivery/reports/release/compositors/probes.sh
here=docs/delivery/reports/release/compositors
cd /mnt/c/Users/Randy/Coding/chatmon-wt/compositors || exit 1
tmp=/var/tmp/compositors-probes
rm -rf "$tmp" && mkdir -p "$tmp"
run() { bash "$here/run.sh" "$here/logs/$1" "${@:2}"; }
for variant in as-is exclusive remap recreate; do
  run "probe-kwin-keyboard-$variant.log" python "$here/probes/kwin_keyboard.py" "$tmp/kwin-keyboard-$variant" "$variant"
done
run probe-kwin-qt-clipboard.log python "$here/probes/kwin_qt_clipboard.py" "$tmp/kwin-clipboard"
run probe-kwin-output-relayout.log python "$here/probes/kwin_output_relayout.py" "$tmp/kwin-relayout"
for step in 110 40 20 5; do
  for name in hyprland kwin sway; do
    run "probe-drag-$name-$step.log" python "$here/probes/drag_events.py" "$name" "$tmp/drag-$name-$step" "$step" 0.016
  done
done
run probe-hyprland-headless.log bash "$here/probes/hyprland_headless.sh"
