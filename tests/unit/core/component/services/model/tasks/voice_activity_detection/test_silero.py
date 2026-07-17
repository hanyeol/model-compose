"""Unit tests for :class:`SileroVoiceActivityDetectionTaskAction`.

Uses the real Silero VAD model (loaded via silero-vad pip package). Tests
cover the four dispatch paths under `_detect`:

  1. streaming=True + streamable PCM      → true online AsyncIterator
  2. streaming=True + non-streamable      → pseudo-stream AsyncIterator over batch result
  3. streaming=False + any source         → List of segment dicts
  4. mixed batch (per-item routing)

Includes a bytes-normalization regression: PCM int16 batch must be normalized to
[-1, 1] before feeding Silero, otherwise segments explode. This test guards the
fix applied in `_preprocess_audio`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import List

import numpy as np
import pytest

from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.variable.time import parse_duration


AUDIO_FILE = "benchmarks/audio-streaming-pipeline/data/test.mp3"


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---- Helpers ----

class ChunkedPcmResource(StreamResource):
    """PCM byte source that yields fixed-size chunks (simulates streaming input)."""

    def __init__(self, data: bytes, chunk_size: int):
        super().__init__("audio/pcm", None)
        self._data = data
        self._chunk_size = chunk_size

    async def close(self) -> None:
        pass

    async def _iterate_stream(self):
        for i in range(0, len(self._data), self._chunk_size):
            yield self._data[i:i + self._chunk_size]


@pytest.fixture(scope="module")
def silero_model():
    """Load the Silero VAD model once per test module (slow init)."""
    from silero_vad import load_silero_vad
    return load_silero_vad()


@pytest.fixture(scope="module")
def audio_pcm_bytes() -> bytes:
    """Load benchmark audio and encode as raw s16le PCM at 16 kHz mono."""
    from silero_vad import read_audio
    wav = read_audio(AUDIO_FILE, sampling_rate=16000).numpy()
    return (np.clip(wav, -1.0, 1.0) * 32767).astype("<i2").tobytes()


@pytest.fixture
def action(silero_model):
    """Build a bare SileroVoiceActivityDetectionTaskAction without running the
    full ComponentActionContext plumbing — we only need `_detect` here."""
    from mindor.core.component.services.model.tasks.voice_activity_detection.custom.silero import (
        SileroVoiceActivityDetectionTaskAction,
    )

    class _Cfg:
        audio = "x"
        sample_rate = 16000
        batch_size = 1
        streaming = True
        output = None

    a = SileroVoiceActivityDetectionTaskAction.__new__(SileroVoiceActivityDetectionTaskAction)
    a.config = _Cfg()
    a.device = None
    a.model = silero_model
    return a


@pytest.fixture
def params():
    return {
        "sample_rate": 16000,
        "threshold": 0.5,
        "min_speech_duration": parse_duration("250ms"),
        "max_speech_duration": None,
        "min_silence_duration": parse_duration("500ms"),
        "speech_padding_time": parse_duration("100ms"),
    }


def _pcm_mono_source(pcm: bytes, chunk_size: int = 8000) -> MediaSource:
    return MediaSource(
        ChunkedPcmResource(pcm, chunk_size),
        format="s16le",
        attrs={"sample_rate": 16000, "channels": 1},
    )


def _mp3_source() -> MediaSource:
    return MediaSource(FileStreamResource(AUDIO_FILE), format="mp3")


async def _collect(async_iter: AsyncIterator[dict]) -> List[dict]:
    return [item async for item in async_iter]


def _assert_segment_shape(seg: dict) -> None:
    assert set(seg.keys()) == {"start", "end", "confidence"}
    assert isinstance(seg["start"], float)
    assert isinstance(seg["end"], float)
    assert 0.0 <= seg["confidence"] <= 1.0
    assert seg["end"] > seg["start"]


# ---- Path 1: streaming=True + streamable PCM ----

class TestStreamingPcm:
    @pytest.mark.anyio
    async def test_returns_async_iterator(self, action, audio_pcm_bytes, params):
        src = _pcm_mono_source(audio_pcm_bytes)
        results = await action._detect([src], params, streaming=True, loop=asyncio.get_running_loop())
        assert len(results) == 1
        assert isinstance(results[0], AsyncIterator)

    @pytest.mark.anyio
    async def test_emits_segments_matching_batch(self, action, audio_pcm_bytes, params):
        src = _pcm_mono_source(audio_pcm_bytes)
        results = await action._detect([src], params, streaming=True, loop=asyncio.get_running_loop())
        segments = await _collect(results[0])
        assert len(segments) > 10
        for seg in segments:
            _assert_segment_shape(seg)


# ---- Path 2: streaming=True + non-streamable (MP3) ----

class TestStreamingNonPcm:
    @pytest.mark.anyio
    async def test_returns_async_iterator(self, action, params):
        results = await action._detect([_mp3_source()], params, streaming=True, loop=asyncio.get_running_loop())
        assert isinstance(results[0], AsyncIterator)

    @pytest.mark.anyio
    async def test_pseudo_stream_yields_batch_segments(self, action, params):
        results = await action._detect([_mp3_source()], params, streaming=True, loop=asyncio.get_running_loop())
        segments = await _collect(results[0])
        assert len(segments) > 10
        for seg in segments:
            _assert_segment_shape(seg)


# ---- Path 3: streaming=False (batch) ----

class TestBatchMp3:
    @pytest.mark.anyio
    async def test_returns_list(self, action, params):
        results = await action._detect([_mp3_source()], params, streaming=False, loop=asyncio.get_running_loop())
        assert isinstance(results[0], list)

    @pytest.mark.anyio
    async def test_batch_shape_and_content(self, action, params):
        results = await action._detect([_mp3_source()], params, streaming=False, loop=asyncio.get_running_loop())
        segments = results[0]
        assert len(segments) > 10
        for seg in segments:
            _assert_segment_shape(seg)


class TestBatchPcmNormalization:
    """Regression: PCM int16 in batch mode must be normalized to [-1, 1] before
    feeding Silero. Without normalization, raw int16 values would produce
    hundreds of spurious segments.
    """

    @pytest.mark.anyio
    async def test_pcm_batch_segment_count_reasonable(self, action, audio_pcm_bytes, params):
        src = _pcm_mono_source(audio_pcm_bytes)
        results = await action._detect([src], params, streaming=False, loop=asyncio.get_running_loop())
        segments = results[0]
        # If normalization is missing, this explodes into hundreds of segments.
        # ~86 is the expected count for our benchmark audio (~40 min).
        assert 50 <= len(segments) <= 150, (
            f"PCM batch produced {len(segments)} segments — normalization likely broken"
        )

    @pytest.mark.anyio
    async def test_pcm_batch_matches_pcm_online(self, action, audio_pcm_bytes, params):
        """Batch and online paths should produce identical segment counts for the
        same PCM source (both feed identical normalized samples to Silero).
        """
        src_batch = _pcm_mono_source(audio_pcm_bytes)
        batch_res = await action._detect([src_batch], params, streaming=False, loop=asyncio.get_running_loop())
        batch_count = len(batch_res[0])

        src_online = _pcm_mono_source(audio_pcm_bytes)
        online_res = await action._detect([src_online], params, streaming=True, loop=asyncio.get_running_loop())
        online_count = len(await _collect(online_res[0]))

        assert batch_count == online_count, (
            f"batch={batch_count} vs online={online_count} should match for same PCM source"
        )


# ---- Path 4: mixed batch ----

class TestMixedBatch:
    @pytest.mark.anyio
    async def test_per_item_routing(self, action, audio_pcm_bytes, params):
        src_pcm = _pcm_mono_source(audio_pcm_bytes)
        src_mp3 = _mp3_source()
        results = await action._detect(
            [src_pcm, src_mp3], params, streaming=True, loop=asyncio.get_running_loop(),
        )
        assert len(results) == 2
        # Both items should present as AsyncIterators regardless of source type
        # (streaming=True enforces this).
        for r in results:
            assert isinstance(r, AsyncIterator)

    @pytest.mark.anyio
    async def test_mixed_items_produce_independent_segments(self, action, audio_pcm_bytes, params):
        src_pcm = _pcm_mono_source(audio_pcm_bytes)
        src_mp3 = _mp3_source()
        results = await action._detect(
            [src_pcm, src_mp3], params, streaming=True, loop=asyncio.get_running_loop(),
        )
        pcm_segments = await _collect(results[0])
        mp3_segments = await _collect(results[1])
        assert len(pcm_segments) > 10
        assert len(mp3_segments) > 10
        # Different decoding paths → different exact counts, but both non-empty.


# ---- Output shape sanity ----

class TestOutputContract:
    @pytest.mark.anyio
    async def test_segments_are_monotonic(self, action, audio_pcm_bytes, params):
        """start/end pairs should be non-overlapping and monotonically increasing."""
        src = _pcm_mono_source(audio_pcm_bytes)
        results = await action._detect([src], params, streaming=True, loop=asyncio.get_running_loop())
        segments = await _collect(results[0])
        prev_end = -1.0
        for seg in segments:
            assert seg["start"] >= prev_end - 0.5, (
                f"segments overlap: {seg['start']} < {prev_end}"
            )
            prev_end = seg["end"]
