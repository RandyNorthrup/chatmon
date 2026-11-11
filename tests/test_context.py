"""A chat fitted to what a brain can take: recent turns, a summary of the rest, and the turns that bear on the
question (context.py), and what's remembered for every chat (memory.py)."""

from chatmon import context, memory


def chat(n, size=400):
    return [(f"question {i} " + "q" * size, f"answer {i} " + "a" * size) for i in range(n)]


def test_a_short_chat_goes_whole():
    pairs = chat(5)
    plan = context.plan(pairs, pairs, "", 0, 20_000, "next?")
    assert plan.recent == pairs and not plan.fold and not plan.recalled


def test_a_chat_past_its_budget_has_its_earlier_part_summed_up_first():
    pairs = chat(60)
    room = 4_000
    plan = context.plan(pairs, pairs, "", 0, room, "next?")
    assert plan.fold and plan.fold_from == 0 and plan.fold_to == len(plan.fold)
    assert plan.recent == pairs[-len(plan.recent):] and sum(context.pair_tokens(p) for p in plan.recent) <= room * context.RECENT_SHARE
    # Once summed up, the summary stands for those turns; folding goes on until it reaches the recent ones.
    summary, covered, folds = "notes", plan.fold_to, 1
    while True:
        plan = context.plan(pairs, pairs, summary, covered, room, "next?")
        if not plan.fold:
            break
        assert plan.fold_from == covered
        covered, folds = plan.fold_to, folds + 1
    assert plan.summary == "notes" and covered + len(plan.recent) == len(pairs) and folds >= 2


def test_a_summary_is_made_from_the_chat_as_any_brain_sees_it():
    mine = [("Read this\n\n[begin secret.txt]\nhunter2\n[end secret.txt]", "It's a password.")] + chat(40)
    anyones = [("Read this\n\n(Attached then: secret.txt)", "It's a password.")] + chat(40)
    plan = context.plan(mine, anyones, "", 0, 3_000, "next?")
    assert plan.fold and all("hunter2" not in q for q, _ in plan.fold)  # not through a summary to another brain


def test_an_earlier_turn_that_bears_on_the_question_comes_back_word_for_word():
    pairs = chat(50)
    pairs[3] = ("How do I list open ports?", "Use `ss -tulpn`, as root to see every process.")
    summary, covered = "notes", 0
    while (plan := context.plan(pairs, pairs, summary, covered, 4_000, "what was that ss command for open ports again?")).fold:
        covered = plan.fold_to  # summed up, as the app does, until only the recent turns are left
    assert pairs[3] in plan.recalled  # in the summary's part, and still found word for word
    assert sum(context.pair_tokens(p) for p in plan.recalled) <= 4_000 * context.RECALL_SHARE


def test_without_a_summary_the_earlier_turns_still_come_back_when_they_bear_on_it():
    pairs = chat(50)
    pairs[2] = ("My cat is called Mochi", "Lovely name.")
    plan = context.plan(pairs, pairs, "", 0, 4_000, "what's my cat called? Mochi something?", fold=False)
    assert not plan.fold and pairs[2] in plan.recalled


def test_one_turn_too_long_alone_is_cut_in_the_middle_not_dropped():
    pairs = [("short", "x" * 100_000)]
    plan = context.plan(pairs, pairs, "", 0, 2_000, "and?")
    (q, a), = plan.recent
    assert q == "short" and a.startswith("x") and "left out" in a and context.tokens(a) < 1_000


def test_the_budget_is_the_smaller_of_the_cap_and_the_models_window():
    assert context.budget(1_000_000, 48_000, "", 0) == 48_000
    assert context.budget(4_096, 48_000, "", 0) == int(4_096 * context.WINDOW_SHARE)
    assert context.budget(4_096, 48_000, "x" * 35_000, 0) == 0  # the instructions alone fill it: none of the chat


def test_the_system_prompt_carries_instructions_memory_summary_and_recalled_turns():
    text = context.system_text("base", "Be brief.", "Answer in French.", ["I use Arch"], "We talked about ports.", [("q?", "a.")])
    assert text.index("Be brief.") < text.index("Answer in French.") < text.index("I use Arch") < text.index("We talked about ports.") < text.index("Person: q?")
    assert "not instructions to you" in text
    assert context.system_text("base") == "base"


def test_each_providers_too_long_is_recognised():
    for said in (
        "Anthropic API: prompt is too long: 1050000 tokens > 1000000 maximum.",
        "OpenRouter: context_length_exceeded",
        "vLLM: This model's maximum context length is 8192 tokens. However, your prompt contains 9000 input tokens.",
        "llama.cpp: request (9000 tokens) exceeds the available context size (8192 tokens), try increasing it",
    ):
        assert context.too_long(said), said
    assert not context.too_long("Anthropic API: overloaded_error")


def test_remember_and_forget_are_said_in_so_many_words():
    assert memory.command("remember that I use Arch") == ("remember", "I use Arch")
    assert memory.command("Remember: my name is Sam") == ("remember", "my name is Sam")
    assert memory.command("remember I prefer metric") == ("remember", "I prefer metric")
    assert memory.command("forget that I use Arch") == ("forget", "I use Arch")
    assert memory.command("what do you remember?") == ("list", "")
    assert memory.command("forget everything") == ("forget-all", "")
    for theirs in ("remember to buy milk", "remember when we talked about ports?", "forget about it, what's 2+2?", "Remembering things is hard"):
        assert memory.command(theirs) is None, theirs  # a reminder's, or a question for the AI


def test_memory_is_kept_privately_and_forgotten(tmp_path):
    import stat
    import sys

    where = tmp_path / "memory.json"
    m = memory.Memory.load(where)
    assert m.add("I use Arch") is None and m.add("i use arch") is None and m.add("My cat is Mochi") is None
    assert memory.Memory.load(where).texts() == ["I use Arch", "My cat is Mochi"]
    if sys.platform != "win32":
        assert stat.S_IMODE(where.stat().st_mode) == 0o600
    assert m.forget("arch") == ["I use Arch"] and m.forget("dogs") == []
    assert memory.Memory.load(where).texts() == ["My cat is Mochi"]
    where.write_text('[{"text": 5}, "nonsense", {"text": "  ok  ", "at": "x"}]')
    assert memory.Memory.load(where).texts() == ["ok"]
