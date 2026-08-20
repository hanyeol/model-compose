from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union, List
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
    background: Optional[Union[Tuple[int, int, int], Tuple[int, int, int, int]]] = None,
) -> PILImage.Image:
    """Draw a pose skeleton.

    `limb_colors` / `joint_colors` default to HSV-spaced palettes sized to the
    given limbs / keypoints so different limbs stay visually distinguishable.

    `background` controls the canvas fill and output mode:
    - `None` (default) — transparent RGBA canvas, right for alpha-compositing
      the skeleton onto a source frame.
    - `(r, g, b)` or `(r, g, b, 255)` — solid RGB canvas; pass `(0, 0, 0)`
      for the black-canvas variant that ControlNet OpenPose models expect
      as their conditioning input.
    - `(r, g, b, a)` with `a < 255` — RGBA canvas pre-filled with that
      semi-transparent color, so alpha-compositing it onto a source frame
      tints the frame instead of fully replacing it.
    """
    from PIL import ImageDraw

    points = _keypoints_to_points(keypoints)
    limb_colors = limb_colors if limb_colors is not None else _hsv_palette(len(limbs))
    joint_colors = joint_colors if joint_colors is not None else _hsv_palette(len(points))

    if background is None:
        image = PILImage.new("RGBA", (width, height), color=(0, 0, 0, 0))
    elif len(background) == 4 and background[3] < 255:
        image = PILImage.new("RGBA", (width, height), color=background)
    else:
        image = PILImage.new("RGB", (width, height), color=background[:3])

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
