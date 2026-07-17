"""Unit tests for :class:`PyannoteSpeakerDiarizationTaskAction`.

pyannote.audio is heavy (gated model + HF token); tests mock the pipeline and
focus on the task-owned post-processing:

  1. `_merge_segments` correctly fuses same-speaker turns within `merge_gap`
     and never merges across speakers.
  2. `_collect_segments` applies `min_segment_duration` filter, sorts by
     start time, and produces `{speaker, start, end, confidence}` shape.
  3. Pipeline kwargs routing (`num_speakers` overrides min/max hints).
  4. `_diarize` returns `List[List[dict]]` / `List[AsyncIterator[dict]]`
     matching the shape base `TaskAction.run()` expects.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, List, Tuple

import numpy as np
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _Turn:
    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end


class _FakeAnnotation:
    def __init__(self, tracks: List[Tuple[_Turn, str]]):
        self._tracks = tracks

    def itertracks(self, yield_label: bool = False):
        for turn, speaker in self._tracks:
            if yield_label:
                yield turn, None, speaker
            else:
                yield turn, None


class _FakePyannotePipeline:
    """Callable mock mirroring `pyannote.audio.Pipeline` semantics."""

    def __init__(self, tracks: List[Tuple[_Turn, str]]):
        self.tracks = tracks
        self.last_call_kwargs: dict = {}
        self.last_input: Any = None

    def __call__(self, audio_input, **kwargs):
        self.last_input = audio_input
        self.last_call_kwargs = kwargs
        return _FakeAnnotation(self.tracks)


@pytest.fixture
def action():
    from mindor.core.component.services.model.tasks.speaker_diarization.custom.pyannote import (
        PyannoteSpeakerDiarizationTaskAction,
    )

    class _Cfg:
        audio = "x"
        sample_rate = 16000
        batch_size = 1
        streaming = False
        output = None

    a = PyannoteSpeakerDiarizationTaskAction.__new__(PyannoteSpeakerDiarizationTaskAction)
    a.config = _Cfg()
    a.device = None
    a.pipeline = _FakePyannotePipeline([])
    return a


def _assert_segment(seg: dict) -> None:
    assert set(seg.keys()) == {"speaker", "start", "end", "confidence"}
    assert isinstance(seg["speaker"], str)
    assert isinstance(seg["start"], float)
    assert isinstance(seg["end"], float)
    assert seg["end"] > seg["start"]
    assert 0.0 <= seg["confidence"] <= 1.0


def _base_params(action, **overrides) -> dict:
    """Build the params dict that `_resolve_params` would produce, letting the
    action compute `pipeline` from num/min/max speakers so tests stay aligned
    with the real dispatch path."""
    params: dict = {
        "sample_rate": 16000,
        "num_speakers": None,
        "min_speakers": None,
        "max_speakers": None,
        "merge_gap": 0.0,
        "min_segment_duration": 0.0,
    }
    params.update(overrides)
    params["pipeline"] = action._resolve_pipeline_params(params)
    return params


class TestMergeSegments:
    def test_no_merge_when_gap_is_zero(self, action):
        segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "confidence": 1.0},
            {"speaker": "SPEAKER_00", "start": 1.2, "end": 2.0, "confidence": 1.0},
        ]
        merged = action._merge_segments(segments, merge_gap=0.0)
        assert len(merged) == 2

    def test_merges_same_speaker_within_gap(self, action):
        segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "confidence": 1.0},
            {"speaker": "SPEAKER_00", "start": 1.2, "end": 2.0, "confidence": 1.0},
        ]
        merged = action._merge_segments(segments, merge_gap=0.5)
        assert len(merged) == 1
        assert merged[0]["start"] == 0.0
        assert merged[0]["end"] == 2.0

    def test_never_merges_across_speakers(self, action):
        segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "confidence": 1.0},
            {"speaker": "SPEAKER_01", "start": 1.1, "end": 2.0, "confidence": 1.0},
        ]
        merged = action._merge_segments(segments, merge_gap=1.0)
        assert len(merged) == 2

    def test_multiple_merges_per_speaker(self, action):
        segments = [
            {"speaker": "A", "start": 0.0, "end": 1.0, "confidence": 1.0},
            {"speaker": "A", "start": 1.1, "end": 2.0, "confidence": 1.0},
            {"speaker": "A", "start": 2.1, "end": 3.0, "confidence": 1.0},
        ]
        merged = action._merge_segments(segments, merge_gap=0.2)
        assert len(merged) == 1
        assert merged[0]["end"] == 3.0

    def test_gap_larger_than_threshold_not_merged(self, action):
        segments = [
            {"speaker": "A", "start": 0.0, "end": 1.0, "confidence": 1.0},
            {"speaker": "A", "start": 5.0, "end": 6.0, "confidence": 1.0},
        ]
        merged = action._merge_segments(segments, merge_gap=0.5)
        assert len(merged) == 2


class TestResolvePipelineParams:
    """`num_speakers` overrides `min/max_speakers`; unset values are dropped."""

    def test_empty_when_all_unset(self, action):
        assert action._resolve_pipeline_params({
            "num_speakers": None,
            "min_speakers": None,
            "max_speakers": None,
        }) == {}

    def test_num_speakers_overrides_min_max(self, action):
        assert action._resolve_pipeline_params({
            "num_speakers": 2,
            "min_speakers": 3,
            "max_speakers": 5,
        }) == {"num_speakers": 2}

    def test_min_max_hints_passed_when_num_absent(self, action):
        assert action._resolve_pipeline_params({
            "num_speakers": None,
            "min_speakers": 2,
            "max_speakers": 4,
        }) == {"min_speakers": 2, "max_speakers": 4}

    def test_only_min_speakers_present(self, action):
        assert action._resolve_pipeline_params({
            "num_speakers": None,
            "min_speakers": 2,
            "max_speakers": None,
        }) == {"min_speakers": 2}


class TestCollectSegments:
    def test_produces_expected_shape(self, action):
        action.pipeline = _FakePyannotePipeline([
            (_Turn(0.5, 3.2), "SPEAKER_00"),
            (_Turn(3.4, 7.1), "SPEAKER_01"),
        ])
        waveform = np.zeros(16000, dtype=np.float32)
        segments = action._collect_segments(waveform, sample_rate=16000, params=_base_params(action))
        assert len(segments) == 2
        for seg in segments:
            _assert_segment(seg)

    def test_filters_by_min_segment_duration(self, action):
        action.pipeline = _FakePyannotePipeline([
            (_Turn(0.0, 0.1), "SPEAKER_00"),  # too short
            (_Turn(1.0, 3.0), "SPEAKER_01"),
        ])
        waveform = np.zeros(16000, dtype=np.float32)
        segments = action._collect_segments(waveform, sample_rate=16000, params=_base_params(action, min_segment_duration=0.5))
        assert len(segments) == 1
        assert segments[0]["speaker"] == "SPEAKER_01"

    def test_sorts_output_by_start_time(self, action):
        action.pipeline = _FakePyannotePipeline([
            (_Turn(5.0, 6.0), "SPEAKER_00"),
            (_Turn(1.0, 2.0), "SPEAKER_01"),
            (_Turn(3.0, 4.0), "SPEAKER_00"),
        ])
        waveform = np.zeros(16000, dtype=np.float32)
        segments = action._collect_segments(waveform, sample_rate=16000, params=_base_params(action))
        starts = [seg["start"] for seg in segments]
        assert starts == sorted(starts)

    def test_forwards_pipeline_params_to_pipeline(self, action):
        action.pipeline = _FakePyannotePipeline([(_Turn(0.0, 1.0), "SPEAKER_00")])
        waveform = np.zeros(16000, dtype=np.float32)
        action._collect_segments(waveform, sample_rate=16000, params=_base_params(action, num_speakers=2))
        assert action.pipeline.last_call_kwargs == {"num_speakers": 2}

    def test_passes_waveform_and_sample_rate(self, action):
        action.pipeline = _FakePyannotePipeline([(_Turn(0.0, 1.0), "SPEAKER_00")])
        waveform = np.zeros(16000, dtype=np.float32)
        action._collect_segments(waveform, sample_rate=16000, params=_base_params(action))
        assert set(action.pipeline.last_input.keys()) == {"waveform", "sample_rate"}
        assert action.pipeline.last_input["sample_rate"] == 16000
        # waveform arrives as (1, samples) tensor
        assert tuple(action.pipeline.last_input["waveform"].shape) == (1, 16000)


class TestDiarizeReturnShape:
    """`_diarize` output shape must match what base `TaskAction.run()` expects."""

    @pytest.mark.anyio
    async def test_streaming_false_returns_list_of_lists(self, action, monkeypatch):
        action.pipeline = _FakePyannotePipeline([(_Turn(0.0, 1.0), "SPEAKER_00")])

        async def _fake_preprocess(audios, sample_rate):
            return [np.zeros(16000, dtype=np.float32), np.zeros(16000, dtype=np.float32)]

        monkeypatch.setattr(action, "_preprocess_audio", _fake_preprocess)

        results = await action._diarize(
            audios=["a", "b"],
            params=_base_params(action),
            streaming=False,
            loop=asyncio.get_event_loop(),
        )
        assert len(results) == 2
        for per_audio in results:
            assert isinstance(per_audio, list)
            for seg in per_audio:
                _assert_segment(seg)

    @pytest.mark.anyio
    async def test_streaming_true_returns_async_iterators(self, action, monkeypatch):
        action.pipeline = _FakePyannotePipeline([
            (_Turn(0.0, 1.0), "SPEAKER_00"),
            (_Turn(1.5, 2.5), "SPEAKER_01"),
        ])

        async def _fake_preprocess(audios, sample_rate):
            return [np.zeros(16000, dtype=np.float32)]

        monkeypatch.setattr(action, "_preprocess_audio", _fake_preprocess)

        results = await action._diarize(
            audios=["a"],
            params=_base_params(action),
            streaming=True,
            loop=asyncio.get_event_loop(),
        )
        assert len(results) == 1
        assert isinstance(results[0], AsyncIterator)
        collected = [chunk async for chunk in results[0]]
        assert len(collected) == 2
        for seg in collected:
            _assert_segment(seg)
