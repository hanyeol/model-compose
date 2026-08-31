"""Unit tests for `QueueCodec` — Redis-backed value-tree encoder/decoder for the
queue-subscribe adapter.

Covers the `queue.v2` wire contract defined in
`docs/specs/queue-subscribe-codec-spec.md`:

- Round-trip of JSON-native scalars, containers, `BaseModel`, `AtomicDict`/`AtomicList`.
- `bytes` inline (≤ `inline_bytes_threshold`) vs. blob offload (> threshold) via
  `__variable__` markers, including `SETEX`/`GETDEL` interaction with a fake Redis.
- `bytes` payload > `max_blob_size` raising `BlobTooLargeError` with partial blob
  cleanup.
- Stream markers for `PIL.Image`, `UploadFile`, `StreamResource` subclasses —
  `attrs` and `content_type` preservation.
- Key-ownership boundary: user dicts with an unrelated `"key"` field are not
  misinterpreted as blob references.
- Nested containers walk recursively without loss.

Implementation is not yet in place; module-level import is guarded so the whole
file skips cleanly when the target symbols do not exist.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from pydantic import BaseModel
from PIL import Image as PILImage
from starlette.datastructures import UploadFile

from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.audio import PcmStreamResource

pytest.importorskip("mindor.core.controller.queue.codec")

from mindor.core.controller.queue.codec import QueueCodec  # noqa: E402
from mindor.core.controller.queue.errors import (  # noqa: E402
    BlobNotFoundError,
    BlobTooLargeError,
)


# ============================================================================
# Fixtures & fakes
# ============================================================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRedis:
    """Minimal `redis.asyncio.Redis` stand-in for codec-level tests.

    Only implements the surface QueueCodec touches: `setex`, `get`, `delete`,
    `execute_command("GETDEL", key)`, and a transaction pipeline for the
    GETDEL fallback path. Payloads are stored as raw bytes.
    """

    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.getdel_supported: bool = True

    async def setex(self, key: str, ttl: int, value: bytes) -> None:
        self.store[key] = value
        self.ttls[key] = ttl

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if self.store.pop(k, None) is not None:
                removed += 1
            self.ttls.pop(k, None)
        return removed

    async def execute_command(self, cmd: str, key: str):
        if cmd != "GETDEL":
            raise RuntimeError(f"unexpected command {cmd}")
        if not self.getdel_supported:
            from redis.exceptions import ResponseError
            raise ResponseError("unknown command 'GETDEL'")
        value = self.store.pop(key, None)
        self.ttls.pop(key, None)
        return value

    def pipeline(self, transaction: bool = True):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client: FakeRedis):
        self.client = client
        self.ops: list[tuple[str, str]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def get(self, key: str) -> None:
        self.ops.append(("get", key))

    def delete(self, key: str) -> None:
        self.ops.append(("delete", key))

    async def execute(self):
        results = []
        for op, key in self.ops:
            if op == "get":
                results.append(self.client.store.get(key))
            elif op == "delete":
                self.client.store.pop(key, None)
                self.client.ttls.pop(key, None)
                results.append(1)
        return results


def make_codec(
    client: FakeRedis,
    *,
    inline_bytes_threshold: int = 64,
    max_blob_size: int | None = 10 * 1024 * 1024,
    blob_ttl: int = 60,
    result_ttl: int = 60,
) -> QueueCodec:
    return QueueCodec(
        client=client,
        blob_prefix="q:wf:run:blob:",
        stream_prefix="q:wf:run:outstream:",
        blob_ttl=blob_ttl,
        result_ttl=result_ttl,
        inline_bytes_threshold=inline_bytes_threshold,
        max_blob_size=max_blob_size,
    )


def marker(node: Any) -> dict | None:
    """Extract the `__variable__` marker dict from an encoded node, or None."""
    if isinstance(node, dict) and "__variable__" in node:
        return node["__variable__"]
    return None


# ============================================================================
# JSON-native passthrough
# ============================================================================

class TestPassthrough:

    @pytest.mark.anyio
    async def test_scalars_pass_through(self):
        codec = make_codec(FakeRedis())
        encoded, blobs, streams = await codec.encode_input(
            {"n": 1, "f": 3.14, "b": True, "s": "hi", "z": None}
        )
        assert blobs == []
        assert streams == {}
        assert encoded == {"n": 1, "f": 3.14, "b": True, "s": "hi", "z": None}

    @pytest.mark.anyio
    async def test_scalars_roundtrip(self):
        client = FakeRedis()
        codec = make_codec(client)
        value = {"n": 1, "f": 3.14, "b": True, "s": "hi", "z": None}
        encoded, _, streams = await codec.encode_input(value)
        decoded = await codec.decode_input(encoded, streams)
        assert decoded == value

    @pytest.mark.anyio
    async def test_nested_containers(self):
        codec = make_codec(FakeRedis())
        value = {"outer": [{"inner": [1, 2, {"x": "y"}]}, [3, 4]]}
        encoded, _, streams = await codec.encode_input(value)
        decoded = await codec.decode_input(encoded, streams)
        assert decoded == value

    @pytest.mark.anyio
    async def test_tuple_normalized_to_list(self):
        codec = make_codec(FakeRedis())
        encoded, _, streams = await codec.encode_input((1, "a", 3.14))
        decoded = await codec.decode_input(encoded, streams)
        assert decoded == [1, "a", 3.14]


# ============================================================================
# bytes: inline vs blob offload
# ============================================================================

class TestBytesInline:

    @pytest.mark.anyio
    async def test_small_bytes_inline_marker(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=64)

        encoded, blobs, _ = await codec.encode_input({"data": b"hello"})

        assert blobs == []  # no Redis touch for inline
        assert client.store == {}
        node = marker(encoded["data"])
        assert node is not None
        assert node["type"] == "bytes"
        assert "value" in node
        assert "key" not in node

    @pytest.mark.anyio
    async def test_small_bytes_roundtrip(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=64)
        encoded, _, streams = await codec.encode_input({"data": b"hello"})
        decoded = await codec.decode_input(encoded, streams)
        assert decoded == {"data": b"hello"}

    @pytest.mark.anyio
    async def test_bytearray_encoded_as_bytes(self):
        client = FakeRedis()
        codec = make_codec(client)
        encoded, _, streams = await codec.encode_input({"data": bytearray(b"abc")})
        decoded = await codec.decode_input(encoded, streams)
        assert decoded["data"] == b"abc"
        assert isinstance(decoded["data"], bytes)


class TestBytesOffload:

    @pytest.mark.anyio
    async def test_large_bytes_offloaded_to_blob(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8, blob_ttl=90)

        payload = b"X" * 100
        encoded, blobs, _ = await codec.encode_input({"data": payload})

        assert len(blobs) == 1
        assert blobs[0].startswith("q:wf:run:blob:")
        assert client.store[blobs[0]] == payload
        assert client.ttls[blobs[0]] == 90

        node = marker(encoded["data"])
        assert node is not None
        assert node["type"] == "bytes"
        assert node["key"] == blobs[0]
        assert node["size"] == 100
        assert "value" not in node

    @pytest.mark.anyio
    async def test_large_bytes_roundtrip_consumes_blob(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8)

        payload = b"X" * 100
        encoded, _, streams = await codec.encode_input({"data": payload})
        decoded = await codec.decode_input(encoded, streams)

        assert decoded == {"data": payload}
        assert client.store == {}  # GETDEL consumed the blob

    @pytest.mark.anyio
    async def test_missing_blob_raises(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8)

        # forge a marker whose blob has expired
        marker_node = {
            "__variable__": {
                "type": "bytes",
                "key": "q:wf:run:blob:missing",
                "size": 5,
            }
        }
        with pytest.raises(BlobNotFoundError):
            await codec.decode_input({"data": marker_node}, {})

    @pytest.mark.anyio
    async def test_getdel_unsupported_falls_back(self):
        client = FakeRedis()
        client.getdel_supported = False
        codec = make_codec(client, inline_bytes_threshold=8)

        encoded, _, streams = await codec.encode_input({"data": b"X" * 100})
        decoded = await codec.decode_input(encoded, streams)
        assert decoded["data"] == b"X" * 100
        assert client.store == {}


class TestBytesLimits:

    @pytest.mark.anyio
    async def test_payload_over_max_blob_size_raises(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8, max_blob_size=50)

        with pytest.raises(BlobTooLargeError):
            await codec.encode_input({"data": b"X" * 100})
        # nothing partially persisted
        assert client.store == {}

    @pytest.mark.anyio
    async def test_partial_success_cleaned_up_on_failure(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8, max_blob_size=50)

        with pytest.raises(BlobTooLargeError):
            await codec.encode_input({"ok": b"X" * 20, "fail": b"X" * 100})
        assert client.store == {}

    @pytest.mark.anyio
    async def test_max_blob_size_none_disables_check(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8, max_blob_size=None)

        big = b"X" * (256 * 1024)
        encoded, blobs, _ = await codec.encode_input({"data": big})
        assert len(blobs) == 1
        assert client.store[blobs[0]] == big


# ============================================================================
# Stream markers: PIL.Image, UploadFile, StreamResource subclasses
# ============================================================================

class TestStreamMarkers:

    @pytest.mark.anyio
    async def test_pil_image_becomes_stream_marker(self):
        codec = make_codec(FakeRedis())
        img = PILImage.new("RGB", (2, 2), color=(255, 0, 0))

        encoded, _, streams = await codec.encode_input({"img": img})

        node = marker(encoded["img"])
        assert node is not None
        assert node["type"] == "stream"
        assert node["kind"] == "bytes"
        assert node["content_type"] == "image/png"
        assert node["id"] in streams
        assert streams[node["id"]]["content_type"] == "image/png"

    @pytest.mark.anyio
    async def test_upload_file_becomes_stream_marker(self):
        codec = make_codec(FakeRedis())
        uf = UploadFile(
            file=io.BytesIO(b"payload"),
            filename="doc.bin",
            headers={"content-type": "application/octet-stream"},
        )

        encoded, _, streams = await codec.encode_input({"file": uf})

        node = marker(encoded["file"])
        assert node is not None
        assert node["type"] == "stream"
        assert node["content_type"] == "application/octet-stream"
        assert node["filename"] == "doc.bin"
        assert node["id"] in streams

    @pytest.mark.anyio
    async def test_bytes_stream_resource_preserves_content_type(self):
        codec = make_codec(FakeRedis())
        resource = BytesStreamResource(b"payload", content_type="application/x-bin", filename="x.bin")

        encoded, _, streams = await codec.encode_input({"r": resource})

        node = marker(encoded["r"])
        assert node["type"] == "stream"
        assert node["content_type"] == "application/x-bin"
        assert node["filename"] == "x.bin"
        assert node["size"] == len(b"payload")

    @pytest.mark.anyio
    async def test_text_stream_resource_kind(self):
        codec = make_codec(FakeRedis())
        resource = TextStreamResource("hello", encoding="utf-8")

        encoded, _, streams = await codec.encode_input({"r": resource})

        node = marker(encoded["r"])
        assert node["type"] == "stream"
        assert node["content_type"].startswith("text/")

    @pytest.mark.anyio
    async def test_pcm_stream_attrs_preserved(self):
        codec = make_codec(FakeRedis())
        # PcmStreamResource expects an async-iterable source; we don't iterate here.
        class _Empty:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        resource = PcmStreamResource(_Empty(), attrs={"sample_rate": 16000, "channels": 1})

        encoded, _, streams = await codec.encode_input({"r": resource})

        node = marker(encoded["r"])
        assert node is not None
        assert node["type"] == "stream"
        assert node["attrs"] == {"sample_rate": 16000, "channels": 1}
        assert streams[node["id"]]["attrs"] == {"sample_rate": 16000, "channels": 1}


# ============================================================================
# BaseModel / AtomicDict / AtomicList
# ============================================================================

class _M(BaseModel):
    name: str
    age: int


class TestPydanticAndAtomic:

    @pytest.mark.anyio
    async def test_basemodel_encoded_via_model_dump(self):
        codec = make_codec(FakeRedis())
        encoded, _, streams = await codec.encode_input({"m": _M(name="a", age=1)})
        decoded = await codec.decode_input(encoded, streams)
        # Round-trips as dict — matches VariableCodec semantics; BaseModel identity
        # is not preserved on the wire.
        assert decoded == {"m": {"name": "a", "age": 1}}

    @pytest.mark.anyio
    async def test_atomic_dict_roundtrip(self):
        from mindor.core.foundation.variable.atomic import AtomicDict
        codec = make_codec(FakeRedis())

        value = AtomicDict({"k": "v"})
        encoded, _, streams = await codec.encode_input({"d": value})
        decoded = await codec.decode_input(encoded, streams)

        assert isinstance(decoded["d"], AtomicDict)
        assert dict(decoded["d"]) == {"k": "v"}

    @pytest.mark.anyio
    async def test_atomic_list_roundtrip(self):
        from mindor.core.foundation.variable.atomic import AtomicList
        codec = make_codec(FakeRedis())

        value = AtomicList([1, 2, 3])
        encoded, _, streams = await codec.encode_input({"l": value})
        decoded = await codec.decode_input(encoded, streams)

        assert isinstance(decoded["l"], AtomicList)
        assert list(decoded["l"]) == [1, 2, 3]


# ============================================================================
# Key-ownership boundary — user dicts that look like markers
# ============================================================================

class TestKeyOwnership:

    @pytest.mark.anyio
    async def test_user_dict_with_key_field_not_treated_as_blob_ref(self):
        client = FakeRedis()
        codec = make_codec(client)

        # A user dict that happens to have a "key" field. It's NOT wrapped in
        # `__variable__`, so codec must pass it through untouched.
        user_input = {"config": {"key": "user-key", "note": "mine"}}
        encoded, _, streams = await codec.encode_input(user_input)
        decoded = await codec.decode_input(encoded, streams)

        assert decoded == user_input

    @pytest.mark.anyio
    async def test_foreign_prefix_marker_not_consumed(self):
        """A `__variable__ {type: bytes, key: ...}` whose key is under a
        foreign blob_prefix must not silently trigger a Redis lookup — that
        would let a malicious producer read other tenants' blobs."""
        client = FakeRedis()
        client.store["OTHER:prefix:victim"] = b"victim-data"
        codec = make_codec(client)  # blob_prefix = "q:wf:run:blob:"

        forged = {
            "data": {
                "__variable__": {
                    "type": "bytes",
                    "key": "OTHER:prefix:victim",
                    "size": 11,
                }
            }
        }
        from mindor.core.controller.queue.errors import BlobUnauthorizedError

        with pytest.raises(BlobUnauthorizedError):
            await codec.decode_input(forged, {})

        assert client.store["OTHER:prefix:victim"] == b"victim-data"


# ============================================================================
# Output encoding — symmetric to input, plus stream registry population
# ============================================================================

class TestOutputEncoding:

    @pytest.mark.anyio
    async def test_output_bytes_roundtrip(self):
        client = FakeRedis()
        codec = make_codec(client, inline_bytes_threshold=8)

        encoded, blobs, streams = await codec.encode_output({"out": b"X" * 100})
        assert streams == {}
        assert len(blobs) == 1

        decoded = await codec.decode_output(encoded, streams)
        assert decoded == {"out": b"X" * 100}

    @pytest.mark.anyio
    async def test_output_scalar_no_side_effects(self):
        client = FakeRedis()
        codec = make_codec(client)

        encoded, blobs, streams = await codec.encode_output({"count": 42})
        assert blobs == []
        assert streams == {}
        assert client.store == {}
        assert (await codec.decode_output(encoded, streams)) == {"count": 42}

    @pytest.mark.anyio
    async def test_output_stream_marker_registers_stream_meta(self):
        codec = make_codec(FakeRedis())
        resource = BytesStreamResource(b"", content_type="audio/wav", filename="x.wav")

        encoded, _, streams = await codec.encode_output({"audio": resource})

        node = marker(encoded["audio"])
        assert node["type"] == "stream"
        assert streams[node["id"]]["content_type"] == "audio/wav"
        assert streams[node["id"]]["stream_key"].startswith("q:wf:run:outstream:")
