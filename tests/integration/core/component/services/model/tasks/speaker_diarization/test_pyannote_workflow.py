"""Integration test for the pyannote speaker-diarization component: full
`action.run(ctx, loop)` flow with a real pyannote pipeline, exercising the
`ComponentActionContext` plumbing (render_audio, render_variable,
register_source, streaming wrap-up).

Skipped by default unless `pyannote.audio` (and its deps) are installed AND
an `HF_TOKEN` environment variable is available with access to the gated
`pyannote/speaker-diarization-3.1` model.
"""

from __future__ import annotations

import asyncio
import math
import os
import struct
import tempfile
import wave
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindor.core.component.context import ComponentActionContext
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.dsl.schema.action import SpeakerDiarizationModelActionConfig


def _has_module(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


pyannote_required = pytest.mark.skipif(
    not all(_has_module(mod) for mod in ("pyannote.audio", "torch", "torchaudio", "soxr"))
    or not os.environ.get("HF_TOKEN"),
    reason="pyannote.audio/torch/torchaudio/soxr not available, or HF_TOKEN not set",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- WAV synth ----

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
    """A 3-second 440 Hz sine wave. Diarization on a pure tone typically yields
    zero speaker turns — we only assert shape at the run() boundary."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    _write_wav(tmp.name, duration=3.0, frequency=440.0, sample_rate=16000)
    yield tmp.name
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


# ---- pyannote action factory ----

@pytest.fixture(scope="module")
def pyannote_action_factory():
    try:
        from pyannote.audio import Pipeline
    except Exception as e:
        pytest.skip(f"pyannote.audio not importable: {e}")

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=os.environ["HF_TOKEN"],
        )
    except Exception as e:
        pytest.skip(f"could not load pyannote/speaker-diarization-3.1: {e}")

    if pipeline is None:
        pytest.skip("pyannote pipeline returned None (token missing or model access denied)")

    from mindor.core.component.services.model.tasks.speaker_diarization.custom.pyannote import (
        PyannoteSpeakerDiarizationTaskAction,
    )

    def _factory(config: SpeakerDiarizationModelActionConfig) -> PyannoteSpeakerDiarizationTaskAction:
        return PyannoteSpeakerDiarizationTaskAction(config, pipeline=pipeline, device=None)

    return _factory


# ---- Context builder ----

def _make_context(audio_value: Any) -> ComponentActionContext:
    from mindor.core.foundation.streaming.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
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
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    merge_gap: str = "0s",
    min_segment_duration: str = "0s",
) -> SpeakerDiarizationModelActionConfig:
    payload: dict = {
        "audio": audio,
        "streaming": streaming,
        "batch_size": batch_size,
        "sample_rate": 16000,
        "params": {
            "num_speakers": num_speakers,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
            "merge_gap": merge_gap,
            "min_segment_duration": min_segment_duration,
        },
    }
    if output is not None:
        payload["output"] = output
    return SpeakerDiarizationModelActionConfig.model_validate(payload)


def _assert_segment(seg: dict) -> None:
    assert set(seg.keys()) == {"speaker", "start", "end", "confidence"}
    assert isinstance(seg["speaker"], str)
    assert isinstance(seg["start"], float)
    assert isinstance(seg["end"], float)
    assert seg["end"] > seg["start"]
    assert 0.0 <= seg["confidence"] <= 1.0


# ---- Non-streaming ----

@pyannote_required
class TestNonStreaming:
    @pytest.mark.anyio
    async def test_single_input_returns_list(self, synthetic_wav_path, pyannote_action_factory):
        config = _make_config(streaming=False)
        ctx = _make_context(synthetic_wav_path)
        action = pyannote_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        for seg in result:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_lists(self, synthetic_wav_path, pyannote_action_factory):
        config = _make_config(streaming=False, batch_size=2)
        ctx = _make_context([synthetic_wav_path, synthetic_wav_path])
        action = pyannote_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for per_audio in result:
            assert isinstance(per_audio, list)
            for seg in per_audio:
                _assert_segment(seg)


# ---- Streaming ----

@pyannote_required
class TestStreaming:
    @pytest.mark.anyio
    async def test_single_input_returns_stream_chunk_iterator(self, synthetic_wav_path, pyannote_action_factory):
        config = _make_config(streaming=True)
        ctx = _make_context(synthetic_wav_path)
        action = pyannote_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, StreamChunkIterator)
        collected = [seg async for seg in result]
        for seg in collected:
            _assert_segment(seg)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_stream_chunk_iterators(self, synthetic_wav_path, pyannote_action_factory):
        config = _make_config(streaming=True, batch_size=2)
        ctx = _make_context([synthetic_wav_path, synthetic_wav_path])
        action = pyannote_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, StreamChunkIterator)
            collected = [seg async for seg in item]
            for seg in collected:
                _assert_segment(seg)
