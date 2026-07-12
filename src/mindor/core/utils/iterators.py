from typing import Any, List, Tuple
from collections.abc import AsyncIterator, AsyncIterable
from mindor.core.foundation.streaming.iterators import StreamIterator
import codecs

class BatchSourceIterator:
    """Yield items from a heterogeneous source as batches.

    Source may be:
    - AsyncIterator: yielded as-is
    - list/tuple: iterated
    - any other value: yielded as a single item
    - tuple of sources: zipped — each tick yields a tuple of per-source batches.
      A `None` slot is broadcast (its batch stays `None` instead of being treated as
      a single-item sequence). A scalar slot (any non-iterable, non-tuple, non-None
      value that is not a list/AsyncIterator/StreamIterator) is also broadcast: its
      value is repeated for every tick until the iterable slots are exhausted. If
      all slots are scalar/None, the zip yields once. Iterable sources must produce
      the same number of items or ValueError is raised. To pass a single-source
      tuple/list as a sequence rather than a zip group, wrap it in another value
      type or pre-materialize it.

    Items are grouped into batches (lists) of `batch_size`. The final batch may be
    smaller than `batch_size`.
    """
    def __init__(self, source: Any, batch_size: int):
        self.source: Any = source
        self.batch_size: int = batch_size

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._iterate_batches(self.source, self.batch_size)

    async def _iterate_batches(self, source: Any, batch_size: int) -> AsyncIterator[Any]:
        if isinstance(source, tuple):
            active = tuple(single for single in source if single is not None)

            if active:
                batches: List[List[Any]] = [ [] for _ in active ]

                def _pack_batch() -> Tuple[Any, ...]:
                    batch_iterator = iter(batches)
                    return tuple(None if single is None else next(batch_iterator) for single in source)

                async for items in self._iterate_zipped(active):
                    for index, item in enumerate(items):
                        batches[index].append(item)

                    if len(batches[0]) >= batch_size:
                        yield _pack_batch()
                        batches = [ [] for _ in active ]

                if batches[0]:
                    yield _pack_batch()

            return

        batch: List[Any] = []

        async for item in self._iterate_items(source):
            batch.append(item)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    async def _iterate_items(self, source: Any) -> AsyncIterator[Any]:
        if isinstance(source, tuple):
            active = tuple(single for single in source if single is not None)

            if active:
                async for items in self._iterate_zipped(active):
                    item_iterator = iter(items)
                    yield tuple(None if single is None else next(item_iterator) for single in source)

            return

        async for item in self._iterate_single(source):
            yield item

    async def _iterate_zipped(self, source: Tuple[Any, ...]) -> AsyncIterator[Tuple[Any, ...]]:
        iterables = [ isinstance(value, (list, tuple, StreamIterator, AsyncIterator)) for value in source ]
        iterators = [ self._iterate_single(value).__aiter__() if iterable else None for value, iterable in zip(source, iterables) ]
        has_iterables = any(iterables)

        while True:
            items: List[Any] = []
            stops: List[bool] = []

            for index, iterator in enumerate(iterators):
                if iterator is None:
                    items.append(source[index])
                    stops.append(False)
                    continue
                try:
                    items.append(await iterator.__anext__())
                    stops.append(False)
                except StopAsyncIteration:
                    items.append(None)
                    stops.append(True)

            if has_iterables:
                iterable_stops = [ stops[i] for i, iterable in enumerate(iterables) if iterable ]
                if all(iterable_stops):
                    return
                if any(iterable_stops):
                    raise ValueError("zipped sources have different lengths")

            yield tuple(items)

            if not has_iterables:
                return

    async def _iterate_single(self, source: Any) -> AsyncIterator[Any]:
        if isinstance(source, (StreamIterator, AsyncIterator)):
            async for item in source:
                yield item
            return

        if isinstance(source, (list, tuple)):
            for item in source:
                yield item
            return

        yield source

class TextDecodeIterator:
    """Decode a stream of bytes/str chunks into str chunks, multi-byte safe.

    Uses an incremental decoder so multi-byte sequences split across chunk
    boundaries are not corrupted into U+FFFD. `str` chunks pass through
    unchanged. `None` chunks are skipped. The final decoder flush is emitted
    as a trailing chunk if non-empty.
    """
    def __init__(
        self,
        source: AsyncIterable,
        encoding: str = "utf-8",
        errors: str = "replace",
    ):
        self.source: AsyncIterable = source
        self.encoding: str = encoding
        self.errors: str = errors

    async def __aiter__(self) -> AsyncIterator[str]:
        decoder = codecs.getincrementaldecoder(self.encoding)(errors=self.errors)

        async for chunk in self.source:
            if chunk is None:
                continue
            if isinstance(chunk, str):
                yield chunk
                continue
            text = decoder.decode(chunk, final=False)
            if text:
                yield text

        text = decoder.decode(b"", final=True)
        if text:
            yield text
