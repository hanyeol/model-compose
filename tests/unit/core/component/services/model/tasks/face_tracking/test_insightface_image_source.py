"""Unit tests for how `image_source` propagates through `_add_face_to_track`.

The flag split (`return_track_image` vs `return_detection_image`) is a memory
fix: on long non-streaming runs, holding a padded BGR sub-crop on every
tracked face in `tracked_frames` pins gigabytes of pixels for the whole run.
These tests pin the invariant that lets the fix work — best_face always
keeps the sub-crop (segment crop is lazy, 1 per segment), the returned face
only keeps it when the caller asked for per-detection crops.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)


FRAME_PERIOD = 0.5


def _frame(height: int = 200, width: int = 300) -> np.ndarray:
    return np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)


def _face(bbox=(100, 80, 150, 130), score: float = 0.9) -> Dict[str, Any]:
    return {
        "embedding":    np.zeros(3),
        "bounding_box": bbox,
        "score":        score,
    }


def _extractor(frame: np.ndarray):
    def extract(bounding_box: Tuple[int, int, int, int]):
        return InsightfaceFaceTrackingTaskAction._extract_face_region(frame, bounding_box, 0.0)
    return extract


def _add(action, cluster_tracks, face, stash: bool, extractor):
    return action._add_face_to_track(
        cluster_tracks,
        cluster_id=0,
        timestamp=0.0,
        face=face,
        merge_gap=10.0,
        frame_period=FRAME_PERIOD,
        bounding_box_padding=0.0,
        bounding_box_smoothing=None,
        extract_image_source=extractor,
        stash_image_source=stash,
    )


def test_returned_face_drops_image_source_when_stash_disabled() -> None:
    frame = _frame()
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    cluster_tracks: Dict[int, Dict[str, Any]] = {}

    returned, _ = _add(action, cluster_tracks, _face(), stash=False, extractor=_extractor(frame))

    assert "image_source" not in returned
    assert "image_source_origin" not in returned


def test_returned_face_keeps_image_source_when_stash_enabled() -> None:
    frame = _frame()
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)
    cluster_tracks: Dict[int, Dict[str, Any]] = {}

    returned, _ = _add(action, cluster_tracks, _face(), stash=True, extractor=_extractor(frame))

    assert returned.get("image_source") is not None
    assert returned.get("image_source_origin") is not None


def test_best_face_carries_pil_image_regardless_of_stash() -> None:
    # best_face materializes the PIL `image` from image_source at segment
    # time, so it must land on best_face whether or not per-frame crops are
    # retained — otherwise segment track images disappear in the memory-saving
    # path, which is the whole point of return_track_image.
    frame = _frame()
    action = InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)

    for stash in (False, True):
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        _add(action, cluster_tracks, _face(), stash=stash, extractor=_extractor(frame))

        best_face = cluster_tracks[0]["current"]["best_face"]
        assert best_face.get("image") is not None, f"stash={stash}"
        # best_face only keeps the materialized PIL — the raw sub-crop and
        # its origin are dropped during materialization.
        assert "image_source" not in best_face
        assert "image_source_origin" not in best_face
