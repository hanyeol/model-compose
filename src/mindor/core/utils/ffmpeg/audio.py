from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from collections.abc import AsyncIterable
from mindor.core.utils.shell import run_subprocess

if TYPE_CHECKING:
    import numpy as np

async def _decode_pcm(
    sample_rate: int,
    path: Optional[str] = None,
    stream: Optional[AsyncIterable[bytes]] = None,
    format: Optional[str] = None,
) -> np.ndarray:
    import numpy as np

    command = [ "ffmpeg", "-hide_banner", "-loglevel", "error" ]

    if stream is not None and format:
        command.extend([ "-f", format ])

    command.extend([ "-i", path if path is not None else "pipe:0" ])
    # `-vn` drops any video track so containers like mp4/mkv decode cleanly
    # to a raw audio stream without ffmpeg trying to also process video.
    command.extend([ "-vn", "-f", "s16le", "-ac", "1", "-ar", str(sample_rate), "pipe:1" ])

    process, stdout, stderr = await run_subprocess(
        command,
        stream,
        stdout_handler=lambda r: r.read(),
        stderr_handler=lambda r: r.read(),
    )

    if process.returncode != 0:
        error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
        raise RuntimeError(f"ffmpeg PCM decode failed (exit code {process.returncode}): {error_message}")

    return np.frombuffer(stdout, dtype=np.int16).astype(np.float32) / 32768.0

async def decode_pcm_from_file(
    path: str,
    sample_rate: int
) -> np.ndarray:
    """Decode an audio/video file into mono float32 PCM in [-1, 1] via ffmpeg."""
    return await _decode_pcm(sample_rate, path=path)

async def decode_pcm_from_stream(
    stream: AsyncIterable[bytes],
    sample_rate: int,
    format: Optional[str] = None,
) -> np.ndarray:
    """Decode an audio/video byte stream into mono float32 PCM in [-1, 1] via ffmpeg."""
    return await _decode_pcm(sample_rate, stream=stream, format=format)
