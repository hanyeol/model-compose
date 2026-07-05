"""Unit tests for VariableCodec — value-tree transformer for workflow variables.

Covers:
- JSON-native scalars/containers + pydantic BaseModel.
- bytes/bytearray → `__variable__` variable (type: "bytes").
- StreamResource, iterators, PIL.Image → `__variable__` variable (type: "stream").
- Rejected types: io.IOBase, socket.socket, sync generators, numpy/torch/pandas.
- Callbacks: on_stream encode/decode bridge to a dispatcher.
- User dict shaped like a variable is passed through (no validation policy).
"""

from __future__ import annotations

import base64
import io
import socket
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pytest
from pydantic import BaseModel

from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.iterators import (
    StreamEncodingFormat,
    StreamEncodingIterator,
    StreamChunkIterator,
)
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.foundation.variable.codec import VariableCodec


@pytest.fixture
def codec() -> VariableCodec:
    return VariableCodec()


def _is_ulid(value: str) -> bool:
    return isinstance(value, str) and len(value) == 26 and value.isalnum()


async def _aiter_bytes(items: List[bytes]) -> AsyncIterator[bytes]:
    for item in items:
        yield item


# ============================================================================
# JSON-native + special types
# ============================================================================


class TestScalars:
    def test_none(self, codec):
        assert codec.encode(None) is None
        assert codec.decode(None) is None

    def test_bool_true(self, codec):
        assert codec.decode(codec.encode(True)) is True

    def test_bool_false(self, codec):
        assert codec.decode(codec.encode(False)) is False

    def test_int_zero(self, codec):
        assert codec.decode(codec.encode(0)) == 0

    def test_int_positive(self, codec):
        assert codec.decode(codec.encode(12345)) == 12345

    def test_int_negative(self, codec):
        assert codec.decode(codec.encode(-9876)) == -9876

    def test_int_very_large(self, codec):
        big = 2**63 + 1
        assert codec.decode(codec.encode(big)) == big

    def test_float(self, codec):
        assert codec.decode(codec.encode(3.14)) == 3.14

    def test_float_zero(self, codec):
        assert codec.decode(codec.encode(0.0)) == 0.0

    def test_float_negative(self, codec):
        assert codec.decode(codec.encode(-2.718)) == -2.718

    def test_string_empty(self, codec):
        assert codec.decode(codec.encode("")) == ""

    def test_string_ascii(self, codec):
        assert codec.decode(codec.encode("hello")) == "hello"

    def test_string_unicode_preserved(self, codec):
        assert codec.decode(codec.encode("한국어")) == "한국어"

    def test_string_with_special_chars(self, codec):
        s = 'tab\tnewline\n"quote"\\backslash'
        assert codec.decode(codec.encode(s)) == s


class TestContainers:
    def test_empty_dict(self, codec):
        assert codec.decode(codec.encode({})) == {}

    def test_empty_list(self, codec):
        assert codec.decode(codec.encode([])) == []

    def test_flat_dict(self, codec):
        msg = {"a": 1, "b": "two", "c": None, "d": True, "e": 3.14}
        assert codec.decode(codec.encode(msg)) == msg

    def test_flat_list(self, codec):
        msg = [1, "two", None, True, 3.14]
        assert codec.decode(codec.encode(msg)) == msg

    def test_nested_dict(self, codec):
        msg = {"a": {"b": {"c": {"d": 1}}}}
        assert codec.decode(codec.encode(msg)) == msg

    def test_nested_list(self, codec):
        msg = [[1, 2], [3, [4, 5]]]
        assert codec.decode(codec.encode(msg)) == msg

    def test_mixed_dict_and_list(self, codec):
        msg = {"users": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": []}]}
        assert codec.decode(codec.encode(msg)) == msg

    def test_tuple_becomes_list(self, codec):
        # Tuples are not JSON-native; codec turns them into lists.
        out = codec.encode((1, 2, 3))
        assert out == [1, 2, 3]

    def test_set_is_rejected(self, codec):
        # set/frozenset are not JSON-native and are not auto-converted; users must
        # convert to list before sending.
        with pytest.raises(TypeError, match="Cannot serialize"):
            codec.encode({1, 2, 3})

    def test_dict_keys_coerced_to_string(self, codec):
        # Non-string keys are stringified during encode.
        out = codec.encode({1: "a", 2: "b"})
        assert out == {"1": "a", "2": "b"}


class TestSpecialTypes:
    def test_pydantic_basemodel_flattened(self, codec):
        class User(BaseModel):
            id: int
            name: str
            tags: List[str]

        u = User(id=1, name="Hanyeol", tags=["admin"])
        assert codec.encode(u) == {"id": 1, "name": "Hanyeol", "tags": ["admin"]}

    def test_pydantic_with_datetime_uses_json_mode(self, codec):
        # BaseModel.model_dump(mode="json") converts datetime to ISO inside.
        class Event(BaseModel):
            when: datetime

        e = Event(when=datetime(2026, 6, 25, tzinfo=timezone.utc))
        out = codec.encode(e)
        assert isinstance(out["when"], str)
        assert "2026-06-25" in out["when"]


# ============================================================================
# bytes variable
# ============================================================================


class TestBytesVariable:
    def test_top_level_bytes_value(self, codec):
        out = codec.encode({"data": b"hello"})
        assert out == {
            "data": {
                "__variable__": {
                    "type": "bytes",
                    "value": base64.b64encode(b"hello").decode("ascii"),
                }
            }
        }

    def test_bytes_roundtrip_to_bytes(self, codec):
        original = b"binary\x00data\xff"
        result = codec.decode(codec.encode(original))
        assert result == original
        assert isinstance(result, bytes)

    def test_empty_bytes(self, codec):
        assert codec.decode(codec.encode(b"")) == b""

    def test_large_bytes(self, codec):
        original = b"x" * 100_000
        assert codec.decode(codec.encode(original)) == original

    def test_bytearray_encodes_as_bytes(self, codec):
        original = bytearray(b"\x01\x02\x03")
        result = codec.decode(codec.encode(original))
        assert result == bytes(original)
        assert isinstance(result, bytes)

    def test_bytes_nested_in_dict(self, codec):
        msg = {"a": {"b": {"c": b"deep"}}}
        result = codec.decode(codec.encode(msg))
        assert result == {"a": {"b": {"c": b"deep"}}}

    def test_bytes_nested_in_list(self, codec):
        msg = [b"a", b"b", b"c"]
        result = codec.decode(codec.encode(msg))
        assert result == [b"a", b"b", b"c"]

    def test_multiple_bytes_in_one_message(self, codec):
        msg = {"a": b"first", "b": b"second", "c": [b"x", b"y"]}
        result = codec.decode(codec.encode(msg))
        assert result == msg


# ============================================================================
# stream variable
# ============================================================================


class TestStreamVariable:
    def test_stream_resource_top_level(self, codec):
        res = BytesStreamResource(b"audio-bytes", content_type="audio/wav")
        out = codec.encode({"audio": res})
        variable = out["audio"]["__variable__"]
        assert variable["type"] == "stream"
        assert _is_ulid(variable["id"])
        assert variable["kind"] == "bytes"
        assert variable["content_type"] == "audio/wav"

    def test_each_stream_gets_unique_id(self, codec):
        res1 = BytesStreamResource(b"a")
        res2 = BytesStreamResource(b"b")
        out = codec.encode({"a": res1, "b": res2})
        id1 = out["a"]["__variable__"]["id"]
        id2 = out["b"]["__variable__"]["id"]
        assert id1 != id2

    def test_same_resource_used_twice_still_gets_two_ids(self, codec):
        res = BytesStreamResource(b"shared")
        out = codec.encode({"a": res, "b": res})
        id1 = out["a"]["__variable__"]["id"]
        id2 = out["b"]["__variable__"]["id"]
        assert id1 != id2

    def test_text_stream_resource_kind_is_bytes(self, codec):
        res = TextStreamResource("hello")
        variable = codec.encode(res)["__variable__"]
        assert variable["kind"] == "bytes"
        assert variable["content_type"].startswith("text/plain")

    def test_event_stream_text_kind(self, codec):
        it = StreamEncodingIterator(_aiter_bytes([b"a"]), format=StreamEncodingFormat.TEXT)
        assert codec.encode(it)["__variable__"]["kind"] == "text"

    def test_event_stream_json_kind(self, codec):
        it = StreamEncodingIterator(_aiter_bytes([b"a"]), format=StreamEncodingFormat.JSON)
        assert codec.encode(it)["__variable__"]["kind"] == "object"

    def test_event_stream_format_none_kind_is_object(self, codec):
        it = StreamEncodingIterator(_aiter_bytes([b"a"]), format=None)
        assert codec.encode(it)["__variable__"]["kind"] == "object"

    def test_stream_chunk_iterator_kind_is_object(self, codec):
        it = StreamChunkIterator(_aiter_bytes([b"a"]))
        assert codec.encode(it)["__variable__"]["kind"] == "object"

    def test_async_iterator_kind_is_object(self, codec):
        assert codec.encode(_aiter_bytes([b"a"]))["__variable__"]["kind"] == "object"

    def test_stream_resource_with_attrs(self, codec):
        from mindor.core.foundation.streaming.audio import PcmStreamResource

        res = PcmStreamResource(b"pcm-bytes", attrs={"sample_rate": 16000, "channels": 1})
        variable = codec.encode(res)["__variable__"]
        assert variable["attrs"] == {"sample_rate": 16000, "channels": 1}

    def test_pil_image_auto_lifted_to_stream(self, codec):
        try:
            from PIL import Image
        except Exception:
            pytest.skip("PIL not installed")
        img = Image.new("RGB", (1, 1), color=(255, 0, 0))
        variable = codec.encode(img)["__variable__"]
        assert variable["type"] == "stream"
        assert variable["kind"] == "bytes"
        assert variable["content_type"].startswith("image/")

    def test_stream_nested_in_list(self, codec):
        res = BytesStreamResource(b"x")
        out = codec.encode([res])
        assert out[0]["__variable__"]["type"] == "stream"

    def test_stream_nested_in_dict(self, codec):
        res = BytesStreamResource(b"x")
        out = codec.encode({"a": {"b": res}})
        assert out["a"]["b"]["__variable__"]["type"] == "stream"


class TestStreamCallbacks:
    def test_on_stream_encode_called_with_id_and_source(self, codec):
        res = BytesStreamResource(b"a")
        captured: List[Tuple[str, Any]] = []
        codec.encode(res, on_stream_encode=lambda sid, src, kind: captured.append((sid, src)))
        assert len(captured) == 1
        sid, src = captured[0]
        assert _is_ulid(sid)
        assert src is res

    def test_on_stream_encode_multiple_streams(self, codec):
        res1 = BytesStreamResource(b"a")
        res2 = BytesStreamResource(b"b")
        captured: List[Tuple[str, Any]] = []
        codec.encode({"a": res1, "b": res2}, on_stream_encode=lambda sid, src, kind: captured.append((sid, src)))
        assert len(captured) == 2
        sources = [src for _, src in captured]
        assert res1 in sources and res2 in sources

    def test_on_stream_encode_id_matches_variable(self, codec):
        res = BytesStreamResource(b"a")
        captured_id = []
        out = codec.encode(res, on_stream_encode=lambda sid, src, kind: captured_id.append(sid))
        variable_id = out["__variable__"]["id"]
        assert captured_id == [variable_id]

    def test_on_stream_decode_called_per_stream_variable(self, codec):
        res = BytesStreamResource(b"a")
        encoded = codec.encode({"v": res})
        seen: List[Dict[str, Any]] = []

        def on_decode(variable):
            seen.append(variable)
            return f"proxy({variable['id']})"

        result = codec.decode(encoded, on_stream_decode=on_decode)
        assert len(seen) == 1
        assert result["v"] == f"proxy({seen[0]['id']})"

    def test_decode_without_callback_raises_on_stream(self, codec):
        res = BytesStreamResource(b"a")
        encoded = codec.encode({"v": res})
        with pytest.raises(RuntimeError, match="on_stream_decode"):
            codec.decode(encoded)

    def test_bytes_variable_does_not_invoke_stream_callback(self, codec):
        called = []
        codec.decode(codec.encode({"v": b"hi"}), on_stream_decode=lambda m: called.append(m))
        assert called == []


# ============================================================================
# Rejected types
# ============================================================================


class TestRejectedTypes:
    """All non-handled types fall through to a single TypeError at encode time."""

    def test_io_base_raises(self, codec):
        with pytest.raises(TypeError, match="Cannot serialize"):
            codec.encode(io.BytesIO(b"a"))

    def test_socket_raises(self, codec):
        sock = socket.socket()
        try:
            with pytest.raises(TypeError, match="Cannot serialize"):
                codec.encode(sock)
        finally:
            sock.close()

    def test_sync_generator_raises(self, codec):
        def gen():
            yield 1

        with pytest.raises(TypeError, match="Cannot serialize"):
            codec.encode(gen())

    def test_numpy_ndarray_raises(self, codec):
        try:
            import numpy as np
        except Exception:
            pytest.skip("numpy not installed")
        with pytest.raises(TypeError, match="Cannot serialize"):
            codec.encode(np.array([1, 2, 3]))

    def test_unknown_object_raises(self, codec):
        class Foo:
            pass

        with pytest.raises(TypeError, match="Cannot serialize"):
            codec.encode(Foo())


# ============================================================================
# User dict that looks like a variable — pass-through policy
# ============================================================================


class TestUserDictResemblingVariable:
    def test_user_dict_with_variable_key_passes_through_on_encode(self, codec):
        # Codec does not validate user dicts; they go through as-is.
        msg = {"__variable__": {"type": "bytes", "value": "literal"}}
        assert codec.encode(msg) == msg

    def test_user_dict_with_only_variable_key_decodes_as_variable(self, codec):
        # By policy, a single-key dict with variable key and a dict value carrying
        # a "type" discriminator is interpreted as a variable on decode.
        encoded = {"v": {"__variable__": {"type": "bytes", "value": base64.b64encode(b"x").decode()}}}
        result = codec.decode(encoded)
        assert result == {"v": b"x"}

    def test_user_dict_with_variable_key_plus_others_is_not_variable(self, codec):
        # Decoding logic requires the dict to be exactly the variable key only.
        msg = {"v": {"__variable__": {"type": "bytes", "value": "x"}, "extra": 1}}
        result = codec.decode(msg)
        # The dict has two keys, so it's treated as a plain user dict.
        assert result == {"v": {"__variable__": {"type": "bytes", "value": "x"}, "extra": 1}}


# ============================================================================
# Roundtrip integrity for mixed-tier inputs
# ============================================================================


class TestMixedRoundtrip:
    def test_mixed_scalars_and_bytes(self, codec):
        msg = {
            "id": 42,
            "name": "Hanyeol",
            "blob": b"\x00\x01\x02",
            "nested": {"more_blob": b"\xff\xfe"},
        }
        out = codec.decode(codec.encode(msg))
        assert out == msg

    def test_mixed_with_stream_and_bytes_in_list(self, codec):
        res = BytesStreamResource(b"audio")
        out = codec.encode({"items": [b"prelude", res, b"coda"]})
        items = out["items"]
        # bytes variables
        assert items[0]["__variable__"]["type"] == "bytes"
        assert items[2]["__variable__"]["type"] == "bytes"
        # stream variable
        assert items[1]["__variable__"]["type"] == "stream"


# ============================================================================
# Stream callback synchronization (encode ↔ decode)
# ============================================================================


class TestStreamRoundtrip:
    def test_stream_id_from_encode_matches_decode(self, codec):
        # The stream_id emitted by on_stream_encode must be exactly the same as
        # the id carried in the variable dict that on_stream_decode receives.
        res = BytesStreamResource(b"x")

        encoded_id_holder = []
        encoded = codec.encode(
            {"v": res},
            on_stream_encode=lambda sid, src, kind: encoded_id_holder.append(sid),
        )

        decoded_id_holder = []
        codec.decode(
            encoded,
            on_stream_decode=lambda v: decoded_id_holder.append(v["id"]) or "proxy",
        )

        assert encoded_id_holder == decoded_id_holder

    def test_multiple_streams_preserve_id_pairing(self, codec):
        res1 = BytesStreamResource(b"a")
        res2 = BytesStreamResource(b"b")
        res3 = BytesStreamResource(b"c")

        encode_map = {}  # stream_id → source
        encoded = codec.encode(
            {"a": res1, "b": res2, "list": [res3]},
            on_stream_encode=lambda sid, src, kind: encode_map.__setitem__(sid, src),
        )

        decoded_ids = []
        codec.decode(
            encoded,
            on_stream_decode=lambda v: decoded_ids.append(v["id"]) or "proxy",
        )

        # Encode emitted 3 unique ids, all of which appear in decode.
        assert len(encode_map) == 3
        assert sorted(decoded_ids) == sorted(encode_map.keys())

    def test_decode_callback_receives_attrs_and_content_type(self, codec):
        from mindor.core.foundation.streaming.audio import PcmStreamResource

        res = PcmStreamResource(b"pcm", attrs={"sample_rate": 16000, "channels": 1})
        encoded = codec.encode({"v": res})

        seen: List[Dict[str, Any]] = []
        codec.decode(
            encoded,
            on_stream_decode=lambda v: seen.append(v) or "proxy",
        )

        assert len(seen) == 1
        variable = seen[0]
        assert variable["content_type"] == "audio/pcm"
        assert variable["attrs"] == {"sample_rate": 16000, "channels": 1}
        assert variable["kind"] == "bytes"


# ============================================================================
# Invalid input
# ============================================================================


class TestInvalidInput:
    def test_decode_unknown_variable_type_raises(self, codec):
        encoded = {"v": {"__variable__": {"type": "weird"}}}
        with pytest.raises(ValueError, match="Unknown variable type"):
            codec.decode(encoded)

    def test_decode_bytes_variable_with_non_string_value_raises(self, codec):
        encoded = {"v": {"__variable__": {"type": "bytes", "value": 123}}}
        with pytest.raises(ValueError, match="must be a string"):
            codec.decode(encoded)


# ============================================================================
# Deep nesting + mixed types
# ============================================================================


class TestDeepNestedRoundtrip:
    def test_deep_mixed_value_roundtrip(self, codec):
        res = BytesStreamResource(b"audio")
        msg = {
            "level1": {
                "level2": {
                    "stream": res,
                    "bytes": b"binary",
                    "list": [{"nested_bytes": b"x"}, [b"y", b"z"]],
                    "scalar": 42,
                }
            }
        }

        encode_seen: List[str] = []
        encoded = codec.encode(
            msg,
            on_stream_encode=lambda sid, src, kind: encode_seen.append(sid),
        )
        # Only the one StreamResource is registered.
        assert len(encode_seen) == 1

        decode_seen: List[str] = []
        result = codec.decode(
            encoded,
            on_stream_decode=lambda v: decode_seen.append(v["id"]) or "<proxy>",
        )

        # Same stream_id appears on both sides.
        assert decode_seen == encode_seen

        # Bytes preserved through nested containers.
        l2 = result["level1"]["level2"]
        assert l2["bytes"] == b"binary"
        assert l2["list"][0]["nested_bytes"] == b"x"
        assert l2["list"][1] == [b"y", b"z"]
        assert l2["scalar"] == 42
        # Stream replaced by proxy.
        assert l2["stream"] == "<proxy>"
