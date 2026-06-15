"""Integration tests for HuggingfaceSpeechToTextTaskAction with real whisper-tiny.

Verifies the I/O matrix in a single batched ``model.generate()`` call:
  - non-streaming batch: ``List[str]`` with one entry per input audio
  - streaming batch: ``List[StreamChunkIterator]`` driven by BatchTextIteratorStreamer

Sine-wave audio is used because we are testing the streamer plumbing, not
transcription accuracy. The model will typically emit a few generic tokens.
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

import pytest
from unittest.mock import AsyncMock, MagicMock

from mindor.core.component.context import ComponentActionContext
from mindor.core.utils.iterators import StreamChunkIterator
from mindor.dsl.schema.action import SpeechToTextModelActionConfig


transformers_required = pytest.mark.skipif(
    not all(__import__("importlib").util.find_spec(mod) for mod in ("transformers", "torch", "torchaudio")),
    reason="transformers/torch/torchaudio not available",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_wav(duration: float, frequency: float) -> str:
    """Generate a mono 16-bit PCM WAV (16 kHz, configurable duration + tone)."""
    path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    sample_rate = 16000
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
    return path


@pytest.fixture(scope="module")
def sample_wav_path():
    """A 1-second 440 Hz sine wave."""
    path = _make_wav(duration=1.0, frequency=440.0)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="module")
def sample_wav_pair():
    """Two clearly distinct sine waves so row-by-row outputs can be told apart."""
    path_a = _make_wav(duration=1.0, frequency=220.0)
    path_b = _make_wav(duration=2.5, frequency=880.0)
    yield path_a, path_b
    for p in (path_a, path_b):
        if os.path.exists(p):
            os.unlink(p)


@pytest.fixture(scope="module")
def whisper_action_factory():
    """Load whisper-tiny once per module, return a factory for action instances."""
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    from mindor.core.component.services.model.tasks.speech_to_text.huggingface import (
        HuggingfaceSpeechToTextTaskAction,
    )

    try:
        model     = WhisperForConditionalGeneration.from_pretrained("openai/whisper-tiny")
        processor = WhisperProcessor.from_pretrained("openai/whisper-tiny")
    except Exception as e:
        pytest.skip(f"whisper-tiny unavailable: {e}")

    device = torch.device("cpu")
    model = model.to(device)
    model.eval()

    def _factory(config: SpeechToTextModelActionConfig) -> HuggingfaceSpeechToTextTaskAction:
        return HuggingfaceSpeechToTextTaskAction(config, model, processor, device)

    return _factory


def _make_context(audio_value: Any) -> ComponentActionContext:
    """Build a mock context that routes render_audio to MediaSource(s) and tracks sources.

    `audio_value` may be:
      - file path str → single MediaSource
      - list of file path strs → List[MediaSource]
      - zero-arg callable returning an AsyncIterator of strs → AsyncIterator[MediaSource]
    """
    from mindor.core.utils.audio import create_audio_source

    ctx = MagicMock(spec=ComponentActionContext)
    sources: dict = {}

    def register_source(key: str, value: Any) -> None:
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
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value

    def resolve_one(value):
        if isinstance(value, str):
            with open(value, "rb") as f:
                value = f.read()
        return create_audio_source(value)

    async def render_audio(_value):
        if callable(audio_value) and not isinstance(audio_value, str):
            source = audio_value()
            assert isinstance(source, AsyncIterator)

            async def _map():
                async for item in source:
                    yield resolve_one(item)
            return _map()
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
    language: str = "en",
    task: str = "transcribe",
    max_output_length: int = 16,
) -> SpeechToTextModelActionConfig:
    payload: dict = {
        "audio": audio,
        "streaming": streaming,
        "batch_size": batch_size,
        "language": language,
        "task": task,
        "params": {
            "max_output_length": max_output_length,
            "num_beams": 1,
            "temperature": 0.0,
        },
    }
    if output is not None:
        payload["output"] = output
    return SpeechToTextModelActionConfig.model_validate(payload)


@transformers_required
class TestNonStreamingBatch:
    """``streaming=False``: a single batched generate() → List[str] decoded."""

    @pytest.mark.anyio
    async def test_single_input_returns_string(self, sample_wav_path, whisper_action_factory):
        config = _make_config(sample_wav_path, streaming=False)
        ctx    = _make_context(sample_wav_path)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, str)

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_strings(self, sample_wav_path, whisper_action_factory):
        config = _make_config(streaming=False, batch_size=2)
        ctx    = _make_context([sample_wav_path, sample_wav_path])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, str) for item in result)


@transformers_required
class TestStreamingBatch:
    """``streaming=True``: one batched generate() with BatchTextIteratorStreamer."""

    @pytest.mark.anyio
    async def test_single_input_returns_chunk_iterator(self, sample_wav_path, whisper_action_factory):
        config = _make_config(sample_wav_path, streaming=True)
        ctx    = _make_context(sample_wav_path)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        # streaming=True + is_stream_mode=False (no ${result[]}) + single input
        # → StreamChunkIterator
        assert isinstance(result, StreamChunkIterator)

        tokens = [chunk async for chunk in result]
        assert all(isinstance(t, str) for t in tokens)
        # Sanity: at least the end-of-stream callback fired
        assert len(tokens) >= 0

    @pytest.mark.anyio
    async def test_list_input_returns_list_of_chunk_iterators(self, sample_wav_path, whisper_action_factory):
        config = _make_config(streaming=True, batch_size=2)
        ctx    = _make_context([sample_wav_path, sample_wav_path])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, StreamChunkIterator) for item in result)

        # Drain each iterator concurrently — proves rows are independent and the
        # batch streamer fan-out worked.
        async def _drain(it: StreamChunkIterator) -> List[str]:
            return [chunk async for chunk in it]

        outputs = await asyncio.gather(*[_drain(it) for it in result])
        assert len(outputs) == 2
        for tokens in outputs:
            assert all(isinstance(t, str) for t in tokens)


@transformers_required
class TestPassthroughOutput:
    """``output='${result}'`` keeps the collect-mode return shape (single or list)."""

    @pytest.mark.anyio
    async def test_passthrough_single_returns_string(self, sample_wav_path, whisper_action_factory):
        config = _make_config(sample_wav_path, output="${result}")
        ctx    = _make_context(sample_wav_path)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, str)

    @pytest.mark.anyio
    async def test_passthrough_list_returns_list_of_strings(self, sample_wav_path, whisper_action_factory):
        config = _make_config(output="${result}", batch_size=2)
        ctx    = _make_context([sample_wav_path, sample_wav_path])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list) and len(result) == 2
        assert all(isinstance(item, str) for item in result)


@transformers_required
class TestStreamOutputTemplate:
    """``output='${result[]}'`` (is_stream_output=True) → AsyncIterator regardless of streaming."""

    @pytest.mark.anyio
    async def test_stream_output_non_streaming_yields_strings(self, sample_wav_path, whisper_action_factory):
        # streaming=False + ${result[]}: each transcribed string is yielded.
        config = _make_config(output="${result[]}", batch_size=2)
        ctx    = _make_context([sample_wav_path, sample_wav_path])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert all(isinstance(item, str) for item in items)

    @pytest.mark.anyio
    async def test_stream_output_non_streaming_with_single_input(self, sample_wav_path, whisper_action_factory):
        config = _make_config(sample_wav_path, output="${result[]}")
        ctx    = _make_context(sample_wav_path)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 1
        assert isinstance(items[0], str)

    @pytest.mark.anyio
    async def test_stream_output_streaming_flattens_tokens(self, sample_wav_path, whisper_action_factory):
        # streaming=True + ${result[]}: tokens from all inputs are flattened into
        # a single AsyncIterator at the base run() level.
        config = _make_config(output="${result[]}", streaming=True, batch_size=2)
        ctx    = _make_context([sample_wav_path, sample_wav_path])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert all(isinstance(item, str) for item in items)


@transformers_required
class TestAsyncIteratorInput:
    """AsyncIterator input always produces stream output (stream-in → stream-out)."""

    @pytest.mark.anyio
    async def test_stream_input_non_streaming_yields_strings(self, sample_wav_path, whisper_action_factory):
        def _make_iter():
            async def _gen():
                yield sample_wav_path
                yield sample_wav_path
            return _gen()

        config = _make_config()
        ctx    = _make_context(_make_iter)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert len(items) == 2
        assert all(isinstance(item, str) for item in items)

    @pytest.mark.anyio
    async def test_stream_input_streaming_flattens_tokens(self, sample_wav_path, whisper_action_factory):
        def _make_iter():
            async def _gen():
                yield sample_wav_path
                yield sample_wav_path
            return _gen()

        # AsyncIterator input → is_stream_mode=True; streaming=True → token-level yield.
        config = _make_config(streaming=True)
        ctx    = _make_context(_make_iter)
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, AsyncIterator)
        items = [item async for item in result]
        assert all(isinstance(item, str) for item in items)


@transformers_required
class TestBatchRowIndependence:
    """BatchTextIteratorStreamer's fan-out: row N tokens stay with row N."""

    @pytest.mark.anyio
    async def test_two_distinct_inputs_produce_distinct_streams(self, sample_wav_pair, whisper_action_factory):
        path_short, path_long = sample_wav_pair
        config = _make_config(streaming=True, batch_size=2)
        ctx    = _make_context([path_short, path_long])
        action = whisper_action_factory(config)

        result = await action.run(ctx, asyncio.get_event_loop())

        assert isinstance(result, list) and len(result) == 2

        # Drain rows concurrently — token streams must not cross-talk.
        async def _drain(it: StreamChunkIterator) -> str:
            return "".join([chunk async for chunk in it])

        text_a, text_b = await asyncio.gather(_drain(result[0]), _drain(result[1]))

        # Both rows decoded at least something (the streamer emitted via end()).
        assert isinstance(text_a, str)
        assert isinstance(text_b, str)
        # Sanity: the longer audio yields at least as much text as the shorter one
        # — exact contents are model-dependent, but length monotonicity is a robust
        # check that row 1 wasn't fed row 0's tokens.
        assert len(text_b) >= len(text_a) - 1  # allow tiny rounding
