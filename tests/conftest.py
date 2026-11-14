"""Shared test setup."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# A Chatmon address of the run's own (inherited by child processes), so no test reaches a Chatmon you have
# running, or another test run going on at the same time.
os.environ.setdefault("CHATMON_INSTANCE", f"test-{os.getpid()}")


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole run, held here: one made and dropped in
    a test is freed at once, and the next pixmap aborts the process."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


@pytest.fixture(autouse=True)
def _local_app_data(tmp_path, monkeypatch):
    """Windows keeps Chatmon's settings and state in %LOCALAPPDATA%: each test gets a folder of its own."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
