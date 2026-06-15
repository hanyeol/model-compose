from __future__ import annotations

from typing import Optional, Dict, List, Set, Tuple, Any
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import VideoFrameExtractorService, VideoFrameExtractorDriver, register_video_frame_extractor_service
from ..base import ComponentActionContext
from .common import VideoFrameExtractorAction
from PIL import Image as PILImage
from io import BytesIO
import asyncio, os, re

_PTS_TIME_PATTERN = re.compile(rb"pts_time:\s*(\d+(?:\.\d+)?)")
_PNG_SIGNATURE    = b"\x89PNG\r\n\x1a\n"
_PNG_IEND_MARKER  = b"IEND\xaeB`\x82"

# Container formats safe to feed through ffmpeg pipe:0. Other formats (mp4/mov/mkv/webm/avi/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

class FFmpegVideoFrameExtractorAction(VideoFrameExtractorAction):
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        input_path, spooled = await self._resolve_input_path(video)

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info" ]

        if video.format and input_path is None:
            command.extend([ "-f", video.format ])
        if video.attrs.get("resolution"):
            command.extend([ "-s", str(video.attrs["resolution"]) ])
        if video.attrs.get("fps"):
            command.extend([ "-r", str(video.attrs["fps"]) ])
        if video.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(video.attrs["pixel_format"]) ])

        if start_time is not None:
            command.extend([ "-ss", str(start_time) ])
        if end_time is not None:
            command.extend([ "-to", str(end_time) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])

        filters: List[str] = []
        if frame_interval > 1:
            filters.append(f"select='not(mod(n\\,{frame_interval}))'")
        filters.append("showinfo")

        command.extend([ "-vf", ",".join(filters), "-vsync", "vfr" ])

        if max_frame_count is not None:
            command.extend([ "-frames:v", str(max_frame_count) ])

        command.extend([ "-f", "image2pipe", "-vcodec", "png", "pipe:1" ])

        logging.debug(f"Extracting frames with ffmpeg ({'path' if input_path else 'pipe'} input)")

        try:
            process, frames, (timestamps, raw) = await run_subprocess(
                command,
                video.stream if input_path is None else None,
                stdout_handler=lambda r: self._handle_stdout(r, frame_interval, max_frame_count),
                stderr_handler=self._handle_stderr,
            )

            if process.returncode != 0:
                stderr_text = b"".join(raw).decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg frame extraction failed (exit code {process.returncode}): {stderr_text}")

            for index, frame in enumerate(frames):
                frame["timestamp"] = timestamps[index] if index < len(timestamps) else 0.0

            return frames
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    async def _resolve_input_path(self, video: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mpegts, webm, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/mkv/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(video.stream, FileStreamResource):
            return video.stream.path, False

        if video.format and video.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before extraction")

        spooled_path = await save_stream_to_temporary_file(video.stream, video.format)

        return spooled_path, True

    async def _handle_stdout(
        self,
        reader: asyncio.StreamReader,
        frame_interval: int,
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        frames: List[Dict[str, Any]] = []
        buffer = b""

        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break

            buffer += chunk

            while True:
                start = buffer.find(_PNG_SIGNATURE)
                if start < 0:
                    break

                end = buffer.find(_PNG_IEND_MARKER, start + len(_PNG_SIGNATURE))
                if end < 0:
                    break

                end += len(_PNG_IEND_MARKER)
                payload = buffer[start:end]
                buffer = buffer[end:]

                image = PILImage.open(BytesIO(payload))
                image.load()

                source_frame = len(frames) * frame_interval
                frames.append({
                    "frame": source_frame,
                    "image": image,
                })

                if max_frame_count is not None and len(frames) >= max_frame_count:
                    return frames

        return frames

    async def _handle_stderr(self, reader: asyncio.StreamReader) -> Tuple[List[float], List[bytes]]:
        timestamps: List[float] = []
        raw: List[bytes] = []

        while True:
            line = await reader.readline()
            if not line:
                break
            raw.append(line)
            match = _PTS_TIME_PATTERN.search(line)
            if match:
                timestamps.append(float(match.group(1)))

        return timestamps, raw

@register_video_frame_extractor_service(VideoFrameExtractorDriver.FFMPEG)
class FFmpegVideoFrameExtractorService(VideoFrameExtractorService):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoFrameExtractorAction(action).run(context, loop)
