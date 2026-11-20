from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image as PILImage
from ...pose_detection.utils.skeleton import draw_skeleton

# OpenPose hand 21-keypoint topology — matches MediaPipe Hand index layout
# (wrist + 4 joints × 5 fingers), so natural keypoints feed in without remap.
# Only the color scheme (official OpenPose hand palette) differs from
# `blazehand.render_skeleton`.
#
# https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/include/openpose/hand/handParameters.hpp

_HAND_21_LIMBS: List[Tuple[int, int]] = [
    # Thumb (wrist → tip)
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (0, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (0, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
]

# OpenPose official HAND_COLORS_RENDER (21 keypoints). Each finger gets a hue
# that brightens along the chain so distal joints are easier to read.
_HAND_21_JOINT_COLORS: List[Tuple[int, int, int]] = [
    (100, 100, 100),
    (100,   0,   0), (150,   0,   0), (200,   0,   0), (255,   0,   0),
    (100, 100,   0), (150, 150,   0), (200, 200,   0), (255, 255,   0),
    (  0, 100,  50), (  0, 150,  75), (  0, 200, 100), (  0, 255, 125),
    (  0,  50, 100), (  0,  75, 150), (  0, 100, 200), (  0, 125, 255),
    (100,   0, 100), (150,   0, 150), (200,   0, 200), (255,   0, 255),
]

# Limb color = color of its distal joint (same convention as OpenPose's own
# renderer), so each finger's limbs match its tip hue.
_HAND_21_LIMB_COLORS: List[Tuple[int, int, int]] = [ _HAND_21_JOINT_COLORS[b] for _, b in _HAND_21_LIMBS ]

def render_skeleton(
    keypoints: List[Dict[str, Any]],
    width: int,
    height: int,
    limb_thickness: int = 4,
    joint_radius: int = 4,
    background: Optional[Union[Tuple[int, int, int], Tuple[int, int, int, int]]] = None,
) -> PILImage.Image:
    """Render an OpenPose 21-point hand in standard OpenPose colors. See
    `draw_skeleton` for `background` semantics."""
    return draw_skeleton(
        keypoints,
        _HAND_21_LIMBS,
        width,
        height,
        limb_colors=_HAND_21_LIMB_COLORS,
        joint_colors=_HAND_21_JOINT_COLORS,
        limb_thickness=limb_thickness,
        joint_radius=joint_radius,
        background=background,
    )
