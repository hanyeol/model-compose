"""Convert data/test.mp3 into the 16 kHz mono int16 WAV the runner expects.

The source `test.mp3` is checked in (or dropped in) by the operator; this
script just normalizes its full length into `sample.wav`. Idempotent —
delete `sample.wav` if you want to regenerate.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "test.mp3"
OUT = HERE / "sample.wav"


def main() -> int:
    if OUT.exists():
        print(f"already have {OUT}")
        return 0
    if not SRC.exists():
        print(f"missing {SRC}; drop a source audio file there and re-run",
              file=sys.stderr)
        return 1
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH", file=sys.stderr)
        return 1

    subprocess.check_call(
        ["ffmpeg", "-y", "-i", str(SRC),
         "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
         str(OUT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
