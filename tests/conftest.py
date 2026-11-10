"""Shared test setup."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole run, held here: one made and dropped in
    a test is freed at once, and the next pixmap aborts the process."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app
