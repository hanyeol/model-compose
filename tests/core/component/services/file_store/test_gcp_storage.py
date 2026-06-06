"""Integration tests for the gcp-storage file-store driver using fake-gcs-server."""

from __future__ import annotations

import json

import aiohttp
import pytest
from pydantic import TypeAdapter

pytest.importorskip("gcloud.aio.storage")

from gcloud.aio.storage import Storage

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.file_store.drivers.gcp_storage import (
    GcpStorageFileStoreAction,
    GcsLocation,
)
from mindor.core.utils.streaming import BytesStreamResource, StreamResource
from mindor.dsl.schema.action import GcpStorageFileStoreActionConfig


pytest_plugins = ["tests._fixtures.gcp_storage"]


ActionAdapter = TypeAdapter(GcpStorageFileStoreActionConfig)

BUCKET = "test-bucket"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def gcs_client(fake_gcs_endpoint):
    """Create the test bucket and a Storage client pointed at the emulator."""
    # fake-gcs-server requires explicit bucket creation via its REST API.
    async with aiohttp.ClientSession() as init_session:
        async with init_session.post(
            f"{fake_gcs_endpoint}/storage/v1/b",
            json={"name": BUCKET},
        ) as response:
            # 200/409 are both fine — 409 means the bucket survived from a previous run.
            if response.status not in (200, 409):
                response.raise_for_status()

    session = aiohttp.ClientSession()
    client = Storage(session=session, api_root=fake_gcs_endpoint)

    try:
        yield client, fake_gcs_endpoint
    finally:
        # best-effort cleanup of all objects in the bucket
        try:
            listing = await client.list_objects(BUCKET)
            for blob in listing.get("items", []) or []:
                try:
                    await client.delete(BUCKET, blob["name"])
                except Exception:
                    pass
        except Exception:
            pass
        await client.close()
        await session.close()


def _action(config: dict) -> GcpStorageFileStoreActionConfig:
    return ActionAdapter.validate_python(config)


def _ctx(input: dict | None = None) -> ComponentActionContext:
    return ComponentActionContext("run-test", input or {})


def _make_action(client_pair, config: dict, base_path: str | None = None) -> GcpStorageFileStoreAction:
    client, endpoint = client_pair
    normalized = (base_path.rstrip("/") + "/") if base_path else None
    return GcpStorageFileStoreAction(
        _action(config),
        client,
        location=GcsLocation(bucket=BUCKET, endpoint=endpoint),
        base_path=normalized,
    )


class TestPut:
    @pytest.mark.anyio
    async def test_put_bytes(self, gcs_client):
        action = _make_action(gcs_client, {"method": "put", "path": "data/file.bin", "source": b"hello world"})
        result = await action.run(_ctx())
        assert result["path"] == "data/file.bin"
        assert result["size"] == 11

        client, _ = gcs_client
        body = await client.download(BUCKET, "data/file.bin")
        assert body == b"hello world"

    @pytest.mark.anyio
    async def test_put_str_encodes_utf8(self, gcs_client):
        action = _make_action(gcs_client, {"method": "put", "path": "msg.txt", "source": "안녕"})
        result = await action.run(_ctx())
        assert result["size"] == len("안녕".encode("utf-8"))
        assert result["content_type"] == "text/plain"

        client, _ = gcs_client
        body = await client.download(BUCKET, "msg.txt")
        assert body.decode("utf-8") == "안녕"

    @pytest.mark.anyio
    async def test_put_content_type_from_extension(self, gcs_client):
        action = _make_action(gcs_client, {"method": "put", "path": "img.png", "source": b"fakepng"})
        result = await action.run(_ctx())
        assert result["content_type"] == "image/png"

    @pytest.mark.anyio
    async def test_put_with_base_path(self, gcs_client):
        action = _make_action(gcs_client, {"method": "put", "path": "file.bin", "source": b"x"}, base_path="prefix")
        result = await action.run(_ctx())
        # relative path stays clean; object name carries the prefix
        assert result["path"] == "file.bin"
        assert "prefix/file.bin" in result["url"]

        client, _ = gcs_client
        body = await client.download(BUCKET, "prefix/file.bin")
        assert body == b"x"

    @pytest.mark.anyio
    async def test_put_stream_resource(self, gcs_client):
        action = _make_action(gcs_client, {"method": "put", "path": "stream.bin", "source": "${input.s}"})
        await action.run(_ctx({"s": BytesStreamResource(b"streamed data")}))

        client, _ = gcs_client
        body = await client.download(BUCKET, "stream.bin")
        assert body == b"streamed data"

    @pytest.mark.anyio
    async def test_put_multipart_when_size_unknown(self, gcs_client):
        """StreamResource with no known size exercises the resumable-upload path."""
        class TinyStream(StreamResource):
            def __init__(self):
                super().__init__(None, None)
                self._chunks = [b"abc", b"def", b"ghij"]

            async def close(self):
                pass

            async def _iterate_stream(self):
                for chunk in self._chunks:
                    yield chunk

        action = _make_action(gcs_client, {"method": "put", "path": "mp.bin", "source": "${input.s}"})
        result = await action.run(_ctx({"s": TinyStream()}))
        assert result["size"] == 10

        client, _ = gcs_client
        body = await client.download(BUCKET, "mp.bin")
        assert body == b"abcdefghij"


class TestGet:
    @pytest.mark.anyio
    async def test_get_default_returns_bytes(self, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "f.bin", b"hello")

        action = _make_action(gcs_client, {"method": "get", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result["content"] == b"hello"
        assert result["size"] == 5
        assert result["path"] == "f.bin"
        assert "save_to" not in result

    @pytest.mark.anyio
    async def test_get_with_save_to(self, tmp_path, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "f.bin", b"saved to disk")

        dest = str(tmp_path / "out.bin")
        action = _make_action(gcs_client, {"method": "get", "path": "f.bin", "save_to": dest})
        result = await action.run(_ctx())
        assert result["save_to"] == dest
        assert "content" not in result
        with open(dest, "rb") as f:
            assert f.read() == b"saved to disk"

    @pytest.mark.anyio
    async def test_get_with_streaming(self, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "f.bin", b"streamed")

        action = _make_action(gcs_client, {"method": "get", "path": "f.bin", "streaming": True})
        result = await action.run(_ctx())
        stream = result["content"]
        assert isinstance(stream, StreamResource)

        chunks = []
        async with stream:
            async for chunk in stream:
                chunks.append(chunk)
        assert b"".join(chunks) == b"streamed"

    @pytest.mark.anyio
    async def test_get_with_base_path(self, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "prefix/f.bin", b"prefixed")

        action = _make_action(gcs_client, {"method": "get", "path": "f.bin"}, base_path="prefix")
        result = await action.run(_ctx())
        assert result["content"] == b"prefixed"
        assert result["path"] == "f.bin"  # relative, not the full object name


class TestDelete:
    @pytest.mark.anyio
    async def test_delete_existing(self, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "f.bin", b"x")

        action = _make_action(gcs_client, {"method": "delete", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin"}


class TestExists:
    @pytest.mark.anyio
    async def test_exists_true(self, gcs_client):
        client, _ = gcs_client
        await client.upload(BUCKET, "f.bin", b"")

        action = _make_action(gcs_client, {"method": "exists", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin", "exists": True}

    @pytest.mark.anyio
    async def test_exists_false(self, gcs_client):
        action = _make_action(gcs_client, {"method": "exists", "path": "missing.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "missing.bin", "exists": False}


class TestList:
    @pytest.mark.anyio
    async def test_list_all_recursive(self, gcs_client):
        client, _ = gcs_client
        for key in ["a/1.txt", "a/2.txt", "b/3.txt"]:
            await client.upload(BUCKET, key, b"x")

        action = _make_action(gcs_client, {"method": "list", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/2.txt", "b/3.txt"]

    @pytest.mark.anyio
    async def test_list_with_prefix(self, gcs_client):
        client, _ = gcs_client
        for key in ["images/1.png", "images/2.png", "logs/a.log"]:
            await client.upload(BUCKET, key, b"x")

        action = _make_action(gcs_client, {"method": "list", "path": "images/", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/1.png", "images/2.png"]

    @pytest.mark.anyio
    async def test_list_strips_base_path(self, gcs_client):
        client, _ = gcs_client
        for key in ["prefix/a.bin", "prefix/sub/b.bin"]:
            await client.upload(BUCKET, key, b"x")

        action = _make_action(gcs_client, {"method": "list", "recursive": True}, base_path="prefix")
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.bin", "sub/b.bin"]

    @pytest.mark.anyio
    async def test_list_pattern_filter(self, gcs_client):
        client, _ = gcs_client
        for key in ["a.png", "b.jpg", "c.png", "d.txt"]:
            await client.upload(BUCKET, key, b"x")

        action = _make_action(gcs_client, {"method": "list", "pattern": "*.png"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.png", "c.png"]


class TestRoundTrip:
    @pytest.mark.anyio
    async def test_put_then_get_then_delete(self, gcs_client):
        put = _make_action(gcs_client, {"method": "put", "path": "round.bin", "source": b"roundtrip"})
        await put.run(_ctx())

        get = _make_action(gcs_client, {"method": "get", "path": "round.bin"})
        get_result = await get.run(_ctx())
        assert get_result["content"] == b"roundtrip"

        delete = _make_action(gcs_client, {"method": "delete", "path": "round.bin"})
        await delete.run(_ctx())

        exists = _make_action(gcs_client, {"method": "exists", "path": "round.bin"})
        ex_result = await exists.run(_ctx())
        assert ex_result["exists"] is False
