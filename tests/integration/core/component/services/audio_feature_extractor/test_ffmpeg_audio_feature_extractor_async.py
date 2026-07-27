"""Async-behavior tests for the FFmpeg audio-feature-extractor driver.

Complements ``test_ffmpeg_audio_feature_extractor.py`` (which still passes an
obsolete ``loop`` arg to Action.run — kept as-is until the refactor is applied
there). These tests target the refactored ``.run(context)`` signature and
confirm:

- ``AudioFeatureExtractorAction.run`` accepts only ``(self, context)``
- The ffmpeg subprocess call in ``_decode_pcm`` does NOT block the event loop
- Batch/list inputs are all processed
- CancellationToken firing while ffmpeg is decoding does not deadlock the run
"""

from __future__ import annotations

import asyncio
import inspect
import math
import os
import shutil
import struct
import tempfile
import time
import wave
from typing import Any

import pytest
from unittest.mock import MagicMock

from mindor.core.component.services.audio_feature_extractor.drivers.ffmpeg import (
    FFmpegAudioFeatureExtractorAction,
    FFmpegAudioFeatureExtractorService,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.action import (
    SpectrumAudioFeatureExtractorActionConfig,
    WaveformAudioFeatureExtractorActionConfig,
)
from mindor.dsl.schema.action.impl.audio_feature_extractor.impl.common import AudioFeature

from tests.async_helpers import assert_does_not_block, make_action_context


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
def sine_10s_wav():
    """10-second mono 44.1kHz sine — large enough that ffmpeg PCM decode takes
    real wall time so the non-blocking assertion is meaningful."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=44100, duration=10.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sine_2s_wav():
    """2-second mono 22.05kHz sine wave — used for quick batch tests."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    _write_sine_wav(path, sample_rate=22050, duration=2.0, frequency=440.0, amplitude=0.5)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _wav_input(path: str) -> FileStreamResource:
    """``create_audio_source`` doesn't accept bare file paths, so wrap the path
    in a FileStreamResource which the media renderer can consume."""
    return FileStreamResource(path)


def _attach_cancellation(context, token: CancellationToken) -> None:
    workflow = MagicMock()
    workflow.cancellation_token = token
    workflow.component_event_notifier = None
    context.workflow = workflow


def _spectrum_config(source_template: str, **overrides) -> SpectrumAudioFeatureExtractorActionConfig:
    defaults = dict(
        feature=AudioFeature.SPECTRUM,
        audio=source_template,
        fps=30,
        sample_rate=22050,
        band_count=16,
        window_size=1024,
    )
    defaults.update(overrides)
    return SpectrumAudioFeatureExtractorActionConfig(**defaults)


def _waveform_config(source_template: str, **overrides) -> WaveformAudioFeatureExtractorActionConfig:
    defaults = dict(
        feature=AudioFeature.WAVEFORM,
        audio=source_template,
        fps=30,
        sample_rate=22050,
        point_count=100,
    )
    defaults.update(overrides)
    return WaveformAudioFeatureExtractorActionConfig(**defaults)


@ffmpeg_required
class TestActionRunSignature:
    """The refactored ``AudioFeatureExtractorAction.run`` takes only ``(self, context)``."""

    def test_action_run_signature_has_no_loop_param(self):
        params = list(inspect.signature(FFmpegAudioFeatureExtractorAction.run).parameters)
        assert params == ["self", "context"], f"unexpected run() signature: {params}"

    def test_service_run_signature_takes_action_and_context_only(self):
        params = list(inspect.signature(FFmpegAudioFeatureExtractorService._run).parameters)
        assert params == ["self", "action", "context"], f"unexpected _run signature: {params}"

    @pytest.mark.anyio
    async def test_service_run_can_be_called_with_just_action_and_context(self, sine_2s_wav):
        service = FFmpegAudioFeatureExtractorService(id="t", config=MagicMock(), daemon=False)
        action_config = _spectrum_config("${input.audio}", sample_rate=22050)
        context = make_action_context(input={"audio": _wav_input(sine_2s_wav)})

        result = await service._run(action_config, context)

        assert isinstance(result, dict)
        assert "frames" in result
        assert result["frame_count"] > 0


@ffmpeg_required
class TestNonBlockingBehavior:
    """Confirms the ffmpeg PCM-decode subprocess call does not block the loop.

    NOTE: after the decode, ``_compute_spectrum`` / ``_compute_waveform`` runs
    sync numpy work on the event loop. For small band counts and window sizes
    this completes in a few ms and does not trip the blocking guard, but a
    very large fps / band_count could. If the ticker check fails here, that is
    a latent bug worth flagging — the numpy compute path should be offloaded
    to a thread.
    """

    @pytest.mark.anyio
    async def test_spectrum_extract_does_not_block_event_loop(self, sine_10s_wav):
        config = _spectrum_config("${input.audio}", sample_rate=44100, fps=30, band_count=16)
        context = make_action_context(input={"audio": _wav_input(sine_10s_wav)})

        result = await assert_does_not_block(
            FFmpegAudioFeatureExtractorAction(config).run(context),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, dict)
        assert result["frame_count"] > 0

    @pytest.mark.anyio
    async def test_waveform_extract_does_not_block_event_loop(self, sine_10s_wav):
        config = _waveform_config("${input.audio}", sample_rate=44100, fps=30, point_count=100)
        context = make_action_context(input={"audio": _wav_input(sine_10s_wav)})

        result = await assert_does_not_block(
            FFmpegAudioFeatureExtractorAction(config).run(context),
            tick_interval_s=0.01,
            min_ticks=5,
        )

        assert isinstance(result, dict)
        assert result["frame_count"] > 0


@ffmpeg_required
class TestBatchInput:
    @pytest.mark.anyio
    async def test_list_input_all_items_processed(self, sine_2s_wav):
        config = _spectrum_config("${input.audios}")
        context = make_action_context(
            input={"audios": [_wav_input(sine_2s_wav) for _ in range(3)]},
        )

        result = await FFmpegAudioFeatureExtractorAction(config).run(context)

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert isinstance(item, dict)
            assert item["frame_count"] > 0


@ffmpeg_required
class TestCancellation:
    @pytest.mark.anyio
    async def test_cancellation_does_not_deadlock(self, sine_10s_wav):
        """Firing the token mid-decode should not cause the action to hang.

        The feature extractor's ffmpeg subprocess does not have its own
        cancellation watcher (unlike audio_extractor); cancellation instead
        surfaces on the next await after the PCM buffer is materialized. This
        test asserts the run terminates within a bounded time even when a
        token is cancelled mid-flight.
        """
        config = _spectrum_config("${input.audio}", sample_rate=44100, fps=30, band_count=16)
        context = make_action_context(input={"audio": _wav_input(sine_10s_wav)})
        token = CancellationToken()
        _attach_cancellation(context, token)

        async def _fire_soon():
            await asyncio.sleep(0.05)
            token.cancel("test-cancellation")

        fire_task = asyncio.create_task(_fire_soon())
        start = time.monotonic()

        try:
            await FFmpegAudioFeatureExtractorAction(config).run(context)
        except (asyncio.CancelledError, RuntimeError):
            pass

        elapsed = time.monotonic() - start
        await fire_task

        assert elapsed < 15.0, f"decode did not terminate promptly: {elapsed:.2f}s"
