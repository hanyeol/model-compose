"""Unit tests for InsightfaceFaceTrackingTaskAction crop / image_source helpers.

Covers the invariant that lets us stash a small sub-crop around each detection
instead of the whole frame: cropping the sub-crop with `origin=(mx1, my1)` must
yield the same pixels as cropping the full frame with `origin=(0, 0)`. If that
ever drifts, hour-long tracks silently start returning wrong face images.
"""

from __future__ import annotations

import numpy as np
import pytest

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)


def _frame(height: int = 200, width: int = 300) -> np.ndarray:
    return np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)


def test_extract_face_region_returns_copy_not_view() -> None:
    frame = _frame()
    sub, _ = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, (100, 80, 150, 130), 300, 200)

    assert sub is not None
    # A view keeps the parent buffer alive and defeats the memory fix.
    assert sub.base is None


@pytest.mark.parametrize("padding", [0.0, 0.1, 0.3, 0.5])
def test_crop_via_subregion_matches_full_frame(padding: float) -> None:
    frame = _frame()
    bbox = (100, 80, 150, 130)

    from_full = InsightfaceFaceTrackingTaskAction._crop_face_image(frame, bbox, padding)
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, 300, 200)
    from_sub = InsightfaceFaceTrackingTaskAction._crop_face_image(sub, bbox, padding, origin=origin)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))


def test_crop_at_frame_edge_clips_same_from_subregion() -> None:
    # A bbox that's partly off-screen should get the same clipped result
    # whether we crop the whole frame or the sub-region.
    frame = _frame(height=200, width=300)
    bbox = (280, 190, 320, 220)

    from_full = InsightfaceFaceTrackingTaskAction._crop_face_image(frame, bbox, 0.2)
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, 300, 200)
    from_sub = InsightfaceFaceTrackingTaskAction._crop_face_image(sub, bbox, 0.2, origin=origin)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))


def test_extract_face_region_off_screen_returns_none() -> None:
    frame = _frame()
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, (400, 400, 450, 450), 300, 200)

    assert sub is None
    assert origin == (0, 0)


def test_build_face_with_image_uses_subregion_origin() -> None:
    frame = _frame()
    bbox = (100, 80, 150, 130)
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, 300, 200)

    face = {
        "embedding":            np.zeros(3),
        "bounding_box":         bbox,
        "score":                0.9,
        "image_source":         sub,
        "image_source_origin":  origin,
    }

    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    materialized = action._build_face_with_image(face, bounding_box_padding=0.2)

    from_full = InsightfaceFaceTrackingTaskAction._crop_face_image(frame, bbox, 0.2)

    assert "image_source" not in materialized
    assert "image_source_origin" not in materialized
    assert materialized["image"] is not None
    assert np.array_equal(np.array(materialized["image"]), np.array(from_full))
