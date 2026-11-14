"""Chatmon's sound cues: measure candidates, build the shipped WAVs, and make an audition file.

usage:
  python art/tools/sound-cues.py candidates [--out DIR]   measure every candidate, draw its spectrogram, audition
  python art/tools/sound-cues.py build                    make chatmon/sounds/*.wav from art/sounds/cues.json
  python art/tools/sound-cues.py check                    check the shipped WAVs against the targets (no ffmpeg
                                                          writes; exit 1 on a failure)
  python art/tools/sound-cues.py audition [--out DIR]     the shipped cues in one file, with an index

art/sounds/cues.json names, for each cue, its source file in the sound library (the owner's
Documents/ContentLibrary/explainer-channel/sfx, where every file's origin and licence is in SOURCES.md), how
long it may be, and its alternatives. `build` trims leading and trailing silence, cuts it to its longest, fades
it out, makes it mono 44.1 kHz 16-bit, and matches its loudness (RMS) to the target without letting the peak
pass the ceiling; then it checks each result and writes art/sounds/SOURCES.md from the library's records.

Needs ffmpeg and ffprobe on PATH. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CUES = ROOT / "art" / "sounds" / "cues.json"
SOURCES_OUT = ROOT / "art" / "sounds" / "SOURCES.md"
SHIPPED = ROOT / "chatmon" / "sounds"
RMS_TOLERANCE_DB = 1.5
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def load() -> dict:
    data = json.loads(CUES.read_text(encoding="utf-8"))
    data["library_path"] = Path(os.path.expanduser(os.path.expandvars(data["library"])))
    return data


def ffmpeg(*args: str) -> str:
    done = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg {' '.join(args)}\n{done.stderr[-2000:]}")
    return done.stderr


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True, creationflags=NO_WINDOW).stdout
    return float(out.strip())


def levels(path: Path) -> dict:
    """RMS and peak of the whole file (astats' Overall section, which comes last), in dBFS."""
    err = ffmpeg("-i", str(path), "-af", "astats=metadata=0", "-f", "null", "-")
    rms = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", err)
    peak = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", err)
    as_db = (lambda v: float("-inf") if v == "-inf" else float(v))
    return {"rms": as_db(rms[-1]), "peak": as_db(peak[-1]), "duration": duration(path)}


def spectrogram(src: Path, png: Path) -> None:
    ffmpeg("-i", str(src), "-lavfi", "showspectrumpic=s=480x160:legend=0", str(png))


def library_records(library: Path) -> dict[str, tuple[str, str]]:
    """The library's SOURCES.md rows: file -> (origin, licence)."""
    records = {}
    for line in (library / "SOURCES.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] not in ("File", "---") and not set(cells[0]) <= {"-"}:
            records[cells[0]] = (cells[1], cells[2])
    return records


def build_one(src: Path, out: Path, spec: dict, data: dict) -> dict:
    max_s, fade = float(spec["max_s"]), float(spec.get("fade_ms", 60)) / 1000
    target = float(data["target_rms_db"]) + float(spec.get("gain_db", 0))
    ceiling = float(data["peak_db"])
    with tempfile.TemporaryDirectory(prefix="chatmon-cue-") as tmp:
        trimmed = Path(tmp) / "trimmed.wav"
        # Leading and trailing silence off (the trailing one by trimming the reversed sound), at most max_s long,
        # one channel at the shipped rate.
        ffmpeg("-i", str(src), "-af",
               "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
               "silenceremove=start_periods=1:start_threshold=-55dB,areverse,"
               f"atrim=0:{max_s},aformat=channel_layouts=mono,aresample={data['rate']}",
               "-c:a", "pcm_s16le", str(trimmed))
        got = levels(trimmed)
        gain = min(target - got["rms"], ceiling - got["peak"])  # loud enough, never past the ceiling
        start = max(0.0, got["duration"] - fade)
        out.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", str(trimmed), "-af", f"afade=t=out:st={start:.3f}:d={fade:.3f},volume={gain:.2f}dB",
               "-ar", str(data["rate"]), "-ac", "1", "-c:a", "pcm_s16le", str(out))
    return {"target_rms": target, "gain": gain}


def check_one(path: Path, spec: dict, data: dict) -> list[str]:
    problems = []
    with wave.open(str(path)) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, int(data["rate"])):
            problems.append(f"format {w.getnchannels()} ch, {8 * w.getsampwidth()} bit, {w.getframerate()} Hz; "
                            f"want mono 16 bit {data['rate']} Hz")
    got = levels(path)
    target = float(data["target_rms_db"]) + float(spec.get("gain_db", 0))
    if got["duration"] > float(spec["max_s"]) + 0.02:
        problems.append(f"{got['duration']:.2f} s is longer than {spec['max_s']} s")
    if got["duration"] < 0.05:
        problems.append(f"{got['duration']:.3f} s is too short to hear")
    if got["peak"] > float(data["peak_db"]) + 0.1:
        problems.append(f"peak {got['peak']:.1f} dBFS is past the {data['peak_db']} ceiling")
    if got["rms"] < -50:
        problems.append("it is silent")
    elif got["rms"] > target + RMS_TOLERANCE_DB:
        problems.append(f"RMS {got['rms']:.1f} dBFS is louder than {target:.1f}")
    elif got["rms"] < target - RMS_TOLERANCE_DB and got["peak"] < float(data["peak_db"]) - 0.5:
        problems.append(f"RMS {got['rms']:.1f} dBFS is quieter than {target:.1f} with headroom left")
    return problems


def cmd_build(data: dict) -> int:
    records = library_records(data["library_path"])
    rows, failed = [], False
    for name, spec in data["cues"].items():
        src = data["library_path"] / spec["source"]
        if spec["source"] not in records:
            print(f"{name}: {spec['source']} has no origin and licence in the library's SOURCES.md", file=sys.stderr)
            return 1
        out = SHIPPED / f"{name}.wav"
        info = build_one(src, out, spec, data)
        problems = check_one(out, spec, data)
        failed |= bool(problems)
        got = levels(out)
        print(f"{'FAIL' if problems else 'ok  '} {name:11} {got['duration']:.2f} s  RMS {got['rms']:6.1f}  "
              f"peak {got['peak']:5.1f}  (gain {info['gain']:+.1f} dB) {'; '.join(problems)}")
        origin, licence = records[spec["source"]]
        rows.append(f"| chatmon/sounds/{name}.wav | {spec['source']}: {origin} | {licence} |")
    SOURCES_OUT.write_text(
        "# Where Chatmon's sounds come from\n\n"
        "Made by `python art/tools/sound-cues.py build` from `cues.json`: each source file is trimmed, faded, made\n"
        "mono 44.1 kHz and matched in loudness. Sources are in the owner's sound library, whose own SOURCES.md is\n"
        "where these origins come from. ElevenLabs Sound Effects made on the owner's paid plan are the owner's to\n"
        "use commercially and are released here under the project's MIT licence, as is the owner's own synthesized\n"
        "work.\n\n| File | Source | Licence |\n|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return 1 if failed else 0


def cmd_check(data: dict) -> int:
    failed = False
    for name, spec in data["cues"].items():
        path = SHIPPED / f"{name}.wav"
        problems = check_one(path, spec, data) if path.exists() else ["missing"]
        failed |= bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {name}: {'; '.join(problems) or 'within targets'}")
    return 1 if failed else 0


def audition(files: list[tuple[str, Path]], out_dir: Path, stem: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chatmon-audition-") as tmp:
        parts, index, at = [], [], 0.0
        gap = Path(tmp) / "gap.wav"
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.8", "-c:a", "pcm_s16le", str(gap))
        for i, (label, path) in enumerate(files):
            norm = Path(tmp) / f"{i}.wav"
            ffmpeg("-i", str(path), "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(norm))
            index.append(f"{at:6.1f} s  {label}")
            at += duration(norm) + 0.8
            parts += [norm, gap]
        listing = Path(tmp) / "list.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        wav = out_dir / f"{stem}.wav"
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "pcm_s16le", str(wav))
    (out_dir / f"{stem}-index.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    return wav


def cmd_candidates(data: dict, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines, files = [], []
    for name, spec in data["cues"].items():
        for rel in [spec["source"], *spec.get("alternatives", [])]:
            src = data["library_path"] / rel
            got = levels(src)
            png = out_dir / f"{name}--{Path(rel).stem}.png"
            spectrogram(src, png)
            mark = "*" if rel == spec["source"] else " "
            lines.append(f"{mark} {name:11} {rel:40} {got['duration']:5.2f} s  RMS {got['rms']:6.1f}  peak {got['peak']:5.1f}")
            files.append((f"{mark} {name}: {rel}", src))
    (out_dir / "candidates.txt").write_text("* = the cue's current source\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"audition: {audition(files, out_dir, 'candidates')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["candidates", "build", "check", "audition"])
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "chatmon-sounds")
    args = parser.parse_args(argv)
    data = load()
    if args.command == "build":
        return cmd_build(data)
    if args.command == "check":
        return cmd_check(data)
    if args.command == "candidates":
        return cmd_candidates(data, args.out)
    files = [(name, SHIPPED / f"{name}.wav") for name in data["cues"]]
    print(f"audition: {audition(files, args.out, 'chatmon-cues')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
