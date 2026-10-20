"""Unit tests for how `image_source` propagates through `_add_objects_to_tracks`.

The flag split (`return_track_image` vs `return_detection_image`) is a memory
fix: on long non-streaming runs, holding a padded PIL sub-crop on every
tracked object in `tracked_frames` pins gigabytes of pixels for the whole
run. These tests pin the invariant that lets the fix work — best_object
always keeps the sub-crop (segment crop is lazy, 1 per segment), the
per-frame `tracked_objects` entry only keeps it when the caller asked for
per-detection crops.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.object_tracking.custom.ultralytics import (
    YoloObjectTrackingTaskAction,
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


def _object(bbox=(100, 80, 150, 130), score: float = 0.9) -> Dict[str, Any]:
    return {
        "track_id":     1,
        "label":        "car",
        "label_id":     2,
        "bounding_box": bbox,
        "score":        score,
        "width":        300,
        "height":       200,
    }


def _extractor(frame: PILImage.Image):
    def extract(bounding_box: Tuple[int, int, int, int]):
        return YoloObjectTrackingTaskAction._extract_object_region(frame, bounding_box, 0.0)
    return extract


def _add(action, track_segments, objects: List[Dict[str, Any]], params: Dict[str, Any], extractor):
    return action._add_objects_to_tracks(
        objects,
        timestamp=0.0,
        frame_period=FRAME_PERIOD,
        track_segments=track_segments,
        params=params,
        extract_image_source=extractor,
    )


def test_tracked_object_drops_image_source_when_detection_image_disabled() -> None:
    frame = _frame()
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_objects, _ = _add(
        action, track_segments, [_object()],
        _default_params(return_track_image=True, return_detection_image=False),
        _extractor(frame),
    )

    (object, _) = tracked_objects[0]
    assert "image_source" not in object
    assert "image_source_origin" not in object


def test_tracked_object_keeps_image_source_when_detection_image_enabled() -> None:
    frame = _frame()
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_objects, _ = _add(
        action, track_segments, [_object()],
        _default_params(return_detection_image=True),
        _extractor(frame),
    )

    (object, _) = tracked_objects[0]
    assert object.get("image_source") is not None
    assert object.get("image_source_origin") is not None


def test_best_object_keeps_image_source_regardless_of_detection_image_flag() -> None:
    # best_object carries the sub-crop so the segment can emit the
    # representative image via `_crop_object_image`; this is why the flag
    # split works at all. If best_object ever lost its reference under
    # `return_detection_image: false`, segment crops would silently vanish.
    frame = _frame()
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)

    for detection_image in (False, True):
        track_segments: Dict[int, Dict[str, Any]] = {}
        _add(
            action, track_segments, [_object()],
            _default_params(return_track_image=True, return_detection_image=detection_image),
            _extractor(frame),
        )

        best_object = track_segments[1]["current"]["best_object"]
        assert best_object.get("image_source") is not None, f"detection_image={detection_image}"
        assert best_object.get("image_source_origin") is not None, f"detection_image={detection_image}"


def test_no_image_source_stashed_when_extractor_is_none() -> None:
    # When neither flag is set the orchestrator skips extractor creation; the
    # tracking path must handle `extract_image_source=None` without pinning
    # anything on best_object or tracked_objects.
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}

    tracked_objects, _ = action._add_objects_to_tracks(
        [_object()],
        timestamp=0.0,
        frame_period=FRAME_PERIOD,
        track_segments=track_segments,
        params=_default_params(),
        extract_image_source=None,
    )

    (object, _) = tracked_objects[0]
    best_object = track_segments[1]["current"]["best_object"]

    assert "image_source" not in object
    assert "image_source" not in best_object
