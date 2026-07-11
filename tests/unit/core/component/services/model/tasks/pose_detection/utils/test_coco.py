"""Unit tests for the COCO-17 topology helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_detection.utils import coco


def _kp(x: int, y: int, visibility: float = 1.0) -> dict:
    return { "x": x, "y": y, "visibility": visibility }


def _coco_17(visibility: float = 1.0) -> list[dict]:
    # 17 distinct positions so mapping errors are easy to spot.
    return [ _kp(i * 10, i * 10, visibility) for i in range(17) ]


class TestToBody18:
    def test_returns_18_entries(self):
        body_18 = coco.to_body_18(_coco_17())

        assert len(body_18) == 18

    def test_maps_nose_and_shoulders(self):
        body_18 = coco.to_body_18(_coco_17())

        # COCO 0 (nose) → BODY_18 0
        assert body_18[0]["x"] == 0
        # COCO 6 (right shoulder) → BODY_18 2
        assert body_18[2] == { "x": 60, "y": 60, "visibility": 1.0 }
        # COCO 5 (left shoulder) → BODY_18 5
        assert body_18[5] == { "x": 50, "y": 50, "visibility": 1.0 }

    def test_synthesizes_neck_at_shoulder_midpoint(self):
        body_18 = coco.to_body_18(_coco_17())

        # Neck (BODY_18 index 1) is the midpoint of shoulders (COCO 5 & 6).
        assert body_18[1] == { "x": 55, "y": 55, "visibility": 1.0 }

    def test_neck_visibility_averages_shoulders(self):
        coco_17 = _coco_17(visibility=1.0)
        coco_17[5]["visibility"] = 0.4  # left shoulder
        coco_17[6]["visibility"] = 0.8  # right shoulder

        body_18 = coco.to_body_18(coco_17)

        assert body_18[1]["visibility"] == pytest.approx(0.6)

    def test_neck_omitted_when_a_shoulder_hidden(self):
        coco_17 = _coco_17()
        coco_17[5]["visibility"] = 0.0  # hide left shoulder

        body_18 = coco.to_body_18(coco_17)

        # With only one shoulder visible, neck stays at the default zero entry.
        assert body_18[1] == { "x": 0, "y": 0, "visibility": 0.0 }

    def test_neck_omitted_when_both_shoulders_hidden(self):
        coco_17 = _coco_17(visibility=0.0)

        body_18 = coco.to_body_18(coco_17)

        assert body_18[1]["visibility"] == 0.0


class TestRenderSkeleton:
    def test_returns_pil_image_of_given_size(self):
        image = coco.render_skeleton(_coco_17(), 64, 48)

        assert isinstance(image, PILImage.Image)
        assert image.size == (64, 48)

    def test_black_background_when_no_visible_keypoints(self):
        image = coco.render_skeleton(_coco_17(visibility=0.0), 32, 32)
        assert image.getextrema() == ((0, 0), (0, 0), (0, 0))

    def test_draws_something_when_visible(self):
        image = coco.render_skeleton(_coco_17(), 200, 200)
        # Any non-black pixel means bones or joints were drawn.
        assert image.getextrema() != ((0, 0), (0, 0), (0, 0))
