"""Tests for the FFmpeg audio-feature-extractor driver.

Covers two features:
  - Spectrum: FFT-based frequency-band magnitudes per frame.
  - Waveform: Time-domain amplitude summary per frame (peak / RMS).
"""

import math
import asyncio
import os
import shutil
import struct
import tempfile
import wave
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.audio_feature_extractor.drivers.ffmpeg import (
    FFmpegAudioFeatureExtractorAction,
)
from mindor.dsl.schema.action import (
    SpectrumAudioFeatureExtractorActionConfig,
    WaveformAudioFeatureExtractorActionConfig,
)
from mindor.dsl.schema.action.impl.audio_feature_extractor.impl.common import AudioFeature


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not available on PATH"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _write_sine_wav(path: str, sample_rate: int, duration: float, frequency: float, amplitude: float = 0.5) -> None:
    n_samples = int(sample_rate * duration)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames += struct.pack("<h", value)
        w.writeframes(bytes(frames))


@pytest.fixture(scope="module")
def sine_440hz_wav():
    """3-second mono 22.05 kHz 440 Hz sine wave."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=22050, duration=3.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sine_2khz_wav():
    """1-second mono 22.05 kHz 2 kHz sine wave (higher frequency band)."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=22050, duration=1.0, frequency=2000.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def silent_wav():
    """1-second mono 22.05 kHz silence."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=22050, duration=1.0, frequency=440.0, amplitude=0.0)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _make_context(audio_value: Any) -> ComponentActionContext:
    """Mock context where render_audio wraps file paths into MediaSource."""
    from mindor.core.foundation.streaming.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
    ctx.cancellation_token = None
    sources: dict = {}

    def register_source(key: str, value: Any, scope: Any = None) -> None:
        sources[key] = value
    ctx.register_source = MagicMock(side_effect=register_source)

    async def render_variable(value, **kwargs):
        return value

    def resolve_one(value):
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


def _spectrum_config(audio: Any = "<placeholder>", **overrides) -> SpectrumAudioFeatureExtractorActionConfig:
    defaults = dict(
        feature=AudioFeature.SPECTRUM,
        audio=audio,
        fps=30,
        sample_rate=22050,
        band_count=32,
    )
    defaults.update(overrides)
    return SpectrumAudioFeatureExtractorActionConfig(**defaults)


def _waveform_config(audio: Any = "<placeholder>", **overrides) -> WaveformAudioFeatureExtractorActionConfig:
    defaults = dict(
        feature=AudioFeature.WAVEFORM,
        audio=audio,
        fps=30,
        sample_rate=22050,
        point_count=100,
    )
    defaults.update(overrides)
    return WaveformAudioFeatureExtractorActionConfig(**defaults)


@ffmpeg_required
class TestSpectrumExtractor:
    @pytest.mark.anyio
    async def test_spectrum_output_shape(self, sine_440hz_wav):
        config = _spectrum_config(sine_440hz_wav, fps=30, sample_rate=22050, band_count=32)
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, dict)
        assert result["fps"] == 30
        assert result["sample_rate"] == 22050
        assert result["band_count"] == 32
        assert result["frame_count"] > 0
        assert len(result["frames"]) == result["frame_count"]
        for frame in result["frames"]:
            assert len(frame) == 32

    @pytest.mark.anyio
    async def test_spectrum_peak_percentile_bounded_0_1(self, sine_440hz_wav):
        config = _spectrum_config(sine_440hz_wav, normalize_mode="peak-percentile")
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        max_value = max(v for frame in result["frames"] for v in frame)
        min_value = min(v for frame in result["frames"] for v in frame)
        assert 0.0 <= min_value
        assert max_value <= 1.0
        # With a strong 440 Hz tone, the peak should reach the top of the scale.
        assert max_value > 0.9

    @pytest.mark.anyio
    async def test_spectrum_no_normalization_raw_magnitudes(self, sine_440hz_wav):
        config = _spectrum_config(sine_440hz_wav, normalize_mode="none")
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        max_value = max(v for frame in result["frames"] for v in frame)
        # Unnormalized FFT magnitudes are >> 1 for a full-scale tone.
        assert max_value > 1.0

    @pytest.mark.anyio
    async def test_spectrum_dominant_band_matches_tone_frequency(self, sine_440hz_wav):
        """The band containing 440 Hz should peak higher than other bands (averaged over frames)."""
        config = _spectrum_config(
            sine_440hz_wav,
            band_count=32,
            min_frequency=40.0,
            frequency_scale="log",
        )
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        # Average magnitude per band, then find the peak band.
        band_count = result["band_count"]
        averages = [
            sum(frame[i] for frame in result["frames"]) / len(result["frames"])
            for i in range(band_count)
        ]
        peak_band = max(range(band_count), key=lambda i: averages[i])

        # For log-spaced bands (40 Hz - 11025 Hz, 32 bands), 440 Hz sits around band 9-13.
        assert 5 <= peak_band <= 20

    @pytest.mark.anyio
    async def test_spectrum_linear_scale(self, sine_440hz_wav):
        config = _spectrum_config(sine_440hz_wav, frequency_scale="linear")
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["frame_count"] > 0
        assert result["band_count"] == 32

    @pytest.mark.anyio
    async def test_spectrum_higher_fps_yields_more_frames(self, sine_440hz_wav):
        config_30 = _spectrum_config(sine_440hz_wav, fps=30)
        config_60 = _spectrum_config(sine_440hz_wav, fps=60)
        ctx_30 = _make_context(sine_440hz_wav)
        ctx_60 = _make_context(sine_440hz_wav)

        loop = asyncio.get_running_loop()
        result_30 = await FFmpegAudioFeatureExtractorAction(config_30).run(ctx_30, loop)
        result_60 = await FFmpegAudioFeatureExtractorAction(config_60).run(ctx_60, loop)

        assert result_60["frame_count"] > result_30["frame_count"]

    @pytest.mark.anyio
    async def test_spectrum_silent_input_has_low_magnitude(self, silent_wav):
        config = _spectrum_config(silent_wav, normalize_mode="none")
        ctx = _make_context(silent_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        max_value = max((v for frame in result["frames"] for v in frame), default=0.0)
        # Silent input should produce near-zero magnitudes.
        assert max_value < 1e-3

    @pytest.mark.anyio
    async def test_spectrum_string_inputs_are_cast(self, sine_440hz_wav):
        """Params arriving as strings (from YAML/webui) should be cast to numeric types."""
        config = _spectrum_config(
            sine_440hz_wav,
            fps="30",
            sample_rate="22050",
            band_count="16",
            min_frequency="40",
            window_size="1024",
            percentile="99",
        )
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["band_count"] == 16
        assert result["fps"] == 30


@ffmpeg_required
class TestWaveformExtractor:
    @pytest.mark.anyio
    async def test_waveform_output_shape(self, sine_440hz_wav):
        config = _waveform_config(sine_440hz_wav, fps=30, point_count=100)
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert result["fps"] == 30
        assert result["point_count"] == 100
        assert result["frame_count"] > 0
        for frame in result["frames"]:
            assert len(frame) == 100

    @pytest.mark.anyio
    async def test_waveform_peak_matches_amplitude(self, sine_440hz_wav):
        """Peak summary of a 0.5-amplitude sine should max out near 0.5."""
        config = _waveform_config(sine_440hz_wav, summary_mode="peak", rectify=True)
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        max_value = max(v for frame in result["frames"] for v in frame)
        assert 0.4 <= max_value <= 0.55

    @pytest.mark.anyio
    async def test_waveform_rms_is_smaller_than_peak(self, sine_440hz_wav):
        """For a sine wave, RMS = amplitude / sqrt(2) < peak amplitude."""
        peak_config = _waveform_config(sine_440hz_wav, summary_mode="peak", rectify=True)
        rms_config  = _waveform_config(sine_440hz_wav, summary_mode="rms",  rectify=True)
        loop = asyncio.get_running_loop()

        peak_result = await FFmpegAudioFeatureExtractorAction(peak_config).run(_make_context(sine_440hz_wav), loop)
        rms_result  = await FFmpegAudioFeatureExtractorAction(rms_config ).run(_make_context(sine_440hz_wav), loop)

        max_peak = max(v for frame in peak_result["frames"] for v in frame)
        max_rms  = max(v for frame in rms_result ["frames"] for v in frame)
        # RMS of a full-window sine ≈ amplitude / sqrt(2). It should be visibly smaller than the peak.
        assert max_rms < max_peak
        assert max_rms > 0.25  # roughly 0.5/sqrt(2) ≈ 0.354

    @pytest.mark.anyio
    async def test_waveform_rectified_values_are_non_negative(self, sine_440hz_wav):
        config = _waveform_config(sine_440hz_wav, summary_mode="peak", rectify=True)
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        min_value = min(v for frame in result["frames"] for v in frame)
        assert min_value >= 0.0

    @pytest.mark.anyio
    async def test_waveform_signed_values_span_negative(self, sine_440hz_wav):
        """When rectify=False, peak mode returns signed peaks (can be negative)."""
        config = _waveform_config(sine_440hz_wav, summary_mode="peak", rectify=False)
        ctx = _make_context(sine_440hz_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        min_value = min(v for frame in result["frames"] for v in frame)
        max_value = max(v for frame in result["frames"] for v in frame)
        assert min_value < 0.0 < max_value

    @pytest.mark.anyio
    async def test_waveform_window_duration_string(self, sine_440hz_wav):
        """window_duration accepts human strings like '40ms', '0.04s'."""
        config_ms = _waveform_config(sine_440hz_wav, window_duration="40ms")
        config_s  = _waveform_config(sine_440hz_wav, window_duration="0.04s")
        loop = asyncio.get_running_loop()

        result_ms = await FFmpegAudioFeatureExtractorAction(config_ms).run(_make_context(sine_440hz_wav), loop)
        result_s  = await FFmpegAudioFeatureExtractorAction(config_s ).run(_make_context(sine_440hz_wav), loop)

        # 40ms == 0.04s → identical frame count.
        assert result_ms["frame_count"] == result_s["frame_count"]

    @pytest.mark.anyio
    async def test_waveform_silent_input(self, silent_wav):
        config = _waveform_config(silent_wav)
        ctx = _make_context(silent_wav)

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        max_value = max((v for frame in result["frames"] for v in frame), default=0.0)
        assert max_value < 1e-3


@ffmpeg_required
class TestBatchInputs:
    @pytest.mark.anyio
    async def test_list_input_returns_list_of_results(self, sine_440hz_wav, sine_2khz_wav):
        config = _spectrum_config([sine_440hz_wav, sine_2khz_wav])
        ctx = _make_context([sine_440hz_wav, sine_2khz_wav])

        result = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert item["band_count"] == 32
            assert item["frame_count"] > 0

    @pytest.mark.anyio
    async def test_dominant_band_differs_by_input_frequency(self, sine_440hz_wav, sine_2khz_wav):
        """Different tones should place their peak in different bands."""
        config = _spectrum_config(
            [sine_440hz_wav, sine_2khz_wav],
            band_count=32,
            min_frequency=40.0,
            frequency_scale="log",
        )
        ctx = _make_context([sine_440hz_wav, sine_2khz_wav])

        results = await FFmpegAudioFeatureExtractorAction(config).run(ctx, asyncio.get_running_loop())

        def peak_band(spec: dict) -> int:
            band_count = spec["band_count"]
            averages = [
                sum(frame[i] for frame in spec["frames"]) / len(spec["frames"])
                for i in range(band_count)
            ]
            return max(range(band_count), key=lambda i: averages[i])

        band_440  = peak_band(results[0])
        band_2khz = peak_band(results[1])
        assert band_2khz > band_440
