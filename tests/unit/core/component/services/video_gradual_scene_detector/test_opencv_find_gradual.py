"""Smoke tests for OpenCvVideoGradualSceneDetectorAction._detect.

Synthetic frame sequences exercise the find_gradual port directly — the
scanner's window loop, the plateau / motion / structure gates. Builds
PIL frames in memory so no video decode is involved."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pytest
from PIL import Image as PILImage

from mindor.core.component.services.video_gradual_scene_detector.drivers.opencv import OpenCvVideoGradualSceneDetectorAction
from mindor.core.foundation.variable.image import ImageArrayValue


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action() -> OpenCvVideoGradualSceneDetectorAction:
    """The per-run `_detect` method does not read `self.config`, so an
    action built with a bare object works for the algorithm-level tests."""
    return OpenCvVideoGradualSceneDetectorAction.__new__(OpenCvVideoGradualSceneDetectorAction)


def _pattern(seed: int, width: int = 160, height: int = 90) -> np.ndarray:
    """Deterministic high-variance picture; two different seeds produce two
    structurally different pictures that fail same_structure and that optical
    flow cannot warp into one another."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 256, size=(height, width), dtype=np.uint8)
    frame = np.repeat(np.repeat(base[::8, ::8], 8, axis=0), 8, axis=1)[:height, :width]
    return frame


def _rgb_from_gray(frame: np.ndarray) -> PILImage.Image:
    return PILImage.fromarray(np.stack([frame] * 3, axis=-1), mode="RGB")


def _dissolve_sequence(
    plateau_frames: int,
    ramp_frames: int,
    seed_a: int = 1,
    seed_b: int = 2,
) -> List[PILImage.Image]:
    """`plateau_frames` of picture A, `ramp_frames` of linear A→B crossfade,
    `plateau_frames` of picture B."""
    picture_a = _pattern(seed_a).astype(np.float32)
    picture_b = _pattern(seed_b).astype(np.float32)

    frames: List[PILImage.Image] = []
    for _ in range(plateau_frames):
        frames.append(_rgb_from_gray(picture_a.astype(np.uint8)))

    for index in range(1, ramp_frames + 1):
        alpha = index / (ramp_frames + 1)
        blend = ((1.0 - alpha) * picture_a + alpha * picture_b).clip(0, 255).astype(np.uint8)
        frames.append(_rgb_from_gray(blend))

    for _ in range(plateau_frames):
        frames.append(_rgb_from_gray(picture_b.astype(np.uint8)))

    return frames


_PARAMS: Dict[str, Any] = {
    "downsample_width":          96,
    "window_lengths":          (0.2, 0.35, 0.6),
    "plateau_share":           0.3,
    "min_changed_share":       0.5,
    "endpoint_min_std":        12.0,
    "endpoint_diff_threshold": 10.0,
    "motion_warp_threshold":   0.45,
}


@pytest.mark.anyio
async def test_detects_dissolve_between_two_pictures():
    frames = ImageArrayValue(_dissolve_sequence(plateau_frames=20, ramp_frames=8))
    results = await _make_action()._detect(
        frames, frame_rate=30.0, known_boundaries=[], streaming=False, params=_PARAMS,
    )

    assert len(results) >= 1
    boundary = results[0]
    # ramp sits roughly in frames 20..28 of the 48-frame sequence
    assert 18 <= boundary["boundary_frame"] <= 30
    assert boundary["start_frame"] < boundary["boundary_frame"] < boundary["end_frame"]
    assert boundary["frame_rate"] == 30.0


@pytest.mark.anyio
async def test_skips_boundaries_already_taken():
    frames = ImageArrayValue(_dissolve_sequence(plateau_frames=20, ramp_frames=8))
    # Mark the center of the ramp as a known boundary — the scanner should
    # skip every window that overlaps the pad around it.
    results = await _make_action()._detect(
        frames, frame_rate=30.0, known_boundaries=[24], streaming=False, params=_PARAMS,
    )

    assert results == []


@pytest.mark.anyio
async def test_steady_shot_produces_no_boundary():
    picture = _pattern(1).astype(np.uint8)
    frames = ImageArrayValue([_rgb_from_gray(picture) for _ in range(60)])
    results = await _make_action()._detect(
        frames, frame_rate=30.0, known_boundaries=[], streaming=False, params=_PARAMS,
    )

    assert results == []


@pytest.mark.anyio
async def test_short_sequence_returns_empty():
    frames = ImageArrayValue([_rgb_from_gray(_pattern(1).astype(np.uint8)) for _ in range(4)])
    results = await _make_action()._detect(
        frames, frame_rate=30.0, known_boundaries=[], streaming=False, params=_PARAMS,
    )

    assert results == []
