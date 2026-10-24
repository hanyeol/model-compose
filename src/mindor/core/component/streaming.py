from typing import Union, Literal, Optional, Callable, Awaitable, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator, StreamEncodingIterator
from mindor.core.logger import logging
import asyncio

StreamTerminatedEvent = Literal[ "completed", "cancelled", "failed" ]
StreamTerminatedCallback = Callable[[StreamTerminatedEvent, Optional[str]], Awaitable[None]]

class ComponentOutputStreamIterator(StreamChunkIterator):
    """StreamChunkIterator wrapper that fires a callback on stream termination.

    Mirrors `JobOutputStreamIterator` at the component layer: when a component
    returns an iterator, the "completed" event must not fire at the moment
    the iterator is handed back — it should fire only once the consumer has
    drained the stream, so downstream observers see accurate timing.
    """
    def __init__(self, source: Union[StreamIterator, AsyncIterator], on_terminated: StreamTerminatedCallback):
        super().__init__(source, is_fragmented=source.is_fragmented if isinstance(source, StreamChunkIterator) else False)

        self.on_terminated: StreamTerminatedCallback = on_terminated

        self._notified_terminated: bool = False

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        iterator = self.source.__aiter__()

        try:
            async for chunk in iterator:
                yield chunk
        except asyncio.CancelledError:
            await self._notify_terminated("cancelled", None)
            raise
        except Exception as e:
            await self._notify_terminated("failed", str(e))
            raise
        else:
            await self._notify_terminated("completed", None)
        finally:
            await self._close_stream(iterator)

            if not self._notified_terminated:
                await self._notify_terminated("cancelled", "consumer closed stream")

    async def aclose(self) -> None:
        closer = getattr(self.source, "aclose", None)

        if closer is not None:
            try:
                await closer()
            except Exception:
                pass

        if not self._notified_terminated:
            await self._notify_terminated("cancelled", "consumer closed stream")

    async def _notify_terminated(self, event: StreamTerminatedEvent, error: Optional[str]) -> None:
        self._notified_terminated = True

        try:
            await self.on_terminated(event, error)
        except Exception:
            logging.warning("Streaming component lifecycle callback failed", exc_info=True)

class ComponentOutputStreamEncodingIterator(ComponentOutputStreamIterator):
    def __init__(self, source: StreamEncodingIterator, on_terminated: StreamTerminatedCallback):
        super().__init__(source, on_terminated)

        self.format = source.format
