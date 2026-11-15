"""Sounds (sound.py): which cues sound and when, and each player for real with silent WAVs made for the test (the
real cues are M9's, in chatmon/sounds/)."""

import array
import io
import logging
import os
import sys
import time
import wave
from pathlib import Path

import pytest

from chatmon import sound

RATE = 44100


def silent_wav(path: Path, seconds: float = 0.3, width: int = 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(RATE)
        w.writeframes((b"\x80" if width == 1 else b"\x00" * width) * int(RATE * seconds))
    return path


@pytest.fixture
def cues(tmp_path):
    """A folder with every cue, each a short silent WAV."""
    for cue in sound.CUES:
        silent_wav(tmp_path / f"{cue}.wav")
    return tmp_path


class Recorder:
    """An output that records what it was asked to play: the test's ears, standing in for a sound card."""

    name = "recorder"

    def __init__(self, works: bool = True):
        self.works = works
        self.played: list[tuple[str, float]] = []

    def play(self, path, volume):
        if self.works:
            self.played.append((Path(path).stem, volume))
        return self.works


# -- what sounds, and when


def test_only_the_alerts_sound_until_you_turn_the_others_on():
    expected = {"needs-you": True, "reminder": True, "focus-done": True, "done": False, "success": False, "error": False, "pop": False}
    assert sound.Sounds().cues == expected
    s = sound.Sounds()
    s.configure(cues={"pop": True, "reminder": False, "from-a-newer-chatmon": True})
    assert s.cues == {**expected, "pop": True, "reminder": False}
    s.configure()  # configuring again starts from the defaults
    assert s.cues == expected


def test_a_cue_that_is_on_plays_at_the_volume_set(cues):
    ears = Recorder()
    s = sound.Sounds(cues, players=[ears])
    s.configure(volume=40)
    assert s.play("needs-you") and ears.played == [("needs-you", 0.4)] and s.player == "recorder"
    for volume, kept in ((150, 100), (-5, 0), (33.4, 33)):
        s.configure(volume=volume)
        assert s.volume == kept


def test_nothing_sounds_when_it_shouldnt(cues):
    ears = Recorder()
    s = sound.Sounds(cues, players=[ears])
    s.configure(enabled=True)
    assert not s.play("pop")  # off unless turned on
    s.configure(enabled=False)
    assert not s.play("needs-you")  # the one switch
    s.configure(volume=0)
    assert not s.play("needs-you")
    s.configure(quiet=lambda: "Do Not Disturb")
    assert not s.play("reminder")  # a quiet time
    s.configure(quiet=lambda: None)
    assert s.play("reminder")
    assert ears.played == [("reminder", 0.7)]


def test_the_same_cue_twice_at_once_sounds_once(cues):
    ears = Recorder()
    s = sound.Sounds(cues, players=[ears])
    assert s.play("needs-you") and not s.play("needs-you") and s.play("reminder")
    time.sleep(sound.AGAIN_AFTER + 0.05)
    assert s.play("needs-you")
    assert [cue for cue, _ in ears.played] == ["needs-you", "reminder", "needs-you"]


def test_a_missing_file_or_unknown_cue(tmp_path):
    ears = Recorder()
    s = sound.Sounds(tmp_path, players=[ears])  # M9's files not there (yet)
    assert not s.play("needs-you") and ears.played == []
    with pytest.raises(ValueError, match="no sound called 'ding'"):
        s.play("ding")


def test_the_next_player_is_tried_when_one_cant(cues):
    broken, ears = Recorder(works=False), Recorder()
    s = sound.Sounds(cues, players=[broken, ears])
    assert s.play("focus-done") and ears.played == [("focus-done", 0.7)] and s.player == "recorder"
    assert not sound.Sounds(cues, players=[Recorder(works=False)]).play("focus-done")


def test_a_player_that_wont_start_goes_to_the_log_and_the_next_one_plays(cues, monkeypatch, caplog):
    """A Linux player gone since it was found (uninstalled, or PATH changed): why it couldn't start is in the
    debug log, and the next player sounds the cue as before."""
    caplog.set_level(logging.DEBUG, logger="chatmon.sound")
    monkeypatch.setenv("PATH", str(cues))  # nothing to run there: starting pw-play fails for real
    ears = Recorder()
    s = sound.Sounds(cues, players=[sound.CommandPlayer("pw-play"), ears])
    assert s.play("needs-you") and s.player == "recorder" and ears.played == [("needs-you", 0.7)]
    logged = [r.getMessage() for r in caplog.records if r.name == "chatmon.sound" and r.levelno == logging.DEBUG]
    assert len(logged) == 1 and logged[0].startswith("couldn't start pw-play: ")


def test_closing_waits_for_a_sound_still_playing_and_leaves_no_player_behind(cues, tmp_path, monkeypatch):
    """As Chatmon quits (sound.close): a player still sounding is let finish, then reaped, never left running; the
    next sound finds the players again."""
    done = tmp_path / "done"
    # The player's command line: a sound half a second long, which says when it's over.
    monkeypatch.setattr(sound, "player_command", lambda player, path, volume: [sys.executable, "-c", f"import time; time.sleep(0.5); open({str(done)!r}, 'w').close()"])
    player = sound.CommandPlayer("pw-play")
    s = sound.Sounds(cues, players=[player, Recorder()])
    monkeypatch.setattr(sound, "_sounds", s)
    assert s.play("needs-you") and s.player == "pw-play" and not done.exists()
    running = list(player._running)
    sound.close()
    assert done.exists() and running and all(p.poll() is not None for p in running) and player._running == []
    assert s._players is None  # found again for the next sound


# -- for players without a volume of their own


def wav_bytes(samples, width: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(RATE)
        w.writeframes(bytes(samples) if width == 1 else array.array("h", samples).tobytes())
    return out.getvalue()


def samples_of(data: bytes) -> list[int]:
    with wave.open(io.BytesIO(data)) as w:
        frames = w.readframes(w.getnframes())
        return list(frames) if w.getsampwidth() == 1 else list(array.array("h", frames))


def test_samples_are_scaled_for_the_volume():
    assert samples_of(sound.scaled_wav(wav_bytes([1000, -1000, 32767, -32768, 0], 2), 0.5)) == [500, -500, 16384, -16384, 0]
    assert samples_of(sound.scaled_wav(wav_bytes([128, 228, 28, 255], 1), 0.5)) == [128, 178, 78, 192]  # 8-bit is centred on 128
    original = wav_bytes([1000], 2)
    assert sound.scaled_wav(original, 1.0) == original
    assert sound.scaled_wav(b"not a wav file", 0.5) == b"not a wav file"


def test_each_linux_player_is_told_the_volume(tmp_path):
    f = tmp_path / "pop.wav"
    assert sound.player_command("pw-play", f, 0.4) == ["pw-play", "--volume=0.40", str(f)]
    assert sound.player_command("paplay", f, 0.5) == ["paplay", "--volume=32768", str(f)]
    assert sound.player_command("canberra-gtk-play", f, 0.1) == ["canberra-gtk-play", "-f", str(f), "--volume=-20.0"]
    with pytest.raises(ValueError):
        sound.player_command("aplay", f, 1)


# -- the players, for real


def test_qsoundeffect_plays_it_without_waiting(qapp, cues):
    if not sound.QtPlayer.usable():
        pytest.skip("no QtMultimedia, or no audio device to play to")
    path = silent_wav(cues / "reminder.wav", seconds=1.0)
    player = sound.QtPlayer()
    s = sound.Sounds(cues, players=[player])
    s.configure(volume=40)
    started = time.monotonic()
    assert s.play("reminder") and time.monotonic() - started < 0.2 and s.player == "qt"
    effect = player.effects[path]
    playing = []
    effect.playingChanged.connect(lambda: playing.append(effect.isPlaying()))
    deadline = time.monotonic() + 5
    while True not in playing and not effect.isPlaying() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert True in playing or effect.isPlaying(), f"never played (status {effect.status()})"
    assert effect.source().toLocalFile() == path.as_posix() and effect.volume() == pytest.approx(0.4, abs=0.01)
    effect.stop()


def audio_devices_on_windows() -> int:
    import ctypes

    return ctypes.WinDLL("winmm").waveOutGetNumDevs()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_playsound_plays_on_its_own_thread(cues):
    if not audio_devices_on_windows():
        pytest.skip("no audio device")
    path = silent_wav(cues / "needs-you.wav", seconds=0.5)
    player = sound.WindowsPlayer()
    try:
        started = time.monotonic()
        assert player.play(path, 0.5)
        assert time.monotonic() - started < 0.1  # handed over, not played here
        deadline = started + 10
        while player.played + player.failed == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (player.played, player.failed) == (1, 0)
        assert time.monotonic() - started >= 0.4  # PlaySound held its own thread for the sound's length
    finally:
        player.close()
    assert not player.play(cues / "absent.wav", 0.5)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux only")
def test_linux_players_follow_the_sound_server_and_never_make_you_wait(tmp_path, monkeypatch, cues):
    bin_dir, runtime, log = tmp_path / "bin", tmp_path / "run", tmp_path / "played.log"
    bin_dir.mkdir()
    (runtime / "pulse").mkdir(parents=True)
    for name in sound.LINUX_PLAYERS:  # each pretends to play for a second, then says what it was asked
        script = bin_dir / name
        script.write_text(f'#!/bin/sh\nsleep 1\necho "$(basename "$0") $*" >> "{log}"\n')
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert [p.name for p in sound.linux_players(str(runtime))] == ["canberra-gtk-play"]  # no sound server running
    (runtime / "pulse" / "native").touch()
    assert [p.name for p in sound.linux_players(str(runtime))] == ["paplay", "canberra-gtk-play"]
    (runtime / "pipewire-0").touch()
    players = sound.linux_players(str(runtime))
    assert [p.name for p in players] == ["pw-play", "paplay", "canberra-gtk-play"]

    s = sound.Sounds(cues, players=players)
    s.configure(volume=50)
    started = time.monotonic()
    assert s.play("needs-you") and s.player == "pw-play"
    assert time.monotonic() - started < 0.5  # started, not waited for
    deadline = time.monotonic() + 10
    while not log.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert log.read_text().split() == ["pw-play", "--volume=0.50", str(cues / "needs-you.wav")]
    for player in players:
        player.close()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_nssound_plays_at_the_volume(cues):
    player = sound.MacPlayer()
    path = silent_wav(cues / "focus-done.wav", seconds=0.3)
    result = player.play(path, 0.5)
    assert player.sounds[path], "NSSound couldn't read the file"
    assert player.volume(path) == pytest.approx(0.5)
    assert result in (True, False)  # False only where macOS has no output to play to
    assert not player.play(cues / "absent.wav", 0.5)


def test_this_platforms_players(qapp):
    players = sound.default_players()
    names = [p.name for p in players]
    for player in players:
        getattr(player, "close", lambda: None)()
    if sound.QtPlayer.usable():
        assert names[0] == "qt"
    if sys.platform == "win32":
        assert "playsound" in names
    elif sys.platform == "darwin":
        assert "nssound" in names


def test_without_qtmultimedia_the_systems_own_player_is_used():
    """A distribution's PyQt6 without QtMultimedia (Debian and Fedora package it apart): the system's player."""
    import subprocess

    code = ("import sys; sys.modules['PyQt6.QtMultimedia'] = None\n"  # as if it weren't installed
            "from chatmon import sound\n"
            "players = sound.default_players()\n"
            "print(sound.QtPlayer.usable(), [p.name for p in players])\n"
            "[getattr(p, 'close', lambda: None)() for p in players]")
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONPATH=str(root), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    usable, names = out.stdout.strip().split(" ", 1)
    assert usable == "False" and "qt" not in names
    if sys.platform == "win32":
        assert names == "['playsound']"
    elif sys.platform == "darwin":
        assert names == "['nssound']"


QUIT_WHILE_PLAYING = r"""
import sys, time, wave
from pathlib import Path
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from chatmon import sound
folder = Path(sys.argv[1])
with wave.open(str(folder / "reminder.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b"\0\0" * 44100 * 2)
player = sound.QtPlayer()
player.play(folder / "reminder.wav", 0.5)
effect = player.effects[folder / "reminder.wav"]
heard = []
effect.playingChanged.connect(lambda: heard.append(effect.isPlaying()))  # a cycle: only the collector frees it, late
deadline = time.monotonic() + 5
while True not in heard and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
print("playing" if effect.isPlaying() else "silent", flush=True)
"""


def test_quitting_while_a_sound_plays_ends_cleanly(tmp_path):
    """A QSoundEffect still playing as Python shuts down used to end the process with a fail-fast (0xC0000409 on
    Windows): every effect is stopped first."""
    import subprocess

    if not sound.QtPlayer.usable():
        pytest.skip("no QtMultimedia, or no audio device to play to")
    root = Path(__file__).resolve().parent.parent
    env = dict(os.environ, PYTHONPATH=str(root), QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", QUIT_WHILE_PLAYING, str(tmp_path)], cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "playing", out.stderr  # it was still playing at the end
    assert out.returncode == 0, f"exit {out.returncode:#x}: {out.stderr}"
