"""Smoke tests for OpenCvVideoFrameAnalyzerAction._analyze_picture_box.

Synthetic PIL frames exercise the picture-box geometry detector without
needing a real video decode path. Every test calls the private
`_analyze_picture_box` directly with a resolved `params` dict so the gate
logic is isolated from the `_resolve_params` surface."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pytest
from PIL import Image as PILImage

from mindor.core.component.services.video_frame_analyzer.drivers.opencv import OpenCvVideoFrameAnalyzerAction
from mindor.core.foundation.variable.image import ImageArrayValue


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _make_action() -> OpenCvVideoFrameAnalyzerAction:
    """Skip the config/metric plumbing — the per-metric `_analyze_*` methods
    don't read `self.config`, so an action built with a bare object works."""
    return OpenCvVideoFrameAnalyzerAction.__new__(OpenCvVideoFrameAnalyzerAction)


def _letterboxed_frame(
    width: int = 320,
    height: int = 180,
    bar_fraction: float = 0.15,
    picture_value: int = 220,
    bar_value: int = 0,
) -> PILImage.Image:
    """Grayscale picture with horizontal bars top and bottom."""
    frame = np.full((height, width), bar_value, dtype=np.uint8)
    bar_rows = int(round(height * bar_fraction))
    frame[bar_rows:height - bar_rows, :] = picture_value
    return PILImage.fromarray(frame, mode="L").convert("RGB")


def _solid_frame(width: int = 320, height: int = 180, value: int = 200) -> PILImage.Image:
    return PILImage.fromarray(np.full((height, width), value, dtype=np.uint8), mode="L").convert("RGB")


_PICTURE_BOX_PARAMS: Dict[str, Any] = {
    "downsample_width":         320,
    "sample_count":           4,
    "lit_threshold":          24.0,
    "picture_lit_share":      0.6,
    "bar_dark_share":         0.1,
    "bar_min_share":          0.06,
    "picture_edge_lit_share": 0.8,
    "min_picture_fraction":   0.2,
}


@pytest.mark.anyio
async def test_picture_box_detects_horizontal_letterbox():
    frames = ImageArrayValue([_letterboxed_frame() for _ in range(4)])
    result = await _make_action()._analyze_picture_box(frames, frame_rate=24.0, params=_PICTURE_BOX_PARAMS)

    assert result["detected"] is True
    assert result["box"] is not None
    _, y0, _, box_height = result["box"]
    assert y0 == pytest.approx(0.15, abs=0.03)
    assert box_height == pytest.approx(0.7, abs=0.03)
    assert result["aspect"] == pytest.approx(result["box"][2] * 320 / (result["box"][3] * 180), rel=0.01)
    assert result["bar_share"] == pytest.approx(0.3, abs=0.03)
    assert result["frame_count"] == 4
    assert result["sample_count"] == 4
    assert result["frame_rate"] == 24.0


@pytest.mark.anyio
async def test_picture_box_rejects_full_frame_picture():
    frames = ImageArrayValue([_solid_frame() for _ in range(4)])
    result = await _make_action()._analyze_picture_box(frames, frame_rate=24.0, params=_PICTURE_BOX_PARAMS)

    assert result["detected"] is False
    assert result["box"] is None
    assert result["aspect"] is None
    assert result["bar_share"] is None
    assert result["frame_count"] == 4
    assert result["sample_count"] == 4


@pytest.mark.anyio
async def test_picture_box_handles_empty_input():
    frames = ImageArrayValue([])
    result = await _make_action()._analyze_picture_box(frames, frame_rate=None, params=_PICTURE_BOX_PARAMS)

    assert result["detected"] is False
    assert result["frame_count"] == 0
    assert result["sample_count"] == 0
    assert result["downsample_width"] == _PICTURE_BOX_PARAMS["downsample_width"]
