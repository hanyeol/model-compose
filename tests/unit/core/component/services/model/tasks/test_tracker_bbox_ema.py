"""EMA bbox smoothing must keep sub-pixel state across frames.

If the smoothed box is quantized to int every step, slow motion (<0.5 px per
frame after weighting) rounds to zero and the box stalls behind the target by
a weight-dependent offset. Keeping the state as float lets the smoothed box
converge to the true position with a bounded lag of ``smoothing / (1 - smoothing)``
pixels per unit velocity — e.g. 9 px at weight 0.9 for 1 px/frame motion.
"""

from __future__ import annotations

from typing import Callable, Tuple

import pytest

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)
from mindor.core.component.services.model.tasks.object_tracking.custom.yolo import (
    YoloObjectTrackingTaskAction,
)
from mindor.core.component.services.model.tasks.pose_tracking.custom.yolo import (
    YoloPoseTrackingTaskAction,
)


Blender = Callable[
    [Tuple[float, float, float, float], Tuple[float, float, float, float], float],
    Tuple[float, float, float, float],
]


@pytest.mark.parametrize(
    "blend",
    [
        YoloObjectTrackingTaskAction._blend_bounding_box,
        YoloPoseTrackingTaskAction._blend_bounding_box,
        InsightfaceFaceTrackingTaskAction._blend_bounding_box,
    ],
    ids=["object", "pose", "face"],
)
def test_bbox_ema_converges_under_slow_motion(blend: Blender) -> None:
    smoothing = 0.9
    state: Tuple[float, float, float, float] = (0.0, 0.0, 10.0, 10.0)

    # 300 frames at 1 px/frame — far past the ~90-frame settling time of a
    # weight-0.9 EMA. Steady-state lag for `smoothing / (1 - smoothing)` is
    # 9 px, so the smoothed box must stay within 10 px of truth.
    for frame_index in range(1, 301):
        true_box = (float(frame_index), 0.0, 10.0 + frame_index, 10.0)
        state = blend(state, true_box, smoothing)

    final_true = (300.0, 0.0, 310.0, 10.0)
    for i in range(4):
        assert abs(state[i] - final_true[i]) < 10.0, (
            f"EMA stalled at component {i}: state={state} truth={final_true}"
        )

    # And it must actually be tracking, not frozen. With int-quantized state
    # at weight 0.9 the x1 would plateau around 5 px above its initial value.
    assert state[0] > 100.0
