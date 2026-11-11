"""What the installers' Chatmon runs (what Nuitka compiles, packaging/build.py): the same as the chatmon command."""

from chatmon.cli import main

raise SystemExit(main())
