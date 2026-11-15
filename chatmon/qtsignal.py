"""Qt's signals as PyQt6 makes them, typed the way mypy should read them.

PyQt6 6.12.1's stubs give pyqtSignal a keyword-only `arguments` with no default, so mypy reads every
`pyqtSignal(int)` as a call missing it ('Missing named argument "arguments" for "pyqtSignal"'), though PyQt6 itself
never asks for it. Every module declares its signals with this module's pyqtSignal instead of PyQt6.QtCore's: it's
the very same object, so nothing changes as Chatmon runs, typed as something that makes a pyqtSignal, so mypy reads
each declaration alike with 6.11's stubs and 6.12.1's. Once the Qt that's locked has the stub right, modules can
import it from PyQt6.QtCore again and this module go.
"""

from collections.abc import Callable

from PyQt6 import QtCore

pyqtSignal: Callable[..., QtCore.pyqtSignal] = QtCore.pyqtSignal
