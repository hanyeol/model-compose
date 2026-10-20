"""Unit tests for YoloPoseTrackingTaskAction crop / image_source helpers.

Covers the invariant that lets us stash a small sub-crop around each detection
instead of the whole frame: cropping the sub-crop with `origin=(mx1, my1)` must
yield the same pixels as cropping the full frame with `origin=(0, 0)`. If that
ever drifts, hour-long tracks silently start returning wrong pose images.

The extraction runs on the final post-smoothing bbox (see `_add_poses_to_tracks`),
so the margin equals `bounding_box_padding` exactly and the sub-crop matches
the full-frame crop under any smoothing weight / motion speed combination.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_tracking.custom.ultralytics import (
    YoloPoseTrackingTaskAction,
)


def _frame(height: int = 200, width: int = 300) -> PILImage.Image:
    pixels = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
    return PILImage.fromarray(pixels)


def test_extract_pose_region_returns_independent_copy() -> None:
    frame = _frame()
    sub, _ = YoloPoseTrackingTaskAction._extract_pose_region(frame, (100, 80, 150, 130))

    assert sub is not None
    # PIL `.crop()` returns an independent image; dropping the parent frame
    # must not invalidate the sub-crop or we'd lose data mid-track.
    pixels_before = np.array(sub).copy()
    frame.close()
    assert np.array_equal(np.array(sub), pixels_before)


@pytest.mark.parametrize("padding", [0.0, 0.1, 0.3, 0.5, 1.0])
def test_crop_via_subregion_matches_full_frame(padding: float) -> None:
    frame = _frame()
    bbox = (100, 80, 150, 130)

    pose_full = {
        "bounding_box":        bbox,
        "image_source":        frame,
        "image_source_origin": (0, 0),
    }
    sub, origin = YoloPoseTrackingTaskAction._extract_pose_region(frame, bbox, padding)
    pose_sub = {
        "bounding_box":        bbox,
        "image_source":        sub,
        "image_source_origin": origin,
    }

    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    from_full = action._crop_pose_image(pose_full, padding)
    from_sub = action._crop_pose_image(pose_sub, padding)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))


def test_crop_at_frame_edge_clips_same_from_subregion() -> None:
    frame = _frame(height=200, width=300)
    bbox = (280, 190, 320, 220)

    pose_full = {
        "bounding_box":        bbox,
        "image_source":        frame,
        "image_source_origin": (0, 0),
    }
    sub, origin = YoloPoseTrackingTaskAction._extract_pose_region(frame, bbox, 0.2)
    pose_sub = {
        "bounding_box":        bbox,
        "image_source":        sub,
        "image_source_origin": origin,
    }

    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    from_full = action._crop_pose_image(pose_full, 0.2)
    from_sub = action._crop_pose_image(pose_sub, 0.2)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))


def test_extract_pose_region_off_screen_returns_none() -> None:
    frame = _frame()
    sub, origin = YoloPoseTrackingTaskAction._extract_pose_region(frame, (400, 400, 450, 450))

    assert sub is None
    assert origin == (0, 0)


@pytest.mark.parametrize("padding,smoothing,step", [
    (1.0, 0.8, 10),
    (0.5, 0.9, 20),
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

    sub, origin = YoloPoseTrackingTaskAction._extract_pose_region(frame, int_smoothed, padding)
    pose_full = {
        "bounding_box":        int_smoothed,
        "image_source":        frame,
        "image_source_origin": (0, 0),
    }
    pose_sub = {
        "bounding_box":        int_smoothed,
        "image_source":        sub,
        "image_source_origin": origin,
    }

    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    from_full = action._crop_pose_image(pose_full, padding)
    from_sub = action._crop_pose_image(pose_sub, padding)

    assert from_full is not None
    assert from_sub is not None
    assert np.array_equal(np.array(from_full), np.array(from_sub))
