"""What the macOS Chatmon.app runs (PyInstaller, packaging/chatmon.spec): the chatmon command, as
packaging/entry.py is for Windows' build, and also root's check of an update before it's installed.

`Chatmon verify-update KIND PACKAGE SHA256SUMS.txt SHA256SUMS.txt.sig` is Chatmon's release check
(chatmon/releasecheck.py) with this app's own Python and release key: packaging/macos/install-update runs it, as
root, from a copy of the app it has checked is root's alone. It needs nothing but the standard library, so
nothing else of Chatmon (no Qt) is loaded for it."""

import sys

if sys.argv[1:2] == ["verify-update"]:
    from chatmon.releasecheck import main as verify

    raise SystemExit(verify(sys.argv[2:]))

from chatmon.cli import main  # noqa: E402

raise SystemExit(main())
