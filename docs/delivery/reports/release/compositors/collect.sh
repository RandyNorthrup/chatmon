#!/bin/bash
# Copy runs' evidence into this folder: their notes (observed.jsonl, made again from them all), and their screenshots
# by compositor, shots/<compositor>/<check>-<shot>.png (not the empty output each session reads its background from).
#   bash docs/delivery/reports/release/compositors/collect.sh /var/tmp/compositors-evidence /var/tmp/compositors-evidence-sway
here=/mnt/c/Users/Randy/Coding/chatmon-wt/compositors/docs/delivery/reports/release/compositors
: > "$here/observed.jsonl"
for from in "$@"; do
  cat "$from/observed.jsonl" >> "$here/observed.jsonl"
  for dir in "$from"/shots/*/; do
    test=$(basename "$dir")                    # test_name-param, or test_name-a-b-param
    name=${test%-*}; compositor=${test##*-}    # the compositor is the last parameter of every check with screenshots
    case $compositor in kwin|hyprland|sway) ;; *) continue ;; esac
    check=${name#test_}; check=${check:0:100}
    mkdir -p "$here/shots/$compositor"
    for shot in "$dir"*.png; do
      [ -e "$shot" ] && [ "$(basename "$shot")" != empty.png ] || continue
      cp "$shot" "$here/shots/$compositor/$check-$(basename "$shot")"
    done
  done
done
du -sh "$here/shots"
