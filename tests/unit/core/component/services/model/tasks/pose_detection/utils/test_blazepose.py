"""Unit tests for the BlazePose-33 topology helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_detection.utils import blazepose


def _kp(x: int, y: int, visibility: float = 1.0) -> dict:
    return { "x": x, "y": y, "visibility": visibility }


def _blazepose_33(visibility: float = 1.0) -> list[dict]:
    return [ _kp(i * 3, i * 3, visibility) for i in range(33) ]


class TestToBody18:
    def test_returns_18_entries(self):
        body_18 = blazepose.to_body_18(_blazepose_33())

        assert len(body_18) == 18

    def test_maps_nose_and_shoulders(self):
        body_18 = blazepose.to_body_18(_blazepose_33())

        # BlazePose 0 (nose) → BODY_18 0
        assert body_18[0]["x"] == 0
        # BlazePose 12 (right shoulder) → BODY_18 2
        assert body_18[2] == { "x": 36, "y": 36, "visibility": 1.0 }
        # BlazePose 11 (left shoulder) → BODY_18 5
        assert body_18[5] == { "x": 33, "y": 33, "visibility": 1.0 }

    def test_openpose_dicts_only_carry_xy_visibility(self):
        body_18 = blazepose.to_body_18(_blazepose_33())

        # BlazePose keypoints carry `z` and `presence`; the OpenPose layout
        # intentionally drops them.
        for entry in body_18:
            assert set(entry.keys()) == { "x", "y", "visibility" }

    def test_synthesizes_neck_at_shoulder_midpoint(self):
        body_18 = blazepose.to_body_18(_blazepose_33())

        # Neck is midpoint of BlazePose 11 & 12.
        assert body_18[1] == { "x": 34, "y": 34, "visibility": 1.0 }

    def test_neck_visibility_averages_shoulders(self):
        keypoints = _blazepose_33()
        keypoints[11]["visibility"] = 0.4
        keypoints[12]["visibility"] = 0.8

        body_18 = blazepose.to_body_18(keypoints)

        assert body_18[1]["visibility"] == pytest.approx(0.6)

    def test_neck_omitted_when_a_shoulder_hidden(self):
        keypoints = _blazepose_33()
        keypoints[11]["visibility"] = 0.0

        body_18 = blazepose.to_body_18(keypoints)

        assert body_18[1] == { "x": 0, "y": 0, "visibility": 0.0 }


class TestRenderSkeleton:
    def test_returns_pil_image_of_given_size(self):
        image = blazepose.render_skeleton(_blazepose_33(), 64, 48)

        assert isinstance(image, PILImage.Image)
        assert image.size == (64, 48)

    def test_black_background_when_no_visible_keypoints(self):
        image = blazepose.render_skeleton(_blazepose_33(visibility=0.0), 32, 32)
        assert image.getextrema() == ((0, 0), (0, 0), (0, 0))
