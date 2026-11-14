"""Short sounds for what Chatmon tells you: something needs you, a reminder, a focus session done, and (only if you
turn them on) an agent done, a success, an error, and a soft pop for a plain bubble. The files are chatmon/sounds/
<cue>.wav.

As the owner decided: only the alerts (needs-you, reminder, focus-done) sound unless you turn the others on; one
switch turns all sound off; and nothing sounds at a quiet time (Do Not Disturb, Focus, a full-screen app), which the
caller knows and says through `quiet`.

The players, the first that works: Qt's QSoundEffect, where QtMultimedia is installed (PyPI's PyQt6 has it; Debian
and Fedora package it separately) and there's somewhere to play to; else Windows' PlaySound, macOS's NSSound, or on
Linux pw-play (PipeWire), paplay (PulseAudio) or canberra-gtk-play. None of them makes the caller wait: QSoundEffect
and NSSound play in the background, PlaySound plays on a thread of its own, and the Linux players are started and
left to finish. Imports anywhere.
https://doc.qt.io/qt-6/qsoundeffect.html
https://learn.microsoft.com/en-us/previous-versions/dd743680(v=vs.85)
https://developer.apple.com/documentation/appkit/nssound"""

from __future__ import annotations

import array
import atexit
import ctypes
import ctypes.util
import io
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

CUES = ("needs-you", "reminder", "focus-done", "done", "success", "error", "pop")
ON_BY_DEFAULT = frozenset({"needs-you", "reminder", "focus-done"})  # the alerts; the rest wait to be turned on
FOLDER = Path(__file__).with_name("sounds")
DEFAULT_VOLUME = 70  # percent
AGAIN_AFTER = 0.25  # seconds before the same cue sounds again: a burst of bubbles is one pop, not ten
LINUX_PLAYERS = ("pw-play", "paplay", "canberra-gtk-play")


def scaled_wav(data: bytes, volume: float) -> bytes:
    """A WAV file's bytes with its samples scaled by `volume` (0 to 1), for players without a volume of their own.
    8-, 16- and 32-bit PCM; anything else comes back as it was."""
    if volume >= 1:
        return data
    try:
        with wave.open(io.BytesIO(data)) as source:
            params, frames = source.getparams(), source.readframes(source.getnframes())
    except (wave.Error, EOFError):
        return data
    width = params.sampwidth
    if width == 1:  # unsigned, centred on 128
        samples = bytes(max(0, min(255, round(128 + (b - 128) * volume))) for b in frames)
    elif width in (2, 4):
        values = array.array("h" if width == 2 else "i", frames)
        if sys.byteorder == "big":
            values.byteswap()
        values = array.array(values.typecode, (round(v * volume) for v in values))
        if sys.byteorder == "big":
            values.byteswap()
        samples = values.tobytes()
    else:
        return data
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setparams(params)
        target.writeframes(samples)
    return out.getvalue()


def player_command(player: str, path: Path, volume: float) -> list[str]:
    """The command line that plays `path` at `volume` (0 to 1) with one of the Linux players."""
    if player == "pw-play":
        return ["pw-play", f"--volume={volume:.2f}", str(path)]
    if player == "paplay":
        return ["paplay", f"--volume={round(volume * 65536)}", str(path)]  # 65536 is as recorded
    if player == "canberra-gtk-play":
        decibels = 20 * math.log10(max(volume, 0.001))  # its volume is a gain in dB
        return ["canberra-gtk-play", "-f", str(path), f"--volume={decibels:.1f}"]
    raise ValueError(f"No player called {player!r}.")


# -- players: each plays a file at a volume (0 to 1) without waiting, and says whether it could start


class QtPlayer:
    """QSoundEffect, one per file, made and played on the Qt thread. A QSoundEffect still playing when Python shuts
    down takes the process with it (Windows reports a fail-fast, 0xC0000409), so every one is stopped as the app
    quits, and again at exit for a Qt that never said it was quitting."""

    name = "qt"

    def __init__(self) -> None:
        from PyQt6.QtCore import QCoreApplication

        self.effects: dict[Path, object] = {}
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)
        atexit.register(self.close)

    @staticmethod
    def usable() -> bool:
        try:
            from PyQt6.QtMultimedia import QMediaDevices
        except ImportError:  # QtMultimedia not installed (a distribution's PyQt6 without it)
            return False
        return bool(QMediaDevices.audioOutputs())  # no audio device: another player won't do better, but may try

    def play(self, path: Path, volume: float) -> bool:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect

        effect = self.effects.get(path)
        if effect is None:
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(str(path)))  # loaded in the background, played once it is
            self.effects[path] = effect
        if effect.status() == QSoundEffect.Status.Error:
            return False
        effect.setVolume(volume)
        effect.play()
        return True

    def close(self) -> None:
        from PyQt6 import sip

        for effect in self.effects.values():
            if not sip.isdeleted(effect):  # at exit, Qt may have gone first
                effect.stop()
        self.effects.clear()


class WindowsPlayer:
    """PlaySound, from memory with the samples scaled to the volume, on a thread of its own: from memory, Windows
    plays only while the call waits."""

    name = "playsound"

    def __init__(self) -> None:
        self.played = 0  # sounds played to the end
        self.failed = 0  # sounds Windows couldn't play (no audio device, a file it can't read)
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="chatmon-sound", daemon=True)
        self._thread.start()

    def play(self, path: Path, volume: float) -> bool:
        try:
            data = scaled_wav(path.read_bytes(), volume)
        except OSError:
            return False
        self._queue.put(data)
        return True

    def _run(self) -> None:
        import winsound

        while True:
            data = self._queue.get()
            if data is None:
                return
            try:
                winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
                self.played += 1
            except RuntimeError:
                self.failed += 1

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(5)


class MacPlayer:
    """NSSound, one per file, through the Objective-C runtime with exact prototypes (as Apple silicon needs)."""

    name = "nssound"

    def __init__(self) -> None:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = objc.sel_registerName.argtypes = [ctypes.c_char_p]
        self._cls, self._sel = objc.objc_getClass, lambda name: objc.sel_registerName(name.encode())
        send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        self._obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
        self._with_text = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(send)
        self._init_file = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(send)
        self._set_float = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_float)(send)
        self._get_float = ctypes.CFUNCTYPE(ctypes.c_float, ctypes.c_void_p, ctypes.c_void_p)(send)
        self._yes = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(send)
        self.sounds: dict[Path, int] = {}

    def _sound(self, path: Path) -> int:
        sound = self.sounds.get(path)
        if sound is None:
            text = self._with_text(self._obj(self._cls(b"NSString"), self._sel("alloc")), self._sel("initWithUTF8String:"), os.fsencode(str(path)))
            sound = self._init_file(self._obj(self._cls(b"NSSound"), self._sel("alloc")), self._sel("initWithContentsOfFile:byReference:"), text, True) or 0
            self._obj(text, self._sel("release"))
            self.sounds[path] = sound
        return sound

    def volume(self, path: Path) -> float | None:
        sound = self.sounds.get(path)
        return self._get_float(sound, self._sel("volume")) if sound else None

    def play(self, path: Path, volume: float) -> bool:
        sound = self._sound(path)
        if not sound:  # a file NSSound can't read
            return False
        self._yes(sound, self._sel("stop"))  # from the start, if it's still sounding
        self._set_float(sound, self._sel("setVolume:"), volume)
        return self._yes(sound, self._sel("play"))


class CommandPlayer:
    """One of the Linux players, started and left to finish (it's reaped the next time a sound plays)."""

    def __init__(self, player: str) -> None:
        self.name = player
        self._running: list[subprocess.Popen] = []

    def play(self, path: Path, volume: float) -> bool:
        self._running = [p for p in self._running if p.poll() is None]
        try:
            self._running.append(subprocess.Popen(player_command(self.name, path, volume), stdin=subprocess.DEVNULL,
                                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        except OSError:
            return False
        return True


def linux_players(runtime_dir: str | None = None) -> list[CommandPlayer]:
    """The Linux players there are, best first: each sound server's own player only where that server is running
    (its socket is there; PipeWire's pipewire-pulse serves PulseAudio's too), then canberra-gtk-play."""
    runtime = Path(runtime_dir or os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    servers = {"pw-play": runtime / "pipewire-0", "paplay": runtime / "pulse" / "native", "canberra-gtk-play": None}
    return [CommandPlayer(name) for name in LINUX_PLAYERS
            if shutil.which(name) and (servers[name] is None or servers[name].exists())]


def default_players() -> list:
    players: list = []
    if QtPlayer.usable():
        players.append(QtPlayer())
    try:
        if sys.platform == "win32":
            players.append(WindowsPlayer())
        elif sys.platform == "darwin":
            players.append(MacPlayer())
        else:
            players.extend(linux_players())
    except (AttributeError, OSError):  # a runtime without the system's own player
        pass
    return players


class Sounds:
    """Which cues sound, how loud, and when not; `play(cue)` plays one if it should."""

    def __init__(self, folder: Path = FOLDER, players: Sequence | None = None):
        self.folder = Path(folder)
        self.enabled = True
        self.volume = DEFAULT_VOLUME
        self.cues = {cue: cue in ON_BY_DEFAULT for cue in CUES}
        self.player: str | None = None  # the player that played the last sound
        self._quiet: Callable[[], object] | None = None
        self._players = list(players) if players is not None else None  # found on first use
        self._last: dict[str, float] = {}

    def configure(self, enabled: bool = True, volume: float = DEFAULT_VOLUME, cues: Mapping[str, bool] | None = None,
                  quiet: Callable[[], object] | None = None) -> None:
        """`enabled`: the one switch for all sound. `volume`: percent, 0 to 100. `cues`: on or off for each cue named
        (the others keep their default; names Chatmon doesn't know are ignored). `quiet`: called before each sound,
        anything true means not now."""
        self.enabled = bool(enabled)
        self.volume = max(0, min(100, round(volume)))
        self.cues = {cue: cue in ON_BY_DEFAULT for cue in CUES}
        for cue, on in (cues or {}).items():
            if cue in self.cues:
                self.cues[cue] = bool(on)
        self._quiet = quiet

    def path(self, cue: str) -> Path:
        if cue not in CUES:
            raise ValueError(f"There's no sound called {cue!r}; the sounds are {', '.join(CUES)}.")
        return self.folder / f"{cue}.wav"

    def should_play(self, cue: str) -> bool:
        path = self.path(cue)
        if not (self.enabled and self.cues[cue] and self.volume > 0):
            return False
        if self._quiet is not None and self._quiet():
            return False
        return path.is_file()

    def play(self, cue: str) -> bool:
        """Play `cue` if it's on and it isn't a quiet time; True if a sound started. Never waits for it."""
        if not self.should_play(cue):
            return False
        now = time.monotonic()
        if now - self._last.get(cue, -AGAIN_AFTER) < AGAIN_AFTER:
            return False
        if self._players is None:
            self._players = default_players()
        for player in self._players:
            if player.play(self.path(cue), self.volume / 100):
                self._last[cue], self.player = now, player.name
                return True
        return False


_sounds = Sounds()


def configure(enabled: bool = True, volume: float = DEFAULT_VOLUME, cues: Mapping[str, bool] | None = None,
              quiet: Callable[[], object] | None = None) -> None:
    _sounds.configure(enabled, volume, cues, quiet)


def play(cue: str) -> bool:
    return _sounds.play(cue)
