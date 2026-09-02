"""Unit tests for YoloPoseTrackingTaskAction segment merging.

Drives track extension with synthetic poses, so no YOLO model is loaded. The
distance between two consecutive sampled frames is always one frame interval,
so `merge_gap` measures how long a person may go undetected before the segment
is split — not how far apart two detections may be. Measured literally, a
value of 0.0 would split on every frame and emit one zero-length segment per
detection.
"""

from __future__ import annotations

from typing import Any, Dict, List

from mindor.core.component.services.model.tasks.pose_tracking.custom.yolo import (
    YoloPoseTrackingTaskAction,
)

FRAME_RATE = 2.0
FRAME_PERIOD = 1.0 / FRAME_RATE


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "min_confidence":            0.5,
        "min_presence_confidence":   0.5,
        "min_pose_size":             0,
        "min_frame_count":           1,
        "max_pose_count_per_frame":  0,
        "merge_gap":                 0.0,
        "skeleton_format":           "natural",
        "return_tracks":             True,
        "return_keypoints":          False,
        "return_openpose_keypoints": False,
        "return_skeleton_image":     False,
        "return_track_image":        False,
        "return_frame_image":        False,
        "return_metadata":           False,
        "return_detections":         False,
        "bounding_box_padding":      0.0,
    }
    base.update(overrides)
    return base


def _pose(track_id: int = 1, score: float = 0.9, box=(0, 0, 50, 50)) -> Dict[str, Any]:
    x, y, w, h = box
    return {
        "track_id":     track_id,
        "bounding_box": (x, y, x + w, y + h),
        "score":        score,
        "width":        640,
        "height":       480,
    }


def _run(frames: List[List[Dict[str, Any]]], params: Dict[str, Any], frame_rate: float = FRAME_RATE) -> Dict[str, Any]:
    """Feed per-frame poses through track extension and build the result.

    `frames[i]` is the pose list for frame `i`; an empty list is a frame in
    which nobody was detected, which still advances the clock.
    """
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}
    frame_period = 1.0 / frame_rate

    for frame_index, poses in enumerate(frames):
        action._add_poses_to_tracks(poses, frame_index * frame_period, frame_rate, track_segments, params)

    for track in track_segments.values():
        if track["current"] is not None:
            track["segments"].append(track["current"])
            track["current"] = None

    return action._build_tracking_result(track_segments, len(frames), [], params)


def _segments(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    assert len(result["tracks"]) == 1, f"expected a single track, got {len(result['tracks'])}"
    return result["tracks"][0]["segments"]


class TestContiguousFrames:
    """A person detected in every frame is on screen continuously, whatever
    merge_gap says — there is no gap to merge across."""

    def test_default_merge_gap_yields_one_segment(self):
        segments = _segments(_run([[_pose()] for _ in range(5)], _default_params(merge_gap=0.0)))

        assert len(segments) == 1
        assert segments[0]["start_time"] == "00:00:00.000"
        assert segments[0]["end_time"] == "00:00:02.000"

    def test_default_merge_gap_yields_non_zero_duration(self):
        segments = _segments(_run([[_pose()] for _ in range(5)], _default_params(merge_gap=0.0)))

        assert segments[0]["duration"] != "00:00:00.000"

    def test_explicit_merge_gap_yields_one_segment(self):
        segments = _segments(_run([[_pose()] for _ in range(5)], _default_params(merge_gap=1.0)))

        assert len(segments) == 1

    def test_frame_count_matches_detections(self):
        result = _run([[_pose()] for _ in range(5)], _default_params(merge_gap=0.0))

        assert result["tracks"][0]["frame_count"] == 5


class TestAbsence:
    """merge_gap governs how long a person may go undetected before the segment
    is split, measured from the frame they were last seen in."""

    def test_undetected_frame_within_merge_gap_keeps_one_segment(self):
        # Missing for one frame: 0.5s of absence, inside a 0.5s merge_gap.
        frames = [[_pose()], [_pose()], [], [_pose()]]
        segments = _segments(_run(frames, _default_params(merge_gap=0.5)))

        assert len(segments) == 1

    def test_undetected_frames_beyond_merge_gap_split_the_segment(self):
        # Missing for three frames: 1.5s of absence, outside a 0.5s merge_gap.
        frames = [[_pose()], [_pose()], [], [], [], [_pose()]]
        segments = _segments(_run(frames, _default_params(merge_gap=0.5)))

        assert len(segments) == 2
        assert segments[0]["end_time"] == "00:00:00.500"
        assert segments[1]["start_time"] == "00:00:02.500"

    def test_zero_merge_gap_splits_on_the_first_missed_frame(self):
        frames = [[_pose()], [_pose()], [], [_pose()]]
        segments = _segments(_run(frames, _default_params(merge_gap=0.0)))

        assert len(segments) == 2


class TestFloatingPointRobustness:
    """Real callers derive per-frame timestamps as `offset + frame_index / rate`
    while the matcher compares against `1.0 / rate`. Those two derivations
    diverge by ULPs, so on select rate/offset combos consecutive frames drift
    just past frame_period even when the person never left the screen. The
    merge check must absorb that jitter."""

    @staticmethod
    def _run_at(action, frame_rate: float, offset: float, num_frames: int, params: Dict[str, Any]) -> Dict[str, Any]:
        track_segments: Dict[int, Dict[str, Any]] = {}
        frame_period = 1.0 / frame_rate
        for i in range(num_frames):
            timestamp = offset + i / frame_rate
            action._add_poses_to_tracks([_pose()], timestamp, frame_rate, track_segments, params)
        for track in track_segments.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None
        return action._build_tracking_result(track_segments, num_frames, [], params)

    def test_ulp_jitter_at_large_offset_does_not_split(self):
        # rate=5, offset=3600: pathological pair where (offset + n/rate) - prev
        # exceeds 1/rate by ~2.7e-13 on some n.
        action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
        params = _default_params(merge_gap=0.0)
        segments = _segments(self._run_at(action, frame_rate=5.0, offset=3600.0, num_frames=10, params=params))
        assert len(segments) == 1

    def test_ulp_jitter_at_odd_rate_does_not_split(self):
        # rate=7.5, offset=12.5: another combo where derivation paths diverge.
        action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
        params = _default_params(merge_gap=0.0)
        segments = _segments(self._run_at(action, frame_rate=7.5, offset=12.5, num_frames=10, params=params))
        assert len(segments) == 1
