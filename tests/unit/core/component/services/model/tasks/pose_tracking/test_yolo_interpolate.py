"""Unit tests for YoloPoseTrackingTaskAction._interpolate_missing_poses.

Covers the non-streaming interpolation path. The threshold rides each frame's
real prior interval, so a `timestamps`-only call with no `frame_rate` must
succeed and must match the streaming path's `in_same_segment` verdict on both
uniform-stride and VFR inputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from mindor.core.component.services.model.tasks.pose_tracking.custom.yolo import (
    YoloPoseTrackingTaskAction,
)


def _frame(timestamp: float, poses: List[Tuple[Dict[str, Any], int]]) -> Dict[str, Any]:
    return {"timestamp": timestamp, "tracked_poses": list(poses)}


def _pose(bbox: Tuple[int, int, int, int] = (10, 10, 50, 50)) -> Dict[str, Any]:
    return {"bounding_box": bbox, "score": 0.9}


def _interpolated_count(frames: List[Dict[str, Any]], track_id: int) -> int:
    total = 0
    for frame in frames:
        for pose, tid in frame["tracked_poses"]:
            if tid == track_id and pose.get("interpolated"):
                total += 1
    return total


def test_interpolates_without_frame_rate() -> None:
    # timestamps-only path: no `frame_rate` is involved, no `1.0 / None` crash.
    frames = [
        _frame(0.0, [(_pose((0, 0, 40, 40)), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_pose((40, 40, 80, 80)), 1)]),
    ]
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    action._interpolate_missing_poses(frames, merge_gap=1.0)

    assert _interpolated_count(frames, 1) == 1


def test_uniform_stride_matches_streaming_period() -> None:
    # Streaming uses `t[i] - t[i-1]` for `frame_period`. On a 0.5s uniform
    # stride the gap between anchors is 1.0s; threshold is `merge_gap + 0.5s`.
    # merge_gap=0.4 → total 0.9 → below the 1.0 anchor gap → no interpolation.
    frames = [
        _frame(0.0, [(_pose(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_pose(), 1)]),
    ]
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    action._interpolate_missing_poses(frames, merge_gap=0.4)

    assert _interpolated_count(frames, 1) == 0

    # merge_gap=0.6 → total 1.1 → above the 1.0 anchor gap → interpolate.
    frames = [
        _frame(0.0, [(_pose(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_pose(), 1)]),
    ]
    action._interpolate_missing_poses(frames, merge_gap=0.6)

    assert _interpolated_count(frames, 1) == 1


def test_vfr_uses_prior_interval_not_fixed_rate() -> None:
    # The second anchor sits 0.2s after a 0.2s gap frame — the prior interval
    # for the anchor-landing frame is 0.2s, not any "nominal" fps-derived
    # value. With merge_gap=0.0 and a 0.4s anchor-to-anchor gap, threshold =
    # 0.2 + 0.0, which is below 0.4 → no interpolation despite the overall
    # stream looking "slow" by any single-period yardstick.
    frames = [
        _frame(0.0, [(_pose(), 1)]),
        _frame(0.2, []),
        _frame(0.4, [(_pose(), 1)]),
    ]
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    action._interpolate_missing_poses(frames, merge_gap=0.0)

    assert _interpolated_count(frames, 1) == 0

    # With merge_gap=0.3 → threshold = 0.5 → above 0.4 → interpolate.
    frames = [
        _frame(0.0, [(_pose(), 1)]),
        _frame(0.2, []),
        _frame(0.4, [(_pose(), 1)]),
    ]
    action._interpolate_missing_poses(frames, merge_gap=0.3)

    assert _interpolated_count(frames, 1) == 1
