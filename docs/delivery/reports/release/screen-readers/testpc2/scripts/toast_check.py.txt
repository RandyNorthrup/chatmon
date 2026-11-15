"""Chatmon's toasts still in Windows' history (Action Center), under its app ID, then cleared. Run before the app ID's
registration is removed. Shows nothing and says nothing."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"W:\chatmon-sr\src")
from PyQt6.QtGui import QGuiApplication  # noqa: E402

from chatmon import wintoast  # noqa: E402

app = QGuiApplication([])
toaster = wintoast.Toaster("RandyNorthrup.Chatmon")
print("Chatmon's toasts in Action Center before:", toaster.in_action_center())
toaster.clear()
print("after clear():", toaster.in_action_center())
