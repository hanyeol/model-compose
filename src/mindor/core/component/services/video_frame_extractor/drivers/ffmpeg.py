from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import StreamResource
from mindor.core.logger import logging
from ..base import VideoFrameExtractorService, VideoFrameExtractorDriver, register_video_frame_extractor_service
from ..base import ComponentActionContext
from .common import VideoFrameExtractorAction
from io import BytesIO
import asyncio
import re

_PTS_TIME_PATTERN = re.compile(rb"pts_time:\s*(\d+(?:\.\d+)?)")
_PNG_SIGNATURE    = b"\x89PNG\r\n\x1a\n"
_PNG_IEND_MARKER  = b"IEND\xaeB`\x82"

class FFmpegVideoFrameExtractorAction(VideoFrameExtractorAction):
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info" ]

        if video.format:
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

        command.extend([ "-i", "pipe:0" ])

        filters: List[str] = []
        if frame_interval > 1:
            filters.append(f"select='not(mod(n\\,{frame_interval}))'")
        filters.append("showinfo")

        command.extend([ "-vf", ",".join(filters), "-vsync", "vfr" ])

        if max_frame_count is not None:
            command.extend([ "-frames:v", str(max_frame_count) ])

        command.extend([ "-f", "image2pipe", "-vcodec", "png", "pipe:1" ])

        logging.debug("Extracting frames with ffmpeg via stdin pipe")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            feeder       = asyncio.create_task(self._feed_stdin(process, video.stream))
            stderr_task  = asyncio.create_task(self._read_stderr(process))
            frames       = await self._read_frames(process, frame_interval, max_frame_count)

            timestamps = await stderr_task
            await feeder

            return_code = await process.wait()
            if return_code != 0:
                stderr_text = b"".join(timestamps[1]).decode("utf-8", errors="replace") if isinstance(timestamps, tuple) else ""
                raise RuntimeError(f"ffmpeg frame extraction failed (exit code {return_code}): {stderr_text}")

            pts_list = timestamps[0] if isinstance(timestamps, tuple) else timestamps
            for index, frame in enumerate(frames):
                frame["timestamp"] = pts_list[index] if index < len(pts_list) else 0.0

            return frames
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            await video.stream.close()

    async def _feed_stdin(self, process: asyncio.subprocess.Process, stream: StreamResource) -> None:
        assert process.stdin is not None
        try:
            async for chunk in stream:
                process.stdin.write(chunk)
                await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            try:
                process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

    async def _read_stderr(self, process: asyncio.subprocess.Process) -> Tuple[List[float], List[bytes]]:
        assert process.stderr is not None
        timestamps: List[float] = []
        raw: List[bytes] = []

        while True:
            line = await process.stderr.readline()
            if not line:
                break
            raw.append(line)
            match = _PTS_TIME_PATTERN.search(line)
            if match:
                timestamps.append(float(match.group(1)))

        return timestamps, raw

    async def _read_frames(
        self,
        process: asyncio.subprocess.Process,
        frame_interval: int,
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        from PIL import Image as PILImage

        assert process.stdout is not None

        frames: List[Dict[str, Any]] = []
        buffer = b""

        while True:
            chunk = await process.stdout.read(65536)
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

@register_video_frame_extractor_service(VideoFrameExtractorDriver.FFMPEG)
class FFmpegVideoFrameExtractorService(VideoFrameExtractorService):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoFrameExtractorAction(action).run(context, loop)
