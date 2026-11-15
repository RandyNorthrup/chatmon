"""Insert+Esc in this session (Narrator's own "exit Narrator"), then whether Narrator still runs."""
import sys
import time

sys.argv = [sys.argv[0], r"W:\chatmon-sr\out\keys", r"W:\chatmon-sr\src", r"W:\chatmon-sr\rec\run_chatmon.py", "narrator"]
import drive_windows as d  # noqa: E402

print("Narrator before:", d.narrator_running())
VK_INSERT, EXTENDED = 0x2D, 0x1
sent = d._send(d._key(VK_INSERT, flags=EXTENDED), d._key(d.VK_ESCAPE), d._key(d.VK_ESCAPE, flags=d.KEYUP), d._key(VK_INSERT, flags=EXTENDED | d.KEYUP))
print("pressed Insert+Esc, SendInput", sent)
for _ in range(16):
    time.sleep(0.5)
    if not d.narrator_running():
        break
print("Narrator after:", d.narrator_running())
