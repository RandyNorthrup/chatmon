#!/bin/bash
# Why the test bed runs Hyprland inside a headless KWin, with vgem's primary node in place of its render node:
#   1. Hyprland on its own, no KMS device, no Wayland compositor to run in: Aquamarine has no allocator; it aborts.
#   2. Inside a headless KWin, without the redirect: Mesa's software GBM asks vgem's render node for dumb buffers,
#      which a render node refuses; every mode of every output is rejected.
#   3. Inside a headless sway instead: Aquamarine binds xdg_wm_base version 6, which sway 1.12 hasn't (5).
# Each in a runtime folder, session bus and home of its own; everything started is stopped.
#   bash hyprland_headless.sh
set -u
if [ "${1:-}" = inner ]; then  # in the attempt's own environment (env -i below): $2 is 1 to run inside a headless KWin
  cd "$XDG_RUNTIME_DIR" || exit 1
  dbus-daemon --session --nofork --nopidfile --address="unix:path=$XDG_RUNTIME_DIR/bus" > dbus.log 2>&1 & bus=$!
  sleep 0.5
  export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
  host=
  if [ "$2" = 1 ]; then
    LIBGL_ALWAYS_SOFTWARE=1 nice -n 10 kwin_wayland --virtual --width 64 --height 64 --no-lockscreen --no-global-shortcuts --socket kwin-host > kwin.log 2>&1 & host=$!
    for _ in $(seq 100); do [ -S kwin-host ] && break; sleep 0.1; done
    export WAYLAND_DISPLAY=kwin-host
  elif [ "$2" = sway ]; then  # sway can host only with a GLES renderer (Aquamarine needs its dma-buf device)
    printf 'output HEADLESS-1 mode 1280x800\nxwayland disable\n' > sway.conf
    WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=gles2 WLR_RENDERER_ALLOW_SOFTWARE=1 LIBGL_ALWAYS_SOFTWARE=1 \
      nice -n 10 sway -c sway.conf > sway.log 2>&1 & host=$!
    for _ in $(seq 100); do ls wayland-*.lock > /dev/null 2>&1 && break; sleep 0.1; done
    sleep 1
    WAYLAND_DISPLAY=$(ls | grep -E '^wayland-[0-9]+$' | head -1); export WAYLAND_DISPLAY
  fi
  LIBSEAT_BACKEND=noop LIBGL_ALWAYS_SOFTWARE=1 HYPRLAND_NO_SD_NOTIFY=1 HYPRLAND_NO_SD_VARS=1 HYPRLAND_NO_SD_TARGET=1 HYPRLAND_NO_CRASHREPORTER=1 \
    timeout 30 nice -n 10 Hyprland -c hyprland.lua > hypr.log 2>&1 & hypr=$!
  for _ in $(seq 60); do ls hypr/*/.socket.sock > /dev/null 2>&1 && break; kill -0 $hypr 2> /dev/null || break; sleep 0.1; done
  sleep 2
  if kill -0 $hypr 2> /dev/null; then
    export HYPRLAND_INSTANCE_SIGNATURE; HYPRLAND_INSTANCE_SIGNATURE=$(ls hypr | head -1)
    hyprctl output create headless CHATMON-1 > /dev/null
    sleep 2
    echo "  hyprctl -j monitors all:"
    hyprctl -j monitors all | grep -E '^    "(name|width|height|disabled)"' | paste - - - - | sed 's/^/   /'
  else
    echo "  Hyprland stopped: exit $(wait $hypr; echo $?)"
  fi
  sed -E 's/\x1b\[[0-9;]*m//g' hypr.log | grep -a -E "aquamarine|CRIT|GBM|DUMB|REJECTED|what\(\)|invalid version" | grep -v -E "dmabuf_v1: Got format|Supported|libseat" | sort | uniq -c | sort -rn | head -14
  kill $hypr 2> /dev/null; sleep 1; kill -9 $hypr 2> /dev/null
  [ -n "$host" ] && kill $host
  sleep 1; kill $bus; sleep 1
  exit 0
fi
attempt() {  # $1: title; $2: 1 to run inside a headless KWin
  local run; run=$(mktemp -d /tmp/hyprexp-XXXX); chmod 700 "$run"; mkdir -p "$run/home"
  cat > "$run/hyprland.lua" <<'LUA'
hl.monitor({ output = "WAYLAND-1", disabled = true })
hl.monitor({ output = "CHATMON-1", mode = "1280x800@60", position = "0x0", scale = 1 })
hl.config({ debug = { enable_stdout_logs = true, disable_logs = false },
            misc = { disable_hyprland_logo = true, force_default_wallpaper = 0 }, xwayland = { enabled = false } })
LUA
  echo "== $1"
  env -i PATH=/usr/bin HOME="$run/home" XDG_RUNTIME_DIR="$run" LANG=C.UTF-8 bash "$0" inner "$2"
  rm -rf "$run" 2> /dev/null || { sleep 3; rm -rf "$run"; }  # a gvfs mount KWin's bus started goes with its bus
}
attempt "Hyprland on its own" 0
attempt "Hyprland inside a headless KWin, vgem's render node as it is" 1
attempt "Hyprland inside a headless sway 1.12 (GLES)" sway
