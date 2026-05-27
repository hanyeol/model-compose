"""Tests for queue blob serialize/deserialize, marker validation, and cleanup contracts."""

import io

import pytest
from starlette.datastructures import UploadFile

from mindor.core.controller.queue.serialize import (
    serialize_input,
    deserialize_input,
)
from mindor.core.controller.queue.errors import (
    BlobNotFoundError,
    BlobCorruptedError,
    BlobTooLargeError,
)


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# ---- Fakes ----

class FakeRedis:
    """In-memory stand-in for redis.asyncio.Redis used by serialize/deserialize."""

    def __init__(self):
        self.store = {}
        self.ttls = {}
        self.getdel_supported = True
        self.cleanup_raises = False

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    async def execute_command(self, cmd, key):
        if cmd != "GETDEL":
            raise RuntimeError(f"unexpected command {cmd}")
        if not self.getdel_supported:
            from redis.exceptions import ResponseError
            raise ResponseError("unknown command 'GETDEL'")
        return self.store.pop(key, None)

    async def delete(self, *keys):
        if self.cleanup_raises:
            raise RuntimeError("simulated redis connection drop")
        for k in keys:
            self.store.pop(k, None)
            self.ttls.pop(k, None)

    def pipeline(self, transaction=True):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def get(self, key):
        self.ops.append(("get", key))

    def delete(self, key):
        self.ops.append(("delete", key))

    async def execute(self):
        results = []
        for op, key in self.ops:
            if op == "get":
                results.append(self.client.store.get(key))
            elif op == "delete":
                self.client.store.pop(key, None)
                results.append(1)
        return results


# ---- Helpers ----

def make_upload_file(content: bytes, filename: str = "x.bin", content_type: str = "application/octet-stream") -> UploadFile:
    file = UploadFile(file=io.BytesIO(content), filename=filename, headers={"content-type": content_type})
    return file


async def read_upload(uf: UploadFile) -> bytes:
    return await uf.read()


# ---- Serialize / deserialize round-trip ----

class TestRoundTrip:

    @pytest.mark.anyio
    async def test_bytes_payload(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"

        serialized, keys = await serialize_input({"img": b"hello"}, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)

        assert len(keys) == 1
        assert serialized["img"]["origin_type"] == "bytes"
        assert serialized["img"]["size"] == 5
        assert client.ttls[keys[0]] == 60

        restored = await deserialize_input(serialized, client, prefix)
        assert await read_upload(restored["img"]) == b"hello"
        assert client.store == {}

    @pytest.mark.anyio
    async def test_upload_file_payload(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        upload = make_upload_file(b"image-bytes", filename="photo.png", content_type="image/png")

        serialized, keys = await serialize_input({"file": upload}, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        assert serialized["file"]["origin_type"] == "upload_file"
        assert serialized["file"]["filename"] == "photo.png"
        assert serialized["file"]["content_type"] == "image/png"

        restored = await deserialize_input(serialized, client, prefix)
        assert restored["file"].filename == "photo.png"
        assert restored["file"].content_type == "image/png"
        assert await read_upload(restored["file"]) == b"image-bytes"

    @pytest.mark.anyio
    async def test_nested_structure(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        payload = {
            "files": [b"a", b"b"],
            "meta": {"nested": [{"inner": b"c"}]},
            "scalar": 42,
            "label": "hello",
        }

        serialized, keys = await serialize_input(payload, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        assert len(keys) == 3
        assert serialized["scalar"] == 42
        assert serialized["label"] == "hello"

        restored = await deserialize_input(serialized, client, prefix)
        assert await read_upload(restored["files"][0]) == b"a"
        assert await read_upload(restored["files"][1]) == b"b"
        assert await read_upload(restored["meta"]["nested"][0]["inner"]) == b"c"

    @pytest.mark.anyio
    async def test_no_binary_passthrough(self):
        client = FakeRedis()
        serialized, keys = await serialize_input({"a": 1, "b": "x"}, client, "p:", ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        assert keys == []
        assert serialized == {"a": 1, "b": "x"}
        assert client.store == {}

    @pytest.mark.anyio
    async def test_tuple_input_normalized_to_list(self):
        """Renderer 컨벤션과 동일: list/tuple은 한 분기로 처리되어 결과는 list로 정규화."""
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        serialized, keys = await serialize_input((b"a", b"b"), client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        assert isinstance(serialized, list)
        assert len(keys) == 2


# ---- Marker validation ----

class TestMarkerValidation:

    @pytest.mark.anyio
    async def test_user_dict_with_unrelated_key_field_passes_through(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        # 사용자가 우연히 "key" 필드를 가진 dict를 입력에 넣어도, prefix가 다르면 그대로 통과해야 함.
        user_input = {"config": {"key": "user-defined-key", "comment": "i set this myself"}}

        serialized, keys = await serialize_input(user_input, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        assert keys == []
        restored = await deserialize_input(serialized, client, prefix)
        assert restored == user_input

    @pytest.mark.anyio
    async def test_non_string_key_field_passes_through(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        # "key" 필드가 문자열이 아닌 경우 (예: 사용자가 정수 ID를 넣음)
        user_input = {"x": {"key": 12345, "label": "not a blob ref"}}
        restored = await deserialize_input(user_input, client, prefix)
        assert restored == user_input


# ---- Security: key ownership ----

class TestKeyOwnership:

    @pytest.mark.anyio
    async def test_mismatched_prefix_does_not_touch_redis(self):
        """deserialize 시 key_prefix가 다르면 blob ref로 해석되지 않고 일반 dict로 통과."""
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        serialized, _ = await serialize_input({"img": b"hi"}, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)

        # 다른 prefix로 해석을 시도하면 dict로 통과 — Redis 조회 자체가 일어나지 않음.
        restored = await deserialize_input(serialized, client, "OTHER:prefix:")
        assert isinstance(restored["img"], dict)
        assert restored["img"]["key"].startswith(prefix)
        # 원본 blob도 그대로 남아 있어야 함
        assert len(client.store) == 1

    @pytest.mark.anyio
    async def test_foreign_prefix_in_user_input_passes_through(self):
        """사용자 입력에 우리 prefix가 아닌 'key' 필드가 들어와도 그대로 통과해야 하며, 다른 키가 영향받지 않아야 함."""
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        client.store["OTHER:prefix:victim"] = b"victim-data"

        user_input = {
            "ref": {
                "key": "OTHER:prefix:victim",
                "filename": "x",
                "content_type": "x",
                "origin_type": "bytes",
                "size": 11,
            }
        }

        restored = await deserialize_input(user_input, client, prefix)
        assert restored == user_input
        # victim key는 보존되어야 함
        assert client.store["OTHER:prefix:victim"] == b"victim-data"


# ---- Error surfaces ----

class TestErrors:

    @pytest.mark.anyio
    async def test_too_large_cleans_up(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"

        with pytest.raises(BlobTooLargeError):
            await serialize_input({"big": b"X" * 100}, client, prefix, ttl_seconds=60, max_blob_size=50)

        # 부분적으로 저장된 키가 없어야 함
        assert client.store == {}

    @pytest.mark.anyio
    async def test_too_large_after_some_success_cleans_up_all(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"

        with pytest.raises(BlobTooLargeError):
            await serialize_input(
                {"ok": b"small", "fail": b"X" * 100},
                client,
                prefix,
                ttl_seconds=60,
                max_blob_size=50,
            )

        assert client.store == {}

    @pytest.mark.anyio
    async def test_max_blob_size_none_disables_check(self):
        """max_blob_size=None은 size limit 비활성화."""
        client = FakeRedis()
        prefix = "q:wf:run:blob:"

        # max_blob_size를 None으로 두면 아무리 큰 payload도 통과해야 함.
        serialized, keys = await serialize_input(
            {"huge": b"X" * (1024 * 1024)},  # 1MB
            client,
            prefix,
            ttl_seconds=60,
            max_blob_size=None,
        )
        assert len(keys) == 1
        assert serialized["huge"]["size"] == 1024 * 1024

    @pytest.mark.anyio
    async def test_blob_not_found(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        marker = {
            "img": {
                "key": prefix + "missing",
                "filename": "x",
                "content_type": "x",
                "origin_type": "bytes",
                "size": 5,
            }
        }
        with pytest.raises(BlobNotFoundError) as exc:
            await deserialize_input(marker, client, prefix)
        assert "missing or expired" in str(exc.value)
        assert prefix + "missing" in str(exc.value)

    @pytest.mark.anyio
    async def test_blob_corrupted(self):
        client = FakeRedis()
        prefix = "q:wf:run:blob:"
        client.store[prefix + "corrupt"] = b"abc"
        marker = {
            "img": {
                "key": prefix + "corrupt",
                "filename": "x",
                "content_type": "x",
                "origin_type": "bytes",
                "size": 999,
            }
        }
        with pytest.raises(BlobCorruptedError):
            await deserialize_input(marker, client, prefix)


# ---- GETDEL fallback ----

class TestGetdelFallback:

    @pytest.mark.anyio
    async def test_getdel_unsupported_falls_back_to_pipeline(self):
        client = FakeRedis()
        client.getdel_supported = False
        prefix = "q:wf:run:blob:"

        serialized, _ = await serialize_input({"img": b"hello"}, client, prefix, ttl_seconds=60, max_blob_size=10 * 1024 * 1024)
        restored = await deserialize_input(serialized, client, prefix)
        assert await read_upload(restored["img"]) == b"hello"
        assert client.store == {}


