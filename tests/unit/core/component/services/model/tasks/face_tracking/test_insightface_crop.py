"""Unit tests for InsightfaceFaceTrackingTaskAction crop / image_source helpers.

Covers the invariant that lets us stash a small sub-crop around each detection
instead of the whole frame: cropping the sub-crop with `origin=(mx1, my1)` must
yield the same pixels as cropping the full frame with `origin=(0, 0)`. If that
ever drifts, hour-long tracks silently start returning wrong face images.

The extraction runs on the final post-smoothing bbox (see `_add_face_to_track`),
so the margin equals `bounding_box_padding` exactly and the sub-crop matches
the full-frame crop under any smoothing weight / motion speed combination.
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
    sub, _ = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, (100, 80, 150, 130))

    assert sub is not None
    # A view keeps the parent buffer alive and defeats the memory fix.
    assert sub.base is None


@pytest.mark.parametrize("padding", [0.0, 0.1, 0.3, 0.5, 1.0])
def test_crop_via_subregion_matches_full_frame(padding: float) -> None:
    frame = _frame()
    bbox = (100, 80, 150, 130)

    from_full = InsightfaceFaceTrackingTaskAction._crop_face_image(frame, bbox, padding)
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, padding)
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
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, 0.2)
    from_sub = InsightfaceFaceTrackingTaskAction._crop_face_image(sub, bbox, 0.2, origin=origin)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))


def test_extract_face_region_off_screen_returns_none() -> None:
    frame = _frame()
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, (400, 400, 450, 450))

    assert sub is None
    assert origin == (0, 0)


def test_build_face_with_image_uses_subregion_origin() -> None:
    frame = _frame()
    bbox = (100, 80, 150, 130)
    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bbox, 0.2)

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


@pytest.mark.parametrize("padding,smoothing,step", [
    (1.0, 0.8, 10),   # Spec example: padding 1.0, smoothing 0.8.
    (0.5, 0.9, 20),   # Fast pan: 20 px/frame on a ~100 px face — the case
                      # the +smoothing margin heuristic silently clipped
                      # (90 px of the trailing edge).
])
def test_crop_tracks_smoothed_bbox_under_motion(padding: float, smoothing: float, step: int) -> None:
    # Steady-state EMA lag of `step * smoothing / (1 - smoothing)` px: the
    # smoothed bbox trails the detection by a fixed offset. Extraction runs on
    # the smoothed bbox (as production does), so the stashed sub-crop must
    # match a full-frame crop pixel-for-pixel at any lag.
    frame = _frame(height=400, width=640)
    detection_bbox = (300.0, 200.0, 400.0, 300.0)
    lag = step * smoothing / (1.0 - smoothing)
    smoothed_bbox = (
        detection_bbox[0] - lag,
        detection_bbox[1],
        detection_bbox[2] - lag,
        detection_bbox[3],
    )
    int_smoothed = tuple(int(round(v)) for v in smoothed_bbox)

    sub, origin = InsightfaceFaceTrackingTaskAction._extract_face_region(frame, int_smoothed, padding)
    from_sub = InsightfaceFaceTrackingTaskAction._crop_face_image(sub, int_smoothed, padding, origin=origin)
    from_full = InsightfaceFaceTrackingTaskAction._crop_face_image(frame, int_smoothed, padding)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))
