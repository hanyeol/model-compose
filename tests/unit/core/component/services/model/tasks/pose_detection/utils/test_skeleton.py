"""Unit tests for the skeleton rendering primitive."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image as PILImage

from mindor.core.component.services.model.tasks.pose_detection.utils.skeleton import (
    draw_skeleton,
)


def _kp(x: int, y: int, visibility: float = 1.0) -> dict:
    return { "x": x, "y": y, "visibility": visibility }


class TestDrawSkeleton:
    def test_returns_pil_image_of_given_size(self):
        image = draw_skeleton([_kp(10, 10), _kp(20, 20)], [(0, 1)], 64, 48)

        assert isinstance(image, PILImage.Image)
        assert image.size == (64, 48)
        assert image.mode == "RGB"

    def test_black_background_when_no_visible_points(self):
        image = draw_skeleton(
            [_kp(0, 0, visibility=0.0), _kp(0, 0, visibility=0.0)],
            [(0, 1)],
            32, 32,
        )

        # Every pixel must be black — nothing was drawn.
        assert image.getextrema() == ((0, 0), (0, 0), (0, 0))

    def test_hidden_joints_are_not_drawn(self):
        # One point visible, one hidden — the connecting limb must NOT be drawn.
        image = draw_skeleton(
            [_kp(10, 10), _kp(20, 20, visibility=0.0)],
            [(0, 1)],
            32, 32,
        )

        pixels = list(image.getdata())
        # Only the single visible joint should contribute non-black pixels
        # (a small disk around (10, 10)). No pixel near (20, 20) should be lit.
        assert image.getpixel((20, 20)) == (0, 0, 0)

    def test_visible_joints_produce_non_black_pixels(self):
        image = draw_skeleton([_kp(16, 16)], [], 32, 32)

        # At (16, 16) there should be a joint dot; expect a non-black pixel.
        assert image.getpixel((16, 16)) != (0, 0, 0)

    def test_out_of_range_limb_index_is_ignored(self):
        # limb references an index past the keypoint list — must not crash.
        image = draw_skeleton([_kp(5, 5)], [(0, 5)], 16, 16)
        assert isinstance(image, PILImage.Image)

    def test_custom_colors_are_used(self):
        red = (255, 0, 0)
        image = draw_skeleton(
            [_kp(8, 8), _kp(24, 24)],
            [(0, 1)],
            32, 32,
            limb_colors=[red],
            joint_colors=[red, red],
        )
        # At least some pixel must be the exact red we passed in.
        assert red in image.getdata()
