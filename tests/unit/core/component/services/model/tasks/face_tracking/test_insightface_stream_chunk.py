"""Regression tests for the shape of streaming chunks emitted by
InsightfaceFaceTrackingTaskAction. Segment fields must live at the top of the
chunk (flat), matching the non-streaming `tracks[i].segments[j]` element and
the sibling `track` / `detection` chunk shapes."""

from __future__ import annotations

from typing import Any, Dict

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)


def _params(**overrides) -> Dict[str, Any]:
    base = {
        "return_track_image":  False,
        "return_gender_age":   False,
        "bounding_box_padding": 0.0,
    }
    base.update(overrides)
    return base


def _tracked_segment(score: float = 0.9) -> Dict[str, Any]:
    return {
        "start":       1.0,
        "end":         2.5,
        "frame_count": 4,
        "best_face":   { "score": score },
    }


class TestSegmentChunkIsFlat:
    """`segment` chunks must expose their fields at the top level so
    downstream consumers can read `chunk.start_time` etc. directly — the same
    field path used by non-streaming `tracks[i].segments[j]`."""

    def test_segment_chunk_has_no_nested_segment_key(self):
        action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
        chunk = action._build_segment_chunk(0, _tracked_segment(), _params())

        assert "segment" not in chunk

    def test_segment_chunk_carries_expected_flat_fields(self):
        action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
        chunk = action._build_segment_chunk(4, _tracked_segment(score=0.88), _params())

        assert chunk["type"] == "segment"
        assert chunk["track_id"] == 5  # cluster_id + 1
        assert chunk["start_time"] == "00:00:01.000"
        assert chunk["end_time"] == "00:00:02.500"
        assert chunk["duration"] == "00:00:01.500"
        assert chunk["frame_count"] == 4
        assert chunk["score"] == 0.88

    def test_optional_fields_are_flat_when_enabled(self):
        action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
        tracked_segment = {
            "start":       0.0,
            "end":         0.5,
            "frame_count": 2,
            "best_face":   { "score": 0.7, "image": object(), "gender": 1, "age": 30 },
        }
        chunk = action._build_segment_chunk(
            0,
            tracked_segment,
            _params(return_track_image=True, return_gender_age=True),
        )

        assert "image" in chunk
        assert chunk["gender"] == "male"
        assert chunk["age"] == 30
        assert "segment" not in chunk
