from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MediaDownloaderActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

DownloadResult = Union[AudioStreamResource, VideoStreamResource, ImageStreamResource]

class MediaDownloaderAction(ComponentAction):
    """Base for media-downloader driver actions.

    Follows the same shape as `VideoFrameExtractorAction`:
      - `run` renders the URL(s), dispatches through `BatchSourceIterator`
        so a list of URLs downloads concurrently in batches, and yields
        results as they finish for streaming inputs.
      - `_resolve_params` renders driver-specific fields into a dict;
        driver subclasses override to add their own.
      - Drivers implement `_download_batch` for one batch of URLs and
        return one stream resource per URL.
    """
    def __init__(self, config: MediaDownloaderActionConfig, context: ComponentActionContext):
        self.config: MediaDownloaderActionConfig = config
        self.context: ComponentActionContext = context

    async def run(self) -> Any:
        url        = await self.context.render_variable(self.config.url)
        batch_size = await self.context.render_variable(self.config.batch_size)

        params = await self._resolve_params()

        is_single_input  = not isinstance(url, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(url, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_urls in BatchSourceIterator(url, batch_size=batch_size or 1):
                    batch_results = await self._download_batch(batch_urls, params, self.context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[DownloadResult] = []
            async for batch_urls in BatchSourceIterator(url, batch_size=batch_size or 1):
                batch_results = await self._download_batch(batch_urls, params, self.context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            self.context.register_source("result", result)

            return (await self.context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _download_batch(
        self,
        urls: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[DownloadResult]:
        """Download one batch of URLs and return one stream per URL.

        Drivers own storage decisions — a file-based backend spools each
        result to a temp file wrapped in `FileStreamResource(auto_delete=True)`,
        while a streaming backend may return in-memory streams directly.
        Returned resources are consumed once by the caller and clean
        themselves up on close.
        """
        pass
