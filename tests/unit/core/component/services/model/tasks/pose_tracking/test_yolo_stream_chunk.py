"""Regression tests for the shape of streaming chunks emitted by
YoloPoseTrackingTaskAction. Segment fields must live at the top of the chunk
(flat), matching the non-streaming `tracks[i].segments[j]` element and the
sibling `track` / `detection` chunk shapes."""

from __future__ import annotations

from typing import Any, Dict

from mindor.core.component.services.model.tasks.pose_tracking.custom.yolo import (
    YoloPoseTrackingTaskAction,
)


def _params(**overrides) -> Dict[str, Any]:
    base = {
        "return_keypoints":          False,
        "return_openpose_keypoints": False,
        "return_skeleton_image":     False,
        "return_track_image":        False,
        "bounding_box_padding":      0.0,
    }
    base.update(overrides)
    return base


def _tracked_segment(score: float = 0.9) -> Dict[str, Any]:
    return {
        "start":       1.0,
        "end":         2.5,
        "frame_count": 4,
        "best_pose":   {
            "score":        score,
            "bounding_box": (10, 20, 110, 220),
        },
    }


class TestSegmentChunkIsFlat:
    def test_segment_chunk_has_no_nested_segment_key(self):
        action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
        chunk = action._build_segment_chunk(7, _tracked_segment(), _params())

        assert "segment" not in chunk

    def test_segment_chunk_carries_expected_flat_fields(self):
        action = YoloPoseTrackingTaskAction.__new__(YoloPoseTrackingTaskAction)
        chunk = action._build_segment_chunk(7, _tracked_segment(score=0.82), _params())

        assert chunk["type"] == "segment"
        assert chunk["track_id"] == 7
        assert chunk["start_time"] == "00:00:01.000"
        assert chunk["end_time"] == "00:00:02.500"
        assert chunk["duration"] == "00:00:01.500"
        assert chunk["frame_count"] == 4
        assert chunk["score"] == 0.82
        assert chunk["bounding_box"] == { "x": 10, "y": 20, "width": 100, "height": 200 }
