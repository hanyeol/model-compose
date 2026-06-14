"""Tests for the FFmpeg video-converter driver."""

import os
import shutil
import subprocess
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.video_converter.drivers.ffmpeg import (
    FFmpegVideoConverterAction,
)
from mindor.core.utils.streaming import FileStreamResource
from mindor.core.utils.video import VideoStreamResource
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.dsl.schema.action.impl.media import VideoAudioCodecConfig


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_context():
    from mindor.core.utils.video import create_video_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.register_source = MagicMock()
    ctx.contains_variable_reference = MagicMock(return_value=False)

    async def render_variable(value, **kwargs):
        return value

    def resolve_one(value):
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_video_source(value)

    async def render_video(value):
        if isinstance(value, list):
            return [resolve_one(v) for v in value]
        return resolve_one(value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_video = AsyncMock(side_effect=render_video)
    return ctx


def make_config(video, **kwargs):
    return VideoConverterActionConfig(video=video, **kwargs)


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
    src = resource.source
    assert isinstance(src, FileStreamResource)
    dest = tempfile.NamedTemporaryFile(
        suffix=f".{resource.format or 'bin'}", delete=False
    ).name
    with open(src.path, "rb") as f_in, open(dest, "wb") as f_out:
        f_out.write(f_in.read())
    await resource.close()
    return dest


@ffmpeg_required
class TestFFmpegVideoConverter:
    @pytest.mark.anyio
    async def test_mp4_to_webm_conversion(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="webm")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx)

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

        result = await action.run(ctx)

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

        result = await action.run(ctx)

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

        result = await action.run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_video(out_path)
            num, den = info["r_frame_rate"].split("/")
            assert int(num) // int(den) == 12
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_explicit_codec_config(self, sample_mp4_path):
        codec_config = VideoAudioCodecConfig(video="libx264", audio="aac")
        config = make_config(sample_mp4_path, format="mkv", codec=codec_config)
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx)

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

        result = await action.run(ctx)

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
            await action.run(ctx)

    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self, sample_mp4_path):
        config = make_config(sample_mp4_path, format="mp4", output="converted")
        action = FFmpegVideoConverterAction(config)
        ctx = make_context()

        result = await action.run(ctx)

        assert result == "converted"
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        assert isinstance(registered["result"], VideoStreamResource)
        await registered["result"].close()
