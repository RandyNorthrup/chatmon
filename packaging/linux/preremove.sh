#!/bin/sh
# Take away what postinstall compiled (the package doesn't list it), when Chatmon is really going:
# dpkg says "remove" or "purge", rpm says 0. An upgrade compiles the new version over it instead.
case "$1" in
    remove|purge|0)
        find /usr/lib/chatmon -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
        ;;
esac
exit 0
