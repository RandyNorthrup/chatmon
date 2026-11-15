#!/bin/sh
# What the drills could have touched on the owner's Mac, outside their own folder: run before and after, and
# compared (state-before.txt, state-after.txt). Read only.
echo "== sound: $(osascript -e 'get volume settings')"
echo "== front app: $(lsappinfo info -only name "$(lsappinfo front)" 2>/dev/null)"
echo "== processes of the drills (python, pytest, Chatmon, the drills' launchd jobs)"
ps -axo pid,user,command | grep -E 'chatmon-drills|pytest|[Cc]hatmon' | grep -v -E 'grep|state\.sh' || echo none
echo "== launchd jobs named chatmon"
launchctl list | grep -i chatmon || echo none
echo "== ~/Library/LaunchAgents"
ls -la "$HOME/Library/LaunchAgents"
echo "== Chatmon's own folders, the owner's"
for path in "$HOME/.config/chatmon" "$HOME/.local/state/chatmon" "$HOME/Library/Application Support/chatmon" \
    "$HOME/Library/Preferences/com.chatmon.Chatmon.plist" /Applications/Chatmon.app; do
    [ -e "$path" ] && echo "present: $path" || echo "absent: $path"
done
echo "== temporary folders"
ls -d /private/tmp/chatmon* 2>/dev/null || echo "none in /private/tmp"
user_tmp=$(getconf DARWIN_USER_TEMP_DIR)
ls -d "$user_tmp"chatmon* "$user_tmp"pytest-of-* 2>/dev/null || echo "none in $user_tmp"
echo "== keychain: items of Chatmon's service"
security find-generic-password -s chatmon > /dev/null 2>&1 && echo "present" || echo "none"
echo "== Pythons and uv"
ls -la /usr/local/bin/python3 /usr/local/bin/pip3
ls /usr/local/bin | grep -E '^(python|pip)3' | tr '\n' ' '; echo
for path in "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx" "$HOME/.local/share/uv" "$HOME/.cache/uv"; do
    [ -e "$path" ] && echo "present: $path" || echo "absent: $path"
done
echo "== Homebrew's formulae"
/usr/local/bin/brew list --formula --versions | shasum -a 256 | cut -c1-64
/usr/local/bin/brew list --formula --versions | wc -l | tr -d ' '
echo "== pip's cache, the owner's: $(stat -f '%m %z' "$HOME/Library/Caches/pip" 2>/dev/null || echo absent)"
