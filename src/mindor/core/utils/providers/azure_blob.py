from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional
from ..streaming.stream import StreamResource, ChunkedStreamResource, read_stream_to_buffer
import asyncio, uuid, base64

if TYPE_CHECKING:
    from azure.storage.blob.aio import BlobClient

_MIN_BLOCK_SIZE = 4 * 1024 * 1024  # 4MB — Azure permits smaller blocks but this aligns with typical defaults
_MAX_BLOCK_CONCURRENCY = 4  # at most this many blocks in flight; memory ≈ chunk_size × this

async def upload(
    client: BlobClient,
    stream: StreamResource,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to Azure Blob as a single PUT request.

    Buffers the entire stream in memory; use `multipart_upload` for large or
    unknown-size payloads. Returns the total number of bytes uploaded.
    """
    from azure.storage.blob import ContentSettings

    data = (await read_stream_to_buffer(stream)).getvalue()

    upload_params: Dict[str, Any] = { "data": data, "overwrite": True }
    if content_type:
        upload_params["content_settings"] = ContentSettings(content_type=content_type)
    if metadata:
        upload_params["metadata"] = { k: str(v) for k, v in metadata.items() }

    await client.upload_blob(**upload_params)

    return len(data)

async def multipart_upload(
    client: BlobClient,
    stream: StreamResource,
    chunk_size: int,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to Azure Blob via the block list API.

    Streams chunks through `stage_block` × N → `commit_block_list`. On any
    failure staged blocks are abandoned (Azure garbage-collects uncommitted
    blocks after 7 days).

    `chunk_size` is clamped to `_MIN_BLOCK_SIZE`; the last block may be smaller.
    Returns the total number of bytes uploaded.
    """
    from azure.storage.blob import ContentSettings

    chunk_size = max(chunk_size, _MIN_BLOCK_SIZE)
    semaphore = asyncio.Semaphore(_MAX_BLOCK_CONCURRENCY)
    tasks: List[asyncio.Task] = []
    block_ids: List[str] = []
    uploaded_size = 0

    async def _stage_block(block_id: str, chunk: bytes) -> None:
        try:
            await client.stage_block(block_id=block_id, data=chunk)
        finally:
            semaphore.release()

    try:
        async with ChunkedStreamResource(stream, chunk_size) as chunked:
            async for chunk in chunked:
                # Azure requires block IDs to be the same length when base64-encoded
                block_id = base64.b64encode(uuid.uuid4().bytes).decode("ascii")
                block_ids.append(block_id)
                # block until a concurrency slot is free, so unread chunks
                # don't pile up in memory beyond the configured ceiling
                await semaphore.acquire()
                tasks.append(asyncio.create_task(_stage_block(block_id, chunk)))
                uploaded_size += len(chunk)

        # Azure permits an empty block list, producing an empty blob
        if tasks:
            await asyncio.gather(*tasks)

        commit_params: Dict[str, Any] = { "block_list": block_ids }
        if content_type:
            commit_params["content_settings"] = ContentSettings(content_type=content_type)
        if metadata:
            commit_params["metadata"] = { k: str(v) for k, v in metadata.items() }

        await client.commit_block_list(**commit_params)
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        raise

    return uploaded_size
