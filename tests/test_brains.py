from dataclasses import replace
import pytest

from chatmon import brains
from chatmon.brains import Brain, BrainError


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


def test_a_running_local_server_is_picked_with_its_own_model(monkeypatch):
    monkeypatch.setattr(brains.shutil, "which", lambda name: None)
    monkeypatch.setattr(brains, "reachable", lambda url, timeout=0.15, wait=True: "11434" in url)
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
