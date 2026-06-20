from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Any, Dict, List, Optional
from ..streaming.stream import StreamResource, ChunkedStreamResource, read_stream_to_buffer
import json

if TYPE_CHECKING:
    from gcloud.aio.storage import Storage

_CHUNK_ALIGNMENT = 256 * 1024  # GCS resumable uploads require chunk size to be a multiple of 256 KiB
_MIN_CHUNK_SIZE = 256 * 1024

async def upload(
    client: Storage,
    bucket: str,
    key: str,
    stream: StreamResource,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to GCS as a single multipart-or-simple request.

    Buffers the entire stream in memory; use `multipart_upload` for large or
    unknown-size payloads. Returns the total number of bytes uploaded.
    """
    data = (await read_stream_to_buffer(stream)).getvalue()

    metadata_payload: Optional[Dict[str, Any]] = None
    if metadata:
        metadata_payload = { "metadata": { k: str(v) for k, v in metadata.items() } }

    await client.upload(
        bucket=bucket,
        object_name=key,
        file_data=data,
        content_type=content_type or "application/octet-stream",
        metadata=metadata_payload,
        force_resumable_upload=False,
    )

    return len(data)

async def multipart_upload(
    client: Storage,
    bucket: str,
    key: str,
    stream: StreamResource,
    chunk_size: int,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> int:
    """Upload an async byte stream to GCS via the resumable upload protocol.

    Streams chunks of `chunk_size` bytes to a resumable session created via
    `client.session`. On any failure the partial upload is abandoned (GCS
    garbage-collects incomplete resumable sessions after one week).

    `chunk_size` is clamped to a 256 KiB multiple as required by the resumable
    API; the last chunk may be smaller. Returns the total number of bytes
    uploaded.
    """
    chunk_size = max((chunk_size // _CHUNK_ALIGNMENT) * _CHUNK_ALIGNMENT, _MIN_CHUNK_SIZE)
    resolved_content_type = content_type or "application/octet-stream"

    # `_headers()` returns the auth header in prod and an empty dict in dev/emulator mode.
    auth_headers = await client._headers()
    session = client.session
    # `_api_root_write` is the upload endpoint the library itself uses; it tracks
    # the `api_root=` constructor arg and the `STORAGE_EMULATOR_HOST` env var, so
    # reading it here keeps us aligned with whatever endpoint the client targets.
    upload_url = f"{client._api_root_write}/{bucket}/o?uploadType=resumable&name={key}"

    init_headers: Dict[str, str] = {
        **auth_headers,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": resolved_content_type,
    }
    init_body: Dict[str, Any] = { "name": key, "contentType": resolved_content_type }
    if metadata:
        init_body["metadata"] = { k: str(v) for k, v in metadata.items() }

    init_response = await session.post(upload_url, headers=init_headers, data=json.dumps(init_body))
    init_response.raise_for_status()
    session_url = init_response.headers["Location"]

    uploaded_size = 0
    pending_chunk: Optional[bytes] = None

    try:
        async with ChunkedStreamResource(stream, chunk_size) as chunked:
            async for chunk in chunked:
                if pending_chunk is not None:
                    start = uploaded_size
                    end = uploaded_size + len(pending_chunk) - 1
                    headers = {
                        "Content-Length": str(len(pending_chunk)),
                        "Content-Range": f"bytes {start}-{end}/*",
                    }
                    response = await session.put(session_url, headers=headers, data=pending_chunk)
                    if response.status not in (200, 201, 308):
                        response.raise_for_status()
                    uploaded_size += len(pending_chunk)
                pending_chunk = chunk

        # Final chunk (or empty upload): include the known total size to finalize.
        final_chunk = pending_chunk if pending_chunk is not None else b""
        final_size = uploaded_size + len(final_chunk)

        if final_chunk:
            content_range = f"bytes {uploaded_size}-{final_size - 1}/{final_size}"
        else:
            content_range = "bytes */0"

        headers = {
            "Content-Length": str(len(final_chunk)),
            "Content-Range": content_range,
        }
        response = await session.put(session_url, headers=headers, data=final_chunk)
        if response.status not in (200, 201):
            response.raise_for_status()

        uploaded_size = final_size
    except BaseException:
        try:
            await session.delete(session_url, headers={ "Content-Length": "0" })
        except Exception:
            pass
        raise

    return uploaded_size
