"""Smoke tests for OpenCvVideoFrameAnalyzerAction._analyze_palette.

Synthetic flat-color frames go in, the LAB k-means palette output comes
back; the test fixes a small `max_colors` so the sanity checks don't have
to tolerate k-means jitter on a handful of pixels."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pytest
from PIL import Image as PILImage

from mindor.core.component.services.video_frame_analyzer.drivers.opencv import OpenCvVideoFrameAnalyzerAction
from mindor.core.foundation.variable.image import ImageArrayValue


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action() -> OpenCvVideoFrameAnalyzerAction:
    return OpenCvVideoFrameAnalyzerAction.__new__(OpenCvVideoFrameAnalyzerAction)


def _solid_rgb(width: int, height: int, rgb: tuple[int, int, int]) -> PILImage.Image:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[..., 0] = rgb[0]
    frame[..., 1] = rgb[1]
    frame[..., 2] = rgb[2]
    return PILImage.fromarray(frame, mode="RGB")


def _half_half_rgb(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> PILImage.Image:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    half = height // 2
    frame[:half, :, 0] = top[0]
    frame[:half, :, 1] = top[1]
    frame[:half, :, 2] = top[2]
    frame[half:, :, 0] = bottom[0]
    frame[half:, :, 1] = bottom[1]
    frame[half:, :, 2] = bottom[2]
    return PILImage.fromarray(frame, mode="RGB")


_PALETTE_PARAMS: Dict[str, Any] = {
    "downsample_width": 96,
    "sample_count":   4,
    "max_colors":    4,
    "min_share":      0.01,
}


@pytest.mark.anyio
async def test_palette_single_color_shot():
    frames = ImageArrayValue([_solid_rgb(96, 54, (200, 20, 20)) for _ in range(4)])
    result = await _make_action()._analyze_palette(frames, frame_rate=24.0, params=_PALETTE_PARAMS)

    assert result["frame_count"] == 4
    assert result["sample_count"] == 4
    assert result["background"] is not None
    assert len(result["colors"]) == 1
    assert result["colors"][0]["share"] == pytest.approx(1.0, abs=1e-6)
    # Background matches the dominant color on a single-color shot.
    assert result["background"] == result["colors"][0]["hex"]


@pytest.mark.anyio
async def test_palette_two_color_shot_background_is_border_dominant():
    # Bottom half fills the stacked-image border (bottom row + both side
    # columns on the bottom half), so background should match the bottom color.
    bottom = (30, 30, 30)
    top    = (220, 220, 220)
    frames = ImageArrayValue([_half_half_rgb(96, 54, top, bottom) for _ in range(4)])
    result = await _make_action()._analyze_palette(frames, frame_rate=24.0, params=_PALETTE_PARAMS)

    assert len(result["colors"]) == 2
    total_share = sum(color["share"] for color in result["colors"])
    assert total_share == pytest.approx(1.0, abs=1e-6)
    hexes = { color["hex"] for color in result["colors"] }
    assert result["background"] in hexes


@pytest.mark.anyio
async def test_palette_handles_empty_input():
    frames = ImageArrayValue([])
    result = await _make_action()._analyze_palette(frames, frame_rate=None, params=_PALETTE_PARAMS)

    assert result["background"] is None
    assert result["colors"] == []
    assert result["frame_count"] == 0
    assert result["sample_count"] == 0
    assert result["downsample_width"] == _PALETTE_PARAMS["downsample_width"]
