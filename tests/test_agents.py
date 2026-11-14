import itertools
import json
import os
import random
import shutil
import sys
import time
import tomllib

import pytest

from chatmon import agents

# As they are, before the fixture below stands in for them: for the tests that run a stand-in agent for real.
REAL_RUN_JSON, REAL_WHICH, REAL_ELEVATED = agents._run_json, shutil.which, agents.elevated


@pytest.fixture(autouse=True)
def homes(tmp_path, monkeypatch):
    """Every agent's settings live in a temporary home; no real command-line tool is ever run."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / ".state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    for var in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "GEMINI_CLI_HOME", "GROK_HOME", "COPILOT_HOME"):
        monkeypatch.delenv(var, raising=False)

    def no_real_tools(argv, what):
        raise AssertionError(f"tried to run {argv}")

    monkeypatch.setattr(agents, "_run_json", no_real_tools)
    monkeypatch.setattr(agents.shutil, "which", lambda name: f"/usr/bin/{name}")
    # As you, whatever runs the tests (CI's Windows runners are elevated); the tests of elevation say otherwise.
    monkeypatch.setattr(agents, "elevated", lambda: False)
    return tmp_path


def backups(path):
    return sorted(path.parent.glob(path.name + ".chatmon-backup-*"))


def PROGRAM():
    """What our hooks run: /usr/bin/chatmon here (`which` is faked), or plain chatmon on Windows."""
    return agents.hook_program()[0]


# -- settings files in Claude Code's shape (Gemini, Qwen, Devin)


def test_gemini_keeps_your_hooks_and_settings():
    gemini = agents.Gemini()
    path = gemini.config_path()
    path.parent.mkdir(parents=True)
    mine = {"type": "command", "command": "my-linter"}
    path.write_text(json.dumps({"security": {"auth": "oauth"}, "hooks": {"AfterAgent": [{"hooks": [mine]}], "BeforeTool": [{"matcher": "x", "hooks": [mine]}]}}))
    gemini.connect()
    data = json.loads(path.read_text())
    assert gemini.connected() and data["security"] == {"auth": "oauth"}
    assert data["hooks"]["BeforeTool"] == [{"matcher": "x", "hooks": [mine]}]
    assert data["hooks"]["AfterAgent"][0] == {"hooks": [mine]} and len(data["hooks"]["AfterAgent"]) == 2
    ours = data["hooks"]["AfterAgent"][1]["hooks"][0]
    assert "notify done --source gemini --stdin" in ours["command"] and ours["timeout"] == 5000 and ours["name"] == "chatmon-done"
    assert len(backups(path)) == 1


def test_connect_twice_adds_nothing_and_disconnect_restores():
    qwen = agents.Qwen()
    path = qwen.config_path()
    path.parent.mkdir(parents=True)
    original = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mine"}]}]}, "theme": "dark"}
    path.write_text(json.dumps(original))
    qwen.connect()
    qwen.connect()
    data = json.loads(path.read_text())
    assert sum(len(v) for v in data["hooks"].values()) == 4
    assert data["hooks"]["Notification"][0]["matcher"] == "permission_prompt"
    qwen.disconnect()
    assert json.loads(path.read_text()) == original and not qwen.connected()


def test_without_a_settings_file():
    devin = agents.Devin()
    devin.connect()
    assert devin.connected()
    devin.disconnect()
    assert json.loads(devin.config_path().read_text()) == {}


def test_broken_json_is_left_alone():
    gemini = agents.Gemini()
    path = gemini.config_path()
    path.parent.mkdir(parents=True)
    path.write_text("{ not json")
    with pytest.raises(agents.AgentError):
        gemini.connect()
    assert path.read_text() == "{ not json" and not backups(path)


# -- Codex's notify line

CODEX = """# my codex settings
model = "gpt-6.1-sol"

[tui]
notifications = true

[mcp_servers.docs]
command = "docs-server"
"""


def test_codex_connect_puts_notify_at_the_top_level():
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(CODEX)
    codex.connect()
    data = tomllib.loads(path.read_text())
    assert data["model"] == "gpt-6.1-sol" and data["tui"] == {"notifications": True} and data["mcp_servers"]["docs"]["command"] == "docs-server"
    assert data["notify"][-4:] == ["notify", "done", "--source", "codex"]
    codex.connect()
    assert path.read_text().count("notify = [") == 1
    codex.disconnect()
    assert tomllib.loads(path.read_text()) == tomllib.loads(CODEX) and not codex.connected()


def test_codex_never_replaces_someone_elses_notify():
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    path.write_text('notify = ["my-notifier"]\n')
    with pytest.raises(agents.AgentError, match="takes only one"):
        codex.connect()
    assert path.read_text() == 'notify = ["my-notifier"]\n' and not backups(path)


# -- files of our own (Grok, Copilot)


@pytest.mark.parametrize("agent", [agents.Grok(), agents.Copilot()], ids=lambda a: a.name)
def test_own_hooks_file(agent):
    neighbour = agent.config_path().with_name("someone-else.json")
    neighbour.parent.mkdir(parents=True)
    neighbour.write_text("{}")
    agent.connect()
    data = json.loads(agent.config_path().read_text())
    assert agent.connected() and f"--source {agent.name}" in json.dumps(data)
    assert {"UserPromptSubmit", "Stop"} <= set(data["hooks"])
    agent.disconnect()
    assert not agent.config_path().exists() and neighbour.exists()


# -- Cursor's flat hooks list


def test_cursor_merges_into_its_hooks_file():
    cursor = agents.Cursor()
    path = cursor.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "hooks": {"stop": [{"command": "./audit.sh"}]}}))
    cursor.connect()
    data = json.loads(path.read_text())
    assert data["hooks"]["stop"][0] == {"command": "./audit.sh"} and len(data["hooks"]["stop"]) == 2
    assert "notify working --source cursor" in data["hooks"]["beforeSubmitPrompt"][0]["command"]
    cursor.disconnect()
    assert json.loads(path.read_text()) == {"version": 1, "hooks": {"stop": [{"command": "./audit.sh"}]}}


# -- Cline's hook scripts


def test_cline_scripts_and_your_own_are_safe():
    cline = agents.Cline()
    cline.config_path().mkdir(parents=True)
    cline.connect()
    script = cline._file("TaskComplete")
    words = script.read_text().replace("'", "").split()
    assert cline.connected() and words[words.index("notify") :][:4] == ["notify", "done", "--source", "cline"]
    if sys.platform != "win32":
        assert script.stat().st_mode & 0o111
    cline.disconnect()
    assert not script.exists()
    cline._file("TaskComplete").write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(agents.AgentError, match="already have"):
        cline.connect()
    assert cline._file("TaskComplete").read_text() == "#!/bin/sh\necho mine\n" and not cline._file("UserPromptSubmit").exists()


# -- plugins managed by the agent itself (Claude Code, Muse)


class FakeClaude:
    def __init__(self, installed=None, markets=()):
        self.plugins = installed or []
        self.markets = list(markets)
        self.calls = []

    def __call__(self, argv, what):
        self.calls.append(argv[1:4])
        if argv[1:3] == ["plugin", "list"]:
            return self.plugins
        if argv[1:4] == ["plugin", "marketplace", "list"]:
            return [{"name": m} for m in self.markets]
        if argv[1:4] == ["plugin", "marketplace", "add"]:
            self.markets.append("chatmon")
        if argv[1:4] == ["plugin", "marketplace", "remove"]:
            self.markets.remove(argv[4])
        if argv[1:3] == ["plugin", "install"]:
            self.plugins.append({"id": argv[3], "enabled": True})
        if argv[1:3] == ["plugin", "enable"]:
            self.plugins = [{**p, "enabled": True} if p["id"] == argv[3] else p for p in self.plugins]
        if argv[1:3] == ["plugin", "uninstall"]:
            self.plugins = [p for p in self.plugins if p["id"] != argv[3]]
        return {}


def test_claude_installs_its_plugin(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(agents, "_run_json", fake)
    claude = agents.ClaudeCode()
    assert claude.status() == "found"
    claude.connect()
    assert claude.connected() and ["plugin", "marketplace", "add"] in fake.calls and ["plugin", "install", "chatmon@chatmon"] in fake.calls
    claude.disconnect()
    assert not claude.connected()


def test_claude_reads_the_marketplace_from_a_copy_an_upgrade_cant_take_away(monkeypatch):
    added = []
    fake = FakeClaude()

    def run(argv, what):
        if argv[1:4] == ["plugin", "marketplace", "add"]:
            added.append(argv[4])
        return fake(argv, what)

    monkeypatch.setattr(agents, "_run_json", run)
    claude = agents.ClaudeCode()
    claude.connect()
    (folder,) = added
    assert agents.Path(folder) == claude.marketplace_dir() and agents.paths.state_dir() in agents.Path(folder).parents
    assert json.loads((agents.Path(folder) / ".claude-plugin" / "marketplace.json").read_text())["name"] == "chatmon"
    assert (agents.Path(folder) / "chatmon" / "hooks" / "hooks.json").exists()


def test_claude_switches_a_switched_off_plugin_back_on(monkeypatch):
    fake = FakeClaude(installed=[{"id": "chatmon@chatmon", "enabled": False}], markets=["chatmon"])
    monkeypatch.setattr(agents, "_run_json", fake)
    claude = agents.ClaudeCode()
    assert claude.status() == "installed but off"
    claude.connect()
    assert claude.connected() and ["plugin", "enable", "chatmon@chatmon"] in fake.calls
    assert not any(c[:2] == ["plugin", "install"] for c in fake.calls)


def test_claude_status_takes_one_look(monkeypatch):
    """Each look starts Claude Code's command line, a second or so: how it stands takes one."""
    for installed, expected in (
        ([], "found"),
        ([{"id": "chatmon@chatmon", "enabled": True}], "connected"),
        ([{"id": "chatmon@chatmon", "enabled": False}], "installed but off"),
        ([{"id": "penguin-companion@penguin-companion", "enabled": True}], "connected"),  # not moved over yet
    ):
        fake = FakeClaude(installed=installed)
        monkeypatch.setattr(agents, "_run_json", fake)
        assert agents.ClaudeCode().status() == expected
        assert fake.calls == [["plugin", "list", "--json"]]


def test_claude_needs_chatmon_on_path(monkeypatch):
    monkeypatch.setattr(agents, "_run_json", FakeClaude())
    monkeypatch.setattr(agents.shutil, "which", lambda name: None if name == "chatmon" else f"/usr/bin/{name}")
    with pytest.raises(agents.AgentError, match="PATH"):
        agents.ClaudeCode().connect()


def no_claude_on_path(monkeypatch):
    monkeypatch.setattr(agents.shutil, "which", lambda name: None if name == "claude" else f"/usr/bin/{name}")


def editor_extension(editor, version):
    """A Claude Code extension as an editor keeps it, with the command line it carries."""
    exe = "claude.exe" if sys.platform == "win32" else "claude"
    binary = agents.Path.home() / editor / "extensions" / f"anthropic.claude-code-{version}-win32-x64" / "resources" / "native-binary" / exe
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    return str(binary)


def test_claude_from_its_editor_extension_alone(monkeypatch):
    """Installed only as the VS Code (or Cursor...) extension, Claude Code has no `claude` on PATH: the newest
    extension's own command line connects it."""
    no_claude_on_path(monkeypatch)
    editor_extension(".vscode", "2.1.9")
    newest = editor_extension(".vscode", "2.1.10")  # by number, not by name: 10 after 9
    editor_extension(".cursor", "2.0.4")
    (agents.Path.home() / ".vscode" / "extensions" / "anthropic.claude-code-2.2.0-win32-x64").mkdir()  # half removed: no binary
    ran = []
    fake = FakeClaude()

    def run(argv, what):
        ran.append(argv[0])
        return fake(argv, what)

    monkeypatch.setattr(agents, "_run_json", run)
    claude = agents.ClaudeCode()
    assert claude.program() == newest and claude.detected()
    claude.connect()
    assert claude.connected() and ["plugin", "install", "chatmon@chatmon"] in fake.calls
    assert set(ran) == {newest}


def test_claude_with_no_command_line_anywhere_says_how_to_connect_it(monkeypatch):
    """Its settings are here but no `claude` is: it's found, and connecting says what to do in Claude Code."""
    no_claude_on_path(monkeypatch)
    claude = agents.ClaudeCode()
    claude.config_path().parent.mkdir(parents=True)
    assert claude.program() is None and claude.status() == "found"  # runs nothing: there's nothing to run
    with pytest.raises(agents.AgentError, match="isn't on your PATH") as told:
        claude.connect()
    assert "/plugin install chatmon@chatmon" in str(told.value) and str(claude.marketplace_dir()) in str(told.value)
    assert (claude.marketplace_dir() / ".claude-plugin" / "marketplace.json").exists()  # what that command adds


def test_disconnect_all_touches_only_the_agents_connected(monkeypatch, capsys):
    """What uninstalling runs: an agent with hooks of its own but none of ours keeps its file as it was."""
    from chatmon import cli

    monkeypatch.setattr(agents, "_run_json", FakeClaude())  # Claude Code and Muse: nothing of ours installed
    monkeypatch.setattr(cli.paths, "windows_environment", lambda: False)
    gemini, qwen = agents.Gemini(), agents.Qwen()
    gemini.config_path().parent.mkdir(parents=True)
    theirs = '{"hooks": {"AfterAgent": [{"hooks": [{"type": "command", "command": "my-linter"}]}]}}'
    gemini.config_path().write_text(theirs)
    qwen.connect()
    assert cli.hooks(["disconnect", "all"]) == 0
    assert not qwen.connected() and gemini.config_path().read_text() == theirs and not backups(gemini.config_path())
    assert "Disconnected Qwen Code" in capsys.readouterr().out
    assert cli.hooks(["disconnect", "all"]) == 0 and "No coding agents are connected." in capsys.readouterr().out


def test_a_windows_path_gains_only_what_it_lacks():
    current = r"C:\Windows;C:\Tools\;C:\Mine"
    assert agents.paths.windows_path_with(current, [r"c:\tools", r"C:\Windows\\", ""]) == current
    assert agents.paths.windows_path_with(current, [r"C:\Program Files\Chatmon", r"c:\program files\chatmon\\"]) == current + r";C:\Program Files\Chatmon"
    assert agents.paths.windows_path_with("", [r"C:\A"]) == r"C:\A"


def test_claude_plugin_files_match_the_installer():
    root = agents.ClaudeCode.packaged_marketplace()
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
    plugin_dir = root / market["plugins"][0]["source"]
    hooks = json.loads((plugin_dir / "hooks" / "hooks.json").read_text())["hooks"]
    assert market["name"] == "chatmon" and market["plugins"][0]["name"] == "chatmon"
    assert set(hooks) == {"UserPromptSubmit", "Notification", "Stop"}
    for groups in hooks.values():
        command = groups[0]["hooks"][0]["command"]
        assert command.startswith("chatmon notify ") and command.endswith("|| true")


def test_muse_plugin_manifest():
    manifest = agents.Muse().manifest()
    hooks = manifest["capabilities"]["hooks"]
    assert manifest["name"] == "chatmon" and manifest["compat"]["manifestDir"] == ".muse-plugin"
    assert {h["event"] for h in hooks} == {"UserPromptSubmit", "PermissionRequest", "Notification", "Stop", "Interrupt"}
    assert all(h["async"] and "notify" in h["command"] and "muse" in h["command"] for h in hooks)
    assert len({h["id"] for h in hooks}) == len(hooks)


def test_every_agent_explains_itself():
    names = [a.name for a in agents.AGENTS]
    assert len(names) == len(set(names))
    for agent in agents.AGENTS:
        assert agent.label and ("notify" in agent.manual() or "plugin" in agent.manual())
    assert "needs-you" in agents.generic()


# -- hooks connected before the rename (penguin-companion) move to chatmon

OLD = "/usr/bin/penguin-companion"


def test_nothing_to_move_runs_nothing():
    for agent in agents.AGENTS:
        if agent.name not in ("claude", "muse"):  # those two ask their own tool, which the fixture forbids
            assert not agent.legacy() and agent.migrate() == ""


def test_json_hooks_move_to_the_new_name():
    gemini = agents.Gemini()
    path = gemini.config_path()
    path.parent.mkdir(parents=True)
    mine = {"type": "command", "command": "my-linter"}
    old = {"name": "penguin-done", "type": "command", "command": f"{OLD} notify done --source gemini --stdin", "timeout": 5000}
    path.write_text(json.dumps({"hooks": {"AfterAgent": [{"hooks": [mine]}, {"hooks": [old]}]}}))
    assert gemini.connected() and gemini.legacy()
    assert gemini.migrate()
    groups = json.loads(path.read_text())["hooks"]["AfterAgent"]
    assert groups[0] == {"hooks": [mine]} and len(groups) == 2
    assert groups[1]["hooks"][0]["command"].startswith(f"{PROGRAM()} notify done") and groups[1]["hooks"][0]["name"] == "chatmon-done"
    assert gemini.connected() and not gemini.legacy() and backups(path)
    assert gemini.migrate() == ""  # done once


def test_codex_moves_to_the_new_name():
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(f'model = "o3"\nnotify = ["{OLD}", "notify", "done", "--source", "codex"]\n')
    assert codex.legacy()
    codex.migrate()
    data = tomllib.loads(path.read_text())
    assert data["model"] == "o3" and data["notify"][0] == PROGRAM() and not codex.legacy()


def test_own_hook_files_move_to_the_new_name():
    for agent in (agents.Grok(), agents.Copilot()):
        old = agent.legacy_path()
        old.parent.mkdir(parents=True)
        old.write_text(json.dumps({"hooks": {"Stop": [{"command": f"{OLD} notify done"}]}}))
        assert agent.connected() and agent.legacy()
        agent.migrate()
        assert not old.exists() and agent.config_path().name == "chatmon.json" and f"{PROGRAM()} notify" in agent.config_path().read_text()
        agent.disconnect()
        assert not agent.connected()


def test_cursor_and_cline_move_to_the_new_name():
    cursor = agents.Cursor()
    path = cursor.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 1, "hooks": {"stop": [{"command": "mine"}, {"command": f"{OLD} notify done --source cursor"}]}}))
    assert cursor.legacy()
    cursor.migrate()
    stop = json.loads(path.read_text())["hooks"]["stop"]
    assert stop[0] == {"command": "mine"} and stop[1]["command"].startswith(PROGRAM()) and len(stop) == 2

    cline = agents.Cline()
    cline.config_path().mkdir(parents=True)
    cline._file("TaskComplete").write_text(f"#!/bin/sh\n# penguin-companion\n{OLD} notify done --source cline || true\n")
    assert cline.connected() and cline.legacy()
    cline.migrate()
    assert "# chatmon" in cline._file("TaskComplete").read_text() and not cline.legacy()


def test_claude_swaps_the_old_plugin_for_the_new(monkeypatch):
    fake = FakeClaude(installed=[{"id": "penguin-companion@penguin-companion", "enabled": True}], markets=["penguin-companion"])
    monkeypatch.setattr(agents, "_run_json", fake)
    claude = agents.ClaudeCode()
    assert claude.connected() and claude.legacy()
    claude.migrate()
    assert [p["id"] for p in fake.plugins] == ["chatmon@chatmon"] and fake.markets == ["chatmon"]
    assert claude.connected() and not claude.legacy()


def test_claude_leaves_a_switched_off_old_plugin_off(monkeypatch):
    fake = FakeClaude(installed=[{"id": "penguin-companion@penguin-companion", "enabled": False}], markets=["penguin-companion"])
    monkeypatch.setattr(agents, "_run_json", fake)
    claude = agents.ClaudeCode()
    claude.migrate()
    assert fake.plugins == [] and fake.markets == [] and not claude.connected()


def test_muse_swaps_the_old_plugin_for_the_new(monkeypatch):
    installed = {"penguin-companion"}
    calls = []

    def fake(argv, what):
        calls.append(argv[2:4])
        if argv[2] == "list":
            return {"plugins": [{"plugin": {"id": i}} for i in sorted(installed)]}
        if argv[2] == "remove":
            installed.discard(argv[3])
        if argv[2] == "install":
            installed.add("chatmon")
        return {}

    monkeypatch.setattr(agents, "_run_json", fake)
    muse = agents.Muse()
    assert muse.connected() and muse.legacy()
    muse.migrate()
    assert installed == {"chatmon"} and ["remove", "penguin-companion"] in calls and ["approve", "chatmon"] in calls


def test_a_hook_that_only_looks_like_ours_is_left_alone():
    gemini = agents.Gemini()
    path = gemini.config_path()
    path.parent.mkdir(parents=True)
    lookalike = {"hooks": [{"type": "command", "command": "~/bin/chatmonitor notify --all"}]}
    path.write_text(json.dumps({"hooks": {"AfterAgent": [lookalike]}}))
    assert not gemini.connected()
    gemini.connect()
    gemini.disconnect()
    assert json.loads(path.read_text())["hooks"]["AfterAgent"] == [lookalike]

    codex = agents.Codex()
    codex.config_path().parent.mkdir(parents=True)
    codex.config_path().write_text('notify = ["chatmonitor", "notify"]\n')
    with pytest.raises(agents.AgentError, match="only one program"):
        codex.connect()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_settings_are_never_briefly_readable_by_others(tmp_path):
    fresh = tmp_path / "new.json"
    agents.write_atomic(fresh, "{}")
    assert fresh.stat().st_mode & 0o777 == 0o600
    private = tmp_path / "settings.json"
    private.write_text("{}")
    private.chmod(0o600)
    agents.write_atomic(private, '{"a": 1}')
    assert private.stat().st_mode & 0o777 == 0o600 and not list(tmp_path.glob("*.chatmon-tmp"))


def test_cline_scripts_are_backed_up_before_they_change():
    cline = agents.Cline()
    cline.config_path().mkdir(parents=True)
    old = cline._file("TaskComplete")
    old.write_text(f"#!/bin/sh\n# penguin-companion\n{OLD} notify done --source cline || true\n")
    cline.migrate()
    assert backups(old) and "penguin-companion" in backups(old)[0].read_text()


def test_claude_keeps_the_old_plugin_until_chatmon_can_run(monkeypatch):
    fake = FakeClaude(installed=[{"id": "penguin-companion@penguin-companion", "enabled": True}], markets=["penguin-companion"])
    monkeypatch.setattr(agents, "_run_json", fake)
    monkeypatch.setattr(agents.shutil, "which", lambda name: None if name == "chatmon" else f"/usr/bin/{name}")
    with pytest.raises(agents.AgentError, match="PATH"):
        agents.ClaudeCode().migrate()
    assert [p["id"] for p in fake.plugins] == ["penguin-companion@penguin-companion"]  # still there, still working


def test_our_command_is_known_in_every_form_we_write_it():
    ours = [
        "/usr/bin/chatmon notify done --source gemini --stdin",
        'chatmon notify working --source claude --stdin || true',  # the Claude Code plugin
        '"C:\\\\Users\\\\r\\\\chatmon.exe" notify done',  # JSON on Windows
        "C:\\Users\\r\\.local\\bin\\chatmon.EXE notify done --source gemini --stdin",  # as Windows finds it, in PATHEXT's case
        "& 'chatmon' 'notify' 'done' '--source' 'cline'",  # Cline on Windows, by name
        "# chatmon\n& 'C:\\Users\\r\\chatmon.exe' 'notify' 'done' '--source' 'cline'\nexit 0\n",  # Cline, PowerShell
        'notify = ["/usr/bin/chatmon", "notify", "done"]',  # Codex's TOML list
        "/usr/bin/python3 -m chatmon notify done",
        "/usr/bin/penguin-companion notify done",
    ]
    for text in ours:
        assert agents.is_ours(text), text
    for text in ("~/bin/chatmonitor notify", "& 'C:\\x\\chatmonitor.exe' 'notify'", 'notify-send "chatmon"', "my-chatmon notify"):
        assert not agents.is_ours(text), text


# -- elevated: files only, never an agent's own command line


def stand_in_agent(tmp_path, monkeypatch, name):
    """An agent's command line on PATH, standing in for the real one: it leaves a mark when it runs (as whatever
    a user had put in their folders would) and lists no plugins. The real runner and `which` are put back."""
    folder = tmp_path / "bin"
    folder.mkdir(exist_ok=True)
    marker = tmp_path / f"{name}-ran"
    if sys.platform == "win32":
        (folder / f"{name}.cmd").write_text(f'@echo off\r\necho ran>"{marker}"\r\necho []\r\n', encoding="utf-8")
    else:
        script = folder / name
        script.write_text(f'#!/bin/sh\necho ran > "{marker}"\necho "[]"\n', encoding="utf-8")
        script.chmod(0o755)
    if str(folder) not in os.environ["PATH"]:
        monkeypatch.setenv("PATH", str(folder) + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(agents, "_run_json", REAL_RUN_JSON)
    monkeypatch.setattr(agents.shutil, "which", REAL_WHICH)
    return marker


def test_as_you_an_agents_command_line_does_run(monkeypatch, tmp_path):
    """The control for the tests below: the stand-in is found, run, and seen to have run."""
    marker = stand_in_agent(tmp_path, monkeypatch, "claude")
    assert agents.ClaudeCode().status() == "found" and marker.exists()


def test_elevated_no_agents_command_line_ever_starts(monkeypatch, tmp_path):
    claude_ran = stand_in_agent(tmp_path, monkeypatch, "claude")
    muse_ran = stand_in_agent(tmp_path, monkeypatch, "muse")
    stand_in_agent(tmp_path, monkeypatch, "chatmon")  # on PATH, as connecting Claude Code needs
    monkeypatch.setattr(agents, "elevated", lambda: True)
    claude, muse = agents.ClaudeCode(), agents.Muse()
    assert claude.status() == "found" and not claude.connected() and not claude.legacy()
    assert not muse.connected() and not muse.legacy()
    for agent in (claude, muse):
        with pytest.raises(agents.AgentError, match="administrator"):
            agent.connect()
    with pytest.raises(agents.AgentError, match="administrator"):
        muse.disconnect()
    assert not claude_ran.exists() and not muse_ran.exists()


def test_elevated_disconnecting_everything_edits_files_only(monkeypatch, tmp_path, capsys):
    """What an uninstall for everyone runs, as an administrator: file-based agents are disconnected, Claude Code
    by removing the marketplace Chatmon gave it, Muse Code is left with a word on what to do, and no agent's
    program runs."""
    from chatmon import cli

    claude_ran = stand_in_agent(tmp_path, monkeypatch, "claude")
    muse_ran = stand_in_agent(tmp_path, monkeypatch, "muse")
    monkeypatch.setattr(cli.paths, "windows_environment", lambda: False)
    qwen, claude, muse = agents.Qwen(), agents.ClaudeCode(), agents.Muse()
    qwen.connect()
    claude._publish()  # what connecting Claude Code left in Chatmon's folder
    muse.bundle_dir().mkdir(parents=True)
    monkeypatch.setattr(agents, "elevated", lambda: True)
    assert cli.hooks(["disconnect", "all"]) == 1  # Muse Code's couldn't be done
    out = capsys.readouterr()
    assert not qwen.connected() and not claude.marketplace_dir().exists()
    assert "Disconnected Qwen Code" in out.out and "Disconnected Claude Code" in out.out and "Muse Code" in out.err
    assert not claude_ran.exists() and not muse_ran.exists()


def test_elevation_is_read_from_this_process():
    if sys.platform == "win32":
        import ctypes

        assert REAL_ELEVATED() is bool(ctypes.windll.shell32.IsUserAnAdmin())  # Windows' own answer, asked another way
    else:
        assert REAL_ELEVATED() is (os.geteuid() == 0)


# -- backups


def test_backups_are_private_new_files_and_only_the_newest_five_are_kept(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(agents.time, "strftime", lambda fmt: "20261114-120000")  # all in the same second
    taken = settings.with_name("settings.json.chatmon-backup-20261114-120000")
    taken.write_text("someone else's file")  # already at the first name: never written over, nor through
    if sys.platform != "win32":
        victim = tmp_path / "victim"
        victim.write_text("precious")
        settings.with_name(taken.name + "-2").symlink_to(victim)
    for i in range(8):
        settings.write_text(json.dumps({"n": i}))
        if sys.platform != "win32":
            settings.chmod(0o644)  # readable by others, as settings files often are
        copy = agents.backup(settings)
        assert copy.read_text() == json.dumps({"n": i})
        if i == 0:  # the names already there were passed over, not written
            assert copy.name == taken.name + ("-2" if sys.platform == "win32" else "-3")
            assert taken.read_text() == "someone else's file"
        if sys.platform != "win32":
            assert copy.stat().st_mode & 0o777 == 0o600
    if sys.platform != "win32":
        assert victim.read_text() == "precious"
    kept = [p for p in backups(settings) if not p.is_symlink()]
    assert len(kept) == agents.BACKUPS_KEPT == 5
    assert sorted(json.loads(p.read_text())["n"] for p in kept) == [3, 4, 5, 6, 7]  # the newest; the oldest went


def test_every_change_keeps_a_backup_and_they_stop_piling_up():
    gemini = agents.Gemini()
    gemini.config_path().parent.mkdir(parents=True)
    gemini.config_path().write_text("{}")
    for _ in range(4):
        gemini.connect()
        gemini.disconnect()
        time.sleep(0.01)
    assert len(backups(gemini.config_path())) == 5


# -- Codex: valid configs are taken, and only notify ever changes


CODEX_NESTED = """model = "gpt-6"
matrix = [
  [1, 2],
  [3, 4],
]

[tui]
notifications = true
"""


def test_codex_takes_a_config_with_arrays_inside_arrays():
    """A line like "  [1, 2]," inside an array isn't a table: it was taken for one, and the config refused."""
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    path.write_text(CODEX_NESTED)
    codex.connect()
    assert tomllib.loads(path.read_text()) == {**tomllib.loads(CODEX_NESTED), "notify": codex._argv()}
    codex.disconnect()
    assert path.read_text() == CODEX_NESTED


def test_codex_leaves_a_notify_line_in_a_table_alone():
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    profile = '[profiles.quiet]\nnotify = ["/usr/bin/chatmon", "notify", "done"]\n'
    path.write_text(profile)
    codex.connect()
    assert tomllib.loads(path.read_text())["profiles"] == tomllib.loads(profile)["profiles"]
    codex.disconnect()
    assert tomllib.loads(path.read_text()) == tomllib.loads(profile)


def random_codex_config(rng: random.Random) -> str:
    """A valid TOML file of the shapes Codex configs have, and the ones that trip up a reading by lines:
    multi-line arrays whose items start like table headers, tables and arrays of tables, comments with
    brackets, and multi-line strings holding lines like tables and like notify."""
    names = (f"k{n}" for n in itertools.count())

    def scalar():
        return rng.choice([str(rng.randint(-99, 99)), json.dumps(rng.choice(["x", "[not] a table", "notify = 1", "a # b", "é"])), "true", "1.5"])

    def value(depth=0):
        kind = rng.randrange(7 if depth < 2 else 3)
        if kind < 3:
            return scalar()
        if kind == 3:
            return "[" + ", ".join(value(depth + 1) for _ in range(rng.randint(0, 3))) + "]"
        if kind == 4:
            items = ["[" + ", ".join(scalar() for _ in range(2)) + "]" if rng.random() < 0.6 else scalar() for _ in range(rng.randint(1, 4))]
            return "[\n" + "".join(f"  {item},\n" for item in items) + "]"
        if kind == 5:
            return "{ " + ", ".join(f"{next(names)} = {scalar()}" for _ in range(rng.randint(0, 2))) + " }"
        quote = rng.choice(['"""', "'''"])
        return quote + "\n" + rng.choice(["[fake]\n", "[[fake]]\n", 'notify = ["chatmon", "notify"]\n', "  [x]\n"]) + "text" + quote

    out = []
    if rng.random() < 0.5:
        out.append("# Codex [settings]\n")
    if rng.random() < 0.3:
        out.append("\n")
    out += [f"{next(names)} = {value()}\n" for _ in range(rng.randint(0, 4))]
    for _ in range(rng.randint(0, 3)):
        name = next(names)
        headers = [rng.choice([f"[{name}]", f"[{name}.sub]", f"[[{name}]]"])]
        if headers[0].startswith("[[") and rng.random() < 0.5:
            headers.append(headers[0])  # an array of tables, two of them
        for header in headers:
            out.append(f"\n{header}  # a table\n" if rng.random() < 0.3 else f"\n{header}\n")
            out += [f"{next(names)} = {value()}\n" for _ in range(rng.randint(0, 3))]
    return "".join(out)


def test_codex_connect_then_disconnect_changes_nothing_but_notify():
    codex = agents.Codex()
    path = codex.config_path()
    path.parent.mkdir(parents=True)
    for seed in range(300):
        doc = random_codex_config(random.Random(seed))
        original = tomllib.loads(doc)  # a valid config, or the generator is wrong
        path.write_text(doc, encoding="utf-8")
        codex.connect()
        assert tomllib.loads(path.read_text(encoding="utf-8")) == {**original, "notify": codex._argv()}, (seed, doc)
        codex.connect()  # again: the same, one notify
        assert tomllib.loads(path.read_text(encoding="utf-8")) == {**original, "notify": codex._argv()}, (seed, doc)
        codex.disconnect()
        assert tomllib.loads(path.read_text(encoding="utf-8")) == original, (seed, doc)
        assert codex.disconnect() == "Codex wasn't connected."
