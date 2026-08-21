from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoAnalyzerActionConfig
from mindor.dsl.schema.action.impl.video_analyzer.impl.common import VideoAnalyzerMetric
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.logger import logging
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import os

class VideoBlack(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<VideoBlack regions={len(self.get('regions', []))} "
            f"black_ratio={self.get('black_ratio', 0.0):.4f}>"
        )

class VideoFreeze(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<VideoFreeze regions={len(self.get('regions', []))} "
            f"freeze_ratio={self.get('freeze_ratio', 0.0):.4f}>"
        )

class VideoBrightness(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<VideoBrightness mean={self.get('mean_brightness')} "
            f"min={self.get('min_brightness')} max={self.get('max_brightness')}>"
        )

class VideoMotion(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<VideoMotion mean={self.get('mean_motion')} "
            f"max={self.get('max_motion')}>"
        )

class VideoAnalyzerAction(ComponentAction):
    def __init__(self, config: VideoAnalyzerActionConfig):
        self.config: VideoAnalyzerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_video(self.config.video)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.metric, context)

        is_single_input  = not isinstance(video, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(video, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                    batch_results = await self._analyze_batch(batch_videos, self.config.metric, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_videos in BatchSourceIterator(video, batch_size=batch_size or 1):
                batch_results = await self._analyze_batch(batch_videos, self.config.metric, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, metric: VideoAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == VideoAnalyzerMetric.BLACK:
            min_duration      = await context.render_scalar(self.config.min_duration, "time")
            pixel_threshold   = await context.render_scalar(self.config.pixel_threshold, float)
            picture_threshold = await context.render_scalar(self.config.picture_threshold, float)

            return {
                "min_duration":      min_duration,
                "pixel_threshold":   pixel_threshold,
                "picture_threshold": picture_threshold,
            }

        if metric == VideoAnalyzerMetric.FREEZE:
            min_duration    = await context.render_scalar(self.config.min_duration, "time")
            noise_threshold = await context.render_scalar(self.config.noise_threshold, float)

            return {
                "min_duration":    min_duration,
                "noise_threshold": noise_threshold,
            }

        if metric == VideoAnalyzerMetric.BRIGHTNESS:
            sample_rate      = await context.render_scalar(self.config.sample_rate, float)
            include_timeline = await context.render_scalar(self.config.include_timeline, bool)

            return {
                "sample_rate":      sample_rate,
                "include_timeline": include_timeline,
            }

        if metric == VideoAnalyzerMetric.MOTION:
            sample_rate      = await context.render_scalar(self.config.sample_rate, float)
            include_timeline = await context.render_scalar(self.config.include_timeline, bool)

            return {
                "sample_rate":      sample_rate,
                "include_timeline": include_timeline,
            }

        raise ValueError(f"Unsupported video metric: {metric}")

    async def _analyze_batch(
        self,
        videos: List[MediaSource],
        metric: VideoAnalyzerMetric,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[dict]:
        results: List[dict] = []

        for video in videos:
            results.append(await self._analyze(metric, video, params, cancellation_token))

        return results

    async def _analyze(
        self,
        metric: VideoAnalyzerMetric,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> dict:
        if metric == VideoAnalyzerMetric.BLACK:
            return await self._analyze_black(source, params, cancellation_token)

        if metric == VideoAnalyzerMetric.FREEZE:
            return await self._analyze_freeze(source, params, cancellation_token)

        if metric == VideoAnalyzerMetric.BRIGHTNESS:
            return await self._analyze_brightness(source, params, cancellation_token)

        if metric == VideoAnalyzerMetric.MOTION:
            return await self._analyze_motion(source, params, cancellation_token)

        raise ValueError(f"Unsupported video metric: {metric}")

    @staticmethod
    async def _resolve_input_path(source: MediaSource) -> Tuple[Optional[str], bool]:
        """Decide how the analyzer CLI should read the input.

        Container-heavy formats (mp4/mov/mkv) need seekable input and are
        spooled to a temp file; streamable containers (mpegts, flv, ...) can
        be piped via stdin. Returns (input_path, spooled) where
        `input_path is None` means stdin.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if is_streamable_video_format(source.format):
            return None, False

        logging.debug("video analyzer input is not streamable; spooling to a temp file before probing")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    @abstractmethod
    async def _analyze_black(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_freeze(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_brightness(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass

    @abstractmethod
    async def _analyze_motion(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> dict:
        pass
