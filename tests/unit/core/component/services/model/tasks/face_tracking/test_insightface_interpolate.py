"""Unit tests for InsightfaceFaceTrackingTaskAction._interpolate_missing_faces.

Covers the non-streaming interpolation path. The threshold rides each frame's
real prior interval, so a `timestamps`-only call with no `frame_rate` must
succeed. The `max_track_distance` check inside `_interpolate_between_faces`
also uses the per-anchor interval, so VFR streams rank anchor jumps against
the same `gap_frames` the streaming path would compute.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)


def _frame(timestamp: float, faces: List[Tuple[Dict[str, Any], int]]) -> Dict[str, Any]:
    return {"timestamp": timestamp, "tracked_faces": list(faces)}


def _face(bbox: Tuple[int, int, int, int] = (10, 10, 110, 110)) -> Dict[str, Any]:
    return {"bounding_box": bbox, "score": 0.9}


def _interpolated_count(frames: List[Dict[str, Any]], cluster_id: int) -> int:
    total = 0
    for frame in frames:
        for face, cid in frame["tracked_faces"]:
            if cid == cluster_id and face.get("interpolated"):
                total += 1
    return total


def test_interpolates_without_frame_rate() -> None:
    frames = [
        _frame(0.0, [(_face((0, 0, 100, 100)), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_face((40, 40, 140, 140)), 1)]),
    ]
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    action._interpolate_missing_faces(frames, merge_gap=1.0, max_track_distance=0.0)

    assert _interpolated_count(frames, 1) == 1


def test_uniform_stride_matches_streaming_period() -> None:
    frames = [
        _frame(0.0, [(_face(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_face(), 1)]),
    ]
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    action._interpolate_missing_faces(frames, merge_gap=0.4, max_track_distance=0.0)

    assert _interpolated_count(frames, 1) == 0

    frames = [
        _frame(0.0, [(_face(), 1)]),
        _frame(0.5, []),
        _frame(1.0, [(_face(), 1)]),
    ]
    action._interpolate_missing_faces(frames, merge_gap=0.6, max_track_distance=0.0)

    assert _interpolated_count(frames, 1) == 1


def test_vfr_max_track_distance_uses_prior_interval() -> None:
    # Two anchor pairs with different prior intervals. If the interpolator
    # reused a single `frame_period` across pairs (e.g. 1/frame_rate), the
    # second pair's `gap_frames` would be off and the `max_track_distance`
    # verdict would flip. With face_size=100, max_track_distance=0.5,
    # per-frame allowance is 50 px; a 350 px jump is accepted only when
    # gap_frames ≥ 7.
    #
    # Second anchor pair spans 0.8s with prior interval 0.4s → gap_frames=2
    # → allowance 100 px → 350 px center jump is rejected (no interpolation).
    # If `frame_period` were mistakenly reused from the first pair's 0.1s,
    # gap_frames would be 8 → allowance 400 px → the jump would be accepted
    # and the gap would get interpolated.
    frames = [
        _frame(0.0, [(_face((0,   0, 100, 100)), 1)]),
        _frame(0.1, []),
        _frame(0.2, [(_face((50,  0, 150, 100)), 1)]),  # anchor-pair-1 landing
        _frame(0.6, []),
        _frame(1.0, [(_face((400, 0, 500, 100)), 1)]),  # anchor-pair-2 landing: 350 px jump
    ]
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    action._interpolate_missing_faces(frames, merge_gap=1.0, max_track_distance=0.5)

    # Pair 1: 50 px jump across gap_frames=2 → allowance 100 → accepted → 1
    # interpolated frame (the 0.1s hole). Pair 2: 350 px jump across
    # gap_frames=2 → allowance 100 → rejected → 0.6s hole stays empty.
    assert _interpolated_count(frames, 1) == 1
