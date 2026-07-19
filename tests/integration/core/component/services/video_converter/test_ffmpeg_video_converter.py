"""Tests for the FFmpeg video-converter driver.

Covers two layers:
  - Conversion behavior (format / codec / resolution / fps / errors / output template)
  - I/O matrix (single / list / AsyncIterator input, ${result[]} stream output, batch_size)
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from collections.abc import AsyncIterator
from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_converter.drivers.ffmpeg import (
    FFmpegVideoConverterAction,
)
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.dsl.schema.action.impl.media import (
    AudioEncoderConfig,
    VideoAudioEncodingConfig,
    VideoEncoderConfig,
)


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_context(video_value: Any = None) -> ComponentActionContext:
    """Build a mock context where render_video yields VideoStreamResource(s).

    `video_value` may be:
      - a single file path (str) → single MediaSource
      - a list of file paths → List[MediaSource]
      - a zero-arg callable returning an AsyncIterator → AsyncIterator[MediaSource]
      - None → behaves like the old make_context: render_video echoes its input
    """
    from mindor.core.foundation.streaming.video import create_video_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

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
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_video_source(value)

    async def render_video(value):
        target = video_value if video_value is not None else value
        if callable(target) and not isinstance(target, str):
            source = target()
            assert isinstance(source, AsyncIterator)

            async def _map():
                async for item in source:
                    yield resolve_one(item)
            return _map()
        if isinstance(target, list):
            return [resolve_one(v) for v in target]
        return resolve_one(target)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


# Back-compat alias for the existing conversion-behavior tests.
def make_context():
    return _make_context()


def _wrap_encoding(kwargs: dict) -> dict:
    """Translate legacy flat kwargs (format/codec/resolution/fps) into the current
    `encoding=VideoAudioEncodingConfig(...)` shape used by VideoConverterActionConfig."""
    fmt = kwargs.pop("format", None)
    codec = kwargs.pop("codec", None)
    resolution = kwargs.pop("resolution", None)
    fps = kwargs.pop("fps", None)

    if fmt is None and codec is None and resolution is None and fps is None:
        return kwargs

    video_kwargs = {}
    audio_kwargs = {}
    if isinstance(codec, VideoAudioEncodingConfig):
        encoding = codec
        if fmt is not None:
            encoding = encoding.model_copy(update={"format": fmt})
        kwargs["encoding"] = encoding
        return kwargs
    if isinstance(codec, str):
        video_kwargs["codec"] = codec
    elif codec is not None and hasattr(codec, "video"):
        # Back-compat: legacy tests may still pass an object exposing .video/.audio
        if codec.video is not None:
            video_kwargs["codec"] = codec.video
        if codec.audio is not None:
            audio_kwargs["codec"] = codec.audio
    if resolution is not None:
        video_kwargs["resolution"] = resolution
    if fps is not None:
        video_kwargs["fps"] = fps

    kwargs["encoding"] = VideoAudioEncodingConfig(
        format=fmt,
        video=VideoEncoderConfig(**video_kwargs) if video_kwargs else None,
        audio=AudioEncoderConfig(**audio_kwargs) if audio_kwargs else None,
    )
    return kwargs


def make_config(video, **kwargs):
    return VideoConverterActionConfig(video=video, **_wrap_encoding(kwargs))


def _make_config(video: Any = "<placeholder>", **kwargs) -> VideoConverterActionConfig:
    return VideoConverterActionConfig(video=video, **_wrap_encoding(kwargs))


@pytest.fixture(scope="module")
def sample_mp4_path():
    """Generate a tiny mp4 with ffmpeg's testsrc filter (2s, 320x240, 24 fps)."""
    path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            path,
        ],
        check=True, capture_output=True,
    )
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _probe_video(path: str) -> dict:
    """Return ffprobe metadata for a video file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
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


def _probe_audio_codec(path: str) -> str:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


async def _drain_resource_to_file(resource: VideoStreamResource) -> str:
    """Materialize a VideoStreamResource to a temp file on disk.

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
class TestFFmpegVideoConverter:
    @pytest.mark.anyio
    async def test_mp4_to_webm_conversion(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="webm")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert isinstance(result, VideoStreamResource)
        assert result.format == "webm"
        ctx.register_source.assert_called_with("result", result)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "vp9"
            assert _probe_audio_codec(out_path) == "opus"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_default_format_is_mp4(self, sample_mp4_path):
        config = make_config(sample_mp4_path)
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert result.format == "mp4"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_resolution_override(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="mp4", resolution="160x120")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert int(info["width"]) == 160
            assert int(info["height"]) == 120
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_fps_override(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="mp4", fps="12")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            num, den = info["r_frame_rate"].split("/")
            assert int(num) // int(den) == 12
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_explicit_codec_config(self, sample_mp4_path):
        encoding = VideoAudioEncodingConfig(
            format="mkv",
            video=VideoEncoderConfig(codec="libx264"),
            audio=AudioEncoderConfig(codec="aac"),
        )
        config = VideoConverterActionConfig(video=sample_mp4_path, encoding=encoding)
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_string_codec_uses_format_default_audio(self, sample_mp4_path):
        """When codec is a bare string, audio codec falls back to format default."""
        config = make_config(sample_mp4_path, format="mp4", codec="libx264")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            assert info["codec_name"] == "h264"
            # mp4 default audio codec is aac
            assert _probe_audio_codec(out_path) == "aac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_invalid_input_raises_runtime_error(self, tmp_path):
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"definitely not a video" * 32)

        config = make_config(str(bogus), format="mp4")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        with pytest.raises(RuntimeError, match="ffmpeg video conversion failed"):
            await action.run(ctx, asyncio.get_running_loop())

    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="mp4", output="converted")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx, asyncio.get_running_loop())

        assert result == "converted"
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        assert isinstance(registered["result"], VideoStreamResource)
        await registered["result"].close()


@ffmpeg_required
class TestSingleInput:
    """I/O matrix: single input with various output references."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_resource(self, sample_mp4_path):
        config = _make_config(format="mp4")
        ctx = _make_context(sample_mp4_path)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, VideoStreamResource)
        assert result.format == "mp4"
        await result.close()

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_resource(self, sample_mp4_path):
        config = _make_config(output="${result}", format="mp4")
        ctx = _make_context(sample_mp4_path)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, VideoStreamResource)
        await result.close()


@ffmpeg_required
class TestListInput:
    """I/O matrix: list input returns list of resources."""

    @pytest.mark.anyio
    async def test_list_returns_list_of_resources(self, sample_mp4_path):
        config = _make_config(format="mp4")
        ctx = _make_context([sample_mp4_path, sample_mp4_path])

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, VideoStreamResource) for item in result)
        for item in result:
            await item.close()


@ffmpeg_required
class TestStreamInput:
    """I/O matrix: AsyncIterator input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_stream_input_no_output_yields_resources(self, sample_mp4_path):
        def _make_iter():
            async def _gen():
                yield sample_mp4_path
                yield sample_mp4_path
            return _gen()

        config = _make_config(format="mp4")
        ctx = _make_context(_make_iter)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert all(isinstance(item, VideoStreamResource) for item in items)
        for item in items:
            await item.close()

    @pytest.mark.anyio
    async def test_stream_input_passthrough_output_yields_resources(self, sample_mp4_path):
        def _make_iter():
            async def _gen():
                yield sample_mp4_path
            return _gen()

        config = _make_config(output="${result}", format="mp4")
        ctx = _make_context(_make_iter)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1
        assert isinstance(items[0], VideoStreamResource)
        await items[0].close()

    @pytest.mark.anyio
    async def test_stream_input_with_stream_output_template(self, sample_mp4_path):
        def _make_iter():
            async def _gen():
                yield sample_mp4_path
                yield sample_mp4_path
                yield sample_mp4_path
            return _gen()

        config = _make_config(output="${result[]}", format="mp4")
        ctx = _make_context(_make_iter)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 3
        assert all(isinstance(item, VideoStreamResource) for item in items)
        for item in items:
            await item.close()


@ffmpeg_required
class TestStreamOutputTemplate:
    """Under the new model `${result[]}` no longer forces stream mode; video_converter's
    unit result is a VideoStreamResource (already a stream resource), so the outer
    container is decided solely by the input shape — list/single inputs never produce
    an AsyncIterator output even with `${result[]}` in the template."""

    @pytest.mark.anyio
    async def test_list_input_with_stream_output_template_returns_list(self, sample_mp4_path):
        config = _make_config(output="${result[]}", format="mp4")
        ctx = _make_context([sample_mp4_path, sample_mp4_path])

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)

    @pytest.mark.anyio
    async def test_single_input_with_stream_output_template_returns_single(self, sample_mp4_path):
        config = _make_config(output="${result[]}", format="mp4")
        ctx = _make_context(sample_mp4_path)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert not isinstance(result, AsyncIterator)


@ffmpeg_required
class TestBatchSize:
    """I/O matrix: batch_size affects internal chunking but not result shape."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3])
    async def test_list_with_batch_size(self, sample_mp4_path, batch_size: int):
        config = _make_config(batch_size=batch_size, format="mp4")
        ctx = _make_context([sample_mp4_path] * 3)

        result = await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, VideoStreamResource)
            await item.close()


@ffmpeg_required
class TestErrorPropagation:
    """I/O matrix: errors in list inputs propagate via asyncio.gather."""

    @pytest.mark.anyio
    async def test_invalid_input_in_list_raises(self, sample_mp4_path, tmp_path):
        bogus = tmp_path / "bogus.mp4"
        bogus.write_bytes(b"definitely not a video" * 32)

        config = _make_config(format="mp4")
        ctx = _make_context([sample_mp4_path, str(bogus)])

        with pytest.raises(RuntimeError, match="ffmpeg video conversion failed"):
            await FFmpegVideoConverterAction(config).run(ctx, asyncio.get_running_loop())
