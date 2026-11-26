"""Time fragmented stream parsing without a network or Qt event loop.

Run with the project's Python: python tests/benchmark_stream.py
The workload is a 4 MiB line received in 1,024 chunks. It measures the handling of an unfinished line, where
repeated copying and rescanning used to make work grow quadratically. It does not measure provider latency or
end-to-end answer rendering. Times are observations, never an absolute CI threshold on shared hardware.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatmon.brains import Stream

RUNS = 3
CHUNKS = 1024
CHUNK_BYTES = 4096


def main() -> None:
    durations = []
    for _run in range(RUNS):
        stream = Stream("openai")
        started = time.perf_counter()
        for _chunk in range(CHUNKS):
            stream.feed(b"x" * CHUNK_BYTES)
        durations.append(time.perf_counter() - started)
    print(f"Unfinished 4 MiB line, 4 KiB chunks, median of {RUNS}: {statistics.median(durations):.6f} s")


if __name__ == "__main__":
    main()
