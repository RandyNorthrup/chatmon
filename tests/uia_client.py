"""A UI Automation client, as a screen reader is one, for tests/test_platform_events.py. Needs comtypes (a
test-only tool).

usage: python tests/uia_client.py listen LOG SECONDS
         listens for notification events from every window, and writes each one to LOG, a JSON line each; says
         "ready" once it listens, and stops after SECONDS
       python tests/uia_client.py name HWND
         prints the name UI Automation gives that window's element
"""

import json
import sys
import time

sys.coinit_flags = 0  # the multithreaded apartment: UI Automation calls the handler on threads of its own
import comtypes
import comtypes.client

UIA = comtypes.client.GetModule("UIAutomationCore.dll")
automation = comtypes.client.CreateObject(UIA.CUIAutomation8, interface=UIA.IUIAutomation5)


class Heard(comtypes.COMObject):
    _com_interfaces_ = [UIA.IUIAutomationNotificationEventHandler]

    def __init__(self, log: str):
        super().__init__()
        self.log = log

    def HandleNotificationEvent(self, sender, kind, processing, words, activity):
        with open(self.log, "a", encoding="utf-8") as out:
            out.write(json.dumps({"kind": kind, "processing": processing, "words": words, "activity": activity}) + "\n")
        return 0


if sys.argv[1] == "name":
    for attempt in range(10):  # a busy machine can keep the window's answer from coming in time: ask again
        try:
            print(automation.ElementFromHandle(int(sys.argv[2])).CurrentName, flush=True)
            break
        except comtypes.COMError:
            if attempt == 9:
                raise
            time.sleep(0.5)
else:
    log, seconds = sys.argv[2], float(sys.argv[3])
    handler = Heard(log)
    automation.AddNotificationEventHandler(automation.GetRootElement(), UIA.TreeScope_Subtree, None, handler)
    print("ready", flush=True)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        time.sleep(0.1)
    automation.RemoveAllEventHandlers()
