"""Ctrl+Win+Enter in this session (Narrator on or off), then whether Narrator still runs."""
import sys
import time

sys.argv = [sys.argv[0], r"W:\chatmon-sr\out\keys", r"W:\chatmon-sr\src", r"W:\chatmon-sr\rec\run_chatmon.py", "narrator"]
import drive_windows as d  # noqa: E402

print("Narrator before:", d.narrator_running())
d.press(d.VK_CONTROL, d.VK_LWIN, d.VK_RETURN, label="Ctrl+Win+Enter")
for _ in range(16):
    time.sleep(0.5)
    if not d.narrator_running():
        break
print("Narrator after:", d.narrator_running())
