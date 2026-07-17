"""Integration test for the SepFormer speech-separation component: full
`action.run(ctx, loop)` flow with a real SepFormer checkpoint, exercising the
`ComponentActionContext` plumbing (render_audio, render_variable,
register_source, streaming wrap-up).

Skipped by default unless `speechbrain` (and its deps) are installed AND the
`speechbrain/sepformer-wsj02mix` checkpoint is either cached or downloadable.
Uses a very short synthetic sine-wave mixture so no benchmark audio is required.
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
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.iterators import StreamChunkIterator
from mindor.dsl.schema.action import SpeechSeparationModelActionConfig


sepformer_required = pytest.mark.skipif(
    not all(__import__("importlib").util.find_spec(mod) for mod in ("speechbrain", "torch", "torchaudio", "soxr")),
    reason="speechbrain/torch/torchaudio/soxr not available",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- WAV synth ----

def _write_wav(path: str, duration: float, frequency: float, sample_rate: int = 8000) -> None:
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
    """A 1-second 440 Hz sine wave at 8 kHz (SepFormer WSJ mix rate)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    _write_wav(tmp.name, duration=1.0, frequency=440.0, sample_rate=8000)
    yield tmp.name
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


# ---- SepFormer action factory ----

@pytest.fixture(scope="module")
def sepformer_action_factory():
    try:
        from speechbrain.inference.separation import SepformerSeparation
    except Exception as e:
        pytest.skip(f"speechbrain not importable: {e}")

    try:
        model = SepformerSeparation.from_hparams(
            source="speechbrain/sepformer-wsj02mix",
            savedir=os.path.join(tempfile.gettempdir(), "sb-sepformer-wsj02mix"),
            run_opts={"device": "cpu"},
        )
    except Exception as e:
        pytest.skip(f"could not load speechbrain/sepformer-wsj02mix: {e}")

    from mindor.core.component.services.model.tasks.speech_separation.custom.sepformer import (
        SepformerSpeechSeparationTaskAction,
    )

    def _factory(config: SpeechSeparationModelActionConfig) -> SepformerSpeechSeparationTaskAction:
        return SepformerSpeechSeparationTaskAction(config, model=model, device=None)

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
    num_speakers: int = 2,
) -> SpeechSeparationModelActionConfig:
    payload: dict = {
        "audio": audio,
        "streaming": streaming,
        "batch_size": batch_size,
        "sample_rate": 8000,
        "params": {
            "num_speakers": num_speakers,
        },
    }
    if output is not None:
        payload["output"] = output
    return SpeechSeparationModelActionConfig.model_validate(payload)


def _assert_track(track: dict, expected_sample_rate: int = 8000) -> None:
    assert set(track.keys()) == {"index", "sample_rate", "audio"}
    assert isinstance(track["index"], int)
    assert track["sample_rate"] == expected_sample_rate
    assert isinstance(track["audio"], PcmStreamResource)


# ---- Non-streaming ----

@sepformer_required
class TestNonStreaming:
    @pytest.mark.anyio
    async def test_single_input_returns_list_of_tracks(self, synthetic_wav_path, sepformer_action_factory):
        config = _make_config(streaming=False)
        ctx = _make_context(synthetic_wav_path)
        action = sepformer_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        # wsj02mix returns 2 tracks
        assert len(result) == 2
        for i, track in enumerate(result):
            _assert_track(track)
            assert track["index"] == i

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_track_lists(self, synthetic_wav_path, sepformer_action_factory):
        config = _make_config(streaming=False, batch_size=2)
        ctx = _make_context([synthetic_wav_path, synthetic_wav_path])
        action = sepformer_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for per_audio in result:
            assert isinstance(per_audio, list)
            assert len(per_audio) == 2
            for track in per_audio:
                _assert_track(track)


# ---- Streaming ----

@sepformer_required
class TestStreaming:
    @pytest.mark.anyio
    async def test_single_input_returns_stream_chunk_iterator(self, synthetic_wav_path, sepformer_action_factory):
        config = _make_config(streaming=True)
        ctx = _make_context(synthetic_wav_path)
        action = sepformer_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, StreamChunkIterator)
        collected = [track async for track in result]
        assert len(collected) == 2
        for track in collected:
            _assert_track(track)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_stream_chunk_iterators(self, synthetic_wav_path, sepformer_action_factory):
        config = _make_config(streaming=True, batch_size=2)
        ctx = _make_context([synthetic_wav_path, synthetic_wav_path])
        action = sepformer_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, StreamChunkIterator)
            collected = [track async for track in item]
            assert len(collected) == 2
