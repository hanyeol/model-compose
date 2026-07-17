"""Unit tests for :class:`SepformerSpeechSeparationTaskAction`.

The SepFormer model itself is mocked (real WSJ checkpoints are ~100 MB and
require SpeechBrain); tests focus on the task-owned logic:

  1. `_collect_tracks` correctly parses `(samples, sources)` estimates and
     produces one PcmStreamResource per source with the right index/sample_rate.
  2. `_separate` returns `List[List[dict]]` for streaming=False and
     `List[AsyncIterator[dict]]` for streaming=True (the shape base
     `TaskAction.run()` expects).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, List

import numpy as np
import pytest

from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import StreamResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeSepformer:
    """Stand-in for `speechbrain.inference.separation.SepformerSeparation`.

    `separate_batch(tensor)` returns a torch tensor shaped
    `(batch=1, samples, sources)` matching the real SepFormer contract.
    """

    def __init__(self, num_sources: int = 2):
        self.num_sources = num_sources
        self.last_input_shape: Any = None

    def separate_batch(self, tensor):
        import torch

        self.last_input_shape = tuple(tensor.shape)
        # tensor shape: (batch=1, samples)
        samples = tensor.shape[-1]
        # Fabricate distinct per-source waveforms so we can assert routing.
        estimates = torch.stack(
            [torch.full((samples,), float(i + 1) * 0.1) for i in range(self.num_sources)],
            dim=-1,
        ).unsqueeze(0)  # -> (1, samples, sources)
        return estimates


@pytest.fixture
def action():
    from mindor.core.component.services.model.tasks.speech_separation.custom.sepformer import (
        SepformerSpeechSeparationTaskAction,
    )

    class _Cfg:
        audio = "x"
        sample_rate = 8000
        batch_size = 1
        streaming = False
        output = None

    a = SepformerSpeechSeparationTaskAction.__new__(SepformerSpeechSeparationTaskAction)
    a.config = _Cfg()
    a.device = None
    a.model = _FakeSepformer(num_sources=2)
    return a


def _assert_track(track: dict, expected_index: int, expected_sample_rate: int) -> None:
    assert set(track.keys()) == {"index", "sample_rate", "audio"}
    assert track["index"] == expected_index
    assert track["sample_rate"] == expected_sample_rate
    assert isinstance(track["audio"], PcmStreamResource)
    assert track["audio"].attrs["sample_rate"] == str(expected_sample_rate)
    assert track["audio"].attrs["bit_depth"] == "16"


class TestCollectTracks:
    def test_returns_one_track_per_source(self, action):
        waveform = np.zeros(4000, dtype=np.float32)
        tracks = action._collect_tracks(waveform, sample_rate=8000)
        assert len(tracks) == 2
        for i, track in enumerate(tracks):
            _assert_track(track, expected_index=i, expected_sample_rate=8000)

    def test_supports_three_sources(self, action):
        action.model = _FakeSepformer(num_sources=3)
        waveform = np.zeros(4000, dtype=np.float32)
        tracks = action._collect_tracks(waveform, sample_rate=8000)
        assert [t["index"] for t in tracks] == [0, 1, 2]

    def test_wraps_input_as_batch_of_one(self, action):
        waveform = np.zeros(4000, dtype=np.float32)
        action._collect_tracks(waveform, sample_rate=8000)
        assert action.model.last_input_shape == (1, 4000)


class TestSeparateReturnShape:
    """`_separate` output shape must match what base `TaskAction.run()` expects."""

    @pytest.mark.anyio
    async def test_streaming_false_returns_list_of_lists(self, action):
        results = await action._separate(
            audios=[],  # not read (we bypass _preprocess_audio via monkey below)
            params={"sample_rate": 8000, "num_speakers": 2},
            streaming=False,
            loop=asyncio.get_event_loop(),
        )
        assert results == []

    @pytest.mark.anyio
    async def test_streaming_true_returns_async_iterators(self, action, monkeypatch):
        async def _fake_preprocess(audios, sample_rate):
            return [np.zeros(4000, dtype=np.float32), np.zeros(4000, dtype=np.float32)]

        monkeypatch.setattr(action, "_preprocess_audio", _fake_preprocess)

        results = await action._separate(
            audios=["a", "b"],
            params={"sample_rate": 8000, "num_speakers": 2},
            streaming=True,
            loop=asyncio.get_event_loop(),
        )
        assert len(results) == 2
        for item in results:
            assert isinstance(item, AsyncIterator)

        collected: List[List[dict]] = []
        for item in results:
            collected.append([chunk async for chunk in item])

        for per_audio in collected:
            assert len(per_audio) == 2
            for i, track in enumerate(per_audio):
                _assert_track(track, expected_index=i, expected_sample_rate=8000)

    @pytest.mark.anyio
    async def test_streaming_false_batch_returns_lists(self, action, monkeypatch):
        async def _fake_preprocess(audios, sample_rate):
            return [np.zeros(4000, dtype=np.float32), np.zeros(4000, dtype=np.float32)]

        monkeypatch.setattr(action, "_preprocess_audio", _fake_preprocess)

        results = await action._separate(
            audios=["a", "b"],
            params={"sample_rate": 8000, "num_speakers": 2},
            streaming=False,
            loop=asyncio.get_event_loop(),
        )
        assert len(results) == 2
        for per_audio in results:
            assert isinstance(per_audio, list)
            assert len(per_audio) == 2
            for i, track in enumerate(per_audio):
                _assert_track(track, expected_index=i, expected_sample_rate=8000)
