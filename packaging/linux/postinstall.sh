#!/bin/sh
# Compile Chatmon's modules once, as root, so that no start (and no agent's hook) has to.
python3 -m compileall -q -j 0 /usr/lib/chatmon/chatmon >/dev/null 2>&1 || true
exit 0
