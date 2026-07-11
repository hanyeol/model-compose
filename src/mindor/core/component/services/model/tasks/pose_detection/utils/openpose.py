from __future__ import annotations

from typing import Any, Dict, List, Tuple
from PIL import Image as PILImage
from .skeleton import draw_skeleton

# OpenPose BODY_18 keypoint order (COCO + neck at index 1):
# 0: nose, 1: neck, 2: right shoulder, 3: right elbow, 4: right wrist,
# 5: left shoulder, 6: left elbow, 7: left wrist,
# 8: right hip, 9: right knee, 10: right ankle,
# 11: left hip, 12: left knee, 13: left ankle,
# 14: right eye, 15: left eye, 16: right ear, 17: left ear.

_BODY_18_LIMBS: List[Tuple[int, int]] = [
    (1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
    (1, 0), (0, 14), (14, 16), (0, 15), (15, 17),
]

_BODY_18_LIMB_COLORS: List[Tuple[int, int, int]] = [
    (153,   0,   0), (153,  51,   0), (153, 102,   0), (153, 153,   0), (102, 153,   0), ( 51, 153,   0),
    (  0, 153,   0), (  0, 153,  51), (  0, 153, 102), (  0, 153, 153), (  0, 102, 153), (  0,  51, 153),
    (  0,   0, 153), ( 51,   0, 153), (153,   0, 153), (102,   0, 153), (153,   0, 102),
]

_BODY_18_JOINT_COLORS: List[Tuple[int, int, int]] = [
    (255,   0,   0), (255,  85,   0), (255, 170,   0), (255, 255,   0), (170, 255,   0),
    ( 85, 255,   0), (  0, 255,   0), (  0, 255,  85), (  0, 255, 170), (  0, 255, 255),
    (  0, 170, 255), (  0,  85, 255), (  0,   0, 255), ( 85,   0, 255), (170,   0, 255),
    (255,   0, 255), (255,   0, 170), (255,   0,  85),
]

def render_skeleton(
    keypoints: List[Dict[str, Any]],
    width: int,
    height: int,
    limb_thickness: int = 4,
    joint_radius: int = 4,
) -> PILImage.Image:
    """Render an OpenPose BODY_18 pose in standard OpenPose colors on a black canvas."""
    return draw_skeleton(
        keypoints, _BODY_18_LIMBS, width, height,
        limb_colors=_BODY_18_LIMB_COLORS,
        joint_colors=_BODY_18_JOINT_COLORS,
        limb_thickness=limb_thickness,
        joint_radius=joint_radius,
    )
