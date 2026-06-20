from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional
from ..streaming.stream import StreamResource, ChunkedStreamResource, read_stream_to_buffer
import asyncio

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

_MIN_PART_SIZE = 5 * 1024 * 1024  # S3 mandates minimum part size of 5MB (except last part)
_MAX_PART_CONCURRENCY = 4  # at most this many parts in flight; memory ≈ chunk_size × this

async def upload(
    client: S3Client,
    bucket: str,
    key: str,
    stream: StreamResource,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to S3 as a single PUT request.

    Buffers the entire stream in memory; use `multipart_upload` for large or
    unknown-size payloads. Returns the total number of bytes uploaded.
    """
    data = (await read_stream_to_buffer(stream)).getvalue()

    put_params: Dict[str, Any] = { "Bucket": bucket, "Key": key, "Body": data }
    if content_type:
        put_params["ContentType"] = content_type
    if metadata:
        put_params["Metadata"] = { k: str(v) for k, v in metadata.items() }

    await client.put_object(**put_params)

    return len(data)

async def multipart_upload(
    client: S3Client,
    bucket: str,
    key: str,
    stream: StreamResource,
    chunk_size: int,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to S3 via the multipart API.

    Streams chunks through `create_multipart_upload` → `upload_part` × N →
    `complete_multipart_upload`. On any failure the upload is aborted to avoid
    leaving orphaned parts behind.

    `chunk_size` is clamped to the S3 minimum part size (5MB); the last part
    may be smaller. Returns the total number of bytes uploaded.
    """
    chunk_size = max(chunk_size, _MIN_PART_SIZE)

    create_params: Dict[str, Any] = { "Bucket": bucket, "Key": key }
    if content_type:
        create_params["ContentType"] = content_type
    if metadata:
        create_params["Metadata"] = { k: str(v) for k, v in metadata.items() }

    response = await client.create_multipart_upload(**create_params)
    upload_id = response["UploadId"]
    semaphore = asyncio.Semaphore(_MAX_PART_CONCURRENCY)
    tasks: List[asyncio.Task] = []
    uploaded_size = 0

    async def _send_part(part_number: int, chunk: bytes) -> Dict[str, Any]:
        try:
            response = await client.upload_part(
                Bucket=bucket,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=chunk,
            )
            return { "PartNumber": part_number, "ETag": response["ETag"] }
        finally:
            semaphore.release()

    try:
        part_number = 1
        async with ChunkedStreamResource(stream, chunk_size) as chunked:
            async for chunk in chunked:
                # block until a concurrency slot is free, so unread chunks
                # don't pile up in memory beyond the configured ceiling
                await semaphore.acquire()
                tasks.append(asyncio.create_task(_send_part(part_number, chunk)))
                uploaded_size += len(chunk)
                part_number += 1

        # S3 requires at least one part even for an empty object
        if not tasks:
            await semaphore.acquire()
            tasks.append(asyncio.create_task(_send_part(part_number, b"")))

        parts = await asyncio.gather(*tasks)
        parts.sort(key=lambda p: p["PartNumber"])

        await client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={ "Parts": parts },
        )
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        try:
            await client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
        except Exception:
            pass
        raise

    return uploaded_size
