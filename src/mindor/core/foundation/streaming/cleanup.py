from typing import Any
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.logger import logging

async def cleanup_dangling_streams(value: Any) -> None:
    # Walks arbitrarily nested dict/list/tuple structures and closes any
    # StreamIterator or StreamResource it finds. Safe to call on values that
    # a consumer already drained: wrappers guard against double-notify so a
    # second close is a no-op.
    if isinstance(value, StreamIterator):
        try:
            await value.aclose()
        except Exception:
            logging.warning("Failed to close stream iterator", exc_info=True)
        return

    if isinstance(value, StreamResource):
        try:
            await value.close()
        except Exception:
            logging.warning("Failed to close stream resource", exc_info=True)
        return

    if isinstance(value, dict):
        for item in value.values():
            await cleanup_dangling_streams(item)
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            await cleanup_dangling_streams(item)
