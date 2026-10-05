from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.filename import format_filename
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.url import UrlResource
from mindor.core.logger import logging
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

if TYPE_CHECKING:
    HtmlResolver = Callable[[str], Awaitable[UrlResource]]
    SessionFactory = Callable[[], Awaitable[HtmlFrameRendererSession]]

@dataclass
class FrameRenderResult:
    """Result of one worker rendering one frame.

    `image`/`timestamp` are set on success; `error` is set on failure. The
    orchestrator checks `error` first and aborts the whole render call if
    any worker surfaces an exception.
    """
    number: int
    image: Optional[ImageStreamResource] = None
    timestamp: Optional[float] = None
    error: Optional[BaseException] = None

class HtmlFrameRendererSession(ABC):
    """Driver-abstract browser page for rendering frames.

    Owns one browser page for the duration of a single render call. The
    orchestrator opens N sessions in parallel (one per worker) and pulls
    frames from them one at a time.
    """
    @abstractmethod
    async def load_html(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> None:
        """Load the page: navigate to `html`, inject bootstrap, and wait for
        the page's `window.__renderer.ready === true` signal.

        Called exactly once per session before any `render_frame` call.
        Paired with `close()`.
        """
        pass

    @abstractmethod
    async def render_frame(self, timestamp: float) -> ImageStreamResource:
        """Render a single frame at `timestamp` seconds and return its bytes.

        Returned as `ImageStreamResource` carrying the driver's encoded
        bytes (JPEG/PNG) so downstream consumers that can pipe raw bytes
        (e.g. ffmpeg `image2pipe`) avoid a decode/re-encode round-trip.
        Consumers that need a `PIL.Image` call `await frame.as_image()`.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class HtmlFrameRenderOrchestrator:
    """Pull-based multi-worker render coordinator.

    Each session becomes a worker that pulls frame numbers off a shared
    request queue, renders them, and pushes the results onto a shared result
    queue. The orchestrator feeds the request queue (initial burst =
    `len(sessions)`, then one new submit per result received) and reorders
    completed frames back into monotonic order before yielding
    `(number, image, timestamp)` from `render_frames()`.

    Workers are stopped via task cancel when `render_frames()` completes or
    aborts. The sessions themselves are *not* closed here — the caller owns
    their lifecycle.

    Single-use: call `render_frames()` exactly once per instance.
    """
    def __init__(
        self,
        sessions: List[HtmlFrameRendererSession],
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ):
        self._sessions    = sessions
        self._html        = html
        self._props       = props
        self._params      = params
        self._frame_rate  = params["frame_rate"]
        self._frame_count = int(params["duration"] * self._frame_rate + 0.5)

        self._request_queue: asyncio.Queue[int] = asyncio.Queue()
        self._result_queue: asyncio.Queue[FrameRenderResult] = asyncio.Queue()
        self._worker_tasks: List[asyncio.Task] = []

    async def render_frames(self) -> AsyncIterator[Tuple[int, ImageStreamResource, float]]:
        logging.debug(
            "Capturing %d frames at %s fps (%.3fs) across %d worker(s)",
            self._frame_count, self._frame_rate, self._params["duration"], len(self._sessions),
        )

        if self._frame_count == 0:
            return

        # Set up every session in parallel before any frame request is dispatched.
        # One slow session (fonts, textures) shouldn't delay the others' setup.
        await asyncio.gather(
            *(session.load_html(self._html, self._props, self._params)
            for session in self._sessions)
        )

        self._worker_tasks = [
            asyncio.create_task(self._run_worker(session))
            for session in self._sessions
        ]

        try:
            # Initial burst: enqueue up to `worker_count` frame numbers so every
            # worker has something to pick up immediately.
            next_to_submit = 0

            for _ in range(min(len(self._sessions), self._frame_count)):
                self._request_queue.put_nowait(next_to_submit)
                next_to_submit += 1

            reorder_buffer: Dict[int, FrameRenderResult] = {}
            next_to_yield = 0
            received = 0

            while received < self._frame_count:
                result = await self._result_queue.get()
                received += 1

                if result.error is not None:
                    raise result.error

                reorder_buffer[result.number] = result

                # Keep workers busy: one result in → one new submit out, up to
                # the frame count. The last `worker_count - 1` cycles have no
                # submit (frames exhausted), draining the pipeline.
                if next_to_submit < self._frame_count:
                    self._request_queue.put_nowait(next_to_submit)
                    next_to_submit += 1

                # Yield any contiguous prefix of completed frames.
                while next_to_yield in reorder_buffer:
                    frame = reorder_buffer.pop(next_to_yield)
                    yield frame.number, frame.image, frame.timestamp
                    next_to_yield += 1
        finally:
            await self._stop_workers()

    async def _run_worker(self, session: HtmlFrameRendererSession) -> None:
        """Pull frame numbers and push results. Render exceptions are wrapped
        in a `FrameRenderResult` so `render_frames()` can surface them on its own
        event loop step; CancelledError propagates (that's the orchestrator
        telling us to stop)."""
        while True:
            number = await self._request_queue.get()

            try:
                image = await session.render_frame(number / self._frame_rate)
                await self._result_queue.put(FrameRenderResult(
                    number=number,
                    image=image,
                    timestamp=number / self._frame_rate,
                ))
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                await self._result_queue.put(FrameRenderResult(number=number, error=e))

    async def _stop_workers(self) -> None:
        for task in self._worker_tasks:
            task.cancel()

        # Drain CancelledError (and any late non-cancel exceptions) so the event
        # loop doesn't log "Task exception was never retrieved" warnings.
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)

class HtmlFrameRendererAction(ComponentAction):
    def __init__(
        self,
        config: HtmlFrameRendererActionConfig,
        html_resolver: HtmlResolver,
        session_factory: SessionFactory,
    ):
        self.config: HtmlFrameRendererActionConfig = config
        self.html_resolver: HtmlResolver = html_resolver
        self.session_factory: SessionFactory = session_factory

    async def run(self, context: ComponentActionContext) -> Any:
        html       = await context.render_text(self.config.html)
        props      = await context.render_variable(self.config.props) if self.config.props else None
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(html, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(html, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_htmls, batch_props in BatchSourceIterator((html, props), batch_size=batch_size or 1):
                    batch_htmls = [ await self.html_resolver(html) for html in batch_htmls ]
                    batch_results = await self._render_batch(batch_htmls, batch_props, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_htmls, batch_props in BatchSourceIterator((html, props), batch_size=batch_size or 1):
                batch_htmls = [ await self.html_resolver(html) for html in batch_htmls ]
                batch_results = await self._render_batch(batch_htmls, batch_props, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        duration        = await context.render_scalar(self.config.duration, "time")
        frame_rate      = await context.render_scalar(self.config.frame_rate, float)
        width           = await context.render_scalar(self.config.width, int)
        height          = await context.render_scalar(self.config.height, int)
        format          = await context.render_scalar(self.config.format, str)
        quality         = await context.render_scalar(self.config.quality, int) if self.config.quality is not None else None
        transparent     = await context.render_scalar(self.config.transparent, bool)
        ready_timeout   = await context.render_scalar(self.config.ready_timeout, "time")
        render_timeout  = await context.render_scalar(self.config.render_timeout, "time")
        worker_count    = await context.render_scalar(self.config.worker_count, int)
        filename_format = await context.render_variable(self.config.filename_format)

        if duration <= 0:
            raise ValueError(f"'duration' must be > 0, got {duration}")

        if frame_rate <= 0:
            raise ValueError(f"'frame_rate' must be > 0, got {frame_rate}")

        if width <= 0 or height <= 0:
            raise ValueError(f"'width' and 'height' must be > 0, got {width}x{height}")

        if format not in ("jpeg", "png"):
            raise ValueError(f"'format' must be 'jpeg' or 'png', got {format!r}")

        if transparent and format != "png":
            raise ValueError(f"'transparent: true' requires 'format: png' (jpeg has no alpha channel), got {format!r}")

        if worker_count < 1:
            raise ValueError(f"'worker_count' must be >= 1, got {worker_count}")

        return {
            "duration":        duration,
            "frame_rate":      frame_rate,
            "width":           width,
            "height":          height,
            "format":          format,
            "quality":         quality,
            "transparent":     transparent,
            "ready_timeout":   ready_timeout,
            "render_timeout":  render_timeout,
            "worker_count":    worker_count,
            "filename_format": filename_format,
        }

    async def _render_batch(
        self,
        htmls: List[UrlResource],
        props: Optional[List[Optional[Dict[str, Any]]]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]] = []

        for html, props in zip(htmls, props if props is not None else [ None ] * len(htmls)):
            if streaming:
                results.append(self._stream_frames(html, props, params))
            else:
                results.append(await self._collect_frames(html, props, params))

        return results

    async def _collect_frames(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        frames: List[Dict[str, Any]] = []

        async for frame in self._stream_frames(html, props, params):
            frames.append(frame)

        return frames

    async def _stream_frames(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        filename_format = params["filename_format"]
        worker_count    = params["worker_count"]

        sessions = [ await self.session_factory() for _ in range(worker_count) ]

        try:
            orchestrator = HtmlFrameRenderOrchestrator(sessions, html, props, params)

            async for number, image, timestamp in orchestrator.render_frames():
                frame: Dict[str, Any] = {
                    "number":    number + 1,  # 1-based
                    "image":     image,
                    "timestamp": timestamp,
                }

                if filename_format is not None:
                    frame["filename"] = format_filename(filename_format, number + 1)

                yield frame
        finally:
            await asyncio.gather(
                *(session.close() for session in sessions),
                return_exceptions=True,
            )
