from __future__ import annotations

from typing import Any, Dict, List, Tuple
from PIL import Image as PILImage
from .skeleton import draw_skeleton

# BlazePose 33-landmark topology used by MediaPipe Pose Landmarker.
# https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
# Face: 0..10; Torso/arms: 11..22; Legs/feet: 23..32.

_BLAZEPOSE_33_LIMBS: List[Tuple[int, int]] = [
    # Face
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    # Torso
    (11, 12), (11, 23), (12, 24), (23, 24),
    # Left arm
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    # Right arm
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    # Left leg
    (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    # Right leg
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
]

# BlazePose-33 → OpenPose BODY_18 keypoint index mapping. BlazePose has no neck
# landmark; BODY_18 index 1 is derived from the midpoint of the two shoulders below.
_BLAZEPOSE_33_TO_BODY_18: Dict[int, int] = {
    0: 0, 12: 2, 14: 3, 16: 4, 11: 5, 13: 6, 15: 7,
    24: 8, 26: 9, 28: 10, 23: 11, 25: 12, 27: 13,
    5: 14, 2: 15, 8: 16, 7: 17,
}

def to_body_18(natural_keypoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remap BlazePose-33 keypoint dicts to the OpenPose BODY_18 layout.

    Only `{x, y, visibility}` is carried across; BlazePose's `z` and `presence`
    fields do not exist in the OpenPose format. BODY_18 index 1 (neck) is
    synthesized from the midpoint of the two shoulders when both are visible.
    """
    body_18: List[Dict[str, Any]] = [{ "x": 0, "y": 0, "visibility": 0.0 } for _ in range(18)]
    for blaze_index, body_index in _BLAZEPOSE_33_TO_BODY_18.items():
        source = natural_keypoints[blaze_index]
        body_18[body_index] = {
            "x":          source["x"],
            "y":          source["y"],
            "visibility": source["visibility"],
        }

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
    """Render a BlazePose-33 pose on a black canvas."""
    return draw_skeleton(keypoints, _BLAZEPOSE_33_LIMBS, width, height, limb_thickness=limb_thickness, joint_radius=joint_radius)
