"""Tests for the FFmpeg audio-extractor driver.

Covers three layers:
  - Extraction behavior (format / codec / bitrate / track / errors / output template)
  - Input path resolution (FileStreamResource path / streamable pipe:0 / spooled fallback)
  - I/O matrix (single / list input, ${result[]} stream output, batch_size)
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.audio_extractor.drivers.ffmpeg import (
    FFmpegAudioExtractorAction,
)
from mindor.core.utils.streaming.audio import AudioStreamResource
from mindor.core.utils.streaming.media import MediaSource, create_media_source
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.core.utils.streaming.bytes import BytesStreamResource
from mindor.dsl.schema.action import AudioExtractorActionConfig


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_video_path():
    """Generate a tiny mp4 with a silent stereo audio track."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=10",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"ffmpeg failed: {e.stderr.decode('utf-8', errors='replace')}")
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sample_mp3_bytes():
    """Generate a tiny in-memory mp3 (no container metadata after EOF)."""
    path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=16000",
        "-t", "1", "-c:a", "libmp3lame", "-b:a", "32k",
        path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"ffmpeg failed: {e.stderr.decode('utf-8', errors='replace')}")
    try:
        with open(path, "rb") as f:
            yield f.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _make_context(source_value: Any) -> ComponentActionContext:
    """Build a mock context where render_media yields MediaSource(s).

    `source_value` can be:
      - str: treated as file path → FileStreamResource path
      - bytes: treated as in-memory data → BytesStreamResource
      - MediaSource: passed through as-is
      - list of any of the above: returned as list
      - zero-arg callable returning an AsyncIterator of values: AsyncIterator[MediaSource]
    """
    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if isinstance(value, str):
            return f"${{{key}" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
            if value.startswith("${result[].") and value.endswith("}"):
                attr = value[len("${result[]."):-1]
                target = sources.get("result[]")
                return getattr(target, attr, None)
            if value.startswith("${result.") and value.endswith("}"):
                attr = value[len("${result."):-1]
                target = sources.get("result")
                return getattr(target, attr, None)
        return value

    def resolve_one(value):
        if isinstance(value, MediaSource):
            return value
        return create_media_source(value)

    async def render_media(_value):
        if callable(source_value):
            source = source_value()
            assert isinstance(source, AsyncIterator)

            async def _map():
                async for item in source:
                    yield resolve_one(item)
            return _map()
        if isinstance(source_value, list):
            return [resolve_one(v) for v in source_value]
        return resolve_one(source_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_media = AsyncMock(side_effect=render_media)
    return ctx


def _make_config(output: Any = None, **kwargs) -> AudioExtractorActionConfig:
    payload = {"source": "<placeholder>", **kwargs}
    if output is not None:
        payload["output"] = output
    return AudioExtractorActionConfig(**payload)


def _probe_audio_format(path: str) -> dict:
    """Return ffprobe metadata for an audio file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-show_entries", "format=format_name",
            "-of", "default=noprint_wrappers=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    info = {}
    for line in result.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


async def _drain_resource_to_file(resource: AudioStreamResource) -> str:
    """Materialize an AudioStreamResource to a temp file on disk.

    Supports both stream-backed (AsyncIterableStreamResource) and file-backed
    (FileStreamResource) outputs.
    """
    dest = tempfile.NamedTemporaryFile(
        suffix=f".{resource.format or 'bin'}", delete=False
    ).name

    src = resource.source

    if isinstance(src, FileStreamResource):
        with open(src.path, "rb") as f_in, open(dest, "wb") as f_out:
            f_out.write(f_in.read())
    else:
        with open(dest, "wb") as f_out:
            async for chunk in resource:
                f_out.write(chunk)

    await resource.close()
    return dest


@ffmpeg_required
class TestFFmpegAudioExtractor:
    """End-to-end extraction behavior for a single input."""

    @pytest.mark.anyio
    async def test_mp4_to_mp3_extraction(self, sample_video_path):
        config = _make_config(format="mp3")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        assert result.format == "mp3"
        ctx.register_source.assert_called_with("result", result)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_mp4_to_wav_extraction(self, sample_video_path):
        config = _make_config(format="wav")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result.format == "wav"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "pcm_s16le"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_mp4_to_flac_extraction(self, sample_video_path):
        config = _make_config(format="flac")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result.format == "flac"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "flac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_default_format_is_mp3(self, sample_video_path):
        config = _make_config()
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result.format == "mp3"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_track_selection(self, sample_video_path):
        # Source only has one audio track at index 0; ensure -map flag does not break it.
        config = _make_config(format="mp3", track=0)
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_explicit_codec_and_bitrate(self, sample_video_path):
        config = _make_config(format="mp3", codec="libmp3lame", bitrate="64k")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_invalid_input_raises_runtime_error(self, tmp_path):
        # With stream-backed output the error surfaces when the resource is actually
        # consumed, not at run().
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"not a video file at all" * 32)

        config = _make_config(format="mp3")
        ctx = _make_context(str(bogus))

        with pytest.raises(RuntimeError, match="ffmpeg audio extraction failed"):
            result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())
            await _drain_resource_to_file(result)

    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self, sample_video_path):
        config = _make_config(format="mp3", output="extracted")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result == "extracted"
        # 'result' source should still be registered (the AudioStreamResource).
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        assert isinstance(registered["result"], AudioStreamResource)
        await registered["result"].close()


@ffmpeg_required
class TestInputPathResolution:
    """Verify the three input strategies: file path / pipe:0 / spooled."""

    @pytest.mark.anyio
    async def test_file_stream_resource_uses_path_directly(self, sample_video_path):
        """A MediaSource backed by FileStreamResource should be fed via -i <path>."""
        source = MediaSource(FileStreamResource(sample_video_path))
        config = _make_config(format="mp3")
        ctx = _make_context(source)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        await result.close()

    @pytest.mark.anyio
    async def test_streamable_format_uses_pipe(self, sample_mp3_bytes):
        """In-memory mp3 (a streamable format) should go through pipe:0."""
        source = MediaSource(BytesStreamResource(sample_mp3_bytes), format="mp3")
        config = _make_config(format="wav")
        ctx = _make_context(source)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        assert result.format == "wav"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "pcm_s16le"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_non_streamable_bytes_is_spooled(self, sample_video_path):
        """In-memory mp4 bytes should be spooled to a temp file, not piped."""
        with open(sample_video_path, "rb") as f:
            mp4_bytes = f.read()
        source = MediaSource(BytesStreamResource(mp4_bytes), format="mp4")
        config = _make_config(format="mp3")
        ctx = _make_context(source)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_unknown_format_is_spooled(self, sample_video_path):
        """When format is unknown, the safe default is to spool."""
        with open(sample_video_path, "rb") as f:
            mp4_bytes = f.read()
        source = MediaSource(BytesStreamResource(mp4_bytes), format=None)
        config = _make_config(format="mp3")
        ctx = _make_context(source)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        await result.close()

    @pytest.mark.anyio
    async def test_string_path_is_treated_as_file(self, sample_video_path):
        """A plain string path should be normalized to a FileStreamResource-backed MediaSource."""
        config = _make_config(format="mp3")
        ctx = _make_context(sample_video_path)  # bare string

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        await result.close()

    @pytest.mark.anyio
    async def test_spooled_temp_file_is_cleaned_up(self, sample_video_path, tmp_path, monkeypatch):
        """After extraction, the spooled temp file must be removed."""
        with open(sample_video_path, "rb") as f:
            mp4_bytes = f.read()
        source = MediaSource(BytesStreamResource(mp4_bytes), format="mp4")
        config = _make_config(format="mp3")
        ctx = _make_context(source)

        # Track which paths are spooled.
        spooled_paths: list[str] = []
        from mindor.core.component.services.audio_extractor.drivers import ffmpeg as ffmpeg_mod
        original_save = ffmpeg_mod.save_stream_to_temporary_file

        async def tracking_save(stream, ext):
            path = await original_save(stream, ext)
            spooled_paths.append(path)
            return path

        monkeypatch.setattr(ffmpeg_mod, "save_stream_to_temporary_file", tracking_save)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())
        # With stream-backed output, cleanup runs in the generator's finally; trigger
        # full consumption first so the spool file is reliably removed.
        out_path = await _drain_resource_to_file(result)
        os.unlink(out_path)

        assert spooled_paths, "expected at least one spooled temp file"
        for path in spooled_paths:
            assert not os.path.exists(path), f"spooled file leaked: {path}"


@ffmpeg_required
class TestSingleInput:
    """I/O matrix: single input with various output references."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_resource(self, sample_video_path):
        config = _make_config(format="mp3")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        assert result.format == "mp3"
        await result.close()

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_resource(self, sample_video_path):
        config = _make_config(output="${result}", format="mp3")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AudioStreamResource)
        await result.close()


@ffmpeg_required
class TestListInput:
    """I/O matrix: list input returns list of resources."""

    @pytest.mark.anyio
    async def test_list_returns_list_of_resources(self, sample_video_path):
        config = _make_config(format="mp3")
        ctx = _make_context([sample_video_path, sample_video_path])

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, AudioStreamResource) for item in result)
        for item in result:
            await item.close()


@ffmpeg_required
class TestStreamInput:
    """I/O matrix: AsyncIterator input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_stream_input_no_output_yields_resources(self, sample_video_path):
        def _make_iter():
            async def _gen():
                yield sample_video_path
                yield sample_video_path
            return _gen()

        config = _make_config(format="mp3")
        ctx = _make_context(_make_iter)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert all(isinstance(item, AudioStreamResource) for item in items)
        for item in items:
            await item.close()

    @pytest.mark.anyio
    async def test_stream_input_passthrough_output_yields_resources(self, sample_video_path):
        def _make_iter():
            async def _gen():
                yield sample_video_path
            return _gen()

        config = _make_config(output="${result}", format="mp3")
        ctx = _make_context(_make_iter)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1
        assert isinstance(items[0], AudioStreamResource)
        await items[0].close()

    @pytest.mark.anyio
    async def test_stream_input_with_stream_output_template(self, sample_video_path):
        def _make_iter():
            async def _gen():
                yield sample_video_path
                yield sample_video_path
                yield sample_video_path
            return _gen()

        config = _make_config(output="${result[]}", format="mp3")
        ctx = _make_context(_make_iter)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 3
        assert all(isinstance(item, AudioStreamResource) for item in items)
        for item in items:
            await item.close()


@ffmpeg_required
class TestStreamOutputTemplate:
    """Under the new model `${result[]}` no longer forces stream mode; audio_extractor's
    unit result is an AudioStreamResource (already a stream resource), so the outer
    container is decided solely by the input shape — list/single inputs never produce
    an AsyncIterator output even with `${result[]}` in the template."""

    @pytest.mark.anyio
    async def test_list_input_with_stream_output_template_returns_list(self, sample_video_path):
        config = _make_config(output="${result[]}", format="mp3")
        ctx = _make_context([sample_video_path, sample_video_path])

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)

    @pytest.mark.anyio
    async def test_single_input_with_stream_output_template_returns_single(self, sample_video_path):
        config = _make_config(output="${result[]}", format="mp3")
        ctx = _make_context(sample_video_path)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


@ffmpeg_required
class TestBatchSize:
    """I/O matrix: batch_size affects internal chunking but not result shape."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3])
    async def test_list_with_batch_size(self, sample_video_path, batch_size: int):
        config = _make_config(batch_size=batch_size, format="mp3")
        ctx = _make_context([sample_video_path] * 3)

        result = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, AudioStreamResource)
            await item.close()


@ffmpeg_required
class TestErrorPropagation:
    """I/O matrix: errors in list inputs propagate via asyncio.gather."""

    @pytest.mark.anyio
    async def test_invalid_input_in_list_raises(self, sample_video_path, tmp_path):
        # With stream-backed output the error surfaces when each resource is consumed.
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"not a video file at all" * 32)

        config = _make_config(format="mp3")
        ctx = _make_context([sample_video_path, str(bogus)])

        with pytest.raises(RuntimeError, match="ffmpeg audio extraction failed"):
            results = await FFmpegAudioExtractorAction(config).run(ctx, asyncio.get_running_loop())
            for resource in results:
                await _drain_resource_to_file(resource)
