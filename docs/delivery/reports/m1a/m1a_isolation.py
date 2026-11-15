"""Scratch pytest plugin (never committed): what M1A's integration note asks M6A to put in tests/conftest.py.

Each test gets LOCALAPPDATA = its own tmp_path (Windows keeps Chatmon's config and state there since M1A-11),
and the whole run gets a Chatmon address of its own (CHATMON_INSTANCE), inherited by any child process, so no
test can reach a Chatmon you have running, or another worker's test run.

    python -m pytest -q -p no:cacheprovider -p m1a_isolation     (with this folder on PYTHONPATH)
"""

import os

import pytest

os.environ.setdefault("CHATMON_INSTANCE", f"test-{os.getpid()}")


@pytest.fixture(autouse=True)
def _local_app_data(tmp_path, monkeypatch, request):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    if request.node.name == "test_the_pipe_is_named_for_you_and_this_session":  # it checks your own pipe's name
        monkeypatch.delenv("CHATMON_INSTANCE")
