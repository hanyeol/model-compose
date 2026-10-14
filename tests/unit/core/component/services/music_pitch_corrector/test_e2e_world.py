"""End-to-end tests for the WORLD-backed music-pitch-corrector.

PESTO is bypassed by handing the planner synthetic pitch frames directly.
These tests exercise the real planner + WORLD vocoder path (not mocked)
to catch wiring regressions that pure-helper tests miss — scale resolution,
batch/broadcast dispatch, actual audio synthesis.
"""

import math
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
import soundfile as sf

from mindor.core.component.context import ComponentActionContext
from mindor.core.component.services.music_pitch_corrector.drivers.world import (
    WorldMusicPitchCorrectorAction,
)
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.dsl.schema.action import (
    WorldMusicPitchCorrectorPlanActionConfig,
    WorldMusicPitchCorrectorApplyActionConfig,
    WorldMusicPitchCorrectorCorrectActionConfig,
)


_SAMPLE_RATE = 16000
_FRAME_PERIOD = 0.005


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _synthesize_vocal(semitones: List[float], durations: List[float]) -> np.ndarray:
    """Build a monophonic sine-wave recording: one segment per (midi, duration)."""
    chunks = []
    for midi, dur in zip(semitones, durations):
        freq = 440.0 * (2.0 ** ((midi - 69.0) / 12.0))
        t = np.arange(int(dur * _SAMPLE_RATE)) / _SAMPLE_RATE
        chunks.append(0.5 * np.sin(2.0 * np.pi * freq * t))
    return np.concatenate(chunks).astype(np.float32)


def _pitch_frames(semitones: List[float], durations: List[float]) -> List[Dict[str, Any]]:
    """Make per-frame pitch dicts at _FRAME_PERIOD hop matching the vocal."""
    frames: List[Dict[str, Any]] = []
    t = 0.0
    for midi, dur in zip(semitones, durations):
        n = int(dur / _FRAME_PERIOD)
        for _ in range(n):
            frames.append({"time": t, "pitch": float(midi), "confidence": 1.0})
            t += _FRAME_PERIOD
    return frames


def _write_wav(samples: np.ndarray, path: Path) -> None:
    sf.write(str(path), samples, _SAMPLE_RATE, subtype="PCM_16")


def _make_context(input: Dict[str, Any]) -> ComponentActionContext:
    return ComponentActionContext(run_id="test", input=input)


async def _collect_audio(stream) -> np.ndarray:
    """Drain an AudioBufferStreamIterator into a single numpy array."""
    chunks = []
    async for buf in stream:
        chunks.append(np.asarray(buf.waveform))
    return np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)


@pytest.fixture
def flat_vocal_setup(tmp_path: Path):
    """A one-note vocal (A4, 1 second) and matching pitch frames."""
    samples = _synthesize_vocal(semitones=[69.0], durations=[1.0])
    frames = _pitch_frames(semitones=[69.0], durations=[1.0])

    wav_path = tmp_path / "vocal.wav"
    _write_wav(samples, wav_path)

    return {"wav_path": wav_path, "frames": frames, "samples": samples}


@pytest.mark.anyio
async def test_plan_single_scale_name(flat_vocal_setup):
    """`scale: 'minor'` as a bare enum name → broadcasts across the single track."""
    config = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=flat_vocal_setup["frames"],
        key="A",
        scale="minor",
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    result = await action.run(_make_context({}))

    assert "curve" in result and "report" in result
    curve = result["curve"]
    assert curve["settings"]["mode"] == "scale"
    assert curve["settings"]["key"] == "A"
    assert curve["settings"]["scale"] == [0, 2, 3, 5, 7, 8, 10]
    assert curve["notes"]
    assert all(n["sung_pitch"] == pytest.approx(69.0, abs=0.5) for n in curve["notes"])


@pytest.mark.anyio
async def test_plan_single_pitch_class_list(flat_vocal_setup):
    """`scale: [0, 2, 4, 7, 9]` (pentatonic) — single pitch-class list broadcast."""
    config = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=flat_vocal_setup["frames"],
        key="A",
        scale=[0, 2, 4, 7, 9],
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    result = await action.run(_make_context({}))

    assert result["curve"]["settings"]["scale"] == [0, 2, 4, 7, 9]


@pytest.mark.anyio
async def test_plan_batch_pitch_tracks(flat_vocal_setup):
    """Batch of 2 pitch tracks + broadcast key → 2 curves back, same key."""
    frames = flat_vocal_setup["frames"]
    config = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=[frames, frames],  # 2-track batch
        key="A",  # broadcast to every batch item
        scale="major",
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    results = await action.run(_make_context({}))

    assert isinstance(results, list) and len(results) == 2
    assert results[0]["curve"]["settings"]["key"] == "A"
    assert results[1]["curve"]["settings"]["key"] == "A"


@pytest.mark.anyio
async def test_plan_batch_scale_per_track(flat_vocal_setup):
    """Batch of 2 pitch tracks + batch of 2 pitch-class lists → scales pair up."""
    frames = flat_vocal_setup["frames"]
    config = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=[frames, frames],
        key=["A", "A"],
        scale=[[0, 2, 4, 5, 7, 9, 11], [0, 2, 3, 5, 7, 8, 10]],  # major, minor
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    results = await action.run(_make_context({}))

    assert len(results) == 2
    assert results[0]["curve"]["settings"]["scale"] == [0, 2, 4, 5, 7, 9, 11]
    assert results[1]["curve"]["settings"]["scale"] == [0, 2, 3, 5, 7, 8, 10]


@pytest.mark.anyio
async def test_correct_single_track(flat_vocal_setup):
    """Full correct: synthesize A4, correct to A-minor → audio out, roughly same length."""
    config = WorldMusicPitchCorrectorCorrectActionConfig(
        method="correct",
        pitch=flat_vocal_setup["frames"],
        audio="${input.audio}",
        key="A",
        scale="minor",
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    result = await action.run(_make_context({"audio": FileStreamResource(str(flat_vocal_setup["wav_path"]))}))

    assert "audio" in result and "report" in result

    audio_out = await _collect_audio(result["audio"])
    expected = flat_vocal_setup["samples"].size
    # WORLD may add a few frames of tail; allow 10% drift
    assert abs(audio_out.size - expected) / expected < 0.1


@pytest.mark.anyio
async def test_apply_curve_roundtrip(flat_vocal_setup):
    """plan → apply the returned curve → shouldn't crash and should emit audio."""
    plan_cfg = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=flat_vocal_setup["frames"],
        key="A",
        scale="minor",
    )
    plan_action = WorldMusicPitchCorrectorAction(plan_cfg, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    plan_result = await plan_action.run(_make_context({}))
    curve = plan_result["curve"]

    apply_cfg = WorldMusicPitchCorrectorApplyActionConfig(
        method="apply",
        audio="${input.audio}",
        curve=dict(curve),  # unwrap AtomicDict to a plain dict for config
    )
    apply_action = WorldMusicPitchCorrectorAction(apply_cfg, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    apply_result = await apply_action.run(_make_context({"audio": FileStreamResource(str(flat_vocal_setup["wav_path"]))}))

    audio_out = await _collect_audio(apply_result["audio"])
    assert audio_out.size > 0


@pytest.mark.anyio
async def test_plan_mode_scale_requires_key(flat_vocal_setup):
    """Missing key under `mode: scale` must raise."""
    config = WorldMusicPitchCorrectorPlanActionConfig(
        method="plan",
        pitch=flat_vocal_setup["frames"],
        key=None,
        scale="major",
    )
    action = WorldMusicPitchCorrectorAction(config, frame_period=_FRAME_PERIOD, f0_estimator="dio")
    with pytest.raises(ValueError, match="mode: scale"):
        await action.run(_make_context({}))
