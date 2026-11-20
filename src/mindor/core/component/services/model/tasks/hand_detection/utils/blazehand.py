from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image as PILImage
from ...pose_detection.utils.skeleton import draw_skeleton

# MediaPipe Hand Landmarker 21-keypoint topology.
# https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker
# 0: wrist, 1-4: thumb (CMC → TIP), 5-8: index (MCP → TIP),
# 9-12: middle, 13-16: ring, 17-20: pinky.

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

def render_skeleton(
    keypoints: List[Dict[str, Any]],
    width: int,
    height: int,
    limb_thickness: int = 4,
    joint_radius: int = 4,
    background: Optional[Union[Tuple[int, int, int], Tuple[int, int, int, int]]] = None,
) -> PILImage.Image:
    """Render a MediaPipe-21 hand. See `draw_skeleton` for `background` semantics."""
    return draw_skeleton(
        keypoints,
        _HAND_21_LIMBS,
        width,
        height,
        limb_thickness=limb_thickness,
        joint_radius=joint_radius,
        background=background,
    )
