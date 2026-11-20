from __future__ import annotations

from typing import Any, Dict, List, Optional
from PIL import Image as PILImage

def convex_hull_mask(
    keypoints: List[Dict[str, Any]],
    width: int,
    height: int,
) -> Optional[PILImage.Image]:
    """Build an 8-bit grayscale mask from the convex hull of 21 hand keypoints.

    Approximates "hand region" when a true instance segmentation is needed
    downstream (ControlNet / inpaint masks). Not a real silhouette — fingers
    and finger gaps collapse into one convex polygon — but a useful cheap
    stand-in for the Hand Landmarker, which emits no segmentation output.
    """
    if not keypoints:
        return None

    points = [ (int(keypoint["x"]), int(keypoint["y"])) for keypoint in keypoints ]
    hull = _convex_hull(points)

    if len(hull) < 3:
        return None

    mask = PILImage.new("L", (width, height), color=0)

    from PIL import ImageDraw

    ImageDraw.Draw(mask).polygon(hull, fill=255)

    return mask

def _convex_hull(points: List[tuple]) -> List[tuple]:
    # Andrew's monotone-chain O(n log n). n = 21 so sort cost is negligible,
    # but keep the real algorithm — a hand's convex hull may hit all 5 finger
    # tips plus wrist, well above the 3-point degenerate case.
    points = sorted(set(points))
    if len(points) < 3:
        return points

    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[tuple] = []
    for point in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: List[tuple] = []
    for point in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]
