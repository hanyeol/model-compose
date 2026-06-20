"""Integration tests for the local file-store driver."""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any, AsyncIterator, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.file_store.drivers.local import (
    LocalFileStoreAction,
    LocalFileStoreService,
)
from mindor.core.utils.streaming.stream import StreamResource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import LocalFileStoreActionConfig
from mindor.dsl.schema.component import LocalFileStoreComponentConfig


ActionAdapter = TypeAdapter(LocalFileStoreActionConfig)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def base_path(tmp_path):
    return str(tmp_path / "storage")


def _action(config: dict) -> LocalFileStoreActionConfig:
    return ActionAdapter.validate_python(config)


def _ctx(input: dict | None = None) -> ComponentActionContext:
    return ComponentActionContext("run-test", input or {})


def _service(base_path: str) -> LocalFileStoreService:
    config = LocalFileStoreComponentConfig(
        type="file-store",
        driver="local",
        runtime={"type": "native"},
        base_path=base_path,
    )
    return LocalFileStoreService("test", config, daemon=False)


class TestPut:
    @pytest.mark.anyio
    async def test_put_bytes(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "data/file.bin", "source": b"hello world"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())

        assert result["path"] == "data/file.bin"
        assert result["size"] == 11
        assert result["url"].startswith("file://")

        physical = os.path.join(base_path, "data", "file.bin")
        with open(physical, "rb") as f:
            assert f.read() == b"hello world"

    @pytest.mark.anyio
    async def test_put_str_encodes_utf8(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "msg.txt", "source": "안녕"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["size"] == len("안녕".encode("utf-8"))
        assert result["content_type"] == "text/plain"

        with open(os.path.join(base_path, "msg.txt"), "rb") as f:
            assert f.read().decode("utf-8") == "안녕"

    @pytest.mark.anyio
    async def test_put_stream_resource(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "stream.bin", "source": "${input.stream}"}),
            os.path.abspath(base_path),
        )
        stream = BytesStreamResource(b"streamed data")
        result = await action.run(_ctx({"stream": stream}))
        assert result["size"] == len(b"streamed data")

        with open(os.path.join(base_path, "stream.bin"), "rb") as f:
            assert f.read() == b"streamed data"

    @pytest.mark.anyio
    async def test_put_creates_parent_dirs(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "a/b/c/file.bin", "source": b"x"}),
            os.path.abspath(base_path),
        )
        await action.run(_ctx())
        assert os.path.isfile(os.path.join(base_path, "a", "b", "c", "file.bin"))

    @pytest.mark.anyio
    async def test_put_content_type_from_extension(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "img.png", "source": b"fakepng"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["content_type"] == "image/png"

    @pytest.mark.anyio
    async def test_put_explicit_content_type_wins(self, base_path):
        action = LocalFileStoreAction(
            _action({
                "method": "put",
                "path": "data.bin",
                "source": b"x",
                "content_type": "application/custom",
            }),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["content_type"] == "application/custom"

    @pytest.mark.anyio
    async def test_put_rejects_traversal(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "../escape.bin", "source": b"x"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_put_rejects_absolute_path(self, base_path):
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "/etc/passwd", "source": b"x"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_put_atomic_rename_on_failure(self, base_path):
        """If the source iteration fails, no partial file should remain."""
        class FailingStream(StreamResource):
            def __init__(self):
                super().__init__(None, None)

            async def close(self):
                pass

            async def _iterate_stream(self):
                yield b"partial"
                raise RuntimeError("boom")

        action = LocalFileStoreAction(
            _action({"method": "put", "path": "partial.bin", "source": "${input.s}"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(RuntimeError, match="boom"):
            await action.run(_ctx({"s": FailingStream()}))

        target = os.path.join(base_path, "partial.bin")
        tmp = target + ".tmp"
        assert not os.path.exists(target)
        assert not os.path.exists(tmp)


class TestGet:
    @pytest.mark.anyio
    async def test_get_default_returns_bytes(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"hello")

        action = LocalFileStoreAction(
            _action({"method": "get", "path": "f.bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["content"] == b"hello"
        assert result["size"] == 5
        assert result["path"] == "f.bin"
        assert result["modified_at"] is not None
        assert "save_to" not in result

    @pytest.mark.anyio
    async def test_get_with_save_to(self, tmp_path, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"saved to disk")

        dest = str(tmp_path / "out.bin")
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "f.bin", "save_to": dest}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["save_to"] == dest
        assert "content" not in result
        with open(dest, "rb") as f:
            assert f.read() == b"saved to disk"

    @pytest.mark.anyio
    async def test_get_with_streaming(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"streamed")

        action = LocalFileStoreAction(
            _action({"method": "get", "path": "f.bin", "streaming": True}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        stream = result["content"]
        assert isinstance(stream, StreamResource)

        chunks = []
        async with stream:
            async for chunk in stream:
                chunks.append(chunk)
        assert b"".join(chunks) == b"streamed"

    @pytest.mark.anyio
    async def test_get_missing_file_raises(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "missing.bin"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(FileNotFoundError):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_get_save_to_creates_missing_parent(self, tmp_path, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"x")

        nonexistent_dir = str(tmp_path / "nope" / "deeper")
        dest = os.path.join(nonexistent_dir, "out.bin")
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "f.bin", "save_to": dest}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["save_to"] == dest
        with open(dest, "rb") as f:
            assert f.read() == b"x"

    @pytest.mark.anyio
    async def test_get_save_to_directory_uses_basename(self, tmp_path, base_path):
        nested_src = os.path.join(base_path, "reports")
        os.makedirs(nested_src, exist_ok=True)
        with open(os.path.join(nested_src, "q4.pdf"), "wb") as f:
            f.write(b"report-bytes")

        dest_dir = tmp_path / "downloads"
        dest_dir.mkdir()
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "reports/q4.pdf", "save_to": str(dest_dir)}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        expected = str(dest_dir / "q4.pdf")
        assert result["save_to"] == expected
        with open(expected, "rb") as f:
            assert f.read() == b"report-bytes"


class TestDelete:
    @pytest.mark.anyio
    async def test_delete_existing(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        physical = os.path.join(base_path, "f.bin")
        with open(physical, "wb") as f:
            f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "delete", "path": "f.bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result == {"path": "f.bin"}
        assert not os.path.exists(physical)

    @pytest.mark.anyio
    async def test_delete_missing_is_idempotent(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "delete", "path": "missing.bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result == {"path": "missing.bin"}


class TestExists:
    @pytest.mark.anyio
    async def test_exists_true(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"")

        action = LocalFileStoreAction(
            _action({"method": "exists", "path": "f.bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result == {"path": "f.bin", "exists": True}

    @pytest.mark.anyio
    async def test_exists_false(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "exists", "path": "missing.bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result == {"path": "missing.bin", "exists": False}


class TestList:
    @pytest.mark.anyio
    async def test_list_all(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(os.path.join(base_path, "a"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "b"), exist_ok=True)
        for path in ["a/1.txt", "a/2.txt", "b/3.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": True}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/2.txt", "b/3.txt"]
        assert result["count"] == 3
        assert result["next_token"] is None
        for item in result["items"]:
            assert item["size"] == 1
            assert item["url"].startswith("file://")
            assert "modified_at" in item

    @pytest.mark.anyio
    async def test_list_with_prefix(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(os.path.join(base_path, "images"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "logs"), exist_ok=True)
        for path in ["images/1.png", "images/2.png", "logs/a.log"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "path": "images/", "recursive": True}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/1.png", "images/2.png"]

    @pytest.mark.anyio
    async def test_list_pagination(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for i in range(5):
            with open(os.path.join(base_path, f"f{i}.bin"), "wb") as f:
                f.write(b"x")

        seen: List[str] = []
        next_token: Optional[str] = None
        page_count = 0
        while True:
            action = LocalFileStoreAction(
                _action({
                    "method": "list",
                    "max_result_count": 2,
                    **({"next_token": next_token} if next_token else {}),
                }),
                os.path.abspath(base_path),
            )
            result = await action.run(_ctx())
            seen.extend(item["path"] for item in result["items"])
            page_count += 1
            next_token = result["next_token"]
            if next_token is None:
                break
            assert page_count < 10  # safety

        assert sorted(seen) == [f"f{i}.bin" for i in range(5)]
        assert len(seen) == len(set(seen))  # no duplicates

    @pytest.mark.anyio
    async def test_list_empty_when_no_files(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "list"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["items"] == []
        assert result["count"] == 0


class TestListRecursive:
    @pytest.mark.anyio
    async def test_default_is_non_recursive(self, base_path):
        """Without `recursive`, only files directly under the listed directory are returned."""
        os.makedirs(os.path.join(base_path, "sub"), exist_ok=True)
        for path in ["top.txt", "sub/nested.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["top.txt"]

    @pytest.mark.anyio
    async def test_recursive_false_explicit(self, base_path):
        os.makedirs(os.path.join(base_path, "a", "b"), exist_ok=True)
        for path in ["root.txt", "a/mid.txt", "a/b/deep.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": False}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["root.txt"]

    @pytest.mark.anyio
    async def test_recursive_true_walks_all_levels(self, base_path):
        os.makedirs(os.path.join(base_path, "a", "b", "c"), exist_ok=True)
        for path in ["a/1.txt", "a/b/2.txt", "a/b/c/3.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": True}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.txt", "a/b/2.txt", "a/b/c/3.txt"]

    @pytest.mark.anyio
    async def test_recursive_false_under_path(self, base_path):
        """`recursive: false` combined with `path` lists just that directory's files."""
        os.makedirs(os.path.join(base_path, "images", "thumbs"), exist_ok=True)
        for path in ["images/a.png", "images/b.png", "images/thumbs/c.png"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "path": "images"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/a.png", "images/b.png"]

    @pytest.mark.anyio
    async def test_recursive_true_under_path(self, base_path):
        os.makedirs(os.path.join(base_path, "images", "thumbs"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "other"), exist_ok=True)
        for path in ["images/a.png", "images/b.png", "images/thumbs/c.png", "other/d.png"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "path": "images", "recursive": True}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["images/a.png", "images/b.png", "images/thumbs/c.png"]

    @pytest.mark.anyio
    async def test_recursive_via_string_value(self, base_path):
        """`recursive` accepts string values via variable interpolation."""
        os.makedirs(os.path.join(base_path, "sub"), exist_ok=True)
        for path in ["top.txt", "sub/nested.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": "${input.flag}"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx({"flag": True}))
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["sub/nested.txt", "top.txt"]


class TestListPattern:
    @pytest.mark.anyio
    async def test_pattern_extension_filter(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for path in ["a.png", "b.jpg", "c.png", "d.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a.png", "c.png"]

    @pytest.mark.anyio
    async def test_pattern_no_match(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for path in ["a.txt", "b.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result["items"] == []
        assert result["count"] == 0
        assert result["next_token"] is None

    @pytest.mark.anyio
    async def test_pattern_matches_full_relative_path(self, base_path):
        """`**/*.png` matches files under subdirectories when combined with recursive."""
        os.makedirs(os.path.join(base_path, "images", "thumbs"), exist_ok=True)
        for path in ["root.png", "images/a.png", "images/thumbs/b.png", "images/c.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": True, "pattern": "**/*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        # `**/*.png` requires at least one path segment before the file
        assert paths == ["images/a.png", "images/thumbs/b.png"]

    @pytest.mark.anyio
    async def test_pattern_with_prefix_match(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for path in ["report_2024.pdf", "report_2025.pdf", "summary.pdf", "report_2024.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "report_*.pdf"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["report_2024.pdf", "report_2025.pdf"]

    @pytest.mark.anyio
    async def test_pattern_character_class(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for path in ["f1.bin", "f2.bin", "f3.bin", "fa.bin", "g1.bin"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "f[12].bin"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["f1.bin", "f2.bin"]

    @pytest.mark.anyio
    async def test_pattern_case_sensitive(self, base_path):
        """Pattern matching is case-sensitive even on case-insensitive filesystems."""
        os.makedirs(base_path, exist_ok=True)
        for path in ["A.TXT", "b.txt"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "*.txt"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["b.txt"]

    @pytest.mark.anyio
    async def test_pattern_combined_with_path_filter(self, base_path):
        os.makedirs(os.path.join(base_path, "images"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "images", "thumbs"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "logs"), exist_ok=True)
        for path in ["images/a.png", "images/b.jpg", "images/thumbs/c.png", "logs/c.png"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "path": "images", "recursive": True, "pattern": "images/*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        # `images/*.png` matches images/a.png but not images/thumbs/c.png — `*` doesn't cross `/`
        assert paths == ["images/a.png"]

    @pytest.mark.anyio
    async def test_pattern_via_string_interpolation(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        for path in ["a.png", "b.jpg"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "pattern": "${input.ext}"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx({"ext": "*.jpg"}))
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["b.jpg"]

    @pytest.mark.anyio
    async def test_pattern_pagination_yields_only_matches(self, base_path):
        """Pagination must skip non-matching items: filter applies before counting."""
        os.makedirs(base_path, exist_ok=True)
        # 10 .png and 10 .jpg interleaved
        files = []
        for i in range(10):
            files.append(f"img_{i:02d}.png")
            files.append(f"img_{i:02d}.jpg")
        for path in files:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        items = await _list_all(base_path, page_size=3, pattern="*.png", recursive=False)
        paths = sorted(item["path"] for item in items)
        assert paths == sorted(f"img_{i:02d}.png" for i in range(10))
        assert len(paths) == 10
        assert len(paths) == len(set(paths))


class TestListRecursivePattern:
    @pytest.mark.anyio
    async def test_recursive_with_extension_pattern(self, base_path):
        """`*.png` only matches files at the root — `*` does not cross `/`."""
        os.makedirs(os.path.join(base_path, "a", "b"), exist_ok=True)
        for path in ["root.png", "a/1.png", "a/2.txt", "a/b/3.png", "a/b/4.jpg"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": True, "pattern": "*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["root.png"]

    @pytest.mark.anyio
    async def test_recursive_with_glob_star_star(self, base_path):
        """`**/*.png` matches `.png` files at any depth below the root."""
        os.makedirs(os.path.join(base_path, "a", "b"), exist_ok=True)
        for path in ["root.png", "a/1.png", "a/2.txt", "a/b/3.png"]:
            with open(os.path.join(base_path, path), "wb") as f:
                f.write(b"x")

        action = LocalFileStoreAction(
            _action({"method": "list", "recursive": True, "pattern": "**/*.png"}),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        paths = sorted(item["path"] for item in result["items"])
        assert paths == ["a/1.png", "a/b/3.png"]

    @pytest.mark.anyio
    async def test_recursive_pattern_filters_before_pagination_counter(self, base_path):
        """Pagination cursor counts only matching items, so pages are dense, not sparse."""
        os.makedirs(os.path.join(base_path, "d"), exist_ok=True)
        # Mix of matching and non-matching at the same depth
        for i in range(6):
            with open(os.path.join(base_path, "d", f"hit_{i}.log"), "wb") as f:
                f.write(b"x")
            with open(os.path.join(base_path, "d", f"miss_{i}.txt"), "wb") as f:
                f.write(b"x")

        items = await _list_all(
            base_path, page_size=2, pattern="d/hit_*.log", recursive=True,
        )
        paths = sorted(item["path"] for item in items)
        assert paths == sorted(f"d/hit_{i}.log" for i in range(6))


class TestRoundTrip:
    @pytest.mark.anyio
    async def test_put_then_get_then_delete(self, base_path):
        put = LocalFileStoreAction(
            _action({"method": "put", "path": "round.bin", "source": b"roundtrip"}),
            os.path.abspath(base_path),
        )
        put_result = await put.run(_ctx())
        assert put_result["path"] == "round.bin"

        get = LocalFileStoreAction(
            _action({"method": "get", "path": "round.bin"}),
            os.path.abspath(base_path),
        )
        get_result = await get.run(_ctx())
        assert get_result["content"] == b"roundtrip"
        assert get_result["path"] == put_result["path"]

        delete = LocalFileStoreAction(
            _action({"method": "delete", "path": "round.bin"}),
            os.path.abspath(base_path),
        )
        del_result = await delete.run(_ctx())
        assert del_result == {"path": "round.bin"}

        exists = LocalFileStoreAction(
            _action({"method": "exists", "path": "round.bin"}),
            os.path.abspath(base_path),
        )
        ex_result = await exists.run(_ctx())
        assert ex_result["exists"] is False


class TestErrorCases:
    @pytest.mark.anyio
    async def test_put_over_existing_directory_raises(self, base_path):
        os.makedirs(os.path.join(base_path, "target"), exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "target", "source": b"x"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(IsADirectoryError):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_put_missing_source_raises(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "put", "path": "f.bin", "source": "${input.missing}"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(ValueError, match="'source' is required for 'put' action"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_get_on_directory_raises(self, base_path):
        os.makedirs(os.path.join(base_path, "dir"), exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "dir"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(IsADirectoryError):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_get_rejects_traversal(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "get", "path": "../escape"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_delete_rejects_traversal(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "delete", "path": "../escape"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_exists_rejects_traversal(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "exists", "path": "../escape"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_list_on_file_raises(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        with open(os.path.join(base_path, "f.bin"), "wb") as f:
            f.write(b"x")
        action = LocalFileStoreAction(
            _action({"method": "list", "path": "f.bin"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(NotADirectoryError):
            await action.run(_ctx())

    @pytest.mark.anyio
    async def test_list_rejects_traversal(self, base_path):
        os.makedirs(base_path, exist_ok=True)
        action = LocalFileStoreAction(
            _action({"method": "list", "path": "../escape"}),
            os.path.abspath(base_path),
        )
        with pytest.raises(PermissionError, match="escapes the allowed root directory"):
            await action.run(_ctx())


class TestService:
    def test_service_resolves_base_path_to_absolute(self, base_path):
        config = LocalFileStoreComponentConfig(
            type="file-store",
            driver="local",
            runtime={"type": "native"},
            base_path=base_path,
        )
        service = LocalFileStoreService("test", config, daemon=False)
        assert os.path.isabs(service.base_path)
        assert service.base_path == os.path.abspath(base_path)

    @pytest.mark.anyio
    async def test_service_start_creates_base_path(self, tmp_path):
        new_base = str(tmp_path / "fresh" / "storage")
        assert not os.path.exists(new_base)
        config = LocalFileStoreComponentConfig(
            type="file-store",
            driver="local",
            runtime={"type": "native"},
            base_path=new_base,
        )
        service = LocalFileStoreService("test", config, daemon=False)
        await service._start()
        assert os.path.isdir(new_base)


class TestOutputTemplate:
    @pytest.mark.anyio
    async def test_output_template_overrides_default_result(self, base_path):
        action = LocalFileStoreAction(
            _action({
                "method": "put",
                "path": "f.bin",
                "source": b"hello",
                "output": "${result.size} bytes",
            }),
            os.path.abspath(base_path),
        )
        result = await action.run(_ctx())
        assert result == "5 bytes"


def _abs(base_path: str) -> str:
    return os.path.abspath(base_path)


async def _put(base_path: str, path: str, content: bytes) -> dict:
    action = LocalFileStoreAction(
        _action({"method": "put", "path": path, "source": content}),
        _abs(base_path),
    )
    return await action.run(_ctx())


async def _get(base_path: str, path: str) -> dict:
    action = LocalFileStoreAction(
        _action({"method": "get", "path": path}),
        _abs(base_path),
    )
    return await action.run(_ctx())


async def _delete(base_path: str, path: str) -> dict:
    action = LocalFileStoreAction(
        _action({"method": "delete", "path": path}),
        _abs(base_path),
    )
    return await action.run(_ctx())


async def _exists(base_path: str, path: str) -> bool:
    action = LocalFileStoreAction(
        _action({"method": "exists", "path": path}),
        _abs(base_path),
    )
    result = await action.run(_ctx())
    return result["exists"]


async def _list_all(
    base_path: str,
    path: Optional[str] = None,
    page_size: Optional[int] = None,
    recursive: bool = True,
    pattern: Optional[str] = None,
) -> List[dict]:
    items: List[dict] = []
    next_token: Optional[str] = None
    while True:
        config: dict = {"method": "list", "recursive": recursive}
        if path is not None:
            config["path"] = path
        if pattern is not None:
            config["pattern"] = pattern
        if page_size is not None:
            config["max_result_count"] = page_size
        if next_token is not None:
            config["next_token"] = next_token

        action = LocalFileStoreAction(_action(config), _abs(base_path))
        result = await action.run(_ctx())
        items.extend(result["items"])
        next_token = result["next_token"]
        if next_token is None:
            return items


class TestBulkScenarios:
    """End-to-end scenarios that create, read, and delete many files/dirs."""

    @pytest.mark.anyio
    async def test_bulk_create_read_delete_flat(self, base_path):
        """Create 200 files in a single directory, read them all back, then delete them."""
        file_count = 200
        expected = {f"file_{i:04d}.txt": f"contents-of-{i}".encode("utf-8") for i in range(file_count)}

        for path, content in expected.items():
            result = await _put(base_path, path, content)
            assert result["size"] == len(content)

        listed = await _list_all(base_path)
        assert len(listed) == file_count
        assert {item["path"] for item in listed} == set(expected.keys())

        for path, content in expected.items():
            result = await _get(base_path, path)
            assert result["content"] == content
            assert result["size"] == len(content)
            assert result["content_type"] == "text/plain"

        for path in expected:
            await _delete(base_path, path)
            assert not await _exists(base_path, path)

        listed_after = await _list_all(base_path)
        assert listed_after == []

    @pytest.mark.anyio
    async def test_bulk_create_read_delete_nested_tree(self, base_path):
        """Build a 3-level deep tree, walk it, read every file, delete bottom-up."""
        # 3 levels, 4 dirs at each level, 3 files per leaf => 4*4*4*3 = 192 files
        expected: dict[str, bytes] = {}
        for a in range(4):
            for b in range(4):
                for c in range(4):
                    for f in range(3):
                        path = f"l1_{a}/l2_{b}/l3_{c}/file_{f}.dat"
                        content = f"{a}-{b}-{c}-{f}".encode("utf-8") * 10
                        expected[path] = content

        for path, content in expected.items():
            await _put(base_path, path, content)

        listed = await _list_all(base_path)
        assert len(listed) == len(expected)
        assert {item["path"] for item in listed} == set(expected.keys())

        for path, content in expected.items():
            result = await _get(base_path, path)
            assert result["content"] == content

        # Subtree listing - one l1 branch only
        subtree = await _list_all(base_path, path="l1_0")
        assert len(subtree) == 4 * 4 * 3  # 4 l2 dirs * 4 l3 dirs * 3 files
        for item in subtree:
            assert item["path"].startswith("l1_0/")

        # Delete every file
        for path in expected:
            await _delete(base_path, path)

        # Files are gone; empty directories may remain - that's fine, list returns no files
        listed_after = await _list_all(base_path)
        assert listed_after == []

    @pytest.mark.anyio
    async def test_pagination_walks_entire_tree_with_small_page_size(self, base_path):
        """Tiny pages must still cover every file exactly once across a nested tree."""
        expected = set()
        for a in range(3):
            for b in range(5):
                path = f"dir_{a}/sub_{b}/item.bin"
                await _put(base_path, path, f"{a}-{b}".encode())
                expected.add(path)

        # Page through with size 1
        listed_paths: List[str] = []
        items = await _list_all(base_path, page_size=1)
        listed_paths = [item["path"] for item in items]

        assert len(listed_paths) == len(expected)
        assert set(listed_paths) == expected
        assert len(listed_paths) == len(set(listed_paths))  # no duplicates

        # Page through with size 4
        items_p4 = await _list_all(base_path, page_size=4)
        assert {item["path"] for item in items_p4} == expected
        assert len(items_p4) == len(expected)

    @pytest.mark.anyio
    async def test_overwrite_existing_files(self, base_path):
        """Putting to an existing path should replace contents."""
        for i in range(20):
            await _put(base_path, f"data/f_{i}.bin", b"v1-" + str(i).encode())

        for i in range(20):
            result = await _get(base_path, f"data/f_{i}.bin")
            assert result["content"] == b"v1-" + str(i).encode()

        # Overwrite all
        for i in range(20):
            await _put(base_path, f"data/f_{i}.bin", b"v2-" + str(i).encode() * 100)

        for i in range(20):
            result = await _get(base_path, f"data/f_{i}.bin")
            assert result["content"] == b"v2-" + str(i).encode() * 100

        listed = await _list_all(base_path)
        assert len(listed) == 20  # still 20 files, not 40

    @pytest.mark.anyio
    async def test_mixed_operations_interleaved(self, base_path):
        """Create, read, partially delete, create more, list - verify consistency at each step."""
        # Phase 1: create 50 files
        for i in range(50):
            await _put(base_path, f"phase1/f_{i:03d}.txt", f"p1-{i}".encode())

        assert len(await _list_all(base_path)) == 50

        # Phase 2: delete every other file
        deleted = set()
        for i in range(0, 50, 2):
            await _delete(base_path, f"phase1/f_{i:03d}.txt")
            deleted.add(f"phase1/f_{i:03d}.txt")

        listed = await _list_all(base_path)
        assert len(listed) == 25
        listed_paths = {item["path"] for item in listed}
        assert listed_paths.isdisjoint(deleted)

        # Phase 3: add 30 more under a different prefix
        for i in range(30):
            await _put(base_path, f"phase2/g_{i:03d}.txt", f"p2-{i}".encode())

        listed = await _list_all(base_path)
        assert len(listed) == 55  # 25 surviving + 30 new

        # Subtree counts
        p1 = await _list_all(base_path, path="phase1")
        p2 = await _list_all(base_path, path="phase2")
        assert len(p1) == 25
        assert len(p2) == 30

        # Phase 4: read every remaining file
        for item in await _list_all(base_path):
            result = await _get(base_path, item["path"])
            assert result["size"] == item["size"]

        # Phase 5: wipe everything
        for item in await _list_all(base_path):
            await _delete(base_path, item["path"])

        assert await _list_all(base_path) == []

    @pytest.mark.anyio
    async def test_varied_file_sizes(self, base_path):
        """Files spanning multiple chunk boundaries (chunked write/read paths)."""
        # _DEFAULT_CHUNK_SIZE is 8MB. Use sizes around small boundaries to keep the test fast.
        sizes = [0, 1, 1024, 8 * 1024, 64 * 1024, 256 * 1024, 1024 * 1024]
        for i, size in enumerate(sizes):
            content = bytes((b % 256 for b in range(size)))
            await _put(base_path, f"sized/f_{i}_{size}.bin", content)

        for i, size in enumerate(sizes):
            expected = bytes((b % 256 for b in range(size)))
            result = await _get(base_path, f"sized/f_{i}_{size}.bin")
            assert result["size"] == size
            assert result["content"] == expected

        # Delete in reverse order
        for i in reversed(range(len(sizes))):
            size = sizes[i]
            await _delete(base_path, f"sized/f_{i}_{size}.bin")
            assert not await _exists(base_path, f"sized/f_{i}_{size}.bin")

    @pytest.mark.anyio
    async def test_varied_extensions_content_type_detection(self, base_path):
        """Many files with different extensions exercise mimetype guessing on put/get/list."""
        files = {
            "a.txt": "text/plain",
            "b.json": "application/json",
            "c.html": "text/html",
            "d.css": "text/css",
            "e.png": "image/png",
            "f.jpg": "image/jpeg",
            "g.pdf": "application/pdf",
            "h.csv": "text/csv",
            "i.xml": "application/xml",
            "j.unknown_ext_xyz": None,
        }
        for path in files:
            await _put(base_path, f"assets/{path}", b"x")

        for path, expected_ct in files.items():
            result = await _get(base_path, f"assets/{path}")
            assert result["content_type"] == expected_ct, f"get content_type mismatch for {path}"

        listed = await _list_all(base_path, path="assets")
        by_path = {item["path"]: item for item in listed}
        for path, expected_ct in files.items():
            assert by_path[f"assets/{path}"]["content_type"] == expected_ct

    @pytest.mark.anyio
    async def test_subtree_delete_does_not_affect_siblings(self, base_path):
        """Wiping one subtree must leave a sibling subtree untouched."""
        for i in range(30):
            await _put(base_path, f"keep/k_{i}.bin", f"keep-{i}".encode())
            await _put(base_path, f"drop/d_{i}.bin", f"drop-{i}".encode())

        assert len(await _list_all(base_path)) == 60

        # Delete every file under 'drop/'
        drop_items = await _list_all(base_path, path="drop")
        assert len(drop_items) == 30
        for item in drop_items:
            await _delete(base_path, item["path"])

        # 'keep/' is intact
        keep_items = await _list_all(base_path, path="keep")
        assert len(keep_items) == 30
        for item in keep_items:
            result = await _get(base_path, item["path"])
            assert result["content"].startswith(b"keep-")

        # 'drop/' has no files left (directory itself may still exist)
        assert await _list_all(base_path, path="drop") == []

    @pytest.mark.anyio
    async def test_exists_consistency_after_bulk_ops(self, base_path):
        """exists() must agree with the list() view through put/delete churn."""
        paths = [f"area/{ch}/item_{i}.bin" for ch in "abcde" for i in range(10)]

        for p in paths:
            assert not await _exists(base_path, p)

        for p in paths:
            await _put(base_path, p, b"x")
            assert await _exists(base_path, p)

        listed = {item["path"] for item in await _list_all(base_path)}
        assert listed == set(paths)

        # Delete a slice and re-verify
        to_delete = paths[::3]
        for p in to_delete:
            await _delete(base_path, p)

        for p in paths:
            should_exist = p not in set(to_delete)
            assert await _exists(base_path, p) == should_exist

        listed_after = {item["path"] for item in await _list_all(base_path)}
        assert listed_after == set(paths) - set(to_delete)
