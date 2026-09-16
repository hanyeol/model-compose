from __future__ import annotations

from typing import AsyncIterator, Iterable
from PIL import Image as PILImage
import asyncio
from mindor.core.utils.image import convert as convert_image
from mindor.core.utils.shell import stream_subprocess
from .executable import resolve_ffmpeg_executable

def _iter_rgb24_bytes(frames: Iterable[PILImage.Image], width: int, height: int) -> Iterable[bytes]:
    """Yield each frame as raw rgb24 bytes at the target resolution."""
    for frame in frames:
        yield convert_image(frame, width, height).tobytes()

async def encode_video_from_frames(
    frames: Iterable[PILImage.Image],
    width: int,
    height: int,
    fps: int,
    codec: str = "libx264",
    pixel_format: str = "yuv420p",
) -> AsyncIterator[bytes]:
    """Encode PIL frames to a fragmented MP4 byte stream via ffmpeg subprocess.

    Resolves the ffmpeg executable via `resolve_ffmpeg_executable()` (system PATH or
    imageio-ffmpeg's bundled binary). Raises RuntimeError if no ffmpeg is found.
    """
    ffmpeg_executable = resolve_ffmpeg_executable()

    if ffmpeg_executable is None:
        raise RuntimeError("ffmpeg executable not found. Install ffmpeg or `pip install imageio-ffmpeg`.")

    command = [
        ffmpeg_executable, "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:0",
        "-an",
        "-c:v", codec,
        "-pix_fmt", pixel_format,
        # Fragmented MP4: first `moof` flushes as soon as a keyframe is ready,
        # so consumers see bytes without waiting for the whole encode to finish.
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
        "pipe:1",
    ]

    async def _feed() -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        iterator = iter(_iter_rgb24_bytes(frames, width, height))

        # PIL work and rgb24 conversion runs in a thread so the event loop can
        # keep pumping stdout chunks to the consumer.
        end_of_stream = object()

        while True:
            chunk = await loop.run_in_executor(None, next, iterator, end_of_stream)
            if chunk is end_of_stream:
                break
            yield chunk

    error: list = []

    async def _stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            yield chunk

    async def _stderr(reader: asyncio.StreamReader) -> None:
        while True:
            line = await reader.readline()
            if not line:
                break
            error.append(line)

    async with stream_subprocess(
        command,
        source=_feed(),
        stdout_handler=_stdout,
        stderr_handler=_stderr,
    ) as (process, chunks, _):
        async for chunk in chunks:
            yield chunk

    if process.returncode is not None and process.returncode != 0:
        message = b"".join(error).decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg mp4 encoding failed (exit code {process.returncode}): {message}")
