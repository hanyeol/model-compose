from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, AsyncIterator
from PIL import Image as PILImage

from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.utils.url import UrlResource
from ....action.base import ComponentAction
from ..base import ComponentActionContext

HtmlResolver = Callable[[str], Awaitable[UrlResource]]

class HtmlFrameRendererSession(ABC):
    """Driver-abstract browser page for rendering HTML into a stream of frames.

    Owns one browser page for the duration of a single render call. Drivers
    implement `render_frames` to drive their engine (Playwright, CDP, ...).
    """
    @abstractmethod
    async def render_frames(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> AsyncIterator[Tuple[PILImage.Image, float]]:
        """Yield (image, timestamp) per frame.

        `html` is owned by the component and reused across sessions — do not
        close it here. `params` carries the shared render options resolved by
        `HtmlFrameRendererAction` (`fps`, `width`, `height`, `ready_timeout`).
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        pass

class HtmlFrameRendererAction(ComponentAction):
    def __init__(self, config: HtmlFrameRendererActionConfig, html_resolver: HtmlResolver):
        self.config: HtmlFrameRendererActionConfig = config
        self.html_resolver: HtmlResolver = html_resolver

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
        fps             = float(await context.render_variable(self.config.fps))
        width           = int(await context.render_variable(self.config.width))
        height          = int(await context.render_variable(self.config.height))
        ready_timeout   = parse_duration(await context.render_variable(self.config.ready_timeout))
        filename_format = await context.render_variable(self.config.filename_format) if self.config.filename_format is not None else None

        if fps <= 0:
            raise ValueError(f"'fps' must be > 0, got {fps}")

        if width <= 0 or height <= 0:
            raise ValueError(f"'width' and 'height' must be > 0, got {width}x{height}")

        return {
            "fps":             fps,
            "width":           width,
            "height":          height,
            "ready_timeout":   ready_timeout,
            "filename_format": filename_format,
        }

    @abstractmethod
    async def _render_batch(
        self,
        htmls: List[UrlResource],
        props: Optional[List[Optional[Dict[str, Any]]]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        pass
