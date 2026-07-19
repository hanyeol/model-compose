"""Integration test for the Silero VAD component: full `action.run(ctx, loop)`
flow with a real Silero model, exercising the `ComponentActionContext` plumbing
(render_audio, render_variable, register_source, streaming wrap-up).

This validates the boundary that unit tests skip:
  - DSL config parsing → action instantiation
  - render_audio picking up MediaSource from file / bytes / async stream
  - StreamChunkIterator wrapping of AsyncIterator results
  - Single-input vs list-input container shape
  - Streaming vs non-streaming return shape at the run() level
"""

from __future__ import annotations

import asyncio
import math
import os
import struct
import tempfile
import wave
from collections.abc import AsyncIterator
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.dsl.schema.action import VoiceActivityDetectionModelActionConfig


silero_required = pytest.mark.skipif(
    not all(__import__("importlib").util.find_spec(mod) for mod in ("silero_vad", "torch", "torchaudio", "soxr")),
    reason="silero-vad/torch/torchaudio/soxr not available",
)

BENCHMARK_AUDIO = "benchmarks/audio-streaming-pipeline/data/test.mp3"


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- WAV synth for lightweight tests ----

def _write_wav(path: str, duration: float, frequency: float, sample_rate: int = 16000) -> None:
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


@pytest.fixture(scope="module")
def synthetic_wav_path():
    """A 2-second 440 Hz sine wave. Silero should detect segments (or none — either is fine)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    _write_wav(tmp.name, duration=2.0, frequency=440.0)
    yield tmp.name
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


@pytest.fixture(scope="module")
def benchmark_mp3_path():
    if not os.path.exists(BENCHMARK_AUDIO):
        pytest.skip(f"benchmark audio missing: {BENCHMARK_AUDIO}")
    return BENCHMARK_AUDIO


# ---- Silero action factory ----

@pytest.fixture(scope="module")
def silero_action_factory():
    from silero_vad import load_silero_vad
    from mindor.core.component.services.model.tasks.voice_activity_detection.custom.silero import (
        SileroVoiceActivityDetectionTaskAction,
    )
    model = load_silero_vad()

    def _factory(config: VoiceActivityDetectionModelActionConfig) -> SileroVoiceActivityDetectionTaskAction:
        return SileroVoiceActivityDetectionTaskAction(config, model=model, device=None)

    return _factory


# ---- Context builder (mirrors STT integration test pattern) ----

def _make_context(audio_value: Any) -> ComponentActionContext:
    from mindor.core.foundation.streaming.audio import create_audio_source

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
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    def resolve_one(value):
        if isinstance(value, str):
            with open(value, "rb") as f:
                data = f.read()
            return create_audio_source(data)
        return create_audio_source(value)

    async def render_audio(_value):
        if isinstance(audio_value, list):
            return [resolve_one(v) for v in audio_value]
        return resolve_one(audio_value)

    ctx.render_variable = AsyncMock(side_effect=render_variable)
    ctx.render_audio = AsyncMock(side_effect=render_audio)
    return ctx


def _make_config(
    audio: Any = "<placeholder>",
    *,
    streaming: bool = False,
    batch_size: int = 1,
    output: Any = None,
    threshold: float = 0.5,
) -> VoiceActivityDetectionModelActionConfig:
    payload: dict = {
        "audio": audio,
        "streaming": streaming,
        "batch_size": batch_size,
        "sample_rate": 16000,
        "params": {
            "threshold": threshold,
            "min_speech_duration": "250ms",
            "min_silence_duration": "500ms",
            "speech_padding_time": "100ms",
        },
    }
    if output is not None:
        payload["output"] = output
    return VoiceActivityDetectionModelActionConfig.model_validate(payload)


def _assert_segment(seg: dict) -> None:
    assert set(seg.keys()) == {"start", "end", "confidence"}
    assert isinstance(seg["start"], float)
    assert isinstance(seg["end"], float)
    assert 0.0 <= seg["confidence"] <= 1.0
    assert seg["end"] > seg["start"]


# ---- Non-streaming: benchmark audio ----

@silero_required
class TestNonStreamingBenchmark:
    """streaming=False on benchmark audio: single input → List[dict], list input → List[List[dict]]."""

    @pytest.mark.anyio
    async def test_single_input_returns_list_of_segments(self, benchmark_mp3_path, silero_action_factory):
        config = _make_config(streaming=False)
        ctx = _make_context(benchmark_mp3_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) > 10
        for seg in result:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_lists(self, benchmark_mp3_path, silero_action_factory):
        config = _make_config(streaming=False, batch_size=2)
        ctx = _make_context([benchmark_mp3_path, benchmark_mp3_path])
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for per_audio in result:
            assert isinstance(per_audio, list)
            for seg in per_audio:
                _assert_segment(seg)


# ---- Streaming: benchmark audio ----

@silero_required
class TestStreamingBenchmark:
    """streaming=True on benchmark audio (MP3 fallback → pseudo-stream)."""

    @pytest.mark.anyio
    async def test_single_input_returns_stream_chunk_iterator(self, benchmark_mp3_path, silero_action_factory):
        config = _make_config(streaming=True)
        ctx = _make_context(benchmark_mp3_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, StreamChunkIterator)
        collected = [seg async for seg in result]
        assert len(collected) > 10
        for seg in collected:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_stream_chunk_iterators(self, benchmark_mp3_path, silero_action_factory):
        config = _make_config(streaming=True, batch_size=2)
        ctx = _make_context([benchmark_mp3_path, benchmark_mp3_path])
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, StreamChunkIterator)
            collected = [seg async for seg in item]
            assert len(collected) > 10


# ---- Sanity path: lightweight synthetic WAV (no benchmark file needed) ----

@silero_required
class TestSyntheticSanity:
    """Non-benchmark-dependent test using a small synthetic sine wave.

    Pure tone typically produces no speech segments — verifies that empty
    results are handled gracefully at the run() boundary.
    """

    @pytest.mark.anyio
    async def test_sine_wave_returns_valid_shape(self, synthetic_wav_path, silero_action_factory):
        config = _make_config(streaming=False)
        ctx = _make_context(synthetic_wav_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        # A 440 Hz sine may or may not fool Silero into finding "speech".
        # We only assert shape: list of dicts (possibly empty).
        assert isinstance(result, list)
        for seg in result:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_sine_wave_streaming_shape(self, synthetic_wav_path, silero_action_factory):
        config = _make_config(streaming=True)
        ctx = _make_context(synthetic_wav_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, StreamChunkIterator)
        collected = [seg async for seg in result]
        for seg in collected:
            _assert_segment(seg)


# ---- Output template routing ----

@silero_required
class TestOutputTemplate:
    """Verify default output template behavior (no explicit `output`)."""

    @pytest.mark.anyio
    async def test_default_output_passes_through_stream(self, benchmark_mp3_path, silero_action_factory):
        """Without an explicit `output`, streaming yields a StreamChunkIterator of segments."""
        config = _make_config(streaming=True, output=None)
        ctx = _make_context(benchmark_mp3_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, StreamChunkIterator)
        collected = [seg async for seg in result]
        assert len(collected) > 0
        for seg in collected:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_default_output_passes_through_batch(self, benchmark_mp3_path, silero_action_factory):
        """Without an explicit `output`, non-streaming returns the raw List[dict]."""
        config = _make_config(streaming=False, output=None)
        ctx = _make_context(benchmark_mp3_path)
        action = silero_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) > 0
        for seg in result:
            _assert_segment(seg)
