"""Unit tests for how `image_source` propagates through `_add_poses_to_tracks`.

The flag split (`return_track_image` vs `return_detection_image`) is a memory
fix: on long non-streaming runs, holding a padded PIL sub-crop on every
tracked pose in `tracked_frames` pins gigabytes of pixels for the whole run.
These tests pin the invariant that lets the fix work — best_pose always
keeps the sub-crop (segment crop is lazy, 1 per segment), the per-frame
`tracked_poses` entry only keeps it when the caller asked for per-detection
crops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_tracking.custom.ultralytics import (
    YoloPoseTrackingTaskAction,
)


FRAME_PERIOD = 0.5


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "merge_gap":              0.0,
        "bounding_box_padding":   0.0,
        "bounding_box_smoothing": None,
        "return_track_image":     False,
        "return_detection_image": False,
    }
    base.update(overrides)
    return base


def _frame(height: int = 200, width: int = 300) -> PILImage.Image:
    pixels = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
    return PILImage.fromarray(pixels)


def _pose(bbox=(100, 80, 150, 130), score: float = 0.9) -> Dict[str, Any]:
    return {
        "track_id":     1,
        "bounding_box": bbox,
        "score":        score,
        "width":        300,
        "height":       200,
    }


def _extractor(frame: PILImage.Image):
    def extract(bounding_box: Tuple[int, int, int, int]):
        return YoloPoseTrackingTaskAction._extract_pose_region(frame, bounding_box, 0.0)
    return extract


def _add(action, track_segments, poses: List[Dict[str, Any]], params: Dict[str, Any], extractor):
    return action._add_poses_to_tracks(
        poses,
        timestamp=0.0,
        frame_period=FRAME_PERIOD,
        track_segments=track_segments,
        params=params,
        extract_image_source=extractor,
    )


def test_tracked_pose_drops_image_source_when_detection_image_disabled() -> None:
    frame = _frame()
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_poses, _ = _add(
        action, track_segments, [_pose()],
        _default_params(return_track_image=True, return_detection_image=False),
        _extractor(frame),
    )

    (pose, _) = tracked_poses[0]
    assert "image_source" not in pose
    assert "image_source_origin" not in pose


def test_tracked_pose_keeps_image_source_when_detection_image_enabled() -> None:
    frame = _frame()
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_poses, _ = _add(
        action, track_segments, [_pose()],
        _default_params(return_detection_image=True),
        _extractor(frame),
    )

    (pose, _) = tracked_poses[0]
    assert pose.get("image_source") is not None
    assert pose.get("image_source_origin") is not None


def test_best_pose_keeps_image_source_regardless_of_detection_image_flag() -> None:
    # best_pose carries the sub-crop so the segment can emit the
    # representative image via `_crop_pose_image`; this is why the flag split
    # works at all. If best_pose ever lost its reference under
    # `return_detection_image: false`, segment crops would silently vanish.
    frame = _frame()
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)

    for detection_image in (False, True):
        track_segments: Dict[int, Dict[str, Any]] = {}
        _add(
            action, track_segments, [_pose()],
            _default_params(return_track_image=True, return_detection_image=detection_image),
            _extractor(frame),
        )

        best_pose = track_segments[1]["current"]["best_pose"]
        assert best_pose.get("image_source") is not None, f"detection_image={detection_image}"
        assert best_pose.get("image_source_origin") is not None, f"detection_image={detection_image}"


def test_no_image_source_stashed_when_extractor_is_none() -> None:
    # When neither flag is set the orchestrator skips extractor creation; the
    # tracking path must handle `extract_image_source=None` without pinning
    # anything on best_pose or tracked_poses.
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_poses, _ = action._add_poses_to_tracks(
        [_pose()],
        timestamp=0.0,
        frame_period=FRAME_PERIOD,
        track_segments=track_segments,
        params=_default_params(),
        extract_image_source=None,
    )

    (pose, _) = tracked_poses[0]
    best_pose = track_segments[1]["current"]["best_pose"]

    assert "image_source" not in pose
    assert "image_source" not in best_pose
