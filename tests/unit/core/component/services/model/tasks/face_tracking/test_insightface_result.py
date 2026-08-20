"""Unit tests for InsightfaceFaceTrackingTaskAction result shape.

Focuses on fields the result builder puts on each track — currently `track_id`,
which is a stable per-cluster integer so downstream consumers don't have to
rely on list order.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)

FRAME_RATE = 2.0
FRAME_PERIOD = 1.0 / FRAME_RATE

ALICE = [1.0, 0.0, 0.0]
BOB   = [0.0, 1.0, 0.0]
CAROL = [0.0, 0.0, 1.0]


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "similarity_threshold":     0.4,
        "min_face_size":            0,
        "min_frame_count":          1,
        "merge_gap":                10.0,
        "max_face_count_per_frame": 0,
        "max_track_distance":       0.0,
        "return_tracks":            True,
        "return_track_image":       False,
        "return_frame_image":       False,
        "return_metadata":          False,
        "return_embedding":         False,
        "return_gender_age":        False,
        "return_frames":            False,
        "bounding_box_padding":     0.0,
    }
    base.update(overrides)
    return base


def _face(embedding: List[float], box=(0, 0, 50, 50), score: float = 0.9) -> Dict[str, Any]:
    x, y, width, height = box
    return {
        "embedding":    np.array(embedding, dtype=float),
        "bounding_box": (x, y, x + width, y + height),
        "score":        score,
    }


def _run(frames: List[List[Dict[str, Any]]], params: Dict[str, Any]) -> Dict[str, Any]:
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    cluster_tracks: Dict[int, Dict[str, Any]] = {}
    centroids_state: Dict[str, Any] = {"centroids": [], "counts": []}
    tracked_frames: List[Dict[str, Any]] = []

    for frame_index, faces in enumerate(frames):
        timestamp = frame_index * FRAME_PERIOD
        tracked_faces, _ = action._cluster_faces(faces, timestamp, FRAME_RATE, centroids_state, cluster_tracks, params)
        if params["return_frames"]:
            tracked_frames.append({
                "number":        frame_index + 1,
                "timestamp":     timestamp,
                "tracked_faces": tracked_faces,
            })

    for track in cluster_tracks.values():
        if track["current"] is not None:
            track["segments"].append(track["current"])
            track["current"] = None

    return action._build_tracking_result(cluster_tracks, centroids_state, len(frames), tracked_frames, params)


class TestTrackId:

    def test_single_track_gets_track_id_one(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params())

        assert len(result["tracks"]) == 1
        assert result["tracks"][0]["track_id"] == 1

    def test_track_ids_are_one_based_and_increment_by_cluster_order(self):
        # Two people appear together across three frames, so two clusters spawn
        # in a well-defined order (Alice first because she's the first detection
        # of the first frame).
        frames = [[_face(ALICE), _face(BOB, box=(200, 0, 50, 50))] for _ in range(3)]
        result = _run(frames, _default_params())

        track_ids = [track["track_id"] for track in result["tracks"]]
        assert track_ids == [1, 2]

    def test_track_ids_stay_stable_when_min_frame_count_prunes(self):
        # Carol appears in a single frame and gets dropped by min_frame_count.
        # The surviving tracks must keep their original cluster-order ids so
        # external references (e.g. per-frame face lists) stay valid.
        frames = [
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50)), _face(CAROL, box=(400, 0, 50, 50))],
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50))],
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50))],
        ]
        result = _run(frames, _default_params(min_frame_count=2))

        track_ids = [track["track_id"] for track in result["tracks"]]
        assert track_ids == [1, 2]  # Carol's id (3) is dropped, not renumbered


class TestTrackedFrames:
    """`return_frames` opts into a frame-centric view alongside the track-
    centric `tracks` list. Each entry is one input frame with the faces
    detected in it, tagged by track_id so consumers can cross-reference the
    two views."""

    def test_return_frames_false_omits_the_field(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params(return_frames=False))

        assert "frames" not in result

    def test_return_frames_true_produces_one_entry_per_input_frame(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params(return_frames=True))

        assert "frames" in result
        assert len(result["frames"]) == 3

    def test_frame_number_is_one_based_and_sequential(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params(return_frames=True))

        numbers = [entry["number"] for entry in result["frames"]]
        assert numbers == [1, 2, 3]

    def test_frame_timestamp_matches_frame_rate(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params(return_frames=True))

        timestamps = [entry["timestamp"] for entry in result["frames"]]
        assert timestamps == ["00:00:00.000", "00:00:00.500", "00:00:01.000"]

    def test_frame_entry_carries_faces_with_track_id_and_bounding_box(self):
        result = _run([[_face(ALICE, box=(10, 20, 30, 40), score=0.9)]], _default_params(return_frames=True))

        faces = result["frames"][0]["faces"]
        assert len(faces) == 1
        assert faces[0] == {
            "track_id":     1,
            "bounding_box": {"x": 10, "y": 20, "width": 30, "height": 40},
            "score":        0.9,
        }

    def test_empty_frame_yields_empty_faces_list(self):
        # A frame with no detections still advances the clock and appears in
        # the output — just with an empty `faces` list.
        frames = [[_face(ALICE)], [], [_face(ALICE)]]
        result = _run(frames, _default_params(return_frames=True))

        assert len(result["frames"]) == 3
        assert result["frames"][1]["faces"] == []
        assert result["frames"][1]["number"] == 2

    def test_multiple_faces_in_one_frame_reference_their_own_track_ids(self):
        frames = [[_face(ALICE, box=(0, 0, 30, 30)), _face(BOB, box=(200, 0, 30, 30))]]
        result = _run(frames, _default_params(return_frames=True))

        faces = result["frames"][0]["faces"]
        track_ids = sorted(f["track_id"] for f in faces)
        assert track_ids == [1, 2]

    def test_pruned_tracks_still_appear_in_frames_by_design(self):
        # Carol is pruned from `tracks` by min_frame_count, but her track_id (3)
        # remains in `frames[0].faces` as a dangling reference. This is the
        # documented "gap-tolerant" contract — consumers that only care about
        # confirmed tracks look them up in `tracks`; the rest is discovery
        # information about low-confidence detections.
        frames = [
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50)), _face(CAROL, box=(400, 0, 50, 50))],
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50))],
            [_face(ALICE), _face(BOB, box=(200, 0, 50, 50))],
        ]
        result = _run(frames, _default_params(min_frame_count=2, return_frames=True))

        first_frame_track_ids = sorted(f["track_id"] for f in result["frames"][0]["faces"])
        assert first_frame_track_ids == [1, 2, 3]

        surviving_track_ids = {t["track_id"] for t in result["tracks"]}
        assert surviving_track_ids == {1, 2}


class TestReturnTracks:
    """`return_tracks` opts out of the per-person track list entirely — useful
    when the caller only needs the frame-centric view (e.g. per-frame
    redaction pipelines)."""

    def test_return_tracks_false_omits_the_field(self):
        params = _default_params(return_tracks=False, return_frames=True)
        result = _run([[_face(ALICE)] for _ in range(3)], params)

        assert "tracks" not in result
        assert "frames" in result

    def test_return_tracks_true_is_the_default(self):
        result = _run([[_face(ALICE)] for _ in range(3)], _default_params())

        assert "tracks" in result
