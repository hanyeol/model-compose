from __future__ import annotations

from typing import AsyncIterator, Iterable
from .image import convert as convert_image
from PIL import Image as PILImage
import importlib.util
import asyncio, io

async def encode_video_from_frames(
    frames: Iterable[PILImage.Image],
    width: int,
    height: int,
    fps: int,
    codec: str = "libx264",
    pixel_format: str = "yuv420p",
) -> AsyncIterator[bytes]:
    """Encode PIL frames to a fragmented MP4 byte stream via PyAV (`av`).

    Fallback for when no ffmpeg executable is available. Raises ImportError if
    PyAV is not installed.
    """
    import av

    buffer = io.BytesIO()
    container = av.open(
        buffer, mode="w", format="mp4",
        options={ "movflags": "frag_keyframe+empty_moov+default_base_moof" },
    )
    stream = container.add_stream(codec, rate=fps)
    stream.width = width
    stream.height = height
    stream.pix_fmt = pixel_format

    loop = asyncio.get_running_loop()

    def _drain() -> bytes:
        # Snapshot muxed bytes emitted so far, then reset the buffer so the next
        # drain only sees new data. Safe because encode/mux only runs inside the
        # executor calls below.
        chunk = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return chunk

    def _encode_frame(image: PILImage.Image) -> None:
        video_frame = av.VideoFrame.from_image(image)
        for packet in stream.encode(video_frame):
            container.mux(packet)

    def _flush() -> None:
        for packet in stream.encode(None):
            container.mux(packet)

    try:
        for frame in frames:
            image = convert_image(frame, width, height)
            await loop.run_in_executor(None, _encode_frame, image)
            chunk = _drain()
            if chunk:
                yield chunk

        await loop.run_in_executor(None, _flush)
        tail = _drain()
        if tail:
            yield tail
    finally:
        container.close()
        tail = _drain()
        if tail:
            yield tail

def is_available() -> bool:
    """Return True if PyAV (`av`) is importable in the current environment."""
    return importlib.util.find_spec("av") is not None
