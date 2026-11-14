import os
import stat
import tomllib

import pytest

from chatmon.settings import DEFAULTS, TEMPLATE, State, load_config, merge


def test_template_is_valid_and_matches_defaults():
    parsed = tomllib.loads(TEMPLATE)
    assert merge(DEFAULTS, parsed) == DEFAULTS


def test_first_run_writes_the_template(tmp_path):
    path = tmp_path / "config.toml"
    config, error = load_config(path)
    assert error is None and path.read_text(encoding="utf-8") == TEMPLATE and config["size"] == 120


def test_user_values_merge_over_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('size = 90\n[heads_up]\nbattery_low = 30\n[ai.brains.mine]\ntype = "command"\ncommand = ["x"]\n')
    config, _ = load_config(path)
    assert config["size"] == 90 and config["heads_up"]["battery_low"] == 30
    assert config["heads_up"]["disk_full_percent"] == 90 and config["ai"]["brains"]["mine"]["command"] == ["x"]


def test_broken_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("size = = 3\n")
    config, error = load_config(path)
    assert config == DEFAULTS and "config.toml" in error


def test_state_round_trip(tmp_path):
    state = State.load(tmp_path / "s" / "state.json")
    assert state.get("name") is None
    state.set("name", "Sparky")
    state.save()
    assert State.load(tmp_path / "s" / "state.json").get("name") == "Sparky"


# -- every value checked, one at a time (M1B-06)


def test_a_bad_value_costs_only_its_own_setting(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        'size = "big"\nwalk = "no"\n[breaks]\nevery_minutes = "60"\n[heads_up]\nupdates_every_hours = 1000000000\nbattery_low = 30\n'
        '[ai]\ntimeout_seconds = 12.6\n[ai.brains]\nbroken = "claude"\n[ai.brains.mine]\ntype = "command"\ncommand = ["x"]\n',
        encoding="utf-8",
    )
    config, error = load_config(path)
    assert config["size"] == 120  # not a number: its default
    assert config["walk"] is False and config["breaks"]["every_minutes"] == 60 and config["ai"]["timeout_seconds"] == 13
    assert config["heads_up"]["updates_every_hours"] == 168  # past a week: a week, never a timer that overflows
    assert config["heads_up"]["battery_low"] == 30 and config["ai"]["brains"] == {"mine": {"type": "command", "command": ["x"]}}
    assert error.startswith("config.toml: ")
    for named in ("size should be a number", "heads_up.updates_every_hours can be 1 to 168", "ai.brains.broken isn't a table"):
        assert named in error, error
    assert "every_minutes" not in error and "walk" not in error  # read as meant: nothing to report


def test_a_table_given_as_a_value_falls_back_to_its_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('breaks = 5\nfocus = "long"\n', encoding="utf-8")
    config, error = load_config(path)
    assert config["breaks"] == DEFAULTS["breaks"] and config["focus"] == DEFAULTS["focus"]
    assert "breaks should be a table" in error and "focus should be a table" in error


def test_every_setting_the_app_reads_as_a_number_is_one_after_loading():
    """What made Chatmon fail to start, or raise every 30 s: each number the app does arithmetic with."""
    from chatmon.settings import RANGES, coerce

    nonsense = {"size": "big", "sleep_after_minutes": [], "ai": {"timeout_seconds": {}}, "chats": {"context_tokens": None},
                "breaks": {"every_minutes": "", "snooze_minutes": float("nan")}, "focus": {"minutes": True},
                "heads_up": {"battery_low": "x", "battery_critical": -5, "disk_full_percent": 10**12, "updates_every_hours": float("inf")}}
    config, problems = coerce(merge(DEFAULTS, nonsense))
    assert len(problems) == len(RANGES)
    for dotted, (low, high) in RANGES.items():
        node = config
        for key in dotted.split("."):
            node = node[key]
        assert type(node) is int and low <= node <= high, dotted
    assert int(config["heads_up"]["updates_every_hours"] * 3600_000) < 2**31  # a QTimer takes it


# -- files kept safe (M1B-07, M1B-08)


def test_a_damaged_state_file_is_kept_aside_and_the_last_good_copy_used(tmp_path):
    path = tmp_path / "state.json"
    State(path, {"name": "Sparky", "notes": [{"text": "milk", "at": 1}]}).save()
    first = State.load(path)  # read and found good: that's the copy to go back to
    assert first.problem is None and (tmp_path / "state.json.bak").exists()
    first.set("name", "Changed")
    first.save()
    path.write_bytes(b'{"name": "Spa')  # damaged since
    state = State.load(path)
    assert state.get("name") == "Sparky" and state.get("notes") == [{"text": "milk", "at": 1}]
    bad = list(tmp_path.glob("state.json.bad-*"))
    assert len(bad) == 1 and bad[0].read_bytes() == b'{"name": "Spa'  # kept as it was, for a look
    assert "state.json was damaged" in state.problem and bad[0].name in state.problem and "went back to the copy" in state.problem
    state.save()
    assert State.load(path).get("name") == "Sparky" and bad[0].exists()


def test_a_damaged_file_with_no_good_copy_starts_afresh_and_says_so(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")  # JSON, but not the shape of a state file
    state = State.load(path)
    assert state.data == {} and "started it afresh" in state.problem and list(tmp_path.glob("state.json.bad-*"))
    assert State.load(tmp_path / "missing.json").problem is None  # a first run is no problem


def test_a_damaged_memory_file_is_never_written_over(tmp_path):
    from chatmon import memory

    where = tmp_path / "memory.json"
    good = memory.Memory.load(where)
    good.add("I use Arch")
    assert memory.Memory.load(where).texts() == ["I use Arch"]  # read and found good once
    where.write_bytes(b"\xff\xfe not json")
    back = memory.Memory.load(where)
    assert back.texts() == ["I use Arch"] and "memory.json was damaged" in back.problem
    assert [p.read_bytes() for p in tmp_path.glob("memory.json.bad-*")] == [b"\xff\xfe not json"]
    where.write_bytes(b"[" + b'{"text": "x", "at": 0},' * 60000 + b"{}]")  # over a megabyte: not ours
    assert memory.Memory.load(where).texts() == ["I use Arch"] and len(list(tmp_path.glob("memory.json.bad-*"))) == 2


def test_every_save_reaches_the_disk_before_it_replaces_the_old_file(tmp_path, monkeypatch):
    from chatmon import chats, memory

    steps = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (steps.append(("fsync", os.fstat(fd).st_size)), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (steps.append(("replace", os.path.basename(b))), real_replace(a, b))[1])
    State(tmp_path / "state.json", {"name": "Sparky"}).save()
    memory.Memory([memory.Item("x", 1.0)], tmp_path / "memory.json").save()
    chat = chats.Chat()
    chat.add(chats.Message("user", "hi"))
    chats.ChatBook(tmp_path / "chats").save(chat)
    swaps = [i for i, s in enumerate(steps) if s[0] == "replace"]
    assert [steps[i][1] for i in swaps] == ["state.json", "memory.json", f"{chat.id}.json"]
    for i in swaps:  # the file's whole contents synced just before each swap
        assert steps[i - 1][0] == "fsync" and steps[i - 1][1] > 0, steps


posix_only = pytest.mark.skipif(os.name != "posix", reason="file modes are POSIX's; on Windows these folders are the user's by their ACLs")


@posix_only
def test_files_are_made_private_from_the_start_and_folders_too(tmp_path, monkeypatch):
    from chatmon import chats, memory, settings

    first_write = []
    real_write, real_chmod = os.write, os.chmod

    def write(fd, data):
        if os.lseek(fd, 0, os.SEEK_CUR) == 0:  # a file's first bytes: its mode as it was made
            first_write.append((fd, os.fstat(fd).st_mode & 0o777))
        return real_write(fd, data)

    def chmod(path, mode, *args, **kwargs):
        assert os.path.isdir(path), f"{path} was made and only then narrowed"
        return real_chmod(path, mode, *args, **kwargs)

    old = os.umask(0o022)
    try:
        monkeypatch.setattr(os, "write", write)
        monkeypatch.setattr(os, "chmod", chmod)
        config, state_dir = tmp_path / "config" / "chatmon", tmp_path / "state" / "chatmon"
        settings.load_config(config / "config.toml")
        State(state_dir / "state.json", {"name": "x"}).save()
        memory.Memory([memory.Item("y", 1.0)], state_dir / "memory.json").save()
        chat = chats.Chat()
        chat.add(chats.Message("user", "hi"))
        chats.ChatBook(state_dir / "chats").save(chat)
    finally:
        os.umask(old)
    assert len(first_write) == 4 and all(mode == 0o600 for _fd, mode in first_write), first_write
    for f in (config / "config.toml", state_dir / "state.json", state_dir / "memory.json", state_dir / "chats" / f"{chat.id}.json"):
        assert stat.S_IMODE(f.stat().st_mode) == 0o600, f
    for d in (config, state_dir, state_dir / "chats"):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, d


@posix_only
def test_a_leftover_temporary_file_is_never_written_through(tmp_path):
    from chatmon import settings

    target = tmp_path / "state.json"
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("mine", encoding="utf-8")
    (tmp_path / "state.json.tmp").symlink_to(elsewhere)  # left there, or put there
    settings.write_private(target, "{}")
    assert elsewhere.read_text(encoding="utf-8") == "mine" and target.read_text(encoding="utf-8") == "{}"
