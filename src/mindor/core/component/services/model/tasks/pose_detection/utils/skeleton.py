from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
from PIL import Image as PILImage

# Rendering-time keypoint: (x, y) in pixel coords, or None for a missing joint.
BodyKeypoint = Optional[Tuple[float, float]]

def _keypoints_to_points(keypoints: List[Dict[str, Any]]) -> List[BodyKeypoint]:
    points: List[BodyKeypoint] = []

    for keypoint in keypoints:
        visibility = float(keypoint.get("visibility", 1.0))
        if visibility <= 0.0:
            points.append(None)
            continue
        points.append((float(keypoint["x"]), float(keypoint["y"])))

    return points

def _hsv_palette(count: int) -> List[Tuple[int, int, int]]:
    import colorsys

    palette: List[Tuple[int, int, int]] = []

    for index in range(count):
        r, g, b = colorsys.hsv_to_rgb(index / max(count, 1), 1.0, 1.0)
        palette.append((int(r * 255), int(g * 255), int(b * 255)))

    return palette

def draw_skeleton(
    keypoints: List[Dict[str, Any]],
    limbs: List[Tuple[int, int]],
    width: int,
    height: int,
    limb_colors: Optional[List[Tuple[int, int, int]]] = None,
    joint_colors: Optional[List[Tuple[int, int, int]]] = None,
    limb_thickness: int = 4,
    joint_radius: int = 4,
) -> PILImage.Image:
    """Draw a pose on a black canvas.

    `limb_colors` / `joint_colors` default to HSV-spaced palettes sized to the
    given limbs / keypoints so different limbs stay visually distinguishable.
    """
    from PIL import ImageDraw

    points = _keypoints_to_points(keypoints)
    limb_colors = limb_colors if limb_colors is not None else _hsv_palette(len(limbs))
    joint_colors = joint_colors if joint_colors is not None else _hsv_palette(len(points))

    image = PILImage.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    for index, (a, b) in enumerate(limbs):
        if a >= len(points) or b >= len(points):
            continue
        pa, pb = points[a], points[b]
        if pa is None or pb is None:
            continue
        draw.line([pa, pb], fill=limb_colors[index % len(limb_colors)], width=limb_thickness)

    for index, point in enumerate(points):
        if point is None:
            continue
        x, y = point
        r = joint_radius
        draw.ellipse((x - r, y - r, x + r, y + r), fill=joint_colors[index % len(joint_colors)])

    return image
