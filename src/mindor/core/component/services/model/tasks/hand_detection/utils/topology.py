from __future__ import annotations

from typing import Any, Dict, List, Optional

def keypoints_to_bounding_box(keypoints: List[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    """Compute an axis-aligned bounding box from hand keypoints.

    Returns `{"x", "y", "width", "height"}` in pixel coords, or `None` when
    the keypoint list is empty. Hand Landmarker emits all 21 points even
    under occlusion, so every entry contributes to the box.
    """
    if not keypoints:
        return None

    xs = [ int(keypoint["x"]) for keypoint in keypoints ]
    ys = [ int(keypoint["y"]) for keypoint in keypoints ]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    return { "x": x_min, "y": y_min, "width": x_max - x_min, "height": y_max - y_min }
