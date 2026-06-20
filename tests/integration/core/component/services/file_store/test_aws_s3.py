"""Integration tests for the aws-s3 file-store driver using moto."""

from __future__ import annotations

import asyncio
import io
import os
from typing import Any, AsyncIterator

import pytest
from pydantic import TypeAdapter

pytest.importorskip("moto")
pytest.importorskip("aioboto3")

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.file_store.drivers.aws_s3 import (
    AwsS3FileStoreAction,
    AwsS3FileStoreService,
    S3Location,
)
from mindor.core.utils.streaming.stream import StreamResource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import AwsS3FileStoreActionConfig


ActionAdapter = TypeAdapter(AwsS3FileStoreActionConfig)

BUCKET = "test-bucket"
REGION = "us-east-1"


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
            # clean the bucket so each test starts fresh against the shared server
            try:
                response = await client.list_objects_v2(Bucket=BUCKET)
                for obj in response.get("Contents", []) or []:
                    await client.delete_object(Bucket=BUCKET, Key=obj["Key"])
                await client.delete_bucket(Bucket=BUCKET)
            except Exception:
                pass


def _action(config: dict) -> AwsS3FileStoreActionConfig:
    return ActionAdapter.validate_python(config)


def _ctx(input: dict | None = None) -> ComponentActionContext:
    return ComponentActionContext("run-test", input or {})


def _location(region: str | None = REGION, endpoint: str | None = None) -> S3Location:
    return S3Location(bucket=BUCKET, region=region, endpoint=endpoint)


def _make_action(client, config: dict, base_path: str | None = None) -> AwsS3FileStoreAction:
    # AwsS3FileStoreService normalizes base_path before passing it in; mirror that here.
    normalized = (base_path.rstrip("/") + "/") if base_path else None
    return AwsS3FileStoreAction(
        _action(config),
        client,
        location=_location(),
        base_path=normalized,
    )


async def _get_object_bytes(client, key: str) -> bytes:
    response = await client.get_object(Bucket=BUCKET, Key=key)
    async with response["Body"] as body:
        return await body.read()


class TestPut:
    @pytest.mark.anyio
    async def test_put_bytes(self, s3_client):
        action = _make_action(s3_client, {"method": "put", "path": "data/file.bin", "source": b"hello world"})
        result = await action.run(_ctx())
        assert result["path"] == "data/file.bin"
        assert result["size"] == 11
        assert result["url"] == f"https://{BUCKET}.s3.{REGION}.amazonaws.com/data/file.bin"

        body = await _get_object_bytes(s3_client, "data/file.bin")
        assert body == b"hello world"

    @pytest.mark.anyio
    async def test_put_str_encodes_utf8(self, s3_client):
        action = _make_action(s3_client, {"method": "put", "path": "msg.txt", "source": "안녕"})
        result = await action.run(_ctx())
        assert result["size"] == len("안녕".encode("utf-8"))
        assert result["content_type"] == "text/plain"

        body = await _get_object_bytes(s3_client, "msg.txt")
        assert body.decode("utf-8") == "안녕"

    @pytest.mark.anyio
    async def test_put_content_type_from_extension(self, s3_client):
        action = _make_action(s3_client, {"method": "put", "path": "img.png", "source": b"fakepng"})
        result = await action.run(_ctx())
        assert result["content_type"] == "image/png"

        head = await s3_client.head_object(Bucket=BUCKET, Key="img.png")
        assert head["ContentType"] == "image/png"

    @pytest.mark.anyio
    async def test_put_explicit_content_type_wins(self, s3_client):
        action = _make_action(s3_client, {
            "method": "put",
            "path": "data.bin",
            "source": b"x",
            "content_type": "application/custom",
        })
        result = await action.run(_ctx())
        assert result["content_type"] == "application/custom"

    @pytest.mark.anyio
    async def test_put_with_metadata(self, s3_client):
        action = _make_action(s3_client, {
            "method": "put",
            "path": "obj.bin",
            "source": b"x",
            "metadata": {"workflow": "abc"},
        })
        await action.run(_ctx())

        head = await s3_client.head_object(Bucket=BUCKET, Key="obj.bin")
        assert head["Metadata"]["workflow"] == "abc"

    @pytest.mark.anyio
    async def test_put_with_base_path(self, s3_client):
        action = _make_action(s3_client, {"method": "put", "path": "file.bin", "source": b"x"}, base_path="prefix")
        result = await action.run(_ctx())
        # relative path stays clean; object key carries the prefix
        assert result["path"] == "file.bin"
        assert "prefix/file.bin" in result["url"]

        body = await _get_object_bytes(s3_client, "prefix/file.bin")
        assert body == b"x"

    @pytest.mark.anyio
    async def test_put_stream_resource(self, s3_client):
        action = _make_action(s3_client, {"method": "put", "path": "stream.bin", "source": "${input.s}"})
        await action.run(_ctx({"s": BytesStreamResource(b"streamed data")}))

        body = await _get_object_bytes(s3_client, "stream.bin")
        assert body == b"streamed data"

    @pytest.mark.anyio
    async def test_put_multipart_when_size_unknown(self, s3_client):
        """StreamResource has no known size, so multipart path is exercised even on tiny payloads."""
        class TinyStream(StreamResource):
            def __init__(self):
                super().__init__(None, None)
                self._chunks = [b"abc", b"def", b"ghij"]

            async def close(self):
                pass

            async def _iterate_stream(self):
                for chunk in self._chunks:
                    yield chunk

        action = _make_action(s3_client, {"method": "put", "path": "mp.bin", "source": "${input.s}"})
        result = await action.run(_ctx({"s": TinyStream()}))
        assert result["size"] == 10

        body = await _get_object_bytes(s3_client, "mp.bin")
        assert body == b"abcdefghij"


class TestGet:
    @pytest.mark.anyio
    async def test_get_default_returns_bytes(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"hello")

        action = _make_action(s3_client, {"method": "get", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result["content"] == b"hello"
        assert result["size"] == 5
        assert result["path"] == "f.bin"
        assert result["modified_at"] is not None
        assert "save_to" not in result

    @pytest.mark.anyio
    async def test_get_with_save_to(self, tmp_path, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"saved to disk")

        dest = str(tmp_path / "out.bin")
        action = _make_action(s3_client, {"method": "get", "path": "f.bin", "save_to": dest})
        result = await action.run(_ctx())
        assert result["save_to"] == dest
        assert "content" not in result
        with open(dest, "rb") as f:
            assert f.read() == b"saved to disk"

    @pytest.mark.anyio
    async def test_get_save_to_directory_uses_basename(self, tmp_path, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="reports/q4.pdf", Body=b"report-bytes")

        dest_dir = tmp_path / "downloads"
        dest_dir.mkdir()
        action = _make_action(s3_client, {"method": "get", "path": "reports/q4.pdf", "save_to": str(dest_dir)})
        result = await action.run(_ctx())
        expected = str(dest_dir / "q4.pdf")
        assert result["save_to"] == expected
        with open(expected, "rb") as f:
            assert f.read() == b"report-bytes"

    @pytest.mark.anyio
    async def test_get_with_streaming(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"streamed")

        action = _make_action(s3_client, {"method": "get", "path": "f.bin", "streaming": True})
        result = await action.run(_ctx())
        stream = result["content"]
        assert isinstance(stream, StreamResource)

        chunks = []
        async with stream:
            async for chunk in stream:
                chunks.append(chunk)
        assert b"".join(chunks) == b"streamed"

    @pytest.mark.anyio
    async def test_get_with_base_path(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="prefix/f.bin", Body=b"prefixed")

        action = _make_action(s3_client, {"method": "get", "path": "f.bin"}, base_path="prefix")
        result = await action.run(_ctx())
        assert result["content"] == b"prefixed"
        assert result["path"] == "f.bin"  # relative, not the full object key

    @pytest.mark.anyio
    async def test_get_missing_raises(self, s3_client):
        from botocore.exceptions import ClientError
        action = _make_action(s3_client, {"method": "get", "path": "missing.bin"})
        with pytest.raises(ClientError):
            await action.run(_ctx())


class TestDelete:
    @pytest.mark.anyio
    async def test_delete_existing(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"x")

        action = _make_action(s3_client, {"method": "delete", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin"}

        # confirm it's gone
        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            await s3_client.head_object(Bucket=BUCKET, Key="f.bin")

    @pytest.mark.anyio
    async def test_delete_missing_is_idempotent(self, s3_client):
        action = _make_action(s3_client, {"method": "delete", "path": "nope.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "nope.bin"}


class TestExists:
    @pytest.mark.anyio
    async def test_exists_true(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"")

        action = _make_action(s3_client, {"method": "exists", "path": "f.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "f.bin", "exists": True}

    @pytest.mark.anyio
    async def test_exists_false(self, s3_client):
        action = _make_action(s3_client, {"method": "exists", "path": "missing.bin"})
        result = await action.run(_ctx())
        assert result == {"path": "missing.bin", "exists": False}


class TestList:
    @pytest.mark.anyio
    async def test_list_all(self, s3_client):
        for key in ["a/1.txt", "a/2.txt", "b/3.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/2.txt", "b/3.txt"]
        assert result["count"] == 3
        assert result["next_token"] is None
        for item in result["items"]:
            assert item["size"] == 1
            assert item["url"].startswith(f"https://{BUCKET}.s3.")
            assert item["modified_at"] is not None

    @pytest.mark.anyio
    async def test_list_with_prefix(self, s3_client):
        for key in ["images/1.png", "images/2.png", "logs/a.log"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "path": "images/", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/1.png", "images/2.png"]

    @pytest.mark.anyio
    async def test_list_strips_base_path_in_relative(self, s3_client):
        for key in ["prefix/a.bin", "prefix/sub/b.bin"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": True}, base_path="prefix")
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.bin", "sub/b.bin"]

    @pytest.mark.anyio
    async def test_list_pagination(self, s3_client):
        for i in range(5):
            await s3_client.put_object(Bucket=BUCKET, Key=f"f{i}.bin", Body=b"x")

        action = _make_action(s3_client, {"method": "list", "max_result_count": 2})
        result = await action.run(_ctx())
        assert result["count"] == 2
        assert result["next_token"] is not None

        action2 = _make_action(s3_client, {"method": "list", "max_result_count": 2, "next_token": result["next_token"]})
        result2 = await action2.run(_ctx())
        assert result2["count"] == 2

    @pytest.mark.anyio
    async def test_list_empty(self, s3_client):
        action = _make_action(s3_client, {"method": "list"})
        result = await action.run(_ctx())
        assert result["items"] == []
        assert result["count"] == 0


class TestListRecursive:
    @pytest.mark.anyio
    async def test_default_is_non_recursive(self, s3_client):
        """Without `recursive`, only objects directly under the prefix are returned."""
        for key in ["top.txt", "sub/nested.txt", "sub/deeper/x.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["top.txt"]

    @pytest.mark.anyio
    async def test_recursive_false_explicit(self, s3_client):
        for key in ["root.txt", "a/mid.txt", "a/b/deep.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": False})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["root.txt"]

    @pytest.mark.anyio
    async def test_recursive_true_returns_all_levels(self, s3_client):
        for key in ["a/1.txt", "a/b/2.txt", "a/b/c/3.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": True})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/b/2.txt", "a/b/c/3.txt"]

    @pytest.mark.anyio
    async def test_recursive_false_under_prefix(self, s3_client):
        """`recursive: false` with a prefix uses S3 delimiter to scope to one level."""
        for key in ["images/a.png", "images/b.png", "images/thumbs/c.png"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "path": "images/"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/a.png", "images/b.png"]

    @pytest.mark.anyio
    async def test_recursive_via_string_value(self, s3_client):
        """`recursive` accepts string values via variable interpolation."""
        for key in ["top.txt", "sub/nested.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": "${input.flag}"})
        result = await action.run(_ctx({"flag": True}))
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["sub/nested.txt", "top.txt"]


class TestListPattern:
    @pytest.mark.anyio
    async def test_pattern_extension_filter(self, s3_client):
        for key in ["a.png", "b.jpg", "c.png", "d.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "*.png"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.png", "c.png"]

    @pytest.mark.anyio
    async def test_pattern_no_match(self, s3_client):
        for key in ["a.txt", "b.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "*.png"})
        result = await action.run(_ctx())
        assert result["items"] == []
        assert result["count"] == 0

    @pytest.mark.anyio
    async def test_pattern_with_prefix_match(self, s3_client):
        for key in ["report_2024.pdf", "report_2025.pdf", "summary.pdf", "report_2024.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "report_*.pdf"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["report_2024.pdf", "report_2025.pdf"]

    @pytest.mark.anyio
    async def test_pattern_character_class(self, s3_client):
        for key in ["f1.bin", "f2.bin", "f3.bin", "fa.bin", "g1.bin"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "f[12].bin"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["f1.bin", "f2.bin"]

    @pytest.mark.anyio
    async def test_pattern_case_sensitive(self, s3_client):
        """Pattern matching is case-sensitive."""
        for key in ["A.TXT", "b.txt"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "*.txt"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["b.txt"]

    @pytest.mark.anyio
    async def test_pattern_via_string_interpolation(self, s3_client):
        for key in ["a.png", "b.jpg"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "pattern": "${input.ext}"})
        result = await action.run(_ctx({"ext": "*.jpg"}))
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["b.jpg"]


class TestListRecursivePattern:
    @pytest.mark.anyio
    async def test_recursive_with_extension_pattern(self, s3_client):
        """`*.png` only matches keys at the root — `*` does not cross `/`."""
        for key in ["root.png", "a/1.png", "a/2.txt", "a/b/3.png", "a/b/4.jpg"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": True, "pattern": "*.png"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["root.png"]

    @pytest.mark.anyio
    async def test_recursive_with_glob_star_star(self, s3_client):
        """`**/*.png` matches `.png` keys at any depth below the root."""
        for key in ["root.png", "a/1.png", "a/2.txt", "a/b/3.png"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(s3_client, {"method": "list", "recursive": True, "pattern": "**/*.png"})
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.png", "a/b/3.png"]

    @pytest.mark.anyio
    async def test_pattern_under_base_path(self, s3_client):
        """Pattern is matched against the path *relative to* base_path."""
        for key in ["prefix/a.png", "prefix/b.jpg", "prefix/sub/c.png"]:
            await s3_client.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        action = _make_action(
            s3_client,
            {"method": "list", "recursive": True, "pattern": "*.png"},
            base_path="prefix",
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        # After base_path stripping, the relative path is "a.png"/"b.jpg"/"sub/c.png".
        # `*.png` matches only the root-level "a.png".
        assert paths == ["a.png"]


class TestRoundTrip:
    @pytest.mark.anyio
    async def test_put_then_get_then_delete(self, s3_client):
        put = _make_action(s3_client, {"method": "put", "path": "round.bin", "source": b"roundtrip"})
        put_result = await put.run(_ctx())
        assert put_result["path"] == "round.bin"

        get = _make_action(s3_client, {"method": "get", "path": "round.bin"})
        get_result = await get.run(_ctx())
        assert get_result["content"] == b"roundtrip"

        delete = _make_action(s3_client, {"method": "delete", "path": "round.bin"})
        del_result = await delete.run(_ctx())
        assert del_result == {"path": "round.bin"}

        exists = _make_action(s3_client, {"method": "exists", "path": "round.bin"})
        ex_result = await exists.run(_ctx())
        assert ex_result["exists"] is False


class TestUrlConstruction:
    @pytest.mark.anyio
    async def test_url_with_endpoint(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"x")

        action = AwsS3FileStoreAction(
            _action({"method": "get", "path": "f.bin"}),
            s3_client,
            location=_location(endpoint="https://minio.local:9000"),
        )
        result = await action.run(_ctx())
        assert result["url"] == "https://minio.local:9000/test-bucket/f.bin"

    @pytest.mark.anyio
    async def test_url_without_region(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="f.bin", Body=b"x")

        action = AwsS3FileStoreAction(
            _action({"method": "get", "path": "f.bin"}),
            s3_client,
            location=_location(region=None),
        )
        result = await action.run(_ctx())
        assert result["url"] == f"https://s3.amazonaws.com/{BUCKET}/f.bin"

    @pytest.mark.anyio
    async def test_url_percent_encoded(self, s3_client):
        await s3_client.put_object(Bucket=BUCKET, Key="space file.bin", Body=b"x")

        action = AwsS3FileStoreAction(
            _action({"method": "get", "path": "space file.bin"}),
            s3_client,
            location=_location(),
        )
        result = await action.run(_ctx())
        assert "space%20file.bin" in result["url"]
