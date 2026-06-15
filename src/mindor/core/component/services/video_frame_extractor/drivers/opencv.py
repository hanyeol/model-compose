from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any, Iterator
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig
from mindor.dsl.schema.action import VideoFrameExtractorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.logger import logging
from ..base import VideoFrameExtractorService, VideoFrameExtractorDriver, register_video_frame_extractor_service
from ..base import ComponentActionContext
from .common import VideoFrameExtractorAction
import asyncio
import os

class OpenCVVideoFrameExtractorAction(VideoFrameExtractorAction):
    async def _extract(
        self,
        video: MediaSource,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        video_path = await save_stream_to_temporary_file(video.stream, video.format or "mp4")
        try:
            return await asyncio.to_thread(
                self._extract_frames,
                video_path,
                frame_interval,
                start_time,
                end_time,
                max_frame_count
            )
        finally:
            try:
                if video_path and os.path.exists(video_path):
                    os.unlink(video_path)
            except OSError:
                pass

    def _extract_frames(
        self,
        video_path: str,
        frame_interval: int,
        start_time: Optional[float],
        end_time: Optional[float],
        max_frame_count: Optional[int],
    ) -> List[Dict[str, Any]]:
        import cv2
        from PIL import Image as PILImage

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"Failed to open video '{video_path}'")

        frames: List[Dict[str, Any]] = []

        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

            start_frame = int(start_time * fps) if start_time is not None and fps > 0 else 0
            end_frame   = int(end_time * fps) if end_time is not None and fps > 0 else frame_count

            if start_frame > 0:
                capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            current_frame = start_frame
            extracted_count = 0

            while current_frame < end_frame:
                success, bgr_frame = capture.read()
                if not success:
                    break

                if (current_frame - start_frame) % frame_interval == 0:
                    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                    frames.append({
                        "frame": current_frame,
                        "timestamp": (current_frame / fps) if fps > 0 else 0.0,
                        "image": PILImage.fromarray(rgb_frame)
                    })
                    extracted_count += 1

                    if max_frame_count is not None and extracted_count >= max_frame_count:
                        break

                current_frame += 1
        finally:
            capture.release()

        return frames

@register_video_frame_extractor_service(VideoFrameExtractorDriver.OPENCV)
class OpenCVVideoFrameExtractorService(VideoFrameExtractorService):
    def __init__(self, id: str, config: VideoFrameExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "opencv-python" ]

    async def _run(self, action: VideoFrameExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await OpenCVVideoFrameExtractorAction(action).run(context, loop)
