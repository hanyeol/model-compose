"""Tests for the FFmpeg audio-converter driver.

Covers two layers:
  - Conversion behavior (format / codec / sample rate / channels / errors / output template)
  - I/O matrix (single / list input, ${result[]} stream output, batch_size)
"""

import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.audio_converter.drivers.ffmpeg import (
    FFmpegAudioConverterAction,
)
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.streaming import FileStreamResource
from mindor.dsl.schema.action import AudioConverterActionConfig


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
def sample_wav_path():
    """Generate a small mono 16-bit PCM WAV (1 second, 16 kHz, 440 Hz sine)."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0
    n_samples = int(sample_rate * duration)

    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(0.3 * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames += struct.pack("<h", value)
        w.writeframes(bytes(frames))

    yield path

    if os.path.exists(path):
        os.unlink(path)


def _make_context(audio_value: Any) -> ComponentActionContext:
    """Build a mock context where render_audio reads file paths into MediaSource.

    Supports single value or list of values. Tracks registered sources so that
    `${result[]}` / `${result}` output references resolve correctly.
    """
    from mindor.core.utils.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    def contains_ref(key: str, value: Any) -> bool:
        if key == "result[]" and isinstance(value, str):
            return "${result[]" in value
        return False
    ctx.contains_variable_reference = MagicMock(side_effect=contains_ref)

    async def render_variable(value, **kwargs):
        if isinstance(value, str):
            if value == "${result[]}":
                return sources.get("result[]")
            if value == "${result}":
                return sources.get("result")
        return value

    def resolve_one(value):
        # Treat strings as file paths: read into bytes so create_audio_source accepts it.
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_audio_source(value)

    async def render_audio(_value):
        if isinstance(audio_value, list):
            return [resolve_one(v) for v in audio_value]
        return resolve_one(audio_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


def _make_config(audio: Any = "<placeholder>", **kwargs) -> AudioConverterActionConfig:
    return AudioConverterActionConfig(audio=audio, **kwargs)


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
    """Copy a resource's underlying file (FileStreamResource) to a stable temp path."""
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
class TestFFmpegAudioConverter:
    """End-to-end conversion behavior for a single input."""

    @pytest.mark.anyio
    async def test_wav_to_mp3_conversion(self, sample_wav_path):
        config = _make_config(sample_wav_path, format="mp3")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

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
    async def test_wav_to_flac_conversion(self, sample_wav_path):
        config = _make_config(sample_wav_path, format="flac")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert result.format == "flac"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "flac"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_default_format_is_wav(self, sample_wav_path):
        config = _make_config(sample_wav_path)
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert result.format == "wav"
        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "pcm_s16le"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_sample_rate_override(self, sample_wav_path):
        config = _make_config(sample_wav_path, format="wav", sample_rate=8000)
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert int(info["sample_rate"]) == 8000
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_channels_override(self, sample_wav_path):
        # Source is mono; ffmpeg can up-mix to stereo.
        config = _make_config(sample_wav_path, format="wav", channels=2)
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert int(info["channels"]) == 2
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_explicit_codec_override(self, sample_wav_path):
        """Explicit codec config takes precedence over the format default."""
        # mp3 default codec is libmp3lame; keep default to make sure flow uses it.
        config = _make_config(sample_wav_path, format="mp3", codec="libmp3lame", bitrate="64k")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        out_path = await _drain_resource_to_file(result)
        try:
            info = _probe_audio_format(out_path)
            assert info["codec_name"] == "mp3"
        finally:
            os.unlink(out_path)

    @pytest.mark.anyio
    async def test_invalid_input_raises_runtime_error(self, tmp_path):
        # ffmpeg should reject random bytes written to a file.
        bogus = tmp_path / "bogus.wav"
        bogus.write_bytes(b"not an audio file at all" * 32)

        config = _make_config(str(bogus), format="mp3")
        ctx = _make_context(str(bogus))

        with pytest.raises(RuntimeError, match="ffmpeg audio conversion failed"):
            await FFmpegAudioConverterAction(config).run(ctx)

    @pytest.mark.anyio
    async def test_output_template_overrides_return_value(self, sample_wav_path):
        config = _make_config(sample_wav_path, format="mp3", output="converted")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert result == "converted"
        # 'result' source should still be registered (the AudioStreamResource).
        registered = dict(c.args for c in ctx.register_source.call_args_list)
        assert "result" in registered
        assert isinstance(registered["result"], AudioStreamResource)
        await registered["result"].close()


@ffmpeg_required
class TestSingleInput:
    """I/O matrix: single input with various output references."""

    @pytest.mark.anyio
    async def test_no_output_returns_single_resource(self, sample_wav_path):
        config = _make_config(format="mp3")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, AudioStreamResource)
        assert result.format == "mp3"
        await result.close()

    @pytest.mark.anyio
    async def test_passthrough_output_returns_single_resource(self, sample_wav_path):
        config = _make_config(output="${result}", format="wav")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, AudioStreamResource)
        await result.close()


@ffmpeg_required
class TestListInput:
    """I/O matrix: list input returns list of resources."""

    @pytest.mark.anyio
    async def test_list_returns_list_of_resources(self, sample_wav_path):
        config = _make_config(format="mp3")
        ctx = _make_context([sample_wav_path, sample_wav_path])

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, AudioStreamResource) for item in result)
        for item in result:
            await item.close()


@ffmpeg_required
class TestStreamOutput:
    """I/O matrix: ${result[]} stream output yields AsyncIterator."""

    @pytest.mark.anyio
    async def test_stream_output_returns_async_iterator(self, sample_wav_path):
        config = _make_config(output="${result[]}", format="mp3")
        ctx = _make_context([sample_wav_path, sample_wav_path])

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert all(isinstance(item, AudioStreamResource) for item in items)
        for item in items:
            await item.close()

    @pytest.mark.anyio
    async def test_stream_output_with_single_input_yields_one(self, sample_wav_path):
        config = _make_config(output="${result[]}", format="mp3")
        ctx = _make_context(sample_wav_path)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1
        await items[0].close()


@ffmpeg_required
class TestBatchSize:
    """I/O matrix: batch_size affects internal chunking but not result shape."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("batch_size", [1, 2, 3])
    async def test_list_with_batch_size(self, sample_wav_path, batch_size: int):
        config = _make_config(batch_size=batch_size, format="mp3")
        ctx = _make_context([sample_wav_path] * 3)

        result = await FFmpegAudioConverterAction(config).run(ctx)

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, AudioStreamResource)
            await item.close()


@ffmpeg_required
class TestErrorPropagation:
    """I/O matrix: errors in list inputs propagate via asyncio.gather."""

    @pytest.mark.anyio
    async def test_invalid_input_in_list_raises(self, sample_wav_path, tmp_path):
        bogus = tmp_path / "bogus.wav"
        bogus.write_bytes(b"not an audio file at all" * 32)

        config = _make_config(format="mp3")
        ctx = _make_context([sample_wav_path, str(bogus)])

        with pytest.raises(RuntimeError, match="ffmpeg audio conversion failed"):
            await FFmpegAudioConverterAction(config).run(ctx)
