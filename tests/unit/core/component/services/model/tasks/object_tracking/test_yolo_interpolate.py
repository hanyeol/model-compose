"""Unit tests for YoloObjectTrackingTaskAction._interpolate_missing_objects.

Covers the non-streaming interpolation path. The threshold rides each frame's
real prior interval, so a `timestamps`-only call with no `frame_rate` must
succeed and must match the streaming path's `in_same_segment` verdict on both
uniform-stride and VFR inputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from mindor.core.component.services.model.tasks.object_tracking.custom.yolo import (
    YoloObjectTrackingTaskAction,
)


def _frame(timestamp: float, objects: List[Tuple[Dict[str, Any], int]]) -> Dict[str, Any]:
    return {"timestamp": timestamp, "tracked_objects": list(objects)}


def _object(bbox: Tuple[int, int, int, int] = (10, 10, 50, 50)) -> Dict[str, Any]:
    return {"bounding_box": bbox, "score": 0.9}


def _interpolated_count(frames: List[Dict[str, Any]], track_id: int) -> int:
    total = 0
    for frame in frames:
        for object_, tid in frame["tracked_objects"]:
            if tid == track_id and object_.get("interpolated"):
                total += 1
    return total


def test_interpolates_without_frame_rate() -> None:
    frames = [
        _frame(0.0, [(_object((0, 0, 40, 40)), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_object((40, 40, 80, 80)), 1)]),
    ]
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    action._interpolate_missing_objects(frames, merge_gap=1.0)

    assert _interpolated_count(frames, 1) == 1


def test_uniform_stride_matches_streaming_period() -> None:
    frames = [
        _frame(0.0, [(_object(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_object(), 1)]),
    ]
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    action._interpolate_missing_objects(frames, merge_gap=0.4)

    assert _interpolated_count(frames, 1) == 0

    frames = [
        _frame(0.0, [(_object(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_object(), 1)]),
    ]
    action._interpolate_missing_objects(frames, merge_gap=0.6)

    assert _interpolated_count(frames, 1) == 1


def test_vfr_uses_prior_interval_not_fixed_rate() -> None:
    frames = [
        _frame(0.0, [(_object(), 1)]),
        _frame(0.2, []),
        _frame(0.4, [(_object(), 1)]),
    ]
    action = YoloObjectTrackingTaskAction.__new__(YoloObjectTrackingTaskAction)
    action._interpolate_missing_objects(frames, merge_gap=0.0)

    assert _interpolated_count(frames, 1) == 0

    frames = [
        _frame(0.0, [(_object(), 1)]),
        _frame(0.2, []),
        _frame(0.4, [(_object(), 1)]),
    ]
    action._interpolate_missing_objects(frames, merge_gap=0.3)

    assert _interpolated_count(frames, 1) == 1
