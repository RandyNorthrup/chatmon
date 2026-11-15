"""Chatmon's log (chatmon/log.py): a private file in the state folder that starts over past 1 MB, problems on stderr
too, the details only with CHATMON_DEBUG, and never a key, even when a provider repeats one in an error."""

import logging
import os
import sys

import pytest

from chatmon import log, paths


@pytest.fixture
def state(tmp_path, monkeypatch):
    """A state folder of the test's own, and the log set up afresh in it, then taken down again."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))
    monkeypatch.delenv(log.DEBUG_ENV, raising=False)
    yield paths.state_dir()
    log.reset()


def written() -> str:
    for handler in logging.getLogger("chatmon").handlers:
        handler.flush()
    return log.log_file().read_text(encoding="utf-8")


def test_the_log_is_kept_in_the_state_folder_and_says_what_happened_without_the_details(state):
    assert log.setup() == state / "chatmon.log"
    logging.getLogger("chatmon.brains").info("a question failed: Anthropic API: overloaded.")
    logging.getLogger("chatmon.paths").warning("couldn't move %s to %s", "old", "new")
    logging.getLogger("chatmon.chats").debug("couldn't read a chat: not JSON")
    logging.getLogger("someone.else").warning("not Chatmon's to keep")
    text = written()
    assert "INFO chatmon.brains: a question failed: Anthropic API: overloaded." in text
    assert "WARNING chatmon.paths: couldn't move old to new" in text
    assert "couldn't read a chat" not in text and "not Chatmon's" not in text


def test_chatmon_debug_keeps_the_details_too(state, monkeypatch):
    monkeypatch.setenv(log.DEBUG_ENV, "1")
    log.setup()
    logging.getLogger("chatmon.chats").debug("couldn't read a chat: not JSON")
    assert "DEBUG chatmon.chats: couldn't read a chat: not JSON" in written()


def test_problems_reach_stderr_as_well_and_details_and_news_dont(state, capsys):
    log.setup()
    logging.getLogger("chatmon.layer").warning("lost the Wayland connection (closed); quitting.")
    logging.getLogger("chatmon.brains").info("a question failed")
    logging.getLogger("chatmon.chats").debug("a detail")
    err = capsys.readouterr().err
    assert err == "chatmon: lost the Wayland connection (closed); quitting.\n"


def test_without_a_console_it_still_keeps_the_log(state, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)  # started by autostart, chatmonw or pythonw
    assert log.setup() is not None
    logging.getLogger("chatmon.x").warning("nobody is watching")
    assert "nobody is watching" in written()


def test_a_full_log_starts_over_and_the_last_one_is_kept_as_old(state):
    log.setup()
    say = logging.getLogger("chatmon.x")
    line = "x" * 999
    for _ in range(log.LIMIT // 1000):  # each line a little over 1000 bytes: a little over the limit
        say.info(line)
    old = state / "chatmon.log.old"
    assert old.exists() and log.LIMIT - 2000 < old.stat().st_size <= log.LIMIT
    assert log.log_file().stat().st_size < 50_000
    say.info("the newest")
    assert "the newest" in written() and "the newest" not in old.read_text(encoding="utf-8")
    assert sorted(p.name for p in state.iterdir()) == ["chatmon.log", "chatmon.log.old"]  # never a .log.1 or .log.2


def test_setting_up_twice_keeps_one_of_each(state, capsys):
    log.setup()
    log.setup()
    logging.getLogger("chatmon.x").warning("once")
    assert written().count("once") == 1 and capsys.readouterr().err.count("once") == 1


def test_a_state_folder_that_cant_be_written_leaves_chatmon_running_without_a_log(state, tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    monkeypatch.setattr(log, "log_file", lambda: blocker / "chatmon.log")
    assert log.setup() is None
    logging.getLogger("chatmon.x").warning("still fine")  # goes to stderr only, without an error


@pytest.mark.skipif(sys.platform == "win32", reason="file modes and symbolic links are the POSIX log's protections")
def test_the_log_is_readable_only_by_you_and_never_followed_through_a_link(state, tmp_path):
    state.mkdir(parents=True)
    made_at_the_umask = state / "chatmon.log"
    made_at_the_umask.write_text("an older Chatmon's log\n")
    os.chmod(made_at_the_umask, 0o644)
    log.setup()
    logging.getLogger("chatmon.x").warning("private")
    assert os.stat(made_at_the_umask).st_mode & 0o777 == 0o600
    log.reset()
    made_at_the_umask.unlink()
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("someone else's file\n")
    made_at_the_umask.symlink_to(elsewhere)
    assert log.setup() is None
    assert elsewhere.read_text() == "someone else's file\n"


def test_anything_shaped_like_a_key_is_blanked_as_it_is_written(state, capsys):
    log.setup()
    say = logging.getLogger("chatmon.x")
    keys = ["sk-ant-api03-abcdefghijklmnop_QRST", "sk-or-v1-0123456789abcdef0123", "AIzaSyA1234567890abcdefghijklmnopqrstu", "xai-ABCDEFGHIJKLMNOPQRSTUV",
            "gsk_abcdefghijklmnopqrstuvwx"]
    for key in keys:
        say.warning("the provider said: Incorrect API key provided: %s.", key)
    say.warning("sent with authorization: Bearer my-local-server-token")
    try:
        raise ValueError("refused sk-proj-abcdefghijklmnopqrstuvwx")
    except ValueError:
        say.warning("it broke", exc_info=True)
    text, err = written(), capsys.readouterr().err
    for out in (text, err):
        assert not any(key in out for key in keys) and "my-local-server-token" not in out and "sk-proj-" not in out
        assert "Incorrect API key provided: …." in out and "Bearer …" in out and "ValueError: refused …" in out
    assert log.blank_keys("a task: ask Sky about it, risk-free") == "a task: ask Sky about it, risk-free"  # words stay


def test_a_logged_brain_error_never_carries_the_key(state, qapp):
    """The provider repeats the key in its refusal: the bubble, and the log, say what it refused without it. The key
    here has no well-known shape, so it's the brain's own scrubbing that keeps it out, not the log's blanking."""
    from replay_server import Provider, ask, json_reply

    from chatmon import brains, keychain

    before = keychain.use(keychain.InMemory())
    provider = Provider()
    try:
        log.setup()
        key = "local-server-secret-42"
        brain = brains.Brain("mine", "openai", label="My server", url=f"{provider.url}/v1", model="m", api_key=key)
        provider.replies.append(json_reply(401, {"error": {"message": f"Incorrect API key provided: {key}."}}))
        got = ask(brains.Asker(), brain)
    finally:
        provider.close()
        keychain.use(before)
    text = written()
    assert "INFO chatmon.brains: a question failed: My server: Incorrect API key provided: … (HTTP 401)." in text, text
    assert key not in text and key not in got["failed"]
