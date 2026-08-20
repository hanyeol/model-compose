"""Unit tests for InsightfaceFaceTrackingTaskAction._cluster_faces().

Uses synthetic embeddings and bounding boxes so tests run without insightface /
onnxruntime. Focuses on the matcher's behavior — the surrounding I/O
(_track / _track_batch / _collect_tracks / model.get) is intentionally not exercised here.

Regression cases target four known matcher hazards:
  - Order-independent assignment: detection order must not decide which cluster
    a face joins.
  - Spatial tie-breaking: when two clusters score near-identically on embedding
    similarity, the one whose last bounding box overlaps the incoming face
    should win.
  - Stale cluster expiry: a cluster that hasn't been seen for many frames must
    not keep contaminating tie-breaks with its ancient last_bbox.
  - Deterministic ordering for true ties: with identical similarity AND
    identical overlap, the sort must not depend on incidental key ordering.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pytest

from mindor.core.component.services.model.tasks.face_tracking.custom.insightface import (
    InsightfaceFaceTrackingTaskAction,
)


def _action() -> InsightfaceFaceTrackingTaskAction:
    # Skip __init__: it requires a live FaceAnalysis handle we don't need here.
    return InsightfaceFaceTrackingTaskAction.__new__(InsightfaceFaceTrackingTaskAction)


def _unit_embedding(dim: int, index: int) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    v[index] = 1.0
    return v


def _blend(a: np.ndarray, b: np.ndarray, ratio: float) -> np.ndarray:
    v = (1.0 - ratio) * a + ratio * b
    return v / (np.linalg.norm(v) + 1e-12)


def _face(embedding: np.ndarray, bbox: Tuple[int, int, int, int], score: float = 0.9) -> Dict[str, Any]:
    x, y, w, h = bbox
    return {
        "embedding":    embedding,
        "bounding_box": (x, y, x + w, y + h),
        "score":        score,
    }


FRAME_RATE = 2.0


def _default_params(**overrides) -> Dict[str, Any]:
    base = {
        "similarity_threshold":     0.4,
        "min_face_size":            0,
        "max_face_count_per_frame": 0,
        "merge_gap":                10.0,   # loose so a single segment covers a burst
        "bounding_box_padding":     0.0,
        "max_track_distance":       0.0,
        "return_track_image":       False,
        "return_frame_image":       False,
        "return_metadata":          False,
    }
    base.update(overrides)
    return base


def _fresh_state() -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    return {"centroids": [], "counts": []}, {}


class TestOrderIndependentAssignment:
    """When two faces are strong matches for two different existing clusters,
    swapping the input order must not change the final assignment."""

    def test_swapped_detection_order_yields_same_assignment(self):
        action = _action()
        params = _default_params()

        e_alice = _unit_embedding(4, 0)
        e_bob   = _unit_embedding(4, 1)

        # Seed one frame that establishes two clusters with distinct identities.
        centroids_state, cluster_tracks = _fresh_state()
        action._cluster_faces(
            [_face(e_alice, (0, 0, 40, 40)), _face(e_bob, (200, 0, 40, 40))],
            timestamp=0.0,
            frame_rate=FRAME_RATE,
            centroids_state=centroids_state,
            cluster_tracks=cluster_tracks,
            params=params,
        )
        assert len(centroids_state["centroids"]) == 2  # sanity check

        # Second frame in "natural" order.
        state_a, tracks_a = {"centroids": [c.copy() for c in centroids_state["centroids"]],
                             "counts": list(centroids_state["counts"])}, \
                            {k: {"segments": list(v["segments"]),
                                 "current":  dict(v["current"]) if v["current"] else None,
                                 "last_bbox": tuple(v["last_bbox"]) if v["last_bbox"] else None}
                             for k, v in cluster_tracks.items()}
        action._cluster_faces(
            [_face(e_alice, (0, 0, 40, 40)), _face(e_bob, (200, 0, 40, 40))],
            timestamp=1.0, frame_rate=FRAME_RATE, centroids_state=state_a, cluster_tracks=tracks_a, params=params,
        )

        # Second frame with the detection order swapped.
        state_b, tracks_b = {"centroids": [c.copy() for c in centroids_state["centroids"]],
                             "counts": list(centroids_state["counts"])}, \
                            {k: {"segments": list(v["segments"]),
                                 "current":  dict(v["current"]) if v["current"] else None,
                                 "last_bbox": tuple(v["last_bbox"]) if v["last_bbox"] else None}
                             for k, v in cluster_tracks.items()}
        action._cluster_faces(
            [_face(e_bob, (200, 0, 40, 40)), _face(e_alice, (0, 0, 40, 40))],
            timestamp=1.0, frame_rate=FRAME_RATE, centroids_state=state_b, cluster_tracks=tracks_b, params=params,
        )

        # No new clusters should have been spawned in either order.
        assert len(state_a["centroids"]) == 2
        assert len(state_b["centroids"]) == 2
        assert state_a["counts"] == state_b["counts"] == [2, 2]


class TestSpatialTieBreak:
    """When embedding similarities are close (within tie-margin), the face
    that spatially overlaps a cluster's last bbox should win it."""

    def test_close_similarities_defer_to_overlap(self):
        action = _action()
        params = _default_params()

        base_a = _unit_embedding(4, 0)
        base_b = _unit_embedding(4, 1)

        # Seed two clusters at well-separated positions.
        centroids_state, cluster_tracks = _fresh_state()
        action._cluster_faces(
            [_face(base_a, (0, 0, 40, 40)), _face(base_b, (400, 0, 40, 40))],
            timestamp=0.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Craft a new detection that is spatially glued to cluster 0's position
        # but embedding-wise slightly closer to cluster 1 (0.0007 similarity gap
        # — well under a 0.05 tie margin).
        near_a = _blend(base_a, base_b, ratio=0.500)  # ~equidistant
        # Nudge just barely toward B so raw similarity to B is fractionally higher.
        nudged = near_a + 0.001 * base_b
        nudged = nudged / (np.linalg.norm(nudged) + 1e-12)

        sim_to_a = float(np.dot(nudged, centroids_state["centroids"][0]))
        sim_to_b = float(np.dot(nudged, centroids_state["centroids"][1]))
        assert sim_to_b > sim_to_a                        # B wins on raw similarity
        assert abs(sim_to_b - sim_to_a) < 0.05            # ...but only marginally

        action._cluster_faces(
            [_face(nudged, (2, 2, 40, 40))],              # overlaps cluster 0's box
            timestamp=1.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Expected: cluster 0 wins because spatial overlap breaks the near-tie.
        assert centroids_state["counts"] == [2, 1]

    def test_near_tie_across_bucket_boundary_still_defers_to_overlap(self):
        """A quantized tie-break groups similarities into buckets and would miss
        a near-tie whose two similarities happen to straddle a bucket boundary
        (e.g. 0.7499 vs 0.7501). A smooth blend that always adds a small
        overlap-weighted offset avoids that discontinuity."""
        action = _action()
        params = _default_params()

        base_a = _unit_embedding(4, 0)
        base_b = _unit_embedding(4, 1)

        centroids_state, cluster_tracks = _fresh_state()
        action._cluster_faces(
            [_face(base_a, (0, 0, 40, 40)), _face(base_b, (400, 0, 40, 40))],
            timestamp=0.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Craft an embedding whose similarity to the two centroids straddles a
        # 0.05 bucket boundary while keeping the raw gap tiny. base_a and base_b
        # are orthogonal unit vectors, so an embedding with components
        # (sa, sb, sqrt(1 - sa^2 - sb^2), 0) has cos-similarity exactly sa to
        # centroid 0 and sb to centroid 1.
        sa, sb = 0.6999, 0.7001
        rem = 1.0 - sa * sa - sb * sb
        assert rem > 0, "chosen similarities are not simultaneously reachable"
        target = np.array([sa, sb, np.sqrt(rem), 0.0], dtype=np.float32)
        assert int(sa / 0.05) != int(sb / 0.05), "similarities do not straddle a bucket boundary"

        action._cluster_faces(
            [_face(target, (2, 2, 40, 40))],  # overlaps cluster 0
            timestamp=1.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Cluster 0 must still win: the similarity gap is < 0.001, well below
        # any reasonable tie-margin, and the face is glued to cluster 0's bbox.
        assert centroids_state["counts"] == [2, 1]


class TestStaleClusterExpiry:
    """A cluster last seen many frames ago should not keep influencing spatial
    tie-breaks with its stale last_bbox."""

    def test_long_absent_cluster_last_bbox_does_not_break_ties(self):
        action = _action()
        params = _default_params()

        base_a = _unit_embedding(4, 0)
        base_b = _unit_embedding(4, 1)

        # Seed two clusters at well-separated positions at t=0.
        centroids_state, cluster_tracks = _fresh_state()
        action._cluster_faces(
            [_face(base_a, (0, 0, 40, 40)), _face(base_b, (400, 0, 40, 40))],
            timestamp=0.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Cluster 1 stays active up to t=30 — we keep seeing it as it drifts.
        step = 0.5
        for i in range(1, 61):
            t = i * step
            x = 400 + int(i / 6)
            action._cluster_faces(
                [_face(base_b, (x, 0, 40, 40))],
                timestamp=t, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
            )

        # Cluster 0 has been silent since t=0. Its last_bbox is still (0, 0, 40, 40)
        # — 30 seconds stale. Now a face arrives at t=31 spatially glued to
        # cluster 1's active position, embedding-wise a near-tie between the
        # two. Without expiry, cluster 0's ancient bbox could tie the overlap
        # score with cluster 1's fresh bbox (both at 0 overlap for e.g. a
        # coincidentally-placed detection); with expiry, only cluster 1's
        # fresh bbox counts, and the moving cluster wins its own detection.
        near_tie = _blend(base_a, base_b, ratio=0.500)
        nudged   = near_tie + 0.001 * base_b
        nudged   = nudged / (np.linalg.norm(nudged) + 1e-12)

        x1, y1, x2, y2 = cluster_tracks[1]["last_bbox"]
        action._cluster_faces(
            [_face(nudged, (x1, y1, x2 - x1, y2 - y1))],
            timestamp=31.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )

        # Expected: cluster 1 wins because its fresh overlap (~1.0) beats
        # cluster 0's stale overlap (forced to 0 by expiry).
        assert centroids_state["counts"][1] == 62  # 1 seed + 60 drift + 1 new
        assert centroids_state["counts"][0] == 1   # untouched


class TestDeterministicSortOrder:
    """When (similarity, overlap) are exactly equal for multiple pairs, the
    assignment must not depend on incidental key ordering (face_index /
    cluster_id being sorted in reverse)."""

    def test_identical_scores_do_not_bias_toward_later_indices(self):
        action = _action()
        params = _default_params()

        e_alice = _unit_embedding(4, 0)

        # Seed two clusters with the SAME centroid so any face matches both
        # equally on similarity, and neither has a last_bbox overlap advantage
        # for a face detected far from both.
        centroids_state, cluster_tracks = _fresh_state()
        action._cluster_faces(
            [_face(e_alice, (0, 0, 10, 10))],
            timestamp=0.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )
        # Force a second identical cluster by hand.
        centroids_state["centroids"].append(centroids_state["centroids"][0].copy())
        centroids_state["counts"].append(1)
        cluster_tracks[1] = {"segments": [], "current": None, "last_bbox": (500, 500, 510, 510)}

        # A single new face equidistant from both clusters. Overlap with either
        # last_bbox is 0. The winning cluster must be the lower-indexed one
        # (stable / deterministic), not whichever wins from reverse-tuple sort.
        action._cluster_faces(
            [_face(e_alice, (1000, 1000, 10, 10))],
            timestamp=1.0, frame_rate=FRAME_RATE, centroids_state=centroids_state, cluster_tracks=cluster_tracks, params=params,
        )
        assert centroids_state["counts"] == [2, 1]
