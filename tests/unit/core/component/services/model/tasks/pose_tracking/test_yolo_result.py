"""Unit tests for YoloPoseTrackingTaskAction result shape.

Focuses on fields the result builder puts on each track (`track_id`, per-track
segments) and on the frame-centric view exposed via `return_frames`. Uses
synthetic poses so no YOLO model is loaded.
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
        "merge_gap":                 10.0,
        "skeleton_format":           "natural",
        "return_tracks":             True,
        "return_keypoints":          False,
        "return_openpose_keypoints": False,
        "return_skeleton_image":     False,
        "return_track_image":        False,
        "return_frame_image":        False,
        "return_metadata":           False,
        "return_frames":             False,
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


def _run(frames: List[List[Dict[str, Any]]], params: Dict[str, Any]) -> Dict[str, Any]:
    action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
    track_segments: Dict[int, Dict[str, Any]] = {}
    tracked_frames: List[Dict[str, Any]] = []

    for frame_index, poses in enumerate(frames):
        timestamp = frame_index * FRAME_PERIOD
        tracked_poses, _ = action._add_poses_to_tracks(poses, timestamp, FRAME_RATE, track_segments, params)
        if params["return_frames"]:
            tracked_frames.append({
                "number":        frame_index + 1,
                "timestamp":     timestamp,
                "tracked_poses": tracked_poses,
            })

    for track in track_segments.values():
        if track["current"] is not None:
            track["segments"].append(track["current"])
            track["current"] = None

    return action._build_tracking_result(track_segments, len(frames), tracked_frames, params)


class TestTrackId:

    def test_single_track_gets_its_track_id(self):
        result = _run([[_pose(track_id=7)] for _ in range(3)], _default_params())

        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["track_id"] == 7

    def test_multiple_tracks_carry_their_own_ids(self):
        frames = [[_pose(track_id=3), _pose(track_id=5, box=(200, 0, 50, 50))] for _ in range(3)]
        result = _run(frames, _default_params())

        track_ids = sorted(t["track_id"] for t in result["tracks"])
        assert track_ids == [3, 5]

    def test_pruned_tracks_do_not_appear_in_tracks(self):
        # Track 9 appears once and is dropped by min_frame_count=2.
        frames = [
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50)), _pose(track_id=9, box=(400, 0, 50, 50))],
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50))],
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50))],
        ]
        result = _run(frames, _default_params(min_frame_count=2))

        track_ids = sorted(t["track_id"] for t in result["tracks"])
        assert track_ids == [1, 5]


class TestTrackedFrames:
    """`return_frames` opts into a frame-centric view alongside the track-
    centric `tracks` list. Each entry is one input frame with the poses
    detected in it, tagged by track_id so consumers can cross-reference the
    two views."""

    def test_return_frames_false_omits_the_field(self):
        result = _run([[_pose()] for _ in range(3)], _default_params(return_frames=False))

        assert "frames" not in result

    def test_return_frames_true_produces_one_entry_per_input_frame(self):
        result = _run([[_pose()] for _ in range(3)], _default_params(return_frames=True))

        assert "frames" in result
        assert len(result["frames"]) == 3

    def test_frame_number_is_one_based_and_sequential(self):
        result = _run([[_pose()] for _ in range(3)], _default_params(return_frames=True))

        numbers = [entry["number"] for entry in result["frames"]]
        assert numbers == [1, 2, 3]

    def test_frame_timestamp_matches_frame_rate(self):
        result = _run([[_pose()] for _ in range(3)], _default_params(return_frames=True))

        timestamps = [entry["timestamp"] for entry in result["frames"]]
        assert timestamps == ["00:00:00.000", "00:00:00.500", "00:00:01.000"]

    def test_frame_entry_carries_poses_with_track_id_and_bounding_box(self):
        result = _run([[_pose(track_id=2, box=(10, 20, 30, 40), score=0.9)]], _default_params(return_frames=True))

        poses = result["frames"][0]["poses"]
        assert len(poses) == 1
        assert poses[0] == {
            "track_id":     2,
            "bounding_box": {"x": 10, "y": 20, "width": 30, "height": 40},
            "score":        0.9,
        }

    def test_empty_frame_yields_empty_poses_list(self):
        frames = [[_pose()], [], [_pose()]]
        result = _run(frames, _default_params(return_frames=True))

        assert len(result["frames"]) == 3
        assert result["frames"][1]["poses"] == []
        assert result["frames"][1]["number"] == 2

    def test_multiple_poses_in_one_frame_reference_their_own_track_ids(self):
        frames = [[_pose(track_id=1, box=(0, 0, 30, 30)), _pose(track_id=2, box=(200, 0, 30, 30))]]
        result = _run(frames, _default_params(return_frames=True))

        poses = result["frames"][0]["poses"]
        track_ids = sorted(p["track_id"] for p in poses)
        assert track_ids == [1, 2]

    def test_pruned_tracks_still_appear_in_frames_by_design(self):
        # Track 9 is pruned from `tracks` but its track_id remains in
        # `frames[0].poses`. Consumers that only care about confirmed tracks
        # look them up in `tracks`; the rest is discovery information about
        # low-confidence detections.
        frames = [
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50)), _pose(track_id=9, box=(400, 0, 50, 50))],
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50))],
            [_pose(track_id=1), _pose(track_id=5, box=(200, 0, 50, 50))],
        ]
        result = _run(frames, _default_params(min_frame_count=2, return_frames=True))

        first_frame_track_ids = sorted(p["track_id"] for p in result["frames"][0]["poses"])
        assert first_frame_track_ids == [1, 5, 9]

        surviving_track_ids = {t["track_id"] for t in result["tracks"]}
        assert surviving_track_ids == {1, 5}


class TestReturnTracks:
    """`return_tracks` opts out of the per-person track list entirely — useful
    when the caller only needs the frame-centric view."""

    def test_return_tracks_false_omits_the_field(self):
        params = _default_params(return_tracks=False, return_frames=True)
        result = _run([[_pose()] for _ in range(3)], params)

        assert "tracks" not in result
        assert "frames" in result

    def test_return_tracks_true_is_the_default(self):
        result = _run([[_pose()] for _ in range(3)], _default_params())

        assert "tracks" in result
