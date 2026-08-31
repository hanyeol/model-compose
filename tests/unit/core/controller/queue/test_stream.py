"""Unit tests for `RedisOutboundStream` / `RedisInboundStream` — XADD/XREAD
based stream primitives that mirror the IPC stream reader/writer for the
queue-subscribe adapter.

Covers the `queue.v2` chunk frame defined in
`docs/specs/queue-subscribe-codec-spec.md`:

- `encode_chunk` per `StreamKind`:
  - BYTES ≤ threshold → inline base64 string in `data`
  - BYTES > threshold → blob key reference (`blob-key:<key>`)
  - TEXT  → raw str
  - OBJECT → `VariableCodec.encode(chunk)` serialized to JSON string
- `decode_chunk` symmetric inversion including blob consumption via `GETDEL`.
- Wire kind validation: mismatched chunk types raise `StreamKindMismatchError`.
- End/abort/close lifecycle: `end` → `StopAsyncIteration`, `abort` →
  `StreamAbortError`.
- `build_resource` mapping table matches
  `IpcInboundStream._resolve_resource_class` — image/audio/video/text/bytes.
- `MAXLEN` trimming forwarded to `XADD` when configured.

Implementation is not yet in place; module-level import is guarded so the file
skips cleanly when target symbols do not exist.
"""

from __future__ import annotations

from typing import Any

import pytest

from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from mindor.core.foundation.streaming.audio import (
    AudioStreamResource,
    PcmStreamResource,
    WavStreamResource,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource

pytest.importorskip("mindor.core.controller.queue.stream")

from mindor.core.controller.queue.stream import (  # noqa: E402
    RedisInboundStream,
    RedisOutboundStream,
    RedisStreamMeta,
)
from mindor.core.controller.queue.errors import (  # noqa: E402
    StreamAbortError,
    StreamKindMismatchError,
)


# ============================================================================
# Fixtures & fakes
# ============================================================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRedis:
    """Minimal Redis stand-in supporting XADD, XREAD, SETEX/GET/DEL/GETDEL.

    Streams are kept as ordered lists of (entry_id, fields dict). `XREAD` is
    a simple cursor over `_last_id`. Blob store is a plain dict.
    """

    def __init__(self):
        self.streams: dict[str, list[tuple[str, dict[str, bytes]]]] = {}
        self.blobs: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.xadd_maxlen_calls: list[tuple[str, int | None]] = []
        self._seq = 0
        self.getdel_supported: bool = True

    def _next_id(self) -> str:
        self._seq += 1
        return f"0-{self._seq}"

    async def xadd(
        self,
        key: str,
        fields: dict[str, Any],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        entry_id = self._next_id()
        self.streams.setdefault(key, []).append((entry_id, dict(fields)))
        self.xadd_maxlen_calls.append((key, maxlen))
        if maxlen is not None:
            entries = self.streams[key]
            if len(entries) > maxlen:
                del entries[: len(entries) - maxlen]
        return entry_id

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ):
        result = []
        for key, last_id in streams.items():
            entries = self.streams.get(key, [])
            new_entries = [(eid, fields) for eid, fields in entries if eid > last_id]
            if count is not None:
                new_entries = new_entries[:count]
            if new_entries:
                result.append((key, new_entries))
        return result or None

    async def expire(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl

    async def setex(self, key: str, ttl: int, value: bytes) -> None:
        self.blobs[key] = value
        self.ttls[key] = ttl

    async def get(self, key: str) -> bytes | None:
        return self.blobs.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if self.blobs.pop(k, None) is not None:
                removed += 1
        return removed

    async def execute_command(self, cmd: str, key: str):
        if cmd != "GETDEL":
            raise RuntimeError(f"unexpected command {cmd}")
        if not self.getdel_supported:
            from redis.exceptions import ResponseError
            raise ResponseError("unknown command 'GETDEL'")
        return self.blobs.pop(key, None)


def make_outbound(
    client: FakeRedis,
    *,
    kind: StreamKind = StreamKind.BYTES,
    stream_id: str = "s1",
    stream_key: str = "q:wf:run:outstream:s1",
    codec: VariableCodec | None = None,
    inline_bytes_threshold: int = 64,
    blob_ttl: int = 60,
    max_stream_length: int | None = None,
) -> RedisOutboundStream:
    return RedisOutboundStream(
        client=client,
        meta=RedisStreamMeta(
            stream_id=stream_id,
            kind=kind,
            content_type=None,
            filename=None,
            size=None,
            attrs=None,
            stream_key=stream_key,
        ),
        codec=codec or VariableCodec(),
        inline_bytes_threshold=inline_bytes_threshold,
        blob_ttl=blob_ttl,
        max_stream_length=max_stream_length,
    )


def make_inbound(
    client: FakeRedis,
    *,
    kind: StreamKind = StreamKind.BYTES,
    stream_id: str = "s1",
    stream_key: str = "q:wf:run:outstream:s1",
    content_type: str | None = None,
    attrs: dict | None = None,
    filename: str | None = None,
    codec: VariableCodec | None = None,
) -> RedisInboundStream:
    return RedisInboundStream(
        client=client,
        meta=RedisStreamMeta(
            stream_id=stream_id,
            kind=kind,
            content_type=content_type,
            filename=filename,
            size=None,
            attrs=attrs,
            stream_key=stream_key,
        ),
        codec=codec or VariableCodec(),
    )


async def drain_stream(reader: RedisInboundStream) -> list[Any]:
    """Read all chunks until StopAsyncIteration (or raise on abort)."""
    out = []
    async for chunk in reader:
        out.append(chunk)
    return out


# ============================================================================
# encode_chunk / decode_chunk — kind semantics
# ============================================================================

class TestBytesChunks:

    @pytest.mark.anyio
    async def test_small_bytes_inline(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.BYTES, inline_bytes_threshold=64)

        await out.push_chunk(b"hello")
        await out.push_end()

        # XADD entry should contain inline data (no blob key), no side blob store.
        entries = client.streams["q:wf:run:outstream:s1"]
        assert len(entries) == 2  # chunk + end
        _, chunk_fields = entries[0]
        event = chunk_fields.get(b"event", chunk_fields.get("event"))
        event = event.decode() if isinstance(event, bytes) else event
        assert event == "chunk"
        # data is either base64 str or bytes; must not be a blob reference
        data = chunk_fields.get(b"data", chunk_fields.get("data"))
        assert data is not None
        as_text = data.decode() if isinstance(data, bytes) else data
        assert not as_text.startswith("blob-key:")
        assert client.blobs == {}

    @pytest.mark.anyio
    async def test_small_bytes_roundtrip(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.BYTES, inline_bytes_threshold=64)
        inb = make_inbound(client, kind=StreamKind.BYTES)

        await out.push_chunk(b"hello")
        await out.push_end()

        chunks = await drain_stream(inb)
        assert chunks == [b"hello"]

    @pytest.mark.anyio
    async def test_large_bytes_offloaded_to_blob(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.BYTES, inline_bytes_threshold=8)

        payload = b"X" * 100
        await out.push_chunk(payload)

        entries = client.streams["q:wf:run:outstream:s1"]
        _, chunk_fields = entries[0]
        data = chunk_fields.get(b"data", chunk_fields.get("data"))
        as_text = data.decode() if isinstance(data, bytes) else data
        assert as_text.startswith("blob-key:")
        blob_key = as_text[len("blob-key:") :]
        assert client.blobs[blob_key] == payload

    @pytest.mark.anyio
    async def test_large_bytes_roundtrip_consumes_blob(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.BYTES, inline_bytes_threshold=8)
        inb = make_inbound(client, kind=StreamKind.BYTES)

        await out.push_chunk(b"X" * 100)
        await out.push_end()

        chunks = await drain_stream(inb)
        assert chunks == [b"X" * 100]
        assert client.blobs == {}

    @pytest.mark.anyio
    async def test_bytes_kind_rejects_non_bytes(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.BYTES)
        with pytest.raises(StreamKindMismatchError):
            await out.push_chunk("not bytes")


class TestTextChunks:

    @pytest.mark.anyio
    async def test_text_roundtrip(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT)
        inb = make_inbound(client, kind=StreamKind.TEXT)

        for part in ("hello ", "world"):
            await out.push_chunk(part)
        await out.push_end()

        assert (await drain_stream(inb)) == ["hello ", "world"]

    @pytest.mark.anyio
    async def test_text_rejects_bytes(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT)
        with pytest.raises(StreamKindMismatchError):
            await out.push_chunk(b"nope")


class TestObjectChunks:

    @pytest.mark.anyio
    async def test_object_roundtrip_dict(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.OBJECT)
        inb = make_inbound(client, kind=StreamKind.OBJECT)

        payload = {"delta": {"content": "hi"}}
        await out.push_chunk(payload)
        await out.push_end()

        assert (await drain_stream(inb)) == [payload]

    @pytest.mark.anyio
    async def test_object_roundtrip_with_bytes_marker_nested(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.OBJECT)
        inb = make_inbound(client, kind=StreamKind.OBJECT)

        # Nested `bytes` inside an OBJECT chunk should round-trip via the codec's
        # `bytes` marker (inline base64 — chunks don't offload nested bytes).
        payload = {"blob": b"data", "n": 3}
        await out.push_chunk(payload)
        await out.push_end()

        chunks = await drain_stream(inb)
        assert chunks == [payload]


# ============================================================================
# End / abort lifecycle
# ============================================================================

class TestLifecycle:

    @pytest.mark.anyio
    async def test_end_terminates_iteration(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT)
        inb = make_inbound(client, kind=StreamKind.TEXT)

        await out.push_chunk("only")
        await out.push_end()

        assert (await drain_stream(inb)) == ["only"]

    @pytest.mark.anyio
    async def test_abort_raises_stream_abort_error(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT)
        inb = make_inbound(client, kind=StreamKind.TEXT)

        await out.push_chunk("partial")
        await out.push_abort("upstream boom")

        collected: list[str] = []
        with pytest.raises(StreamAbortError) as exc:
            async for chunk in inb:
                collected.append(chunk)

        assert collected == ["partial"]
        assert "upstream boom" in str(exc.value)

    @pytest.mark.anyio
    async def test_aclose_is_idempotent(self):
        client = FakeRedis()
        inb = make_inbound(client, kind=StreamKind.BYTES)
        # Not started; aclose must not raise.
        await inb.aclose()
        await inb.aclose()


# ============================================================================
# build_resource — content_type + kind mapping
# ============================================================================

class TestBuildResource:

    def test_image_content_type_returns_stream_with_image_content_type(self):
        # `ImageStreamResource` requires an in-memory PIL.Image, so streamed
        # image data falls back to an AsyncIterableStreamResource carrying
        # `content_type="image/*"` — consumer decodes via load_image_from_stream.
        inb = make_inbound(FakeRedis(), kind=StreamKind.BYTES, content_type="image/png")
        resource = inb.build_resource()
        assert isinstance(resource, StreamResource)
        assert resource.content_type == "image/png"

    def test_audio_wav_returns_wav_resource(self):
        inb = make_inbound(
            FakeRedis(),
            kind=StreamKind.BYTES,
            content_type="audio/wav",
            attrs={"sample_rate": 16000},
        )
        assert isinstance(inb.build_resource(), WavStreamResource)

    def test_audio_pcm_returns_pcm_resource(self):
        inb = make_inbound(
            FakeRedis(),
            kind=StreamKind.BYTES,
            content_type="audio/pcm",
            attrs={"sample_rate": 24000, "channels": 1},
        )
        resource = inb.build_resource()
        assert isinstance(resource, PcmStreamResource)

    def test_generic_audio_returns_audio_resource(self):
        inb = make_inbound(FakeRedis(), kind=StreamKind.BYTES, content_type="audio/mpeg")
        assert isinstance(inb.build_resource(), AudioStreamResource)

    def test_video_returns_video_resource(self):
        inb = make_inbound(FakeRedis(), kind=StreamKind.BYTES, content_type="video/mp4")
        assert isinstance(inb.build_resource(), VideoStreamResource)

    def test_text_content_type_returns_bytes_iterable_resource(self):
        # Matches IPC semantics: text/* falls back to AsyncIterableStreamResource
        # (a StreamResource), consumer decodes via load_text_from_stream.
        inb = make_inbound(FakeRedis(), kind=StreamKind.BYTES, content_type="text/plain")
        resource = inb.build_resource()
        assert hasattr(resource, "content_type")
        assert resource.content_type == "text/plain"

    def test_no_content_type_bytes_kind_returns_stream_resource(self):
        # BytesStreamResource requires an in-memory `bytes`; falls back to
        # AsyncIterableStreamResource (a StreamResource) for streamed data.
        inb = make_inbound(FakeRedis(), kind=StreamKind.BYTES, content_type=None)
        resource = inb.build_resource()
        assert isinstance(resource, StreamResource)

    def test_no_content_type_text_kind_returns_chunk_iterator(self):
        inb = make_inbound(FakeRedis(), kind=StreamKind.TEXT, content_type=None)
        assert isinstance(inb.build_resource(), StreamChunkIterator)

    def test_no_content_type_object_kind_returns_chunk_iterator(self):
        inb = make_inbound(FakeRedis(), kind=StreamKind.OBJECT, content_type=None)
        assert isinstance(inb.build_resource(), StreamChunkIterator)


# ============================================================================
# max_stream_length — Redis stream trim forwarding
# ============================================================================

class TestMaxStreamLength:

    @pytest.mark.anyio
    async def test_maxlen_forwarded_to_xadd(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT, max_stream_length=3)

        for i in range(5):
            await out.push_chunk(f"chunk-{i}")
        await out.push_end()

        # every XADD call carries maxlen=3
        assert all(maxlen == 3 for _, maxlen in client.xadd_maxlen_calls)
        # trimming keeps the tail
        assert len(client.streams["q:wf:run:outstream:s1"]) <= 3 + 1  # + end

    @pytest.mark.anyio
    async def test_none_disables_trim(self):
        client = FakeRedis()
        out = make_outbound(client, kind=StreamKind.TEXT, max_stream_length=None)

        for i in range(3):
            await out.push_chunk(f"chunk-{i}")
        assert all(maxlen is None for _, maxlen in client.xadd_maxlen_calls)


# ============================================================================
# Attrs propagation into resource constructor
# ============================================================================

class TestAttrsPropagation:

    def test_pcm_attrs_flow_to_resource(self):
        inb = make_inbound(
            FakeRedis(),
            kind=StreamKind.BYTES,
            content_type="audio/pcm",
            attrs={"sample_rate": 22050, "channels": 2},
        )
        resource = inb.build_resource()
        assert isinstance(resource, PcmStreamResource)
        assert getattr(resource, "attrs", None) == {"sample_rate": 22050, "channels": 2}

    def test_wav_attrs_flow_to_resource(self):
        inb = make_inbound(
            FakeRedis(),
            kind=StreamKind.BYTES,
            content_type="audio/wav",
            attrs={"sample_rate": 16000},
            filename="voice.wav",
        )
        resource = inb.build_resource()
        assert isinstance(resource, WavStreamResource)
        assert resource.filename == "voice.wav"
