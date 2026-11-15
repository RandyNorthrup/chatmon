#!/bin/sh
# Run one job.sh step in the signed-in user's Aqua session, where the window server is (Carbon's hot keys,
# NSSound, Qt's cocoa platform); a process started over ssh isn't in it, and `launchctl asuser` needs root.
#
# usage: sh aqua.sh NAME STEP [ARGS...]   (ARGS: paths without spaces or XML's special characters)
#
# The job is a launchd agent bootstrapped into gui/UID from a plist in T/jobs, never ~/Library/LaunchAgents,
# so it isn't a login item and leaves no Background Items entry. It runs once (no KeepAlive), as an
# interactive process (not throttled as background work is). This waits for it to finish, then boots it out
# of launchd: when its main process ends, launchd ends the rest of its process group too. Its output is in
# T/jobs/NAME.out, its exit in T/jobs/NAME.exit.
set -eu
T="$HOME/chatmon-drills-tmp"
name=$1
shift
label="local.chatmon-drills.$name"
plist="$T/jobs/$label.plist"
out="$T/jobs/$name.out"
exitfile="$T/jobs/$name.exit"
mkdir -p "$T/jobs"
rm -f "$out" "$exitfile" "$exitfile.part"
{
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "<key>Label</key><string>$label</string>"
    echo '<key>ProgramArguments</key><array>'
    echo '<string>/bin/sh</string><string>-c</string>'
    echo '<string>code=0; /bin/sh "$0" "$@" || code=$?; echo "$code" > "$EXITFILE.part"; mv "$EXITFILE.part" "$EXITFILE"</string>'
    echo "<string>$T/mac/job.sh</string>"
    for arg in "$@"; do echo "<string>$arg</string>"; done
    echo '</array>'
    echo "<key>EnvironmentVariables</key><dict><key>EXITFILE</key><string>$exitfile</string></dict>"
    echo '<key>RunAtLoad</key><true/>'
    echo "<key>StandardOutPath</key><string>$out</string>"
    echo "<key>StandardErrorPath</key><string>$out</string>"
    echo '<key>ProcessType</key><string>Interactive</string>'
    echo '<key>LimitLoadToSessionType</key><string>Aqua</string>'
    echo '</dict></plist>'
} > "$plist"
plutil -lint "$plist" > /dev/null
launchctl bootstrap "gui/$(id -u)" "$plist"
waited=0
while [ ! -f "$exitfile" ] && [ "$waited" -lt 3600 ]; do
    sleep 2
    waited=$((waited + 2))
done
launchctl bootout "gui/$(id -u)/$label" 2> /dev/null || true
rm -f "$plist"
cat "$out" 2> /dev/null || true
if [ ! -f "$exitfile" ]; then
    echo "aqua.sh: $name didn't finish within an hour; booted out" >&2
    exit 124
fi
exit "$(cat "$exitfile")"
