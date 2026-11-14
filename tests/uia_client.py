"""A UI Automation client, as a screen reader is one, for tests/test_platform_events.py: it listens for notification
events from every window and writes each one's words to the file named on its command line, a JSON line each.
Needs comtypes (a test-only tool). Says "ready" once it listens; runs for the seconds given, then stops.

usage: python tests/uia_client.py LOG SECONDS
"""

import json
import sys
import time

sys.coinit_flags = 0  # the multithreaded apartment: UI Automation calls the handler on threads of its own
import comtypes
import comtypes.client

LOG, SECONDS = sys.argv[1], float(sys.argv[2])
UIA = comtypes.client.GetModule("UIAutomationCore.dll")
automation = comtypes.client.CreateObject(UIA.CUIAutomation8, interface=UIA.IUIAutomation5)


class Heard(comtypes.COMObject):
    _com_interfaces_ = [UIA.IUIAutomationNotificationEventHandler]

    def HandleNotificationEvent(self, sender, kind, processing, words, activity):
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps({"kind": kind, "processing": processing, "words": words, "activity": activity}) + "\n")
        return 0


handler = Heard()
automation.AddNotificationEventHandler(automation.GetRootElement(), UIA.TreeScope_Subtree, None, handler)
print("ready", flush=True)
end = time.monotonic() + SECONDS
while time.monotonic() < end:
    time.sleep(0.1)
automation.RemoveAllEventHandlers()
