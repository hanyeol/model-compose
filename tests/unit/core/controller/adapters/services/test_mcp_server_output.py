"""Unit tests for ``McpServerControllerAdapterService._convert_output_value``.

Covers the mapping from workflow output values to MCP ``ContentBlock``s for
media types (image / audio / video / file). Verifies that raw bytes, streams,
base64 strings, filesystem paths, and URL/data-uri strings are all handled
correctly and produce the expected ``ImageContent`` / ``AudioContent`` /
``EmbeddedResource`` / ``TextContent`` blocks.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from mcp.types import (
    AudioContent,
    EmbeddedResource,
    ImageContent,
    TextContent,
)

from mindor.core.controller.adapters.services.mcp_server import (
    McpServerControllerAdapterService,
)
from mindor.core.controller.base import TaskState, TaskStatus
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.workflow.schema import WorkflowSchema
from mindor.dsl.schema.workflow import (
    WorkflowVariableConfig,
    WorkflowVariableFormat,
    WorkflowVariableGroupConfig,
    WorkflowVariableType,
)


@pytest.fixture
def adapter() -> McpServerControllerAdapterService:
    # Skip __init__; we only need the pure converter methods.
    return McpServerControllerAdapterService.__new__(McpServerControllerAdapterService)


def _run(coro):
    return asyncio.run(coro)


class TestConvertOutputValueImage:
    def test_bytes_auto_encoded_as_image_content(self, adapter):
        raw = b"\x89PNG\r\n\x1a\nfakepng"
        block = _run(adapter._convert_output_value(
            task_id="t1", value=raw, name="image",
            type=WorkflowVariableType.IMAGE, subtype="png", format=None,
        ))
        assert isinstance(block, ImageContent)
        assert block.mimeType == "image/png"
        assert block.data == base64.b64encode(raw).decode("ascii")

    def test_base64_string_passes_through(self, adapter):
        b64 = base64.b64encode(b"already-encoded").decode("ascii")
        block = _run(adapter._convert_output_value(
            task_id="t1", value=b64, name="image",
            type=WorkflowVariableType.IMAGE, subtype="jpeg",
            format=WorkflowVariableFormat.BASE64,
        ))
        assert isinstance(block, ImageContent)
        assert block.mimeType == "image/jpeg"
        assert block.data == b64

    def test_default_subtype_when_omitted(self, adapter):
        block = _run(adapter._convert_output_value(
            task_id="t1", value=b"x", name="image",
            type=WorkflowVariableType.IMAGE, subtype=None, format=None,
        ))
        assert isinstance(block, ImageContent)
        assert block.mimeType == "image/png"

    def test_data_uri_decoded_and_encoded(self, adapter):
        raw = b"\x89PNG-payload"
        data_uri = f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"
        block = _run(adapter._convert_output_value(
            task_id="t1", value=data_uri, name="image",
            type=WorkflowVariableType.IMAGE, subtype="png",
            format=WorkflowVariableFormat.DATA_URI,
        ))
        assert isinstance(block, ImageContent)
        assert block.mimeType == "image/png"
        assert block.data == base64.b64encode(raw).decode("ascii")


class TestConvertOutputValueAudio:
    def test_bytes_auto_encoded_as_audio_content(self, adapter):
        raw = b"RIFF....WAVEfmt "
        block = _run(adapter._convert_output_value(
            task_id="t1", value=raw, name="audio",
            type=WorkflowVariableType.AUDIO, subtype="wav", format=None,
        ))
        assert isinstance(block, AudioContent)
        assert block.mimeType == "audio/wav"
        assert block.data == base64.b64encode(raw).decode("ascii")

    def test_stream_resource_encoded_via_stream(self, adapter, tmp_path):
        raw = b"fake-mp3-bytes"
        audio_file = tmp_path / "song.mp3"
        audio_file.write_bytes(raw)

        stream = FileStreamResource(str(audio_file))
        block = _run(adapter._convert_output_value(
            task_id="t1", value=stream, name="audio",
            type=WorkflowVariableType.AUDIO, subtype="mpeg", format=None,
        ))
        assert isinstance(block, AudioContent)
        assert block.mimeType == "audio/mpeg"
        assert block.data == base64.b64encode(raw).decode("ascii")

    def test_path_string_read_and_encoded(self, adapter, tmp_path: Path):
        raw = b"sample-audio-bytes"
        audio_file = tmp_path / "clip.wav"
        audio_file.write_bytes(raw)

        block = _run(adapter._convert_output_value(
            task_id="t1", value=str(audio_file), name="audio",
            type=WorkflowVariableType.AUDIO, subtype="wav",
            format=WorkflowVariableFormat.PATH,
        ))
        assert isinstance(block, AudioContent)
        assert block.mimeType == "audio/wav"
        assert block.data == base64.b64encode(raw).decode("ascii")

    def test_default_subtype_when_omitted(self, adapter):
        block = _run(adapter._convert_output_value(
            task_id="t1", value=b"x", name="audio",
            type=WorkflowVariableType.AUDIO, subtype=None, format=None,
        ))
        assert isinstance(block, AudioContent)
        assert block.mimeType == "audio/wav"


class TestConvertOutputValueVideoAndFile:
    def test_video_bytes_encoded_as_embedded_resource(self, adapter):
        raw = b"\x00\x00\x00\x18ftypmp42"
        block = _run(adapter._convert_output_value(
            task_id="task-42", value=raw, name="clip",
            type=WorkflowVariableType.VIDEO, subtype="mp4", format=None,
        ))
        assert isinstance(block, EmbeddedResource)
        assert block.resource.mimeType == "video/mp4"
        assert str(block.resource.uri) == "resource://task-42/clip"
        assert block.resource.blob == base64.b64encode(raw).decode("ascii")

    def test_file_uses_octet_stream_and_output_name_fallback(self, adapter):
        raw = b"binary-blob"
        block = _run(adapter._convert_output_value(
            task_id="task-9", value=raw, name=None,
            type=WorkflowVariableType.FILE, subtype=None, format=None,
        ))
        assert isinstance(block, EmbeddedResource)
        assert block.resource.mimeType == "application/octet-stream"
        assert str(block.resource.uri) == "resource://task-9/output"
        assert block.resource.blob == base64.b64encode(raw).decode("ascii")


class TestConvertOutputValueNonMedia:
    def test_none_type_returns_empty_text(self, adapter):
        block = _run(adapter._convert_output_value(
            task_id="t1", value="anything", name=None,
            type=WorkflowVariableType.NONE, subtype=None, format=None,
        ))
        assert isinstance(block, TextContent)
        assert block.text == ""

    def test_dict_serialized_as_json_text(self, adapter):
        block = _run(adapter._convert_output_value(
            task_id="t1", value={"k": "v"}, name=None,
            type=WorkflowVariableType.OBJECT, subtype=None, format=None,
        ))
        assert isinstance(block, TextContent)
        assert block.text == '{"k": "v"}'

    def test_scalar_stringified(self, adapter):
        block = _run(adapter._convert_output_value(
            task_id="t1", value=42, name=None,
            type=WorkflowVariableType.INTEGER, subtype=None, format=None,
        ))
        assert isinstance(block, TextContent)
        assert block.text == "42"

    def test_non_media_stream_resource_wrapped_as_embedded_resource(self, adapter, tmp_path):
        # A non-media output that happens to be a StreamResource (e.g. an
        # `any`-typed output that returned raw bytes) should be safely wrapped
        # instead of falling into str(value) and producing a repr string.
        raw = b"opaque-bytes"
        f = tmp_path / "blob.bin"
        f.write_bytes(raw)

        block = _run(adapter._convert_output_value(
            task_id="task-x", value=FileStreamResource(str(f)), name="payload",
            type=WorkflowVariableType.ANY, subtype=None, format=None,
        ))
        assert isinstance(block, EmbeddedResource)
        assert block.resource.mimeType == "application/octet-stream"
        assert str(block.resource.uri) == "resource://task-x/payload"
        assert block.resource.blob == base64.b64encode(raw).decode("ascii")

    def test_non_media_stream_iterator_wrapped_as_embedded_resource(self, adapter):
        # StreamIterator (async iterable of chunks) — covers streaming outputs
        # that never got materialized into a StreamResource.
        from mindor.core.foundation.streaming.iterators import StreamChunkIterator

        async def _chunks():
            yield b"chunk-1;"
            yield b"chunk-2"

        block = _run(adapter._convert_output_value(
            task_id="task-y", value=StreamChunkIterator(_chunks()), name="stream",
            type=WorkflowVariableType.ANY, subtype=None, format=None,
        ))
        assert isinstance(block, EmbeddedResource)
        assert block.resource.mimeType == "application/octet-stream"
        assert str(block.resource.uri) == "resource://task-y/stream"
        assert block.resource.blob == base64.b64encode(b"chunk-1;chunk-2").decode("ascii")


def _var(name: str, type: WorkflowVariableType) -> WorkflowVariableConfig:
    return WorkflowVariableConfig(name=name, type=type)


def _schema(output_variables) -> WorkflowSchema:
    return WorkflowSchema(
        workflow_id="wf",
        name=None,
        title=None,
        description=None,
        input=[],
        output=output_variables,
        default=False,
    )


def _state(task_id: str, output) -> TaskState:
    return TaskState(task_id=task_id, status=TaskStatus.COMPLETED, output=output)


class TestBuildOutputValueGroup:
    def test_group_emitted_as_json_text_block(self, adapter):
        # A group with `repeat_count > 1` — value at runtime is a list of dicts
        # matching group.variables' schema.
        group = WorkflowVariableGroupConfig(
            name="hits",
            variables=[_var("title", WorkflowVariableType.STRING), _var("score", WorkflowVariableType.NUMBER)],
            repeat_count=3,
        )
        schema = _schema([group])
        state = _state("t1", {"hits": [
            {"title": "a", "score": 0.9},
            {"title": "b", "score": 0.7},
        ]})

        blocks = _run(adapter._build_output_value(state, schema))
        assert len(blocks) == 1
        assert isinstance(blocks[0], TextContent)
        assert json.loads(blocks[0].text) == [
            {"title": "a", "score": 0.9},
            {"title": "b", "score": 0.7},
        ]

    def test_group_and_scalar_coexist(self, adapter):
        group = WorkflowVariableGroupConfig(
            name="hits",
            variables=[_var("title", WorkflowVariableType.STRING)],
            repeat_count=2,
        )
        summary = _var("summary", WorkflowVariableType.STRING)
        schema = _schema([summary, group])
        state = _state("t1", {
            "summary": "found 2",
            "hits": [{"title": "a"}, {"title": "b"}],
        })

        blocks = _run(adapter._build_output_value(state, schema))
        assert len(blocks) == 2
        # scalar → TextContent for the STRING type
        assert isinstance(blocks[0], TextContent)
        assert blocks[0].text == "found 2"
        # group → JSON dump of the list
        assert isinstance(blocks[1], TextContent)
        assert json.loads(blocks[1].text) == [{"title": "a"}, {"title": "b"}]
