#!/bin/sh
# The whole test suite on a Linux distribution's own Python and PyQt6, the ones its .deb or .rpm runs Chatmon
# with, in a fresh container of it (CI's `distro` job). From the repository's root:
#   docker run --rm -v "$PWD:/src:ro" ubuntu:24.04 sh /src/.github/scripts/distro-tests.sh
# CI runs it on ubuntu:24.04, debian:trixie and fedora:44. The tests run on a copy, as an ordinary user.
set -eu
# shellcheck source=/dev/null  # the container's own
. /etc/os-release
case "$ID" in
    ubuntu | debian)
        # Ubuntu's archive hosts' DNS has failed for hours at a time: kernel.org's mirror (apt checks the signatures).
        apt-get update -qq --error-on=any || {
            sed -i -E 's#http://(archive|security)\.ubuntu\.com/ubuntu/?#http://mirrors.edge.kernel.org/ubuntu/#g' /etc/apt/sources.list.d/*.sources 2>/dev/null
            apt-get update -qq
        }
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
            python3-pyqt6 python3-pytest python3-pytest-timeout python3-hypothesis python3-psutil python3-packaging \
            libxkbcommon0 dbus wayland-protocols libwayland-dev tzdata >/dev/null
        ;;
    fedora)
        dnf install -y -q \
            python3-pyqt6 python3-pytest python3-pytest-timeout python3-hypothesis python3-psutil python3-packaging \
            libxkbcommon dbus-daemon wayland-devel wayland-protocols-devel tzdata util-linux >/dev/null
        ;;
    *)
        echo "distro-tests: no recipe for $ID" >&2
        exit 2
        ;;
esac
python3 -c 'import sys; from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR; print(f"{sys.argv[1]}: Python {sys.version.split()[0]}, PyQt6 {PYQT_VERSION_STR}, Qt {QT_VERSION_STR}")' "$PRETTY_NAME"

useradd --create-home chatmon-tests
home=/home/chatmon-tests
cp -R /src "$home/chatmon"
mkdir -m 700 "$home/run"
chown -R chatmon-tests: "$home"
cd "$home/chatmon"
exec runuser -u chatmon-tests -- env HOME="$home" XDG_RUNTIME_DIR="$home/run" QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
    python3 -m pytest -q -p no:cacheprovider
