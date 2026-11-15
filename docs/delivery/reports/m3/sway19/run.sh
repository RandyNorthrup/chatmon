#!/bin/bash
# The CI sway job's tests on Ubuntu 24.04's sway 1.9, in a podman container, against a worktree mounted read-only.
#   bash run.sh /mnt/c/.../worktree [pytest args...]
src=$1; shift
podman run --rm --shm-size=1g -v "$src:/src:ro" -e PYTHONDONTWRITEBYTECODE=1 -e CHATMON_SWAY=1 -e QT_QPA_PLATFORM=offscreen chatmon-sway19 \
  su tester -s /bin/bash -c "sway --version; cd /src && PYTHONDONTWRITEBYTECODE=1 CHATMON_SWAY=1 QT_QPA_PLATFORM=offscreen /venv/bin/python -m pytest -p no:cacheprovider -rs $*"
