#!/bin/sh
# GNOME's own answers, from a real Mutter: run in a fresh ubuntu:24.04 container (CI's `gnome` job).
#   docker run --rm -v "$PWD:/src:ro" ubuntu:24.04 sh /src/tests/gnome-session.sh
set -e
# Ubuntu's archive hosts' DNS has failed for hours at a time: kernel.org's mirror (apt checks the signatures).
apt-get update -qq --error-on=any || { sed -i -E 's#http://(archive|security)\.ubuntu\.com/ubuntu/?#http://mirrors.edge.kernel.org/ubuntu/#g' /etc/apt/sources.list.d/*.sources; apt-get update -qq; }
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends mutter dbus dbus-x11 libglib2.0-bin python3-pyqt6 python3-pytest >/dev/null
mutter --version | head -1
export XDG_RUNTIME_DIR=/tmp/run
mkdir -p -m 700 "$XDG_RUNTIME_DIR"
exec dbus-run-session -- sh -ec '
mutter --headless --wayland --no-x11 --virtual-monitor 1024x768 >/tmp/mutter.log 2>&1 &
for i in $(seq 60); do
  gdbus introspect --session --dest org.gnome.Mutter.IdleMonitor --object-path /org/gnome/Mutter/IdleMonitor/Core >/dev/null 2>&1 && break
  sleep 1
done
cd /src && QT_QPA_PLATFORM=offscreen CHATMON_GNOME_SESSION=1 python3 -m pytest -q -p no:cacheprovider tests/test_presence.py -k gnome || { tail -30 /tmp/mutter.log; exit 1; }
'
