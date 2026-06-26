"""Integration tests for the azure-blob file-store driver using Azurite."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter

pytest.importorskip("azure.storage.blob")
pytest.importorskip("azure.storage.blob.aio")

from azure.storage.blob.aio import BlobServiceClient

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.file_store.drivers.azure_blob import (
    AzureBlobFileStoreAction,
    AzureBlobLocation,
)
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import AzureBlobFileStoreActionConfig


ActionAdapter = TypeAdapter(AzureBlobFileStoreActionConfig)

CONTAINER = "test-container"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def azure_clients(azurite_connection_string):
    """Yield (service_client, container_client) wired up against Azurite."""
    service_client = BlobServiceClient.from_connection_string(azurite_connection_string)
    container_client = service_client.get_container_client(CONTAINER)

    try:
        await container_client.create_container()
    except Exception:
        # already exists from a previous test in the module — fine
        pass

    try:
        yield service_client, container_client
    finally:
        # best-effort cleanup of all blobs in the container
        try:
            async for blob in container_client.list_blobs():
                try:
                    await container_client.delete_blob(blob.name)
                except Exception:
                    pass
        except Exception:
            pass
        await container_client.close()
        await service_client.close()


def _action(config: dict) -> AzureBlobFileStoreActionConfig:
    return ActionAdapter.validate_python(config)


def _ctx(input: dict | None = None) -> ComponentActionContext:
    return ComponentActionContext("run-test", input or {})


def _make_action(clients, config: dict, base_path: str | None = None) -> AzureBlobFileStoreAction:
    _, container_client = clients
    normalized = (base_path.rstrip("/") + "/") if base_path else None
    return AzureBlobFileStoreAction(
        _action(config),
        container_client,
        location=AzureBlobLocation(container=CONTAINER),
        base_path=normalized,
    )


async def _download_blob(container_client, blob_name: str) -> bytes:
    blob_client = container_client.get_blob_client(blob_name)
    downloader = await blob_client.download_blob()
    return await downloader.readall()


class TestPut:
    @pytest.mark.anyio
    async def test_put_bytes(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {"method": "put", "path": "data/file.bin", "source": b"hello world"})
        result = await action.run(_ctx())
        assert result["path"] == "data/file.bin"
        assert result["size"] == 11

        body = await _download_blob(container, "data/file.bin")
        assert body == b"hello world"

    @pytest.mark.anyio
    async def test_put_str_encodes_utf8(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {"method": "put", "path": "msg.txt", "source": "안녕"})
        result = await action.run(_ctx())
        assert result["size"] == len("안녕".encode("utf-8"))
        assert result["content_type"] == "text/plain"

        body = await _download_blob(container, "msg.txt")
        assert body.decode("utf-8") == "안녕"

    @pytest.mark.anyio
    async def test_put_content_type_from_extension(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {"method": "put", "path": "img.png", "source": b"fakepng"})
        result = await action.run(_ctx())
        assert result["content_type"] == "image/png"

        blob_client = container.get_blob_client("img.png")
        props = await blob_client.get_blob_properties()
        assert props.content_settings.content_type == "image/png"

    @pytest.mark.anyio
    async def test_put_with_metadata(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {
            "method": "put",
            "path": "obj.bin",
            "source": b"x",
            "metadata": {"workflow": "abc"},
        })
        await action.run(_ctx())

        blob_client = container.get_blob_client("obj.bin")
        props = await blob_client.get_blob_properties()
        assert props.metadata["workflow"] == "abc"

    @pytest.mark.anyio
    async def test_put_with_base_path(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {"method": "put", "path": "file.bin", "source": b"x"}, base_path="prefix")
        result = await action.run(_ctx())
        assert result["path"] == "file.bin"
        assert "prefix/file.bin" in result["url"]

        body = await _download_blob(container, "prefix/file.bin")
        assert body == b"x"

    @pytest.mark.anyio
    async def test_put_stream_resource(self, azure_clients):
        _, container = azure_clients
        action = _make_action(azure_clients, {"method": "put", "path": "stream.bin", "source": "${input.s}"})
        await action.run(_ctx({"s": BytesStreamResource(b"streamed data")}))

        body = await _download_blob(container, "stream.bin")
        assert body == b"streamed data"

    @pytest.mark.anyio
    async def test_put_multipart_when_size_unknown(self, azure_clients):
        """StreamResource with no known size exercises the block-list multipart path."""
        _, container = azure_clients

        class TinyStream(StreamResource):
            def __init__(self):
                super().__init__(None, None)
                self._chunks = [b"abc", b"def", b"ghij"]

            async def close(self):
                pass

            async def _iterate_stream(self):
                for chunk in self._chunks:
                    yield chunk

        action = _make_action(azure_clients, {"method": "put", "path": "mp.bin", "source": "${input.s}"})
        result = await action.run(_ctx({"s": TinyStream()}))
        assert result["size"] == 10

        body = await _download_blob(container, "mp.bin")
        assert body == b"abcdefghij"


class TestGet:
    @pytest.mark.anyio
    async def test_get_default_returns_bytes(self, azure_clients):
        _, container = azure_clients
        await container.upload_blob("f.bin", b"hello", overwrite=True)

        action = _make_action(azure_clients, {"method": "get", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result["content"] == b"hello"
        assert result["size"] == 5
        assert result["path"] == "f.bin"
        assert result["modified_at"] is not None
        assert "save_to" not in result

    @pytest.mark.anyio
    async def test_get_with_save_to(self, tmp_path, azure_clients):
        _, container = azure_clients
        await container.upload_blob("f.bin", b"saved to disk", overwrite=True)

        dest = str(tmp_path / "out.bin")
        action = _make_action(azure_clients, {"method": "get", "path": "f.bin", "save_to": dest})
        result = await action.run(_ctx())
        assert result["save_to"] == dest
        assert "content" not in result
        with open(dest, "rb") as f:
            assert f.read() == b"saved to disk"

    @pytest.mark.anyio
    async def test_get_with_streaming(self, azure_clients):
        _, container = azure_clients
        await container.upload_blob("f.bin", b"streamed", overwrite=True)

        action = _make_action(azure_clients, {"method": "get", "path": "f.bin", "streaming": True})
        result = await action.run(_ctx())
        stream = result["content"]
        assert isinstance(stream, StreamResource)

        chunks = []
        async with stream:
            async for chunk in stream:
                chunks.append(chunk)
        assert b"".join(chunks) == b"streamed"

    @pytest.mark.anyio
    async def test_get_with_base_path(self, azure_clients):
        _, container = azure_clients
        await container.upload_blob("prefix/f.bin", b"prefixed", overwrite=True)

        action = _make_action(azure_clients, {"method": "get", "path": "f.bin"}, base_path="prefix")
        result = await action.run(_ctx())
        assert result["content"] == b"prefixed"
        assert result["path"] == "f.bin"


class TestDelete:
    @pytest.mark.anyio
    async def test_delete_existing(self, azure_clients):
        _, container = azure_clients
        await container.upload_blob("f.bin", b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "delete", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin"}


class TestExists:
    @pytest.mark.anyio
    async def test_exists_true(self, azure_clients):
        _, container = azure_clients
        await container.upload_blob("f.bin", b"", overwrite=True)

        action = _make_action(azure_clients, {"method": "exists", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin", "exists": True}

    @pytest.mark.anyio
    async def test_exists_false(self, azure_clients):
        action = _make_action(azure_clients, {"method": "exists", "path": "missing.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "missing.bin", "exists": False}


class TestList:
    @pytest.mark.anyio
    async def test_list_all_recursive(self, azure_clients):
        _, container = azure_clients
        for name in ["a/1.txt", "a/2.txt", "b/3.txt"]:
            await container.upload_blob(name, b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "list", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/2.txt", "b/3.txt"]

    @pytest.mark.anyio
    async def test_list_with_prefix(self, azure_clients):
        _, container = azure_clients
        for name in ["images/1.png", "images/2.png", "logs/a.log"]:
            await container.upload_blob(name, b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "list", "path": "images/", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/1.png", "images/2.png"]

    @pytest.mark.anyio
    async def test_list_strips_base_path(self, azure_clients):
        _, container = azure_clients
        for name in ["prefix/a.bin", "prefix/sub/b.bin"]:
            await container.upload_blob(name, b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "list", "recursive": True}, base_path="prefix")
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.bin", "sub/b.bin"]

    @pytest.mark.anyio
    async def test_list_non_recursive_skips_subdirectories(self, azure_clients):
        """Default `recursive: false` uses walk_blobs and skips BlobPrefix entries."""
        _, container = azure_clients
        for name in ["top.txt", "sub/nested.txt", "sub/deeper/x.txt"]:
            await container.upload_blob(name, b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "list"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["top.txt"]

    @pytest.mark.anyio
    async def test_list_pattern_filter(self, azure_clients):
        _, container = azure_clients
        for name in ["a.png", "b.jpg", "c.png", "d.txt"]:
            await container.upload_blob(name, b"x", overwrite=True)

        action = _make_action(azure_clients, {"method": "list", "pattern": "*.png"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.png", "c.png"]


class TestRoundTrip:
    @pytest.mark.anyio
    async def test_put_then_get_then_delete(self, azure_clients):
        put = _make_action(azure_clients, {"method": "put", "path": "round.bin", "source": b"roundtrip"})
        await put.run(_ctx())

        get = _make_action(azure_clients, {"method": "get", "path": "round.bin"})
        get_result = await get.run(_ctx())
        assert get_result["content"] == b"roundtrip"

        delete = _make_action(azure_clients, {"method": "delete", "path": "round.bin"})
        await delete.run(_ctx())

        exists = _make_action(azure_clients, {"method": "exists", "path": "round.bin"})
        ex_result = await exists.run(_ctx())
        assert ex_result["exists"] is False
