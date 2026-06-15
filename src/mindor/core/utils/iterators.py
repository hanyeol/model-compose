from typing import Any, List, Optional, Tuple
from collections.abc import AsyncIterator

class AsyncSourceIterator:
    """Yield items from a heterogeneous source as a unified async iterator.

    Source may be:
    - AsyncIterator: yielded as-is
    - list/tuple: iterated
    - any other value: yielded as a single item
    - tuple of sources: zipped — each tick yields a tuple of items, one per source;
      sources must produce the same number of items or ValueError is raised. To pass
      a single-source tuple/list as a sequence rather than a zip group, wrap it in
      another value type or pre-materialize it.

    When `batch_size` is provided, items are grouped into batches (lists). The final
    batch may be smaller than `batch_size`. When `batch_size` is None, items are
    yielded one at a time.
    """
    def __init__(self, source: Any, batch_size: Optional[int] = None):
        self.source: Any = source
        self.batch_size: Optional[int] = batch_size

    def __aiter__(self) -> AsyncIterator[Any]:
        if self.batch_size is not None:
            return self._iterate_batches()
        
        return self._iterate_items()

    async def _iterate_items(self) -> AsyncIterator[Any]:
        if isinstance(self.source, tuple):
            async for items in self._iterate_zipped():
                yield items
            return
        
        async for item in self._iterate_single(self.source):
            yield item

    async def _iterate_batches(self) -> AsyncIterator[List[Any]]:
        batch: List[Any] = []

        async for item in self._iterate_items():
            batch.append(item)
            if len(batch) >= self.batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def _iterate_single(self, source: Any) -> AsyncIterator[Any]:
        if isinstance(source, AsyncIterator):
            async for item in source:
                yield item
            return
        
        if isinstance(source, (list, tuple)):
            for item in source:
                yield item
            return
        
        yield source

    async def _iterate_zipped(self) -> AsyncIterator[Tuple[Any, ...]]:
        iterators = [ self._iterate_single(src).__aiter__() for src in self.source ]

        while True:
            items: List[Any] = []
            stops: List[bool] = []

            for iterator in iterators:
                try:
                    items.append(await iterator.__anext__())
                    stops.append(False)
                except StopAsyncIteration:
                    stops.append(True)

            if all(stops):
                return

            if any(stops):
                raise ValueError("zipped sources have different lengths")

            yield tuple(items)
