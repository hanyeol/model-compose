from typing import Union, Literal, Optional, Callable, Awaitable, Any
from collections.abc import AsyncIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
import asyncio

StreamTerminatedEvent = Literal[ "completed", "cancelled", "failed" ]
StreamTerminatedCallback = Callable[[StreamTerminatedEvent, Optional[str]], Awaitable[None]]

class JobOutputStreamIterator(StreamIterator):
    def __init__(self, source: Union[StreamIterator, AsyncIterator], on_terminated: StreamTerminatedCallback):
        self.source: Union[StreamIterator, AsyncIterator] = source
        self.on_terminated: StreamTerminatedCallback = on_terminated

        self._notified_terminated: bool = False

    async def _iterate_stream(self) -> AsyncIterator[Any]:
        try:
            async for chunk in self.source:
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
            if not self._notified_terminated:
                await self._notify_terminated("cancelled", "consumer closed stream")

    async def aclose(self) -> None:
        aclose = getattr(self.source, "aclose", None)

        if aclose is not None:
            try:
                await aclose()
            except Exception:
                pass

        if not self._notified_terminated:
            await self._notify_terminated("cancelled", "consumer closed stream")

    async def _notify_terminated(self, event: StreamTerminatedEvent, error: Optional[str]) -> None:
        self._notified_terminated = True
        await self.on_terminated(event, error)
