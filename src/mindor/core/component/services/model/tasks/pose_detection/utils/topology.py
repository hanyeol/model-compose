from __future__ import annotations

from typing import Any, Dict, List, Optional


def keypoints_to_bounding_box(keypoints: List[Dict[str, Any]]) -> Optional[List[int]]:
    """Compute an axis-aligned bounding box from visible keypoints.

    Returns `[x, y, width, height]` in pixel coords, or `None` if no keypoint is
    visible (visibility > 0). A joint is skipped when its visibility is <= 0.
    """
    xs: List[int] = []
    ys: List[int] = []

    for keypoint in keypoints:
        if float(keypoint.get("visibility", 1.0)) <= 0.0:
            continue
        xs.append(int(keypoint["x"]))
        ys.append(int(keypoint["y"]))

    if not xs:
        return None

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    return [ x_min, y_min, x_max - x_min, y_max - y_min ]
