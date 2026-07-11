"""Unit tests for OpenPose BODY_18 rendering."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_detection.utils import openpose


def _kp(x: int, y: int, visibility: float = 1.0) -> dict:
    return { "x": x, "y": y, "visibility": visibility }


def _body_18(visibility: float = 1.0) -> list[dict]:
    # Positions spread over a 180x180 canvas so lines and joints don't overlap.
    return [ _kp(10 + i * 8, 10 + i * 8, visibility) for i in range(18) ]


class TestRenderSkeleton:
    def test_returns_pil_image_of_given_size(self):
        image = openpose.render_skeleton(_body_18(), 200, 200)

        assert isinstance(image, PILImage.Image)
        assert image.size == (200, 200)
        assert image.mode == "RGB"

    def test_black_background_when_no_visible_keypoints(self):
        image = openpose.render_skeleton(_body_18(visibility=0.0), 64, 64)
        assert image.getextrema() == ((0, 0), (0, 0), (0, 0))

    def test_uses_openpose_standard_colors(self):
        image = openpose.render_skeleton(_body_18(), 200, 200)

        # OpenPose standard joint colors include pure red at BODY_18 index 0 (nose)
        # and pure yellow at index 3. Both should appear in the rendered canvas.
        pixels = set(image.getdata())
        assert (255, 0, 0) in pixels
        assert (255, 255, 0) in pixels
