"""Unit tests for InsightfaceFaceTrackingTaskAction segment merging.

Drives clustering with synthetic embeddings, so no insightface / onnxruntime
model is loaded.

The distance between two consecutive sampled frames is always one frame
interval, so `merge_gap` has to be measured on top of that interval: it means
"how long a person may go undetected before the segment is split", not "how far
apart two detections may be". Measured literally, the default of 0.0 splits on
every frame and emits one zero-length segment per detection.
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


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "similarity_threshold":     0.4,
        "min_face_size":            0,
        "min_frame_count":          1,
        "merge_gap":                0.0,
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
    """Feed per-frame detections through clustering and build the result.

    `frames[i]` is the detection list for frame `i`; an empty list is a frame in
    which nobody was detected, which still advances the clock.
    """
    # Instantiate without going through __init__ (which needs a real model handle).
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    cluster_tracks: Dict[int, Dict[str, Any]] = {}
    centroids_state: Dict[str, Any] = {"centroids": [], "counts": []}

    for frame_index, faces in enumerate(frames):
        action._cluster_faces(faces, frame_index * FRAME_PERIOD, FRAME_RATE, centroids_state, cluster_tracks, params)

    # Flush the still-open segment, as _collect_tracks() does before building the result.
    for track in cluster_tracks.values():
        if track["current"] is not None:
            track["segments"].append(track["current"])
            track["current"] = None

    return action._build_tracking_result(cluster_tracks, centroids_state, len(frames), [], params)


def _segments(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    assert len(result["tracks"]) == 1, f"expected a single track, got {len(result['tracks'])}"
    return result["tracks"][0]["segments"]


class TestContiguousFrames:
    """A person detected in every frame is on screen continuously, whatever
    merge_gap says — there is no gap to merge across."""

    def test_default_merge_gap_yields_one_segment(self):
        segments = _segments(_run([[_face(ALICE)] for _ in range(5)], _default_params(merge_gap=0.0)))

        assert len(segments) == 1
        assert segments[0]["start_time"] == "00:00:00.000"
        assert segments[0]["end_time"] == "00:00:02.000"

    def test_default_merge_gap_yields_non_zero_duration(self):
        segments = _segments(_run([[_face(ALICE)] for _ in range(5)], _default_params(merge_gap=0.0)))

        assert segments[0]["duration"] != "00:00:00.000"

    def test_explicit_merge_gap_yields_one_segment(self):
        # The bundled example uses merge_gap: 1.0 — guard it against a fix that
        # over-corrects in the other direction.
        segments = _segments(_run([[_face(ALICE)] for _ in range(5)], _default_params(merge_gap=1.0)))

        assert len(segments) == 1

    def test_frame_count_matches_detections(self):
        result = _run([[_face(ALICE)] for _ in range(5)], _default_params(merge_gap=0.0))

        assert result["tracks"][0]["frame_count"] == 5


class TestAbsence:
    """merge_gap governs how long a person may go undetected before the segment
    is split, measured from the frame they were last seen in."""

    def test_undetected_frame_within_merge_gap_keeps_one_segment(self):
        # Missing for one frame: 0.5s of absence, inside a 0.5s merge_gap.
        frames = [[_face(ALICE)], [_face(ALICE)], [], [_face(ALICE)]]
        segments = _segments(_run(frames, _default_params(merge_gap=0.5)))

        assert len(segments) == 1

    def test_undetected_frames_beyond_merge_gap_split_the_segment(self):
        # Missing for three frames: 1.5s of absence, outside a 0.5s merge_gap.
        frames = [[_face(ALICE)], [_face(ALICE)], [], [], [], [_face(ALICE)]]
        segments = _segments(_run(frames, _default_params(merge_gap=0.5)))

        assert len(segments) == 2
        assert segments[0]["end_time"] == "00:00:00.500"
        assert segments[1]["start_time"] == "00:00:02.500"

    def test_zero_merge_gap_splits_on_the_first_missed_frame(self):
        frames = [[_face(ALICE)], [_face(ALICE)], [], [_face(ALICE)]]
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
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        centroids_state: Dict[str, Any] = {"centroids": [], "counts": []}
        for i in range(num_frames):
            timestamp = offset + i / frame_rate
            action._cluster_faces([_face(ALICE)], timestamp, frame_rate, centroids_state, cluster_tracks, params)
        for track in cluster_tracks.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None
        return action._build_tracking_result(cluster_tracks, centroids_state, num_frames, [], params)

    def test_ulp_jitter_at_large_offset_does_not_split(self):
        # rate=5, offset=3600 is one of the reproduced pathological pairs:
        # (offset + n/rate) - prev_ts exceeds 1/rate by ~2.7e-13 on some n.
        action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
        params = _default_params(merge_gap=0.0)
        segments = _segments(self._run_at(action, frame_rate=5.0, offset=3600.0, num_frames=10, params=params))
        assert len(segments) == 1

    def test_ulp_jitter_at_odd_rate_does_not_split(self):
        # rate=7.5, offset=12.5: another combo where the derivation paths
        # diverge and would spuriously split contiguous detections.
        action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
        params = _default_params(merge_gap=0.0)
        segments = _segments(self._run_at(action, frame_rate=7.5, offset=12.5, num_frames=10, params=params))
        assert len(segments) == 1
