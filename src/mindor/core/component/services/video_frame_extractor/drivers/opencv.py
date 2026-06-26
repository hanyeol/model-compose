from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Union, Callable, Any
from collections.abc import AsyncIterator, Iterator
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.logger import logging
from ..base import VideoFrameExtractorService, VideoFrameExtractorDriver, register_video_frame_extractor_service
from ..base import ComponentActionContext
from .common import VideoFrameExtractorAction
from PIL import Image as PILImage
import asyncio, os, threading

_FRAME_QUEUE_MAXSIZE = 16

class OpenCVVideoFrameExtractorAction(VideoFrameExtractorAction):
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        input_path, spooled = await self._resolve_input_path(video)

        def _cleanup() -> None:
            if not spooled:
                return
            try:
                if input_path and os.path.exists(input_path):
                    os.unlink(input_path)
            except OSError:
                pass

        if streaming:
            return self._stream_frames(input_path, frame_interval, start_time, end_time, max_frame_count, loop, _cleanup)

        return await self._collect_frames(input_path, frame_interval, start_time, end_time, max_frame_count, _cleanup)

    async def _collect_frames(
        self,
        input_path: str,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
        cleanup: Callable[[], None],
    ) -> List[Dict[str, Any]]:
        try:
            return await asyncio.to_thread(
                lambda: list(self._extract_frames(input_path, frame_interval, start_time, end_time, max_frame_count, None))
            )
        finally:
            cleanup()

    async def _stream_frames(
        self,
        input_path: str,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
        loop: asyncio.AbstractEventLoop,
        cleanup: Callable[[], None],
    ) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=_FRAME_QUEUE_MAXSIZE)
        cancel_event = threading.Event()

        def _produce() -> None:
            try:
                for frame in self._extract_frames(input_path, frame_interval, start_time, end_time, max_frame_count, cancel_event):
                    asyncio.run_coroutine_threadsafe(queue.put(frame), loop).result()
            except BaseException as e:
                asyncio.run_coroutine_threadsafe(queue.put(e), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        try:
            while True:
                item = await queue.get()

                if item is None:
                    break

                if isinstance(item, BaseException):
                    raise item

                yield item
        finally:
            cancel_event.set()
            await asyncio.to_thread(thread.join)
            cleanup()

    def _extract_frames(
        self,
        input_path: str,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
        cancel_event: Optional[threading.Event],
    ) -> Iterator[Dict[str, Any]]:
        import cv2

        capture = cv2.VideoCapture(input_path)

        if not capture.isOpened():
            raise ValueError(f"Failed to open video '{input_path}'")

        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
            total_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

            start_frame = int(start_time * fps) if start_time is not None and fps > 0 else 0
            end_frame   = int(end_time * fps) if end_time is not None and fps > 0 else total_frame_count

            if start_frame > 0:
                capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            current_frame = start_frame
            frame_count = 0

            while current_frame < end_frame:
                if cancel_event is not None and cancel_event.is_set():
                    break

                success, bgr_frame = capture.read()
                if not success:
                    break

                if (current_frame - start_frame) % frame_interval == 0:
                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    yield {
                        "image": PILImage.fromarray(rgb_frame),
                        "timestamp": (current_frame / fps) if fps > 0 else 0.0,
                    }
                    frame_count += 1

                    if max_frame_count and frame_count >= max_frame_count:
                        break

                current_frame += 1
        finally:
            capture.release()

    async def _resolve_input_path(self, video: MediaSource) -> Tuple[str, bool]:
        """
        OpenCV's VideoCapture only accepts a file path (no stdin pipe).

        - FileStreamResource: use its path directly (no spooling).
        - Otherwise: spool to a temp file so VideoCapture can open it.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(video.stream, FileStreamResource):
            return video.stream.path, False

        logging.debug("opencv input is not a local file; spooling to a temp file before extraction")

        spooled_path = await save_stream_to_temporary_file(video.stream, video.format or "mp4")

        return spooled_path, True

@register_video_frame_extractor_service(VideoFrameExtractorDriver.OPENCV)
class OpenCVVideoFrameExtractorService(VideoFrameExtractorService):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "opencv-python" ]

    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await OpenCVVideoFrameExtractorAction(action).run(context, loop)
