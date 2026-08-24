from __future__ import annotations

from typing import Optional
from ..audio import AudioStream, is_pcm_format
from ..shell import run_subprocess

async def _load_pcm(
    sample_rate: int,
    channels: Optional[int],
    format: str,
    path: Optional[str] = None,
    stream: Optional[AudioStream] = None,
) -> bytes:
    if not is_pcm_format(format):
        raise ValueError(f"Not a raw PCM format: {format!r}")

    command = [ "ffmpeg", "-hide_banner", "-loglevel", "error" ]

    if stream is not None and stream.format:
        command.extend([ "-f", stream.format ])

    command.extend([ "-i", path if path is not None else "pipe:0" ])

    # `-vn` drops any video track so containers like mp4/mkv decode cleanly
    # to a raw audio stream without ffmpeg trying to also process video.
    command.extend([ "-vn", "-f", format ])

    if channels is not None:
        command.extend([ "-ac", str(channels) ])

    command.extend([ "-ar", str(sample_rate), "pipe:1" ])

    process, stdout, stderr = await run_subprocess(
        command,
        stream.stream if stream is not None else None,
        stdout_handler=lambda r: r.read(),
        stderr_handler=lambda r: r.read(),
    )

    if process.returncode != 0:
        error_message = stderr.decode("utf-8", errors="replace") if stderr else ""
        raise RuntimeError(f"ffmpeg PCM decode failed (exit code {process.returncode}): {error_message}")

    return stdout

async def load_pcm_from_file(
    path: str,
    sample_rate: int,
    channels: Optional[int] = None,
    format: str = "s16le",
) -> bytes:
    """Load an audio/video file as raw PCM bytes via ffmpeg."""
    return await _load_pcm(sample_rate, channels, format, path=path)

async def load_pcm_from_stream(
    stream: AudioStream,
    sample_rate: int,
    channels: Optional[int] = None,
    format: str = "s16le",
) -> bytes:
    """Load an audio/video byte stream as raw PCM bytes via ffmpeg."""
    return await _load_pcm(sample_rate, channels, format, stream=stream)
