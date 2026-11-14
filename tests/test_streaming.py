"""Asking brains for real, over HTTP to a pretend provider on this computer (replay_server.py) and through a pretend
Claude Code: answers stream in as they're written, errors read as sentences, cancelling stops at once, and a brain
can be tested. No question ever reaches a real provider."""

import json
import sys
import threading
import time

import pytest
from replay_server import Provider, Reply, ask, json_reply, spin, sse

from chatmon import brains
from chatmon.brains import Brain


@pytest.fixture
def provider(qapp):
    p = Provider()
    yield p
    p.close()


@pytest.fixture(autouse=True)
def no_saved_keys():
    from chatmon import keychain

    before = keychain.use(keychain.InMemory())
    yield
    keychain.use(before)


def anthropic(provider, **kw) -> Brain:
    return Brain("anthropic-api", "anthropic", label="Anthropic API", url=f"{provider.url}/v1/messages", model="claude-haiku-5-5",
                 api_key="sk-ant-test-key-123456", api_key_env="ANTHROPIC_API_KEY", **kw)


ANTHROPIC_EVENTS = sse(
    {"type": "message_start", "message": {"id": "m", "content": []}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hmm"}},
    {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hel"}},
    {"type": "ping"},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "lo, "}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Randy!"}},
    {"type": "content_block_stop", "index": 1},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
    {"type": "message_stop"},
    named=True,
)


# -- streaming (M1B-12)


def test_the_anthropic_api_streams_each_piece_as_its_written(provider):
    provider.replies.append(Reply(pieces=ANTHROPIC_EVENTS))
    got = ask(brains.Asker(), anthropic(provider))
    assert got["partial"] == ["Hel", "lo, ", "Randy!"] and got["answered"] == "Hello, Randy!" and got["failed"] is None
    sent = provider.asked[0]
    assert sent["body"]["stream"] is True and sent["headers"]["accept"] == "text/event-stream"


def test_the_openai_responses_api_streams(provider):
    provider.replies.append(Reply(pieces=sse(
        {"type": "response.created", "response": {"id": "r"}},
        {"type": "response.output_text.delta", "delta": "Two "},
        {"type": "response.output_text.delta", "delta": "words."},
        {"type": "response.completed", "response": {"id": "r", "output_text": "Two words."}},
        named=True,
    )))
    brain = Brain("openai-api", "responses", label="OpenAI API", url=f"{provider.url}/v1", model="gpt-6.1-sol", api_key="sk-test-123456789")
    got = ask(brains.Asker(), brain)
    assert got["partial"] == ["Two ", "words."] and got["answered"] == "Two words."
    assert provider.asked[0]["path"] == "/v1/responses" and provider.asked[0]["body"]["stream"] is True


def test_chat_completions_stream_and_so_does_the_gemini_api(provider):
    chunks = sse(
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "Bon"}}]},
        {"choices": [{"index": 0, "delta": {"reasoning_content": "thinking..."}}]},
        {"choices": [{"index": 0, "delta": {"content": "jour"}, "finish_reason": "stop"}]},
        "[DONE]",
    )
    provider.replies.append(Reply(pieces=chunks))
    gemini = brains.load_brains({"brains": {"gemini-api": {"url": f"{provider.url}/v1beta/openai", "api_key": "AIza-test-key-0000"}}})["gemini-api"]
    got = ask(brains.Asker(), gemini)
    assert got["partial"] == ["Bon", "jour"] and got["answered"] == "Bonjour"
    assert provider.asked[0]["path"] == "/v1beta/openai/chat/completions" and provider.asked[0]["body"]["stream"] is True


def test_a_server_that_doesnt_stream_still_answers_and_streaming_can_be_turned_off(provider):
    provider.replies.append(json_reply(200, {"choices": [{"message": {"content": "Whole answer."}}]}))
    brain = Brain("mine", "openai", url=f"{provider.url}/v1", model="m")
    got = ask(brains.Asker(), brain)
    assert got["answered"] == "Whole answer." and got["partial"] == []
    provider.replies.append(json_reply(200, {"choices": [{"message": {"content": "Asked plainly."}}]}))
    got = ask(brains.Asker(), brains.load_brains({"brains": {"mine": {"type": "openai", "url": f"{provider.url}/v1", "model": "m", "stream": False}}})["mine"])
    assert got["answered"] == "Asked plainly." and "stream" not in provider.asked[1]["body"]


def test_an_error_partway_through_a_stream_is_said(provider):
    provider.replies.append(Reply(pieces=sse(
        {"type": "message_start", "message": {}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Par"}},
        {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
        named=True,
    )))
    got = ask(brains.Asker(), anthropic(provider))
    assert got["partial"] == ["Par"] and got["answered"] is None and got["failed"] == "Anthropic API: Overloaded."


def test_cancelling_stops_the_stream_and_nothing_comes_after(provider):
    hold = threading.Event()
    provider.replies.append(Reply(pieces=ANTHROPIC_EVENTS[:5] + ANTHROPIC_EVENTS[5:], hold=hold))
    asker, got = brains.Asker(), []
    asker.partial.connect(lambda t: got.append(("partial", t)))
    asker.answered.connect(lambda t: got.append(("answered", t)))
    asker.failed.connect(lambda t: got.append(("failed", t)))
    asker.ask(anthropic(provider), "S", [], "q", 10)
    deadline = time.monotonic() + 10
    while not provider.asked and time.monotonic() < deadline:
        spin(0.05)
    spin(0.3)  # the first piece is in; the provider holds the rest back
    started = time.monotonic()
    asker.cancel()
    assert time.monotonic() - started < 0.25 and not asker.busy()
    hold.set()
    assert provider.hung_up.wait(5), "the provider kept writing to nobody"
    spin(0.3)
    assert ("answered" not in [k for k, _ in got]) and ("failed" not in [k for k, _ in got]), got


# -- errors you can act on (M1B-09)


@pytest.mark.parametrize(
    ("status", "body", "said", "hint"),
    [
        (401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}, "invalid x-api-key", "Check its key in ANTHROPIC_API_KEY"),
        (403, {"error": {"message": "Your organization may not use this model."}}, "may not use this model", "Check its key in ANTHROPIC_API_KEY"),
        (429, {"error": {"type": "rate_limit_error", "message": "Rate limit reached for requests"}}, "Rate limit reached", "rate limited"),
        (500, "upstream exploded\nstack trace...", "upstream exploded", "having trouble"),
        (529, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}, "Overloaded", "having trouble"),
        (404, {"detail": "Model not found"}, "Model not found", "model's name"),
        (400, {"detail": [{"loc": ["body", "model"], "msg": "field required"}]}, "field required", ""),
        (400, [{"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}}], "API key not valid", ""),
    ],
)
def test_an_http_error_says_what_the_provider_said_the_status_and_what_to_do(provider, status, body, said, hint):
    provider.replies.append(json_reply(status, body))
    got = ask(brains.Asker(), anthropic(provider))
    assert got["answered"] is None and got["failed"].startswith("Anthropic API: ")
    assert said in got["failed"] and f"(HTTP {status})" in got["failed"] and hint in got["failed"], got["failed"]
    assert "expected shape" not in got["failed"]


def test_a_provider_repeating_the_key_never_puts_it_on_screen(provider):
    provider.replies.append(json_reply(401, {"error": {"message": "Incorrect API key provided: sk-ant-test-key-123456."}}))
    got = ask(brains.Asker(), anthropic(provider))
    assert "sk-ant-test-key-123456" not in got["failed"] and "Incorrect API key provided" in got["failed"]
    assert "sk-ant-test-key-123456" not in repr(anthropic(provider))  # nor in a brain's repr, should one be logged


def test_no_server_at_all_says_its_offline_or_not_running(qapp):
    got = ask(brains.Asker(), Brain("x", "openai", label="Somewhere", url="https://chatmon-test.invalid/v1", model="m", api_key="k"), wait_s=30)
    assert got["failed"].startswith("Somewhere: couldn't find chatmon-test.invalid: are you offline?"), got
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # free once closed: nothing listens there
    got = ask(brains.Asker(), Brain("ollama", "openai", label="Ollama", url=f"http://127.0.0.1:{port}/v1", model="m", local=True))
    assert got["failed"] == "Ollama: nothing is answering at 127.0.0.1: is it running?", got


# -- testing a brain (M1B-14)


def test_a_brain_test_says_how_long_the_answer_took_or_whats_wrong(provider):
    from PyQt6.QtCore import QEventLoop, QTimer

    def run(brain):
        loop, out = QEventLoop(), []
        tester = brain.test(timeout_s=10)
        tester.finished.connect(lambda ok, text, seconds: (out.append((ok, text, seconds)), loop.quit()))
        QTimer.singleShot(10_000, loop.quit)
        loop.exec()
        return out

    provider.replies.append(Reply(pieces=sse({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "OK"}}, named=True), gap_s=0.2))
    [(ok, text, seconds)] = run(anthropic(provider))
    assert ok and text == "OK" and 0.1 < seconds < 10
    assert provider.asked[0]["body"]["messages"][-1]["content"] == "Say OK"
    provider.replies.append(json_reply(401, {"error": {"message": "invalid x-api-key"}}))
    [(ok, text, seconds)] = run(anthropic(provider))
    assert not ok and "invalid x-api-key (HTTP 401). Check its key" in text and seconds >= 0


# -- Claude Code's own stream (M1B-12) and its command line (M1B-02)

FAKE_CLAUDE = r"""
import json, sys, time
args = sys.argv[1:]
question = sys.stdin.read()
open(sys.argv[0] + ".args", "w").write(json.dumps({"args": args, "question": question}))
def out(event):
    print(json.dumps(event), flush=True)
out({"type": "system", "subtype": "hook_started", "hook_name": "SessionStart:startup"})
out({"type": "system", "subtype": "init", "tools": [], "mcp_servers": []})
mode = "MODE"
if mode == "error":
    out({"type": "result", "subtype": "success", "is_error": True, "result": "Invalid API key · Please run /login"})
    sys.exit(1)
for piece in ["Hi ", "from ", "Claude."]:
    out({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": piece}}})
    time.sleep(0.05)
    if mode == "slow":
        time.sleep(60)
out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hi from Claude."}]}})
out({"type": "result", "subtype": "success", "is_error": False, "result": "Hi from Claude."})
"""


def pretend_claude(tmp_path, mode="ok") -> Brain:
    script = tmp_path / "claude.py"
    script.write_text(FAKE_CLAUDE.replace("MODE", mode), encoding="utf-8")
    preset = brains.load_brains({})["claude"]
    return brains.replace(preset, command=[sys.executable, str(script), *preset.command[1:]])


def test_claude_code_streams_its_answer(qapp, tmp_path):
    got = ask(brains.Asker(), pretend_claude(tmp_path), question="Who are you?")
    assert got["partial"] == ["Hi ", "from ", "Claude."] and got["answered"] == "Hi from Claude.", got
    seen = json.loads((tmp_path / "claude.py.args").read_text(encoding="utf-8"))
    assert "Person: Who are you?" in seen["question"]  # the question goes on stdin, never the command line
    args = seen["args"]
    for flag in ("--strict-mcp-config", "--no-session-persistence", "--verbose", "--include-partial-messages"):
        assert flag in args
    assert args[args.index("--tools") + 1] == "" and args[args.index("--permission-mode") + 1] == "dontAsk"
    assert args[args.index("--output-format") + 1] == "stream-json"


def test_claude_codes_own_error_is_said(qapp, tmp_path):
    got = ask(brains.Asker(), pretend_claude(tmp_path, "error"))
    assert got["failed"] == "Claude Code didn't answer (Invalid API key · Please run /login).", got


def test_a_claude_code_started_without_stream_json_still_answers(qapp, tmp_path):
    script = tmp_path / "plain.py"
    script.write_text("import sys; sys.stdin.read(); print('Plain answer.')", encoding="utf-8")
    brain = brains.replace(brains.load_brains({})["claude"], command=[sys.executable, str(script)])
    assert ask(brains.Asker(), brain)["answered"] == "Plain answer."


def test_cancelling_claude_code_returns_at_once_and_stops_it(qapp, tmp_path):
    asker, got = brains.Asker(), []
    asker.partial.connect(got.append)
    asker.ask(pretend_claude(tmp_path, "slow"), "S", [], "q", 30)
    deadline = time.monotonic() + 15
    while not got and time.monotonic() < deadline:
        spin(0.05)
    assert got == ["Hi "]
    proc = asker._proc
    started = time.monotonic()
    asker.cancel()
    assert time.monotonic() - started < 0.25
    deadline = time.monotonic() + 10
    from PyQt6 import sip
    from PyQt6.QtCore import QProcess

    while time.monotonic() < deadline and not sip.isdeleted(proc) and proc.state() != QProcess.ProcessState.NotRunning:
        spin(0.05)
    assert sip.isdeleted(proc) or proc.state() == QProcess.ProcessState.NotRunning
    assert got == ["Hi "]
