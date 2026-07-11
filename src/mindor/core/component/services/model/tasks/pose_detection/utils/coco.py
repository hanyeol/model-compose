from __future__ import annotations

from typing import Any, Dict, List, Tuple
from PIL import Image as PILImage
from .skeleton import draw_skeleton

# COCO-17 keypoint order (used by YOLO pose models):
# 0 nose, 1 L-eye, 2 R-eye, 3 L-ear, 4 R-ear, 5 L-shoulder, 6 R-shoulder,
# 7 L-elbow, 8 R-elbow, 9 L-wrist, 10 R-wrist, 11 L-hip, 12 R-hip,
# 13 L-knee, 14 R-knee, 15 L-ankle, 16 R-ankle.

_COCO_17_LIMBS: List[Tuple[int, int]] = [
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]

# COCO-17 → OpenPose BODY_18 keypoint index mapping. BODY_18 index 1 (neck) is
# absent from COCO and is derived from the midpoint of the two shoulders below.
_COCO_17_TO_BODY_18: Dict[int, int] = {
    0: 0, 6: 2, 8: 3, 10: 4, 5: 5, 7: 6, 9: 7,
    12: 8, 14: 9, 16: 10, 11: 11, 13: 12, 15: 13,
    2: 14, 1: 15, 4: 16, 3: 17,
}

def to_body_18(natural_keypoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remap COCO-17 keypoint dicts to the OpenPose BODY_18 layout.

    BODY_18 index 1 (neck) is synthesized from the midpoint of the two shoulders
    when both are visible.
    """
    body_18: List[Dict[str, Any]] = [{ "x": 0, "y": 0, "visibility": 0.0 } for _ in range(18)]
    for coco_index, body_index in _COCO_17_TO_BODY_18.items():
        body_18[body_index] = dict(natural_keypoints[coco_index])

    left_shoulder, right_shoulder = body_18[5], body_18[2]
    if left_shoulder["visibility"] > 0.0 and right_shoulder["visibility"] > 0.0:
        body_18[1] = {
            "x":          int((left_shoulder["x"] + right_shoulder["x"]) / 2),
            "y":          int((left_shoulder["y"] + right_shoulder["y"]) / 2),
            "visibility": (left_shoulder["visibility"] + right_shoulder["visibility"]) / 2.0,
        }

    return body_18

def render_skeleton(
    keypoints: List[Dict[str, Any]],
    width: int,
    height: int,
    limb_thickness: int = 4,
    joint_radius: int = 4,
) -> PILImage.Image:
    """Render a COCO-17 pose on a black canvas."""
    return draw_skeleton(keypoints, _COCO_17_LIMBS, width, height, limb_thickness=limb_thickness, joint_radius=joint_radius)
