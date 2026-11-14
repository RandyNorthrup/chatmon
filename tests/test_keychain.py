"""Keys in the system's own keychain (keychain.py): the real Credential Manager on Windows and login Keychain on
macOS, each with a name made for the test and always removed after; a pretend Secret Service on a private D-Bus on
Linux (tests/fake_secrets.py); and a brain using a saved key when its variable isn't set."""

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from chatmon import brains, keychain

HERE = Path(__file__).resolve().parent


def _round_trip(name: str) -> None:
    keychain.use(None)  # the system's own
    try:
        assert keychain.get(name) is None and not keychain.has(name)
        assert keychain.set(name, "sk-test-é-" + "x" * 40) is None
        keychain._cache.clear()
        keychain._present.clear()
        assert keychain.has(name) and keychain.get(name) == "sk-test-é-" + "x" * 40
        assert keychain.set(name, "sk-two") is None  # replaced, not a second entry
        keychain._cache.clear()
        assert keychain.get(name) == "sk-two"
        assert keychain.delete(name) is None and keychain.delete(name) is None  # nothing there: no problem
        keychain._cache.clear()
        keychain._present.clear()
        assert keychain.get(name) is None and not keychain.has(name)
    finally:
        keychain.delete(name)
        keychain.use(None)


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows Credential Manager")
def test_windows_credential_manager_keeps_replaces_and_forgets_a_key():
    name = f"test-{uuid.uuid4().hex}"
    try:
        _round_trip(name)
        listed = subprocess.run(["cmdkey", "/list"], capture_output=True, text=True, errors="replace").stdout
        assert name not in listed
    finally:
        keychain.use(None)
        keychain.delete(name)
    assert keychain.where() == "Windows Credential Manager"


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows Credential Manager")
def test_windows_keeps_a_key_on_this_computer_and_files_it_under_chatmon():
    import ctypes

    name = f"test-{uuid.uuid4().hex}"
    keychain.use(None)
    store = keychain._the_store()
    try:
        assert keychain.set(name, "sk-local") is None
        found = ctypes.POINTER(store.Credential)()
        assert store.read(f"chatmon:{name}", store.TYPE_GENERIC, 0, ctypes.byref(found))
        try:
            assert found.contents.Persist == store.PERSIST_LOCAL_MACHINE and found.contents.UserName == name
        finally:
            store.free(found)
        assert "too long" in keychain.set(name, "k" * 2000)
    finally:
        keychain.delete(name)
        keychain.use(None)


@pytest.mark.skipif(sys.platform != "darwin", reason="the macOS Keychain")
def test_macos_keychain_keeps_replaces_and_forgets_a_key():
    name = f"test-{uuid.uuid4().hex}"
    keychain.use(None)
    store = keychain._the_store()
    try:
        store.has(name)
    except keychain.KeychainError as exc:  # a runner with no login keychain: says so rather than passing
        pytest.skip(f"no usable login keychain here: {exc}")
    _round_trip(name)
    assert keychain.where() == "macOS Keychain"


needs_a_bus = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"), reason="Linux with dbus-run-session",
)

CLIENT = r"""
import sys, json
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication
app = QCoreApplication([])
from chatmon import keychain
def fresh():
    keychain._cache.clear()
    keychain._present.clear()
got = {"where": keychain.where(), "absent": keychain.get("anthropic-api"), "has absent": keychain.has("anthropic-api")}
got["set"] = keychain.set("anthropic-api", "sk-ant-é-1")
fresh()
got["has"], got["read"] = keychain.has("anthropic-api"), keychain.get("anthropic-api")
got["replace"] = keychain.set("anthropic-api", "sk-two")
fresh()
got["replaced"], got["other"] = keychain.get("anthropic-api"), keychain.get("openai-api")
got["delete"] = keychain.delete("anthropic-api")
fresh()
got["gone"] = keychain.get("anthropic-api")
print(json.dumps(got))
"""


def _on_a_private_bus(tmp_path, *fake_args: str) -> tuple[dict, list[dict]]:
    log, ready, fake = tmp_path / "asked.jsonl", tmp_path / "ready", HERE / "fake_secrets.py"
    start_fake = (
        f'"{sys.executable}" "{fake}" "{log}" {" ".join(fake_args)} > "{ready}" 2>&1 & fake=$!; '
        f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; '
    ) if fake_args != ("none",) else "fake=; "
    script = start_fake + f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"; [ -n "$fake" ] && kill $fake'
    env = dict(os.environ, CLIENT=CLIENT, QT_QPA_PLATFORM="offscreen")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's keyring
    out = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=90, env=env)
    lines = [line for line in out.stdout.strip().splitlines() if line.startswith("{")]
    assert lines, out.stdout + out.stderr
    asked = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return json.loads(lines[-1]), asked


@needs_a_bus
def test_the_secret_service_keeps_replaces_and_forgets_a_key_in_its_own_types(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    got, asked = _on_a_private_bus(tmp_path, "")
    assert got == {"where": "your desktop's keyring (Secret Service)", "absent": None, "has absent": False, "set": None, "has": True,
                   "read": "sk-ant-é-1", "replace": None, "replaced": "sk-two", "other": None, "delete": None, "gone": None}, got
    signatures = {a["member"]: a["signature"] for a in asked}
    assert signatures["OpenSession"] == "sv" and signatures["SearchItems"] == "a{ss}" and signatures["Unlock"] == "ao"
    assert signatures["CreateItem"] == "a{sv}(oayays)b" and signatures["GetSecret"] == "o" and signatures["ReadAlias"] == "s"
    created = [a for a in asked if a["member"] == "CreateItem"]
    assert all(a["attributes"] == {"application": "chatmon", "brain": "anthropic-api"} and a["session_open"] and a["replace"] for a in created)
    assert {a["algorithm"] for a in asked if a["member"] == "OpenSession"} == {"plain"}
    assert not [a for a in asked if a["member"] == "Prompt"]


@needs_a_bus
def test_a_locked_keyring_is_never_prompted_to_fill_in_the_menu_only_to_save(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    got, asked = _on_a_private_bus(tmp_path, "--locked")
    assert got["absent"] is None and got["read"] is None and "locked" in got["set"]
    prompts = [a for a in asked if a["member"] == "Prompt"]
    assert len(prompts) == 2  # saving twice: each time the keyring's own window, never for reading


@needs_a_bus
def test_no_keyring_at_all_is_said_and_never_waited_for(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    got, _ = _on_a_private_bus(tmp_path, "none")
    assert got["absent"] is None and got["read"] is None and "no keyring is running" in got["set"]


# -- a brain and its saved key (M1B-13)


def test_a_brain_uses_its_saved_key_when_its_variable_isnt_set(qapp, monkeypatch):
    from replay_server import Provider, ask, json_reply

    provider = Provider()
    store = keychain.InMemory()
    before = keychain.use(store)
    try:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        brain = brains.load_brains({"brains": {"anthropic-api": {"url": f"{provider.url}/v1/messages", "stream": False}}})["anthropic-api"]
        assert not brain.available() and brain.why_not() == "ANTHROPIC_API_KEY not set"
        assert keychain.set("anthropic-api", "sk-ant-saved-0001") is None
        assert brain.available() and store.keys == {"anthropic-api": "sk-ant-saved-0001"}
        provider.replies.append(json_reply(200, {"content": [{"type": "text", "text": "Hi"}]}))
        assert ask(brains.Asker(), brain)["answered"] == "Hi"
        assert provider.asked[-1]["headers"]["x-api-key"] == "sk-ant-saved-0001"
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env-002")  # the variable, when set, comes first
        provider.replies.append(json_reply(200, {"content": [{"type": "text", "text": "Hi"}]}))
        ask(brains.Asker(), brain)
        assert provider.asked[-1]["headers"]["x-api-key"] == "sk-ant-from-env-002"
        assert "sk-ant" not in repr(brains.replace(brain, api_key="sk-ant-in-config"))
    finally:
        keychain.use(before)
        provider.close()


def test_the_menu_asks_only_whether_a_key_is_saved_never_for_the_key(monkeypatch):
    """On macOS reading a key can ask you first; whether one is saved never does, and the menu needs only that."""
    reads = []

    class Watched(keychain.InMemory):
        def get(self, name):
            reads.append(name)
            return super().get(name)

    store = Watched()
    store.keys["openai-api"] = "sk-saved"
    before = keychain.use(store)
    try:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        found = brains.load_brains({})
        assert found["openai-api"].available(wait=False) and not found["xai-api"].available(wait=False)
        assert found["xai-api"].why_not() == "XAI_API_KEY not set" and reads == []
        assert found["openai-api"].key() == "sk-saved" and reads == ["openai-api"]
        found["openai-api"].key()
        assert reads == ["openai-api"]  # read once a run
    finally:
        keychain.use(before)
