"""Unit tests for the pose_detection topology helpers."""

from __future__ import annotations

from mindor.core.component.services.model.tasks.pose_detection.utils.topology import (
    keypoints_to_bounding_box,
)


def _kp(x: int, y: int, visibility: float = 1.0) -> dict:
    return { "x": x, "y": y, "visibility": visibility }


class TestKeypointsToBoundingBox:
    def test_returns_xywh_covering_all_visible_points(self):
        box = keypoints_to_bounding_box([_kp(10, 20), _kp(50, 40), _kp(30, 5)])

        assert box == [10, 5, 40, 35]

    def test_ignores_hidden_keypoints(self):
        keypoints = [_kp(10, 10), _kp(999, 999, visibility=0.0), _kp(50, 50)]
        box = keypoints_to_bounding_box(keypoints)

        # The hidden point at (999, 999) must not stretch the bbox.
        assert box == [10, 10, 40, 40]

    def test_returns_none_when_all_keypoints_hidden(self):
        keypoints = [_kp(10, 10, visibility=0.0), _kp(20, 20, visibility=0.0)]

        assert keypoints_to_bounding_box(keypoints) is None

    def test_returns_none_for_empty_list(self):
        assert keypoints_to_bounding_box([]) is None

    def test_single_visible_keypoint_produces_zero_size_box(self):
        box = keypoints_to_bounding_box([_kp(42, 17)])

        assert box == [42, 17, 0, 0]

    def test_missing_visibility_defaults_to_visible(self):
        # visibility 키가 없어도 visible로 취급.
        box = keypoints_to_bounding_box([{ "x": 10, "y": 20 }, { "x": 30, "y": 40 }])

        assert box == [10, 20, 20, 20]
