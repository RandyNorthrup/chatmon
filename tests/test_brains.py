import os
import sys
from dataclasses import replace

import pytest

from chatmon import brains
from chatmon.brains import Brain, BrainError

REAL_REACHABLE = brains.reachable  # before the fixture below stands in for it


def test_presets_and_overrides(monkeypatch):
    found = brains.load_brains(
        {"brains": {"grok": {"command": ["grok", "-p", "{prompt}", "--disable-web-search"]}, "mine": {"type": "command", "command": ["my-llm"]}, "broken": {"type": "nope"}}}
    )
    assert list(found)[0] == "claude" and {"codex", "gemini", "grok", "muse"} <= set(found)
    assert found["grok"].command[-1] == "--disable-web-search" and found["grok"].label == "Grok"
    assert "mine" in found and "broken" not in found


@pytest.fixture(autouse=True)
def nothing_running_here(monkeypatch):
    monkeypatch.setattr(brains, "reachable", lambda url, timeout=0.15, wait=True: False)


@pytest.fixture(autouse=True)
def no_saved_keys():
    """Keys from a keychain of the test's own, never the computer's."""
    from chatmon import keychain

    before = keychain.use(keychain.InMemory())
    yield
    keychain.use(before)


def test_choose_prefers_picked_then_configured_then_first(monkeypatch):
    monkeypatch.setattr(brains.shutil, "which", lambda name: f"/bin/{name}" if name in ("grok", "my-llm") else None)
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    found = brains.load_brains({"brains": {"mine": {"type": "command", "command": ["my-llm"]}}})
    assert brains.choose(found, "auto", None).name == "grok"
    assert brains.choose(found, "mine", None).name == "mine"
    assert brains.choose(found, "mine", "grok").name == "grok"
    assert brains.choose(found, "claude", None).name == "grok"  # configured one missing: fall back
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert found["openai-api"].available()


def test_no_brain_at_all(monkeypatch):
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert brains.choose(brains.load_brains({}), "auto", None) is None


def test_text_prompt_carries_the_conversation():
    text = brains.text_prompt("SYS", [("hi", "hello!")], "and you?")
    assert text.startswith("SYS") and "Person: hi\n\nYou: hello!" in text and text.endswith("Person: and you?")


def test_anthropic_request_shape():
    brain = Brain("a", "anthropic", model="claude-opus-5-5", api_key="k", effort="low")
    headers, body = brains.anthropic_request(brain, "SYS", [("q1", "a1")], "q2")
    assert headers["x-api-key"] == "k" and headers["anthropic-version"] == brains.ANTHROPIC_VERSION
    assert headers["anthropic-beta"] == "server-side-fallback-2026-07-01" and body["fallbacks"] == "default"
    assert body["system"] == "SYS" and [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["output_config"] == {"effort": "low"}
    _, other = brains.anthropic_request(Brain("h", "anthropic", model="claude-haiku-5-5", api_key="k"), "S", [], "q")
    assert "fallbacks" not in other


def test_parse_anthropic():
    data = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": " Hi! "}], "stop_reason": "end_turn"}
    assert brains.parse_anthropic(data) == "Hi!"
    with pytest.raises(BrainError, match="declined"):
        brains.parse_anthropic({"content": [], "stop_reason": "refusal"})
    with pytest.raises(BrainError, match="bad key"):
        brains.parse_anthropic({"type": "error", "error": {"type": "authentication_error", "message": "bad key"}})


def test_openai_request_and_parse():
    headers, body = brains.openai_request(Brain("o", "openai", model="m", api_key="k"), "SYS", [], "q")
    assert headers["authorization"] == "Bearer k" and body["messages"][0] == {"role": "system", "content": "SYS"}
    assert "authorization" not in brains.openai_request(Brain("l", "openai", model="m"), "S", [], "q")[0]
    assert brains.parse_openai({"choices": [{"message": {"content": "yo"}}]}) == "yo"
    assert brains.parse_openai({"choices": [{"message": {"content": [{"type": "text", "text": "a"}, {"text": "b"}]}}]}) == "ab"
    with pytest.raises(BrainError):
        brains.parse_openai({"error": {"message": "quota"}})


def test_keys_only_go_over_https_or_to_this_computer():
    for url in ("https://api.example.com/v1", "http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://[::1]:8080/v1"):
        brains.check_url(url)
    for url in ("http://api.example.com/v1", "http://192.168.1.5:11434/v1", "ftp://x", "http://localhost.evil.com/v1"):
        with pytest.raises(BrainError):
            brains.check_url(url)


def test_custom_headers_read_keys_from_the_environment(monkeypatch):
    monkeypatch.setenv("AZURE_KEY", "secret")
    brain = brains.load_brains({"brains": {"azure": {"type": "openai", "url": "https://x/v1", "model": "m", "headers": {"api-key": "${AZURE_KEY}"}, "extra": {"temperature": 0.2}}}})["azure"]
    headers, body = brains.openai_request(brain, "S", [], "q")
    assert headers["api-key"] == "secret" and body["temperature"] == 0.2 and "authorization" not in headers


def test_clean_output_strips_terminal_colours():
    assert brains.clean_output("\x1b[1;32mDone\x1b[0m\n") == "Done"


def test_auto_never_picks_a_paid_api(monkeypatch):
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    found = brains.load_brains({})
    assert found["openai-api"].available() and brains.choose(found, "auto", None) is None
    assert brains.choose(found, "auto", "openai-api").name == "openai-api"
    assert brains.choose(found, "openai-api", None).name == "openai-api"
    custom = brains.load_brains({"brains": {"mine": {"type": "openai", "url": "https://x/v1", "model": "m", "auto": True}}})
    assert brains.choose(custom, "auto", None).name == "mine"


@pytest.fixture
def servers(monkeypatch):
    """Which local ports a process of yours listens on, as portowner would say (it's tested on its own)."""
    from chatmon import portowner

    yours: dict[int, bool] = {}
    monkeypatch.setattr(portowner, "mine", lambda port: yours.get(port, False))
    monkeypatch.setattr(brains, "_owned", {})
    monkeypatch.setattr(brains, "_unsure_owner", set())
    monkeypatch.setattr(brains, "_confirmed", set())
    return yours


def test_a_running_local_server_is_picked_with_its_own_model(monkeypatch, servers):
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    monkeypatch.setattr(brains, "reachable", lambda url, timeout=0.15, wait=True: "11434" in url)
    servers[11434] = True
    found = brains.load_brains({})
    chosen = brains.choose(found, "auto", None)
    assert chosen.name == "ollama" and chosen.model == "auto"
    assert found["lmstudio"].why_not() == "not running"
    assert brains.first_model({"object": "list", "data": [{"id": "qwen3.8:27b"}]}) == "qwen3.8:27b"
    with pytest.raises(BrainError):
        brains.first_model({"data": []})


def test_bedrock_needs_its_region(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "t")
    monkeypatch.delenv("AWS_REGION", raising=False)
    bedrock = brains.load_brains({})["bedrock-api"]
    assert not bedrock.available() and "AWS_REGION" in bedrock.why_not()
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    assert bedrock.available()
    assert brains.endpoint(bedrock)[0] == "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1/chat/completions"


def test_responses_api():
    brain = Brain("x", "responses", url="https://api.x.ai/v1", model="grok-4.7", api_key="k")
    url, request, parse = brains.endpoint(brain)
    headers, body = request(brain, "SYS", [("hi", "hello")], "and?")
    assert url == "https://api.x.ai/v1/responses" and body["instructions"] == "SYS" and body["input"][-1] == {"role": "user", "content": "and?"}
    reply = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": " Hi! "}]}]}
    assert parse(reply) == "Hi!" and parse({"output_text": "yo"}) == "yo"
    with pytest.raises(BrainError, match="quota"):
        parse({"error": {"message": "quota"}})


def test_every_preset_is_well_formed():
    for brain in brains.load_brains({}).values():
        assert brain.label and brain.type in brains.TYPES
        if brain.type == "command":
            assert brain.command
        else:
            assert (brain.url or brain.type == "anthropic") and brain.model
            if not brain.local and brain.url:
                brains.check_url(brains.expand(brain.url).replace("..", ".x."))
                assert brain.api_key_env


# -- model, effort and thinking, picked from the menu


def test_claude_api_thinking_follows_each_models_rules():
    preset = brains.load_brains({})["anthropic-api"]
    assert preset.effort == "low" and preset.models[0] == preset.model == "claude-opus-5-5"
    assert preset.refuses(thinking="off") and "always thinks" in preset.refuses(thinking="off")
    assert preset.refuses(model="claude-fable-5-2", thinking="off")
    assert preset.refuses(model="claude-sonnet-5-5", thinking="off") is None
    assert "high or below" in preset.refuses(model="claude-sonnet-5-5", effort="max", thinking="off")
    assert preset.refuses(model="claude-haiku-5-5", effort="high", thinking="off") is None
    assert preset.refuses(effort="ludicrous")

    def sent(**options):
        return brains.anthropic_request(replace(preset, api_key="k", **options), "S", [], "q")[1]

    assert "thinking" not in sent()  # the model's own default
    assert sent(thinking="on")["thinking"] == {"type": "adaptive"}
    assert sent(model="claude-sonnet-5-5", thinking="off")["thinking"] == {"type": "between_tools"}
    assert sent(model="claude-haiku-5-5", thinking="off")["thinking"] == {"type": "disabled"}
    assert sent(effort="high")["output_config"] == {"effort": "high"} and "output_config" not in sent(effort="")
    assert sent(model="claude-fable-5-2")["fallbacks"] == "default"


def test_menu_picks_apply_only_when_they_go_together():
    preset = brains.load_brains({})["anthropic-api"]
    picked = preset.with_options({"model": "claude-sonnet-5-5", "effort": "medium", "thinking": "off"})
    assert (picked.model, picked.effort, picked.thinking) == ("claude-sonnet-5-5", "medium", "off")
    clash = preset.with_options({"model": "claude-sonnet-5-5", "effort": "max", "thinking": "off"})
    assert (clash.effort, clash.thinking) == ("max", "auto")  # thinking off can't go with max: left out
    assert preset.with_options({"thinking": "off"}).thinking == "auto"  # Opus 5.5 always thinks
    assert preset.with_options(None) is preset


def test_api_and_command_brains_send_effort_and_thinking_as_declared():
    responses = Brain("r", "responses", model="m", efforts=["low", "high"], effort="high", thinking="off",
                      thinking_fields={"off": {"reasoning.effort": "none"}})
    body = brains.responses_request(responses, "S", [], "q")[1]
    assert body["reasoning"] == {"effort": "none"}  # thinking off wins over the effort
    chat = Brain("c", "openai", model="m", efforts=["low"], effort="low")
    assert brains.openai_request(chat, "S", [], "q")[1]["reasoning_effort"] == "low"
    plain = Brain("p", "openai", model="m", effort="low")  # no efforts declared: nothing sent
    assert "reasoning_effort" not in brains.openai_request(plain, "S", [], "q")[1]
    tool = Brain("t", "command", command=["tool", "-p"], model="big", effort="high", thinking="off",
                 model_args=["--model", "{model}"], effort_args=["-c", "effort={effort}"], thinking_args={"off": ["--no-think"]})
    assert brains.command_args(tool) == ["-p", "--model", "big", "-c", "effort=high", "--no-think"]
    assert brains.command_args(replace(tool, model="", effort="", thinking="auto")) == ["-p"]


def test_a_model_name_can_never_become_a_flag():
    tool = Brain("t", "command", command=["tool"], model="big", model_args=["--model", "{model}"])
    for bad in ("--yolo", "-x", "a b", "big;rm", "", "x" * 300):
        if bad:
            assert tool.refuses(model=bad), bad
            assert tool.with_options({"model": bad}).model == "big"
    assert tool.refuses(model="openai/gpt-oss-120b") is None and tool.refuses(model="global.openai.gpt-6.1-sol") is None
    assert tool.refuses(effort="high") == "it has no effort setting"


def test_your_own_claude_brain_gets_the_same_choices():
    mine = brains.load_brains({"brains": {"work": {"type": "anthropic", "model": "claude-sonnet-5-5", "api_key_env": "WORK_KEY"}}})["work"]
    assert mine.effort == "low" and mine.efforts == brains.ANTHROPIC_EFFORTS
    picked = mine.with_options({"effort": "high", "thinking": "off"})
    assert (picked.effort, picked.thinking) == ("high", "off")


def test_every_preset_is_a_combination_it_takes():
    for name, brain in brains.load_brains({}).items():
        assert brain.refuses() is None, (name, brain.refuses())
        for model in brain.models:
            assert brain.refuses(model=model, effort="", thinking="auto") is None, (name, model)
        if brain.models and brain.model:
            assert brain.model == brain.models[0], name  # the usual one first
        if brain.type == "command" and brain.models:
            assert brain.model_args, name  # a model it can't be told is no choice at all


def test_provider_specifics_reach_the_request():
    found = brains.load_brains({})
    url, _, _ = brains.endpoint(found["perplexity-api"])
    assert url == "https://api.perplexity.ai/v1/agent"  # the Agent API, since Sonar's Chat Completions ended
    router = replace(found["openrouter"], model="openai/gpt-6.1-sol", effort="high")
    assert brains.openai_request(router, "S", [], "q")[1]["reasoning"] == {"effort": "high"}
    assert found["openrouter"].refuses(effort="high")  # the auto router picks its own
    deepseek = replace(found["deepseek-api"], thinking="off")
    assert brains.openai_request(deepseek, "S", [], "q")[1]["thinking"] == {"type": "disabled"}
    sol = found["openai-api"]
    assert sol.refuses(thinking="off") and sol.refuses(model="gpt-6.1-terra", thinking="off") is None
    assert brains.responses_request(replace(sol, model="gpt-6-luna", thinking="off"), "S", [], "q")[1]["reasoning"] == {"effort": "none"}
    meta = found["meta-api"]
    assert meta.effort == "low" and "muse-ember-1.0" in meta.models and meta.refuses(thinking="off")
    codex = replace(found["codex"], effort="high")
    assert brains.command_args(codex)[-2:] == ["-c", 'model_reasoning_effort="high"']
    claude = found["claude"].with_options({"model": "claude-sonnet-5-5", "effort": "medium"})
    assert brains.command_args(claude)[-4:] == ["--model", "claude-sonnet-5-5", "--effort", "medium"]


def test_switching_model_drops_only_what_the_new_one_cant_do():
    sol = brains.load_brains({})["openai-api"]
    terra_off = sol.with_options({"model": "gpt-6.1-terra", "effort": "medium", "thinking": "off"})
    assert (terra_off.model, terra_off.effort, terra_off.thinking) == ("gpt-6.1-terra", "medium", "off")
    back = sol.with_options({"model": "gpt-6.1-sol", "effort": "medium", "thinking": "off"})
    assert (back.model, back.effort, back.thinking) == ("gpt-6.1-sol", "medium", "auto")
    mistral = brains.load_brains({})["mistral-api"].with_options({"model": "mistral-large-4-0", "effort": "low"})
    assert (mistral.model, mistral.effort) == ("mistral-large-4-0", "low")
    small = mistral.with_options({"model": "mistral-small-latest", "effort": "low"})
    assert small.effort == "" and small.effort_levels() == ["high"]  # low isn't one of Small's


def test_a_reply_of_the_wrong_shape_is_an_error_not_a_crash():
    for data in ({"content": ["text", 3]}, {"output": [None, "x"]}, {"choices": "nope"}):
        for parse in (brains.parse_anthropic, brains.parse_responses, brains.parse_openai):
            with pytest.raises(BrainError):
                brains._parsed(parse, data)
    with pytest.raises(ValueError):
        brains._json_object(b"[1, 2]")
    with pytest.raises(ValueError):
        brains._json_object(b"[" * 70000)


def test_a_redirect_never_takes_the_key_anywhere(qapp):
    """Plain HTTP is allowed to this computer only; a redirect from there must not carry the key on."""
    import http.server
    import threading

    from PyQt6.QtCore import QEventLoop, QTimer

    seen = []

    class Elsewhere(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.headers.get("authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    elsewhere = http.server.HTTPServer(("127.0.0.1", 0), Elsewhere)

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(307)
            self.send_header("Location", f"http://127.0.0.1:{elsewhere.server_port}/steal")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    local = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    for server in (local, elsewhere):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        brain = Brain("local", "openai", url=f"http://127.0.0.1:{local.server_port}/v1", model="m", api_key="secret-key")
        asker = brains.Asker()
        result = []
        loop = QEventLoop()
        asker.answered.connect(lambda text: (result.append(("answer", text)), loop.quit()))
        asker.failed.connect(lambda text: (result.append(("failed", text)), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        asker.ask(brain, "S", [], "q", 5.0)
        loop.exec()
        assert result and result[0][0] == "failed" and "redirect" in result[0][1], result
        assert seen == []  # the key never left
    finally:
        local.shutdown()
        elsewhere.shutdown()


def test_only_this_computer_gets_plain_http_and_url_variables_stay_plain(monkeypatch):
    for url in ("http://localhost:11434/v1", "http://127.0.0.1:1234/v1", "http://[::1]:8000/v1", "https://api.example.com/v1"):
        brains.check_url(url)
    for url in ("http://evil.localhost/v1", "http://example.com/v1", "ftp://localhost/v1"):
        with pytest.raises(BrainError):
            brains.check_url(url)
    bedrock = brains.load_brains({})["bedrock-api"]
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert brains.endpoint(bedrock)[0] == "https://bedrock-runtime.us-east-1.amazonaws.com/openai/v1/chat/completions"
    monkeypatch.setenv("AWS_REGION", "attacker.example/x#")
    with pytest.raises(BrainError, match="plain name"):
        brains.endpoint(bedrock)


def test_programs_are_looked_for_now_and_then_not_on_every_menu(monkeypatch):
    """On Windows each look for a program takes a few ms, and the menu asks after a dozen of them."""
    from chatmon import paths

    looks = []
    monkeypatch.setattr(brains.shutil, "which", lambda name: looks.append(name) or f"/bin/{name}")
    grok = brains.Brain(name="grok", type="command", command=["grok"])
    assert grok.available() and grok.available() and looks == ["grok"]
    monkeypatch.setenv("PATH", "/somewhere/else")  # a new PATH: look again
    assert grok.available() and looks == ["grok", "grok"]
    monkeypatch.setattr(paths, "FOUND_FOR", 0)  # and once it's old
    assert grok.available() and looks == ["grok", "grok", "grok"]


# -- how much a model takes at once (context.py fits a chat to it)


def test_each_servers_own_word_for_its_context_window():
    from chatmon import brains

    assert brains._from_ollama_ps({"models": [{"name": "llama3.2:latest", "context_length": 8192}]}, "llama3.2") == 8192
    assert brains._from_ollama_ps({"models": [{"name": "qwen3:8b", "context_length": 4096}]}, "auto") == 4096
    assert brains._from_ollama_ps({"models": []}, "llama3.2") is None  # not loaded yet: not known
    assert brains._from_llamacpp_props({"default_generation_settings": {"n_ctx": 16384}}, "") == 16384
    assert brains._from_model_list({"data": [{"id": "a", "max_model_len": 32768}]}, "a") == 32768  # vLLM
    assert brains._from_model_list({"data": [{"id": "x/y", "context_length": 200000}]}, "x/y") == 200000  # OpenRouter
    assert brains._from_model_list({"data": [{"id": "m", "top_provider": {"context_length": 64000}}]}, "m") == 64000
    assert brains._from_model_list({"data": [{"id": "gpt"}]}, "gpt") is None  # OpenAI's says nothing
    lm = {"models": [{"key": "q", "max_context_length": 131072, "loaded_instances": [{"config": {"context_length": 8192}}]}]}
    assert brains._from_lmstudio(lm, "q") == 8192  # loaded with less than its most


def test_a_local_servers_window_is_asked_for_and_a_redirect_never_followed(qapp):
    import http.server
    import threading

    from chatmon import brains

    class Server(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/v1/models":
                self.send_response(302)
                self.send_header("location", "http://example.com/steal")
                self.end_headers()
                return
            body = b'{"models": [{"name": "tiny:latest", "context_length": 2048}]}' if self.path == "/api/ps" else b"{}"
            self.send_response(200 if self.path == "/api/ps" else 404)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        brain = brains.Brain("ollama", "openai", url=f"http://127.0.0.1:{server.server_port}/v1", model="tiny", local=True, api_key="secret")
        assert brains.context_window(brain) == brains.LOCAL_WINDOW and not brains.window_known(brain)
        assert brains.learn_window(brain) == 2048 and brains.context_window(brain) == 2048
        brains.shrink_window(brain, 3000)
        assert brains.context_window(brain) == 1024
    finally:
        server.shutdown()
        brains._windows.clear()
    remote = brains.Brain("x", "openai", url="http://203.0.113.9/v1", model="m")
    assert brains.learn_window(remote) is None  # plain HTTP only to this computer


# -- what a command-line brain is given (M1B-01, M1B-02, M1B-05)


def _answer(asker, brain, wait_s: float = 40) -> dict:
    from replay_server import ask

    return ask(asker, brain, wait_s=wait_s)


def test_a_command_brain_gets_only_what_it_needs_of_the_environment(qapp, monkeypatch):
    import json
    import sys

    monkeypatch.setenv("CHATMON_TEST_CANARY", "a token for something else")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-another-providers-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-its-own")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/its/own/config")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("TMP", "/a/temp/folder")
    script = "import json, os, sys; sys.stdin.read(); print(json.dumps(dict(os.environ)))"
    brain = brains.replace(brains.load_brains({})["claude"], command=[sys.executable, "-c", script], output="")
    got = _answer(brains.Asker(), brain)
    env = {k.upper(): v for k, v in json.loads(got["answered"]).items()}
    assert "CHATMON_TEST_CANARY" not in env and "OPENAI_API_KEY" not in env
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-its-own" and env["CLAUDE_CONFIG_DIR"] == "/its/own/config"  # its own sign-in
    assert env["HTTPS_PROXY"] == "http://proxy.example:3128" and env["CHATMON_INTERNAL"] == "1" and env["NO_COLOR"] == "1"
    assert env["PATH"] == os.environ["PATH"] and env["TMP"] == "/a/temp/folder"


def test_the_allowlist_takes_names_in_any_case_and_endings_after_a_star():
    brain = brains.Brain("mine", "command", command=["x"], env=["MY_TOOL_*"], api_key_env="MY_KEY", requires=["MY_REGION"])
    given = brains.command_environment(brain, {
        "Path": "/bin", "SystemRoot": r"C:\Windows", "LC_ALL": "C", "my_tool_token": "t", "MY_TOOL": "not a match",
        "MY_KEY": "k", "MY_REGION": "eu", "AWS_SECRET_ACCESS_KEY": "nope", "GITHUB_TOKEN": "nope",
    })
    assert set(given) == {"Path", "SystemRoot", "LC_ALL", "my_tool_token", "MY_KEY", "MY_REGION", "CHATMON_INTERNAL", "NO_COLOR"}


def test_claude_code_is_started_without_tools_mcp_servers_or_anyone_asked():
    command = brains.load_brains({})["claude"].command
    assert command[command.index("--tools") + 1] == "" and "--strict-mcp-config" in command
    assert command[command.index("--permission-mode") + 1] == "dontAsk"


@pytest.mark.skipif(not __import__("shutil").which("claude"), reason="Claude Code isn't installed here")
def test_claude_codes_own_help_lists_every_flag_and_mode_it_is_given():
    import shutil
    import subprocess

    out = subprocess.run([shutil.which("claude"), "--help"], capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace").stdout
    for flag in [a for a in brains.load_brains({})["claude"].command[1:] if a.startswith("-")]:
        assert flag in out, flag
    assert '"dontAsk"' in out  # one of the modes it lists, not an unlisted alias


def test_folders_a_stopped_chatmon_left_are_removed_and_running_ones_kept(qapp, tmp_path, monkeypatch):
    import subprocess
    import time
    import sys
    import tempfile

    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait()
    running = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        made = {}
        for name in (f"chatmon-ask-{ended.pid}-a1", f"chatmon-ask-{running.pid}-b2", f"chatmon-ask-{os.getpid()}-c3", "chatmon-ask-old_d4", "chatmon-ask-new_e5"):
            made[name] = tmp_path / name
            made[name].mkdir()
            (made[name] / "question-1.txt").write_text("attached text", encoding="utf-8")
        old = time.time() - 2 * 3600
        os.utime(made["chatmon-ask-old_d4"], (old, old))  # from before 0.10, and hours old
        (tmp_path / "chatmon-ask-not-a-folder").write_text("x")
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        monkeypatch.setattr(brains, "_tidied", False)
        brains.Asker()  # as Chatmon starts
        left = sorted(p.name for p in tmp_path.iterdir())
        assert left == sorted([f"chatmon-ask-{running.pid}-b2", f"chatmon-ask-{os.getpid()}-c3", "chatmon-ask-new_e5", "chatmon-ask-not-a-folder"])
        brains.Asker()
        assert sorted(p.name for p in tmp_path.iterdir()) == left  # once a run
    finally:
        running.kill()
        running.wait()


# -- whose model server it is (M1B-03)


def test_automatic_uses_only_a_model_server_of_yours_or_one_you_confirmed(monkeypatch, servers):
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    monkeypatch.setattr(brains, "reachable", lambda url, timeout=0.15, wait=True: "11434" in url)
    found = brains.load_brains({})
    assert brains.choose(found, "auto", None) is None  # someone's listening on 11434, but not you
    assert brains.choose(found, "auto", "ollama").name == "ollama"  # picked by name: your own choice
    assert brains.choose(found, "ollama", None).name == "ollama"
    brains.confirm_server("http://localhost:11434/v1")
    assert brains.confirmed_servers() == ["localhost:11434"] and brains.choose(found, "auto", None).name == "ollama"
    brains._confirmed.clear()
    servers[11434] = True
    brains._owned.clear()
    assert brains.choose(found, "auto", None).name == "ollama"


def test_a_server_elsewhere_is_never_counted_as_yours(servers):
    servers[11434] = True  # even with something of yours on the same port here
    assert not brains.trusted("http://192.168.1.20:11434/v1") and brains.trusted("http://127.0.0.1:11434/v1")
    assert brains.trusted("http://[::1]:11434/v1") and brains.trusted("http://localhost:11434/v1")


def test_whose_server_it_is_is_found_off_the_screens_thread(monkeypatch, servers):
    import threading

    from chatmon import portowner

    asked, says = [], portowner.mine  # the servers fixture's
    servers[1234] = True
    monkeypatch.setattr(portowner, "mine", lambda port: (asked.append(threading.current_thread() is threading.main_thread()), says(port))[1])
    assert brains.trusted("http://localhost:1234/v1", wait=False) is False and asked == [] and brains.unsure()
    result = []
    thread = threading.Thread(target=lambda: result.append(brains.look_again()))
    thread.start()
    thread.join(10)
    assert result == [True] and asked == [False] and brains.trusted("http://localhost:1234/v1", wait=False) is True


# -- never holding up the screen (M1B-10, M1B-11)


def test_cancelling_a_command_brain_returns_at_once_and_stops_it(qapp, tmp_path):
    import sys
    import time

    from replay_server import spin

    started = tmp_path / "started"
    script = f"import sys, time; sys.stdin.read(); open(r'{started}', 'w').write('x'); time.sleep(60)"
    asker = brains.Asker()
    asker.ask(brains.Brain("slow", "command", label="Slow", command=[sys.executable, "-c", script]), "", [], "hi", 60)
    deadline = time.monotonic() + 15
    while not started.exists() and time.monotonic() < deadline:
        spin(0.05)
    proc, folder = asker._proc, asker._dir
    began = time.monotonic()
    asker.cancel()
    assert time.monotonic() - began < 0.25 and not asker.busy()
    from PyQt6 import sip
    from PyQt6.QtCore import QProcess

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not sip.isdeleted(proc) and proc.state() != QProcess.ProcessState.NotRunning:
        spin(0.05)
    spin(0.2)
    assert sip.isdeleted(proc) or proc.state() == QProcess.ProcessState.NotRunning
    assert not folder.exists()  # its folder goes once it has ended


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe and the tools npm installs as .cmd files are Windows'")
def test_cancelling_on_windows_stops_the_tool_behind_a_cmd_file_without_waiting(qapp, tmp_path, monkeypatch):
    import time

    from replay_server import spin

    child = tmp_path / "child.pid"
    (tmp_path / "slowbrain.cmd").write_text(
        f'@"{sys.executable}" -c "import os, time; open(r\'{child}\', \'w\').write(str(os.getpid())); time.sleep(60)"\r\n', encoding="utf-8"
    )
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    asker = brains.Asker()
    asker.ask(brains.Brain(name="slow", type="command", label="Slow", command=["slowbrain"]), "", [], "hi", 60)
    deadline = time.monotonic() + 15
    while not (child.exists() and child.read_text()) and time.monotonic() < deadline:
        spin(0.05)
    pid = int(child.read_text())
    real = brains._end_tree
    monkeypatch.setattr(brains, "_end_tree", lambda root: (time.sleep(2), real(root))[1])  # as slow as taskkill was
    began = time.monotonic()
    asker.cancel()
    assert time.monotonic() - began < 0.25  # ending the tree can take seconds: never on the screen's thread
    deadline = time.monotonic() + 10
    while brains._alive(pid) and time.monotonic() < deadline:
        spin(0.1)
    assert not brains._alive(pid), "the tool the .cmd file started is still running"


def test_finding_the_brain_never_probes_on_the_screens_thread_and_remembers(qapp, monkeypatch, servers):
    import threading
    import time

    from replay_server import spin

    monkeypatch.setattr(brains, "reachable", REAL_REACHABLE)
    monkeypatch.setattr(brains, "_reachable", {})
    monkeypatch.setattr(brains, "_unsure", set())
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    looks = []

    def look(url, timeout):
        looks.append(threading.current_thread() is threading.main_thread())
        time.sleep(0.3)  # Windows takes this long, and more, to say nothing listens
        brains._reachable[url] = (time.monotonic(), "11434" in url)
        return "11434" in url

    monkeypatch.setattr(brains, "_look", look)
    servers[11434] = True
    finder, got = brains.Finder(), []
    began = time.monotonic()
    assert finder.find(brains.load_brains({}), "auto", None, got.append) is None  # not known yet
    assert time.monotonic() - began < 0.25 and not any(looks)  # it may have begun looking: elsewhere (blocking: 1.2 s)
    deadline = time.monotonic() + 10
    while not got and time.monotonic() < deadline:
        spin(0.05)
    assert [b.name for b in got] == ["ollama"] and looks and not any(looks) and finder.last.name == "ollama"
    before = len(looks)
    assert finder.find(brains.load_brains({}), "auto", None, got.append).name == "ollama"  # remembered: at once
    spin(0.1)
    assert len(got) == 2 and len(looks) == before


def test_a_brain_setting_of_the_wrong_kind_is_left_out_and_said_never_a_crash():
    problems = []
    found = brains.load_brains({"brains": {
        "claude": {"command": "claude -p --tools Bash"},  # a string: once a command line made of its letters
        "mine": {"type": "command", "command": ["my-llm"], "thinking_fields": 5, "env": "MY_*", "stream": "yes"},
        "odd": "not a table",
    }}, problems)
    assert found["claude"].command == brains.PRESETS["claude"]["command"]
    assert found["mine"].command == ["my-llm"] and found["mine"].thinking_fields == {} and found["mine"].env == []
    assert "odd" not in found
    assert problems == ["ai.brains.claude.command should be a list of text, so it's left out",
                        "ai.brains.mine.thinking_fields should be a table of tables, so it's left out",
                        "ai.brains.mine.env should be a list of text, so it's left out",
                        "ai.brains.mine.stream should be true or false, so it's left out"]


def test_ending_a_brains_processes_never_takes_one_that_only_shares_an_old_parents_number():
    """Windows hands a finished process's number to the next one: a program whose parent finished long ago still
    names that number as its parent. Only what was made after the brain is the brain's."""
    made = {100: 50, 101: 60, 102: 70, 7: 10, 8: 80}  # 7 is older than 100: its parent was another 100, long gone
    children = {100: [101, 7], 101: [102], 7: [8]}
    closed = []
    tree = brains._tree(100, children, lambda pid: (pid, made[pid]) if pid in made else None, closed.append)
    assert sorted(h for h, _ in tree) == [100, 101, 102] and closed == [7]  # nor 8, which 7 started
    assert brains._tree(5, children, lambda pid: None, closed.append) == []  # gone already: nothing


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' process tree")
def test_ending_a_tree_on_windows_ends_the_brain_and_what_it_started_and_nothing_else():
    import subprocess
    import time

    child = "import subprocess, sys, time; c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); print(c.pid, flush=True); time.sleep(60)"
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    root = subprocess.Popen(["cmd", "/c", sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
    try:
        grandchild = int(root.stdout.readline())
        assert brains._end_tree(root.pid) >= 3
        root.wait(10)
        deadline = time.monotonic() + 10
        while brains._alive(grandchild) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not brains._alive(grandchild) and other.poll() is None and brains._alive(os.getpid())
    finally:
        other.kill()
        root.kill()


LET_GO = r"""
import gc, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QEventLoop, QTimer, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
said = []
qInstallMessageHandler(lambda kind, context, text: said.append(text))
app = QApplication([])
from chatmon import brains
flag = Path(sys.argv[2]) / "started"
def spin(s):
    loop = QEventLoop()
    QTimer.singleShot(int(s * 1000), loop.quit)
    loop.exec()
sleeper = Path(sys.argv[2]) / "sleeper.py"
sleeper.write_text("import sys, time\nopen(sys.argv[1], 'w').write('x')\ntime.sleep(60)\n")
if sys.platform == "win32":  # as npm installs a tool: a .cmd file, with the real program under it
    (Path(sys.argv[2]) / "slowbrain.cmd").write_text('@"' + sys.executable + '" "' + str(sleeper) + '" "' + str(flag) + '"\r\n')
    os.environ["PATH"] = sys.argv[2] + os.pathsep + os.environ["PATH"]
    command = ["slowbrain"]
else:
    command = [sys.executable, str(sleeper), str(flag)]
for _ in range(4):  # it went wrong about seven times in ten: four tries all but always catch it
    flag.unlink(missing_ok=True)
    asker = brains.Asker()
    asker.ask(brains.Brain("slow", "command", label="Slow", command=command), "", [], "hi", 60)
    deadline = time.monotonic() + 20
    while not flag.exists() and time.monotonic() < deadline:
        spin(0.05)
    asker.cancel()
    del asker  # straight away, its process not yet ended
    gc.collect()
    spin(0.5)
spin(1)
print("survived", [t for t in said if "Destroyed while" in t])
"""


def test_an_asker_let_go_of_straight_after_cancelling_takes_nothing_down(tmp_path):
    """Qt deleting a process it still thought was running, with the Asker that made it, ended the whole app on
    Windows (0xC0000409). Run apart: a crash here must not take the tests with it."""
    import subprocess
    from pathlib import Path

    out = subprocess.run([sys.executable, "-c", LET_GO, str(Path(__file__).resolve().parent.parent), str(tmp_path)],
                         capture_output=True, text=True, timeout=90)
    assert out.returncode == 0 and "survived []" in out.stdout, (hex(out.returncode & 0xFFFFFFFF), out.stdout[-500:], out.stderr[-2000:])
