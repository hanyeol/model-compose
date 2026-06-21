from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, List, Tuple, Union, Optional
from io import BytesIO
from starlette.datastructures import UploadFile, Headers
from PIL.Image import Image as PILImage
from mindor.core.logger import logging
from mindor.core.utils.streaming.resources import StreamResource
from .errors import BlobNotFoundError, BlobCorruptedError, BlobTooLargeError
import ulid

if TYPE_CHECKING:
    from redis.asyncio import Redis

async def serialize_input(
    input: Any,
    client: Redis,
    key_prefix: str,
    ttl_seconds: int,
    max_blob_size: Optional[int],
) -> Tuple[Any, List[str]]:
    blob_keys: List[str] = []

    async def _store(payload: bytes, filename: Optional[str], content_type: Optional[str], origin_type: str) -> dict:
        if max_blob_size is not None and len(payload) > max_blob_size:
            raise BlobTooLargeError(f"payload size {len(payload)} exceeds max_blob_size {max_blob_size}")

        key = f"{key_prefix}{ulid.ulid()}"
        await client.setex(key, ttl_seconds, payload)
        blob_keys.append(key)

        return {
            "key": key,
            "filename": filename or "blob",
            "content_type": content_type or "application/octet-stream",
            "origin_type": origin_type,
            "size": len(payload),
        }

    async def _walk(element: Any) -> Any:
        if isinstance(element, UploadFile):
            data = await element.read()
            try:
                await element.seek(0)
            except Exception:
                pass
            return await _store(data, element.filename, element.content_type, "upload_file")

        if isinstance(element, (bytes, bytearray)):
            return await _store(bytes(element), None, None, "bytes")

        if isinstance(element, StreamResource):
            chunks: List[bytes] = []
            async for chunk in element:
                chunks.append(chunk)
            return await _store(b"".join(chunks), element.filename, element.content_type, "stream_resource")

        if isinstance(element, PILImage):
            buffer = BytesIO()
            element.save(buffer, format="PNG")
            return await _store(buffer.getvalue(), "image.png", "image/png", "pil_image")

        if isinstance(element, dict):
            return { key: await _walk(value) for key, value in element.items() }

        if isinstance(element, (list, tuple)):
            return [ await _walk(item) for item in element ]

        return element

    try:
        serialized = await _walk(input)
    except BaseException:
        if blob_keys:
            try:
                await client.delete(*blob_keys)
            except BaseException as e:
                logging.warning("Failed to cleanup blob keys (%d keys): %s", len(blob_keys), e)
        raise

    return serialized, blob_keys

async def deserialize_input(
    input: Any,
    client: Redis,
    key_prefix: str,
) -> Any:
    async def _walk(element: Any) -> Any:
        if isinstance(element, dict):
            key = element.get("key")
            if isinstance(key, str) and key.startswith(key_prefix):
                return await _restore_blob(client, element)
            return { key: await _walk(value) for key, value in element.items() }

        if isinstance(element, (list, tuple)):
            return [ await _walk(item) for item in element ]

        return element

    return await _walk(input)

async def _restore_blob(client: Redis, ref: dict) -> UploadFile:
    data = await _consume_blob(client, ref["key"])

    if data is None:
        raise BlobNotFoundError(f"blob missing or expired: key={ref['key']}")

    if len(data) != ref["size"]:
        raise BlobCorruptedError(f"size mismatch: expected {ref['size']}, got {len(data)} (key={ref['key']})")

    return UploadFile(
        file=BytesIO(data),
        filename=ref["filename"],
        headers=Headers({"content-type": ref["content_type"]}),
    )

async def _consume_blob(client: Redis, key: Union[bytes, str]) -> Optional[bytes]:
    async with client.pipeline(transaction=True) as pipeline:
        pipeline.get(key)
        pipeline.delete(key)
        data, _ = await pipeline.execute()
    return data
