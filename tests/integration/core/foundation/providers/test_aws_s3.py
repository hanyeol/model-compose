"""Tests for `core/foundation/providers/aws_s3.py` against an in-process moto server."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import List

import pytest

pytest.importorskip("moto")
pytest.importorskip("aioboto3")

from mindor.core.foundation.providers.aws_s3 import upload, multipart_upload, _MIN_PART_SIZE
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource


BUCKET = "test-bucket"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def s3_client(s3_client_factory):
    async with s3_client_factory() as client:
        await client.create_bucket(Bucket=BUCKET)
        try:
            yield client
        finally:
            try:
                response = await client.list_objects_v2(Bucket=BUCKET)
                for obj in response.get("Contents", []) or []:
                    await client.delete_object(Bucket=BUCKET, Key=obj["Key"])
                await client.delete_bucket(Bucket=BUCKET)
            except Exception:
                pass


async def _get_object_bytes(client, key: str) -> bytes:
    response = await client.get_object(Bucket=BUCKET, Key=key)
    async with response["Body"] as body:
        return await body.read()


class GeneratedStream(StreamResource):
    """Stream that yields a fixed sequence of chunks without buffering them all in memory."""
    def __init__(self, chunks: List[bytes]):
        super().__init__(None, None)
        self._chunks = chunks
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class FailingStream(StreamResource):
    """Stream that yields a few chunks then raises."""
    def __init__(self, good_chunks: List[bytes], error: Exception):
        super().__init__(None, None)
        self._good_chunks = good_chunks
        self._error = error

    async def close(self) -> None:
        pass

    async def _iterate_stream(self) -> AsyncIterator[bytes]:
        for chunk in self._good_chunks:
            yield chunk
        raise self._error


# ─────────────────────────────────────────────
# upload (single PUT)
# ─────────────────────────────────────────────


class TestUpload:
    @pytest.mark.anyio
    async def test_basic(self, s3_client):
        total = await upload(s3_client, BUCKET, "k", BytesStreamResource(b"hello"))
        assert total == 5
        assert await _get_object_bytes(s3_client, "k") == b"hello"

    @pytest.mark.anyio
    async def test_empty(self, s3_client):
        total = await upload(s3_client, BUCKET, "empty", BytesStreamResource(b""))
        assert total == 0
        assert await _get_object_bytes(s3_client, "empty") == b""

    @pytest.mark.anyio
    async def test_content_type(self, s3_client):
        await upload(s3_client, BUCKET, "k.png", BytesStreamResource(b"x"), content_type="image/png")
        head = await s3_client.head_object(Bucket=BUCKET, Key="k.png")
        assert head["ContentType"] == "image/png"

    @pytest.mark.anyio
    async def test_metadata(self, s3_client):
        await upload(s3_client, BUCKET, "k", BytesStreamResource(b"x"), metadata={"workflow": "abc"})
        head = await s3_client.head_object(Bucket=BUCKET, Key="k")
        assert head["Metadata"]["workflow"] == "abc"

    @pytest.mark.anyio
    async def test_metadata_coerces_to_str(self, s3_client):
        await upload(s3_client, BUCKET, "k", BytesStreamResource(b"x"), metadata={"count": 42})
        head = await s3_client.head_object(Bucket=BUCKET, Key="k")
        assert head["Metadata"]["count"] == "42"

    @pytest.mark.anyio
    async def test_closes_stream(self, s3_client):
        stream = GeneratedStream([b"abc", b"def"])
        await upload(s3_client, BUCKET, "k", stream)
        assert stream.closed is True


# ─────────────────────────────────────────────
# multipart_upload
# ─────────────────────────────────────────────


class TestMultipartUpload:
    @pytest.mark.anyio
    async def test_basic_single_part(self, s3_client):
        """Stream smaller than chunk size: emitted as one final part."""
        chunks = [b"abc", b"def", b"ghij"]
        total = await multipart_upload(s3_client, BUCKET, "k", GeneratedStream(chunks), chunk_size=_MIN_PART_SIZE)
        assert total == 10
        assert await _get_object_bytes(s3_client, "k") == b"abcdefghij"

    @pytest.mark.anyio
    async def test_multiple_parts(self, s3_client):
        """Stream large enough to force several parts."""
        part_payload = b"a" * _MIN_PART_SIZE
        chunks = [part_payload, part_payload, b"tail"]
        total = await multipart_upload(s3_client, BUCKET, "k", GeneratedStream(chunks), chunk_size=_MIN_PART_SIZE)
        assert total == 2 * _MIN_PART_SIZE + 4

        body = await _get_object_bytes(s3_client, "k")
        assert body == part_payload + part_payload + b"tail"

    @pytest.mark.anyio
    async def test_empty_stream_uploads_empty_object(self, s3_client):
        """S3 multipart needs at least one part; empty stream → one empty part."""
        total = await multipart_upload(s3_client, BUCKET, "empty", GeneratedStream([]), chunk_size=_MIN_PART_SIZE)
        assert total == 0
        assert await _get_object_bytes(s3_client, "empty") == b""

    @pytest.mark.anyio
    async def test_chunk_size_clamped_to_minimum(self, s3_client):
        """Tiny chunk_size is clamped up to _MIN_PART_SIZE, so a >5MB stream still produces 1 part."""
        payload = b"x" * (_MIN_PART_SIZE + 1024)
        total = await multipart_upload(
            s3_client, BUCKET, "k", GeneratedStream([payload]), chunk_size=1024,
        )
        assert total == len(payload)
        assert await _get_object_bytes(s3_client, "k") == payload

    @pytest.mark.anyio
    async def test_content_type_and_metadata(self, s3_client):
        await multipart_upload(
            s3_client, BUCKET, "k.bin",
            BytesStreamResource(b"x"),
            chunk_size=_MIN_PART_SIZE,
            content_type="application/octet-stream",
            metadata={"workflow": "abc"},
        )
        head = await s3_client.head_object(Bucket=BUCKET, Key="k.bin")
        assert head["ContentType"] == "application/octet-stream"
        assert head["Metadata"]["workflow"] == "abc"

    @pytest.mark.anyio
    async def test_part_order_preserved_under_concurrency(self, s3_client):
        """Many parts uploaded in parallel must still reassemble in the right order."""
        # 10 parts × 5MB each. Identifiable per-part payload so any reordering shows up in the body.
        markers = [bytes([i]) * _MIN_PART_SIZE for i in range(10)]
        expected = b"".join(markers)
        total = await multipart_upload(
            s3_client, BUCKET, "k", GeneratedStream(markers), chunk_size=_MIN_PART_SIZE,
        )
        assert total == len(expected)
        assert await _get_object_bytes(s3_client, "k") == expected

    @pytest.mark.anyio
    async def test_failure_aborts_upload(self, s3_client):
        """When the source stream raises, the multipart upload is aborted (no orphan parts)."""
        stream = FailingStream(
            good_chunks=[b"a" * _MIN_PART_SIZE],
            error=RuntimeError("boom"),
        )
        with pytest.raises(RuntimeError, match="boom"):
            await multipart_upload(s3_client, BUCKET, "doomed", stream, chunk_size=_MIN_PART_SIZE)

        # the object must not exist
        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            await s3_client.head_object(Bucket=BUCKET, Key="doomed")

        # and there should be no in-progress multipart uploads left dangling
        listing = await s3_client.list_multipart_uploads(Bucket=BUCKET)
        assert not listing.get("Uploads"), f"orphan multipart uploads left: {listing.get('Uploads')}"

    @pytest.mark.anyio
    async def test_closes_stream(self, s3_client):
        stream = GeneratedStream([b"abc", b"def"])
        await multipart_upload(s3_client, BUCKET, "k", stream, chunk_size=_MIN_PART_SIZE)
        assert stream.closed is True
