"""What the installers' Chatmon runs (PyInstaller's entry point): the same as the chatmon command."""

from chatmon.cli import main

raise SystemExit(main())
