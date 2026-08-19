from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceTrackingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import FaceTrackingTaskAction, FaceEmbedding
from ....base import ComponentActionContext, ModelTaskService
from PIL import Image as PILImage
import os, shutil

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis
    from insightface.app.common import Face
    import numpy as np

class InsightfaceFaceTrackingTaskAction(FaceTrackingTaskAction):
    config: InsightfaceFaceTrackingModelActionConfig

    def __init__(self, config: InsightfaceFaceTrackingModelActionConfig, model: FaceAnalysis, device_id: int):
        super().__init__(config)

        self.model: FaceAnalysis = model
        self.device_id: int = device_id
        self._prepared: bool = False

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_threshold = await context.render_scalar(self.config.params.detection_threshold, float)
        detection_size      = await context.render_variable(self.config.params.detection_size)
        return_gender_age   = await context.render_scalar(self.config.return_gender_age, bool)

        if not 0.0 <= detection_threshold <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {detection_threshold}")

        if not isinstance(detection_size, (list, tuple)) or len(detection_size) != 2:
            raise ValueError(f"'detection_size' must be a (width, height) pair, got {detection_size!r}")

        params["detection_threshold"] = detection_threshold
        params["detection_size"]      = (int(detection_size[0]), int(detection_size[1]))
        params["return_gender_age"]   = return_gender_age

        return params

    async def _track_batch(
        self,
        frames_batch: List[ImageArrayValue],
        offsets_batch: List[float],
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]] = []

        for frames, offset in zip(frames_batch, offsets_batch):
            results.append(await self._track(
                frames,
                float(offset or 0.0),
                frame_rate,
                streaming,
                params,
                cancellation_token,
            ))

        return results

    async def _track(
        self,
        frames: ImageArrayValue,
        offset: float,
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]:
        """Track faces across one video's frames. Streaming mode returns an
        async iterator of per-frame/per-segment/done events; non-streaming
        mode runs to completion and returns the assembled result dict."""
        if streaming:
            return self._stream_tracks(frames, offset, frame_rate, params, cancellation_token)

        return await self._collect_tracks(frames, offset, frame_rate, params, cancellation_token)

    async def _collect_tracks(
        self,
        frames: ImageArrayValue,
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        centroids_state: Dict[str, Any] = { "centroids": [], "counts": [] }
        tracked_frames: List[Dict[str, Any]] = []
        frame_count = 0

        def _track_frame(image: PILImage.Image, timestamp: float) -> Dict[str, Any]:
            faces = self._detect_frame(image, params)
            tracked_faces, _ = self._cluster_faces(faces, timestamp, frame_rate, centroids_state, cluster_tracks, params)

            tracked_frame: Dict[str, Any] = {
                "number":        frame_count + 1,
                "timestamp":     timestamp,
                "tracked_faces": tracked_faces,
            }

            if params["return_frame_image"]:
                tracked_frame["image"] = image

            return tracked_frame

        async for image in frames:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            timestamp = offset + frame_count / frame_rate
            tracked_frame = await self._run_in_executor(_track_frame, image, timestamp)
            frame_count += 1

            if params["return_frames"]:
                tracked_frames.append(tracked_frame)

        if params["return_frames"]:
            self._interpolate_missing_faces(tracked_frames, frame_rate, params["merge_gap"] or 0.0, params["similarity_threshold"] or 0.0)

        # Flush any still-open `current` segment so every segment is
        # visible to the result builder.
        for track in cluster_tracks.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None

        logging.debug(f"InsightFace face tracking: {frame_count} frames at offset {offset:.3f}s")

        return await self._run_in_executor(self._build_tracking_result, cluster_tracks, centroids_state, frame_count, tracked_frames, params)

    async def _stream_tracks(
        self,
        frames: ImageArrayValue,
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        centroids_state: Dict[str, Any] = { "centroids": [], "counts": [] }
        merge_gap = params["merge_gap"] or 0.0
        similarity_threshold = params["similarity_threshold"] or 0.0
        frame_period = 1.0 / frame_rate
        frame_count = 0

        # Frame chunk emission is delayed by `merge_gap` so that a detection in
        # a later frame can back-fill missing detections in the frames between
        # (linear bounding-box interpolation per cluster). Segment/track/idle
        # chunks still flow at their original moment — consumers that only care
        # about frames (e.g. face-mosaic) see the interpolated stream, and
        # consumers that mix chunk types accept that segment/track chunks may
        # precede their same-timestamp frame chunk.
        pending_frames: List[Dict[str, Any]] = []
        prev_detection: Dict[int, Tuple[float, Dict[str, int], Dict[str, Any]]] = {}

        def _track_frame(image: PILImage.Image, timestamp: float) -> Dict[str, Any]:
            faces = self._detect_frame(image, params)
            tracked_faces, tracked_segments = self._cluster_faces(faces, timestamp, frame_rate, centroids_state, cluster_tracks, params)

            tracked_frame: Dict[str, Any] = {
                "number":            frame_count + 1,
                "timestamp":         timestamp,
                "tracked_faces":     tracked_faces,
                "tracked_segments":  tracked_segments,
                "interpolated_faces": [],
            }

            if params["return_frame_image"]:
                tracked_frame["image"] = image

            return tracked_frame

        def _flush_ready_frames(force: bool) -> List[Dict[str, Any]]:
            ready: List[Dict[str, Any]] = []

            if not pending_frames:
                return ready

            cutoff = pending_frames[-1]["timestamp"] - merge_gap - frame_period - 1e-6

            while pending_frames:
                head = pending_frames[0]

                if not force and head["timestamp"] > cutoff:
                    break

                pending_frames.pop(0)
                head["tracked_faces"] = head["tracked_faces"] + head["interpolated_faces"]
                del head["interpolated_faces"]
                ready.append(head)

            return ready

        async for image in frames:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            timestamp = offset + frame_count / frame_rate
            tracked_frame = await self._run_in_executor(_track_frame, image, timestamp)
            frame_count += 1

            # Fill gaps for every cluster that got a fresh detection this frame
            # and had a prior detection within `merge_gap`. The prior/current
            # pair anchors the linear interpolation across the pending frames
            # in between.
            if params["return_frames"]:
                for face, cluster_id in tracked_frame["tracked_faces"]:
                    prev = prev_detection.get(cluster_id)
                    if prev is not None:
                        prev_timestamp, prev_bbox, prev_face = prev
                        if timestamp - prev_timestamp <= merge_gap + frame_period + 1e-6:
                            self._interpolate_between_faces(
                                pending_frames,
                                0,
                                len(pending_frames),
                                cluster_id,
                                prev_timestamp,
                                prev_bbox,
                                prev_face,
                                timestamp,
                                face["bounding_box"],
                                face,
                                similarity_threshold
                            )
                    prev_detection[cluster_id] = (timestamp, face["bounding_box"], face)

                pending_frames.append(tracked_frame)

                for ready_frame in _flush_ready_frames(force=False):
                    yield self._build_frame_chunk(ready_frame, params)

            if params["return_tracks"]:
                for cluster_id, segment in tracked_frame["tracked_segments"]:
                    yield self._build_segment_chunk(cluster_id, segment, params)

                # Any cluster we didn't touch this frame whose gap now exceeds
                # `merge_gap` is idle: seal its still-open segment and emit a
                # track chunk. The `emitted` flag keeps us from re-emitting a
                # long-idle cluster every frame — a fresh detection resets it
                # in `_add_face_to_track` so the next idle period fires again.
                for cluster_id, segment_chunk, track_chunk in self._sweep_idle_tracks(cluster_tracks, centroids_state, timestamp, frame_period, merge_gap, params):
                    if segment_chunk is not None:
                        yield segment_chunk
                    yield track_chunk

        if params["return_frames"]:
            for ready_frame in _flush_ready_frames(force=True):
                yield self._build_frame_chunk(ready_frame, params)

        # Final flush: seal every still-open segment and emit any track that
        # hasn't been announced yet (including clusters that never went idle).
        if params["return_tracks"]:
            for cluster_id, segment_chunk, track_chunk in self._flush_remaining_tracks(cluster_tracks, centroids_state, params):
                if segment_chunk is not None:
                    yield segment_chunk
                yield track_chunk
        else:
            for track in cluster_tracks.values():
                if track["current"] is not None:
                    track["segments"].append(track["current"])
                    track["current"] = None

        logging.debug(f"InsightFace face tracking (streaming): {frame_count} frames at offset {offset:.3f}s")

        if params["return_metadata"]:
            yield { "type": "metadata", "frame_count": frame_count }

    def _detect_frame(self, image: PILImage.Image, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        import numpy as np
        import cv2

        if not self._prepared:
            self.model.prepare(ctx_id=self.device_id, det_size=params["detection_size"], det_thresh=params["detection_threshold"])
            self._prepared = True

        image_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        detections = self.model.get(image_cv)

        return self._serialize_faces(detections, image_cv, params["return_track_image"], params["return_gender_age"])

    def _cluster_faces(
        self,
        faces: List[Dict[str, Any]],
        timestamp: float,
        frame_rate: float,
        centroids_state: Dict[str, Any],
        cluster_tracks: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[List[Tuple[Dict[str, Any], int]], List[Tuple[int, Dict[str, Any]]]]:
        import numpy as np

        similarity_threshold      = params["similarity_threshold"] or 0.0
        min_face_size             = params["min_face_size"] or 0
        max_face_count_per_frame  = params["max_face_count_per_frame"] or 0
        merge_gap                 = params["merge_gap"] or 0.0
        frame_period              = 1.0 / frame_rate
        bounding_box_padding      = params["bounding_box_padding"] or 0.0
        max_reassignment_distance = params["max_reassignment_distance"] or 0.0

        candidates = self._filter_faces(faces, min_face_size, max_face_count_per_frame)
        centroids: List[np.ndarray] = centroids_state["centroids"]
        counts: List[int] = centroids_state["counts"]

        # Score every (face, cluster) pair up front, then bind them in descending
        # order so a strong match wins its cluster regardless of detection order.
        # The ranking key blends embedding similarity with a small overlap term
        # (`tie_margin * overlap`). Since overlap ∈ [0, 1], the term can only
        # flip the order of two pairs whose raw similarity gap is smaller than
        # `tie_margin` — i.e. a near-tie defers to spatial overlap with no
        # bucket-boundary discontinuities. A cluster's last_bbox is ignored once
        # it goes stale (`stale_after` seconds without a detection) so long-
        # absent clusters can't win tie-breaks with an ancient position.
        tie_margin: float = 0.05
        stale_after: float = 2.0

        embeddings: List[np.ndarray] = []

        for face in candidates:
            embedding = face["embedding"]
            embeddings.append(embedding / (np.linalg.norm(embedding) + 1e-12))

        face_cluster_scores: List[Tuple[float, int, int]] = []

        for face_index, embedding in enumerate(embeddings):
            face_bbox = candidates[face_index]["bounding_box"]
            for cluster_id, centroid in enumerate(centroids):
                similarity = float(np.dot(embedding, centroid))

                if similarity < similarity_threshold:
                    continue

                track = cluster_tracks.get(cluster_id)
                last_bbox = track.get("last_bbox") if track else None
                last_seen = track.get("last_seen") if track else None
                is_stale = last_seen is None or (timestamp - last_seen) > stale_after

                # A live cluster whose last detection is farther than `max_reassignment_distance`
                # face-sizes away can't be the same person — reject the pair outright so the
                # face falls through to a new cluster instead of hijacking this one.
                if not is_stale and last_bbox is not None and max_reassignment_distance > 0.0:
                    if self._bbox_center_distance(face_bbox, last_bbox) > max_reassignment_distance * max(face_bbox["width"], face_bbox["height"]):
                        continue

                overlap = 0.0 if is_stale or last_bbox is None else self._bbox_overlap(face_bbox, last_bbox)
                face_cluster_scores.append((similarity + tie_margin * overlap, face_index, cluster_id))

        # Sort by blended score, descending. Do NOT let face_index / cluster_id
        # influence the order on true ties — a plain reverse-tuple sort would
        # prefer higher indices, which is not a meaningful tie-break.
        face_cluster_scores.sort(key=lambda p: -p[0])

        face_cluster: Dict[int, int] = {}
        used_clusters: set = set()

        for _, face_index, cluster_id in face_cluster_scores:
            if face_index in face_cluster or cluster_id in used_clusters:
                continue

            face_cluster[face_index] = cluster_id
            used_clusters.add(cluster_id)

        tracked_faces: List[Tuple[Dict[str, Any], int]] = []
        tracked_segments: List[Tuple[int, Dict[str, Any]]] = []

        for face_index, face in enumerate(candidates):
            embedding = embeddings[face_index]
            cluster_id = face_cluster.get(face_index, -1)

            if cluster_id >= 0:
                count = counts[cluster_id]
                updated = (centroids[cluster_id] * count + embedding) / (count + 1)
                centroids[cluster_id] = updated / (np.linalg.norm(updated) + 1e-12)
                counts[cluster_id] += 1
            else:
                centroids.append(embedding.copy())
                counts.append(1)
                cluster_id = len(centroids) - 1

            tracked_segment = self._add_face_to_track(cluster_tracks, cluster_id, timestamp, face, merge_gap, frame_period, bounding_box_padding)

            if tracked_segment is not None:
                tracked_segments.append((cluster_id, tracked_segment))

            tracked_faces.append((face, cluster_id))

        return tracked_faces, tracked_segments

    def _add_face_to_track(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        cluster_id: int,
        timestamp: float,
        face: Dict[str, Any],
        merge_gap: float,
        frame_period: float,
        bounding_box_padding: float,
    ) -> Optional[Dict[str, Any]]:
        """Fold a new detection into its cluster's segment history. The
        cluster's `current` segment is extended if this frame is within one
        frame period plus `merge_gap` of the previous one; otherwise the
        current segment is sealed into `segments` and a fresh one starts. The
        frame-period baseline means `merge_gap` measures how long a person may
        go undetected before the segment is split, not how far apart two
        detections may be — consecutive frames always merge, so `merge_gap=0`
        does what a user naïvely expects. Only the highest-scoring frame's
        image is retained per segment, so memory scales with the number of
        segments rather than the number of frames.

        The face crop is materialized here (lazily) rather than up-front in
        `_serialize_faces`, so frames that never become a segment's best
        never pay the crop / PIL-conversion cost.

        Returns the segment that this detection just closed off, or None
        when the detection only extended the current segment. Streaming
        callers use the return value to emit segment events; batch callers
        can ignore it since `track["segments"]` accumulates the same data."""
        track = cluster_tracks.setdefault(cluster_id, { 
            "segments": [],
            "current": None,
            "last_bbox": None,
            "last_seen": None,
            "emitted": False
        })

        track["last_bbox"] = face["bounding_box"]
        track["last_seen"] = timestamp

        current: Optional[Dict[str, Any]] = track["current"]
        score = face["score"]

        # Absorb ULP-scale jitter: caller derives `timestamp` as `offset + n/rate`
        # while `frame_period` is `1/rate`, and the two paths can diverge by up
        # to ~1e-13 for long offsets. `merge_gap` is measured in seconds, so a
        # microsecond tolerance can't blur any user-meaningful behavior.
        if current is not None and timestamp - current["end"] <= frame_period + merge_gap + 1e-6:
            current["end"] = timestamp
            current["frame_count"] += 1

            if score > current["best_face"]["score"]:
                current["best_face"] = self._build_face_snapshot(face, bounding_box_padding)

            return None

        tracked_segment = current

        if tracked_segment is not None:
            track["segments"].append(tracked_segment)

        track["current"] = {
            "start":       timestamp,
            "end":         timestamp,
            "frame_count": 1,
            "best_face":   self._build_face_snapshot(face, bounding_box_padding),
        }

        track["emitted"] = False

        return tracked_segment

    def _sweep_idle_tracks(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        centroids_state: Dict[str, Any],
        timestamp: float,
        frame_period: float,
        merge_gap: float,
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Sweep clusters that have gone idle past `merge_gap` at `timestamp`.

        For each such cluster, seal any still-open `current` segment (returning
        a segment chunk to emit) and produce a track chunk with the running
        aggregates. Mutates track state: seals `current` into `segments`, sets
        `emitted=True` so the same idle stretch is not announced twice. A later
        detection on the same cluster resets `emitted` in `_add_face_to_track`,
        so re-emission on the next idle period is intentional."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"] or 1

        for cluster_id in sorted(cluster_tracks.keys()):
            track = cluster_tracks[cluster_id]
            last_seen = track.get("last_seen")

            if last_seen is None:
                continue

            if timestamp - last_seen <= frame_period + merge_gap + 1e-6:
                continue

            if track["current"] is None and track["emitted"]:
                continue

            segment_chunk: Optional[Dict[str, Any]] = None
            current = track["current"]

            if current is not None:
                track["segments"].append(current)
                track["current"] = None
                segment_chunk = self._build_segment_chunk(cluster_id, current, params)

            track_frame_count = sum(segment["frame_count"] for segment in track["segments"])

            if track_frame_count < min_frame_count:
                continue

            chunks.append((
                cluster_id,
                segment_chunk,
                self._build_track_chunk(cluster_id, track, centroids_state, params),
            ))

            track["emitted"] = True

        return chunks

    def _flush_remaining_tracks(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        centroids_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Emit a track chunk (and any still-open segment) for every cluster
        that hasn't been announced yet. Called once when the frame stream
        ends: at that point every remaining cluster is authoritative, so we
        skip the idle-timeout check and treat `emitted=True` as the only
        reason to omit a cluster."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"] or 1

        for cluster_id in sorted(cluster_tracks.keys()):
            track = cluster_tracks[cluster_id]

            if track["current"] is None and track["emitted"]:
                continue

            segment_chunk: Optional[Dict[str, Any]] = None
            current = track["current"]

            if current is not None:
                track["segments"].append(current)
                track["current"] = None
                segment_chunk = self._build_segment_chunk(cluster_id, current, params)

            track_frame_count = sum(segment["frame_count"] for segment in track["segments"])

            if track_frame_count < min_frame_count:
                continue

            chunks.append((
                cluster_id,
                segment_chunk,
                self._build_track_chunk(cluster_id, track, centroids_state, params),
            ))

            track["emitted"] = True

        return chunks

    def _interpolate_missing_faces(
        self,
        tracked_frames: List[Dict[str, Any]],
        frame_rate: float,
        merge_gap: float,
        similarity_threshold: float,
    ) -> None:
        """Walk every frame in chronological order, and for each cluster,
        interpolate bounding boxes between consecutive detections whose gap is
        within `merge_gap` + one frame period. Interpolated faces are merged
        into each frame's `tracked_faces` in place; `interpolated_faces` is stripped
        so downstream code sees a single unified list."""
        frame_period = 1.0 / frame_rate
        threshold = merge_gap + frame_period + 1e-6
        # Track each cluster's most recent detection's frame index too so we
        # can hand the interpolator a bounded [start, end) range instead of
        # re-scanning every frame per anchor pair — otherwise the cost is
        # O(anchor_pairs × total_frames) on long videos.
        prev_detection: Dict[int, Tuple[int, float, Dict[str, int], Dict[str, Any]]] = {}

        for frame in tracked_frames:
            frame.setdefault("interpolated_faces", [])

        for current_index, frame in enumerate(tracked_frames):
            timestamp = frame["timestamp"]
            for face, cluster_id in frame["tracked_faces"]:
                prev = prev_detection.get(cluster_id)
                if prev is not None:
                    prev_index, prev_timestamp, prev_bbox, prev_face = prev
                    if timestamp - prev_timestamp <= threshold:
                        self._interpolate_between_faces(
                            tracked_frames,
                            prev_index + 1,
                            current_index,
                            cluster_id,
                            prev_timestamp,
                            prev_bbox,
                            prev_face,
                            timestamp,
                            face["bounding_box"],
                            face,
                            similarity_threshold
                        )
                prev_detection[cluster_id] = (current_index, timestamp, face["bounding_box"], face)

        for frame in tracked_frames:
            frame["tracked_faces"] = frame["tracked_faces"] + frame["interpolated_faces"]
            del frame["interpolated_faces"]

    def _interpolate_between_faces(
        self,
        frames: List[Dict[str, Any]],
        start_index: int,
        end_index: int,
        cluster_id: int,
        prev_timestamp: float,
        prev_bbox: Dict[str, int],
        prev_face: Dict[str, Any],
        current_timestamp: float,
        current_bbox: Dict[str, int],
        current_face: Dict[str, Any],
        similarity_threshold: float,
    ) -> None:
        """Fill in a cluster's missing detections between two anchors by linear
        bounding-box interpolation. Frames whose timestamp lies strictly between
        `prev_timestamp` and `current_timestamp` and that have no detection (real or interpolated)
        for `cluster_id` receive a synthetic face. The interpolated bboxes are
        appended to `interpolated_faces` so callers can distinguish them from real
        detections and merge later.

        The two anchors' raw embeddings must agree above `similarity_threshold`;
        otherwise the cluster's centroid has drifted (or overlap-based tie-break
        put two different people into the same cluster) and interpolating would
        paint a ghost face gliding between two different identities."""
        import numpy as np

        span = current_timestamp - prev_timestamp

        if span <= 0:
            return

        prev_embedding = prev_face.get("embedding")
        current_embedding = current_face.get("embedding")

        if prev_embedding is not None and current_embedding is not None:
            prev_normalized = prev_embedding / (np.linalg.norm(prev_embedding) + 1e-12)
            current_normalized = current_embedding / (np.linalg.norm(current_embedding) + 1e-12)
            if float(np.dot(prev_normalized, current_normalized)) < similarity_threshold:
                return

        for index in range(start_index, end_index):
            frame = frames[index]
            frame_timestamp = frame["timestamp"]

            if frame_timestamp <= prev_timestamp or frame_timestamp >= current_timestamp:
                continue

            if any(cid == cluster_id for _, cid in frame["tracked_faces"]):
                continue

            if any(cid == cluster_id for _, cid in frame["interpolated_faces"]):
                continue

            ratio = (frame_timestamp - prev_timestamp) / span
            interpolated_bbox = {
                "x":      int(round(prev_bbox["x"]      + (current_bbox["x"]      - prev_bbox["x"]     ) * ratio)),
                "y":      int(round(prev_bbox["y"]      + (current_bbox["y"]      - prev_bbox["y"]     ) * ratio)),
                "width":  int(round(prev_bbox["width"]  + (current_bbox["width"]  - prev_bbox["width"] ) * ratio)),
                "height": int(round(prev_bbox["height"] + (current_bbox["height"] - prev_bbox["height"]) * ratio)),
            }
            frame["interpolated_faces"].append(({ **prev_face, "bounding_box": interpolated_bbox }, cluster_id))

    def _build_face_snapshot(self, face: Dict[str, Any], bounding_box_padding: float) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "bounding_box": face["bounding_box"],
            "score":        face["score"],
        }

        image_source = face.get("image_source")

        if image_source is not None:
            snapshot["image"] = self._crop_face_image(image_source, face["bounding_box"], bounding_box_padding)

        if "gender" in face:
            snapshot["gender"] = face["gender"]

        if "age" in face:
            snapshot["age"] = face["age"]

        return snapshot

    def _build_tracking_result(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        centroids_state: Dict[str, Any],
        frame_count: int,
        tracked_frames: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_metadata"]:
            result["frame_count"] = frame_count

        if params["return_tracks"]:
            min_frame_count = params["min_frame_count"] or 1
            centroids: List[np.ndarray] = centroids_state["centroids"]
            tracks: List[Dict[str, Any]] = []

            for cluster_id in sorted(cluster_tracks.keys()):
                tracked_segments = cluster_tracks[cluster_id]["segments"]
                track_frame_count = sum(segment["frame_count"] for segment in tracked_segments)

                if track_frame_count < min_frame_count:
                    continue

                segments: List[Dict[str, Any]] = []

                for tracked_segment in tracked_segments:
                    best_face = tracked_segment["best_face"]
                    segment = {
                        "start_time": format_timecode(tracked_segment["start"]),
                        "end_time":   format_timecode(tracked_segment["end"]),
                        "duration":   format_timecode(tracked_segment["end"] - tracked_segment["start"]),
                        "score":      best_face["score"],
                    }

                    if params["return_track_image"] and "image" in best_face:
                        segment["image"] = best_face["image"]

                    segments.append(segment)

                best_segment = max(tracked_segments, key=lambda s: s["best_face"]["score"])
                best_face = best_segment["best_face"]

                track: Dict[str, Any] = {
                    "track_id":    cluster_id + 1,
                    "segments":    segments,
                    "frame_count": track_frame_count,
                    "score":       best_face["score"],
                }

                if params["return_embedding"]:
                    track["embedding"] = FaceEmbedding(centroids[cluster_id].tolist())

                if params["return_gender_age"]:
                    if "gender" in best_face:
                        track["gender"] = best_face["gender"]

                    if "age" in best_face:
                        track["age"] = best_face["age"]

                tracks.append(track)

            result["tracks"] = tracks

        if params["return_frames"]:
            result["frames"] = [self._build_frame_view(tracked_frame, params) for tracked_frame in tracked_frames]

        return result

    def _build_frame_view(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        view: Dict[str, Any] = {
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "faces":     [
                {
                    "track_id":     cluster_id + 1,
                    "bounding_box": face["bounding_box"],
                }
                for face, cluster_id in tracked_frame["tracked_faces"]
            ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            view["image"] = tracked_frame["image"]

        return view

    def _build_track_chunk(
        self,
        cluster_id: int,
        track: Dict[str, Any],
        centroids_state: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        best_segment = max(track["segments"], key=lambda s: s["best_face"]["score"])
        best_face = best_segment["best_face"]

        chunk: Dict[str, Any] = {
            "type":           "track",
            "track_id":       cluster_id + 1,
            "segment_count":  len(track["segments"]),
            "frame_count":    sum(segment["frame_count"] for segment in track["segments"]),
            "score":          best_face["score"],
        }

        if params["return_embedding"]:
            chunk["embedding"] = FaceEmbedding(centroids_state["centroids"][cluster_id].tolist())

        if params["return_gender_age"]:
            if "gender" in best_face:
                chunk["gender"] = best_face["gender"]
            if "age" in best_face:
                chunk["age"] = best_face["age"]

        return chunk

    def _build_segment_chunk(
        self,
        cluster_id: int,
        tracked_segment: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        best_face = tracked_segment["best_face"]
        segment: Dict[str, Any] = {
            "start_time":  format_timecode(tracked_segment["start"]),
            "end_time":    format_timecode(tracked_segment["end"]),
            "duration":    format_timecode(tracked_segment["end"] - tracked_segment["start"]),
            "frame_count": tracked_segment["frame_count"],
            "score":       best_face["score"],
        }

        if params["return_track_image"] and "image" in best_face:
            segment["image"] = best_face["image"]

        if params["return_gender_age"]:
            if "gender" in best_face:
                segment["gender"] = best_face["gender"]
            if "age" in best_face:
                segment["age"] = best_face["age"]

        return {
            "type":     "segment",
            "track_id": cluster_id + 1,
            "segment":  segment,
        }

    def _build_frame_chunk(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        chunk: Dict[str, Any] = {
            "type":      "frame",
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "faces":     [
                {
                    "track_id":     cluster_id + 1,
                    "bounding_box": face["bounding_box"],
                }
                for face, cluster_id in tracked_frame["tracked_faces"]
            ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            chunk["image"] = tracked_frame["image"]

        return chunk

    def _serialize_faces(
        self,
        detections: List[Face],
        image_cv: np.ndarray,
        return_track_image: bool,
        return_gender_age: bool,
    ) -> List[Dict[str, Any]]:
        # Defer cropping to _add_face_to_track: only the frames that actually
        # become a segment's representative are worth converting to PIL, so
        # we pass a reference to the source frame (cheap) instead of eagerly
        # producing an RGB PIL crop for every detection (expensive when a
        # track spans many frames or the input has many candidate faces).
        faces: List[Dict[str, Any]] = []

        for detection in detections:
            embedding = getattr(detection, "normed_embedding", None)

            if embedding is None:
                continue

            face: Dict[str, Any] = {
                "embedding":    embedding,
                "bounding_box": self._serialize_bounding_box(detection.bbox),
                "score":        float(getattr(detection, "det_score", 0.0)),
            }

            if return_track_image:
                face["image_source"] = image_cv

            if return_gender_age:
                gender = getattr(detection, "gender", None)
                age = getattr(detection, "age", None)
                if gender is not None:
                    face["gender"] = self._gender_to_label(int(gender))
                if age is not None:
                    face["age"] = int(age)

            faces.append(face)

        return faces

    @staticmethod
    def _gender_to_label(gender: int) -> str:
        return "male" if gender == 1 else "female"

    @staticmethod
    def _crop_face_image(
        image_cv: np.ndarray,
        bounding_box: Dict[str, int],
        padding: float,
    ) -> Optional[PILImage.Image]:
        """Crop the face at its detected bounding box (as `{x, y, width, height}`
        in the original frame's coordinate system) at the frame's native
        resolution. `padding` grows the box by that ratio of its own
        width/height on each side before clipping to the frame; embeddings
        still use the un-padded box, so this only affects the returned image.
        Downstream consumers get real pixels they can display, resize, or feed
        into another detector for a different embedding backbone. Returns None
        if the bounding box has no valid overlap with the frame (fully off-
        screen or zero-area)."""
        import cv2

        height, width = image_cv.shape[:2]
        x = bounding_box["x"]
        y = bounding_box["y"]
        w = bounding_box["width"]
        h = bounding_box["height"]

        if padding > 0.0:
            x -= int(w * padding)
            y -= int(h * padding)
            w += int(w * padding * 2)
            h += int(h * padding * 2)

        cx1 = max(0, x)
        cy1 = max(0, y)
        cx2 = min(width, x + w)
        cy2 = min(height, y + h)

        if cx2 <= cx1 or cy2 <= cy1:
            return None

        face_crop = image_cv[cy1:cy2, cx1:cx2]

        return PILImage.fromarray(cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB))

    @staticmethod
    def _serialize_bounding_box(box_xyxy: np.ndarray) -> Dict[str, int]:
        x1, y1, x2, y2 = box_xyxy

        return { "x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1) }

    @staticmethod
    def _filter_faces(
        faces: List[Dict[str, Any]],
        min_face_size: int,
        max_face_count_per_frame: int
    ) -> List[Dict[str, Any]]:
        if min_face_size > 0:
            faces = [ face for face in faces if min(face["bounding_box"]["width"], face["bounding_box"]["height"]) >= min_face_size ]

        if max_face_count_per_frame > 0 and len(faces) > max_face_count_per_frame:
            faces = sorted(faces, key=lambda face: face["score"], reverse=True)[:max_face_count_per_frame]

        return faces

    @staticmethod
    def _bbox_center_distance(a: Dict[str, int], b: Dict[str, int]) -> float:
        """Euclidean distance between the centers of two bounding boxes."""
        ax = a["x"] + a["width"]  / 2.0
        ay = a["y"] + a["height"] / 2.0
        bx = b["x"] + b["width"]  / 2.0
        by = b["y"] + b["height"] / 2.0

        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    @staticmethod
    def _bbox_overlap(a: Dict[str, int], b: Dict[str, int]) -> float:
        """Ratio of shared area to combined area of two bounding boxes. Returns 1.0
        for identical boxes and 0.0 for boxes that do not touch."""
        ax1, ay1 = a["x"], a["y"]
        ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
        bx1, by1 = b["x"], b["y"]
        bx2, by2 = bx1 + b["width"], by1 + b["height"]

        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        intersection = (ix2 - ix1) * (iy2 - iy1)
        union = a["width"] * a["height"] + b["width"] * b["height"] - intersection

        return intersection / union if union > 0 else 0.0

class InsightfaceFaceTrackingTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[FaceAnalysis] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "insightface", "opencv-python", "onnxruntime" ]

    async def _load_model(self) -> None:
        self.model = await self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None

    async def _load_pretrained_model(self) -> FaceAnalysis:
        from insightface.app import FaceAnalysis

        root, name = await self._provision_model(self.config.model, prefetch=True)
        providers = self._resolve_onnx_providers()

        logging.debug(f"InsightFace providers: {providers}")

        model = FaceAnalysis(name=name, root=root, providers=providers)
        model.prepare(ctx_id=self._get_device_id())

        return model

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> Tuple[str, str]:
        path = await super()._provision_model(model, prefetch=prefetch)

        # `FaceAnalysis(name=X, root=R)` expects the pack at `R/models/X/*.onnx`.
        # Reconcile whatever the generic provisioner produced with that layout:
        #   1. Flatten `path/name/` archive nesting if present.
        #   2. Ensure a `models` directory (or symlink) sits alongside the pack.
        name = os.path.basename(path)
        self._flatten_nested_pack(path, name)

        root = os.path.dirname(path)
        self._ensure_models_dir(root)

        # If the pack already lives under a real `models/` directory (e.g. the
        # user pointed `path` at `.../models/antelopev2`), step one level up so
        # `root` names the parent, not the `models` dir itself.
        if os.path.basename(root) == "models" and not os.path.islink(root):
            root = os.path.dirname(root)

        return (root, name)

    @staticmethod
    def _resolve_onnx_providers() -> List[str]:
        """Prefer hardware-accelerated onnxruntime providers over CPU. InsightFace's
        default is `[CUDA, CPU]`, so on Apple Silicon it silently falls back to CPU
        and per-frame detection can take seconds. Adding CoreML (Apple), then any
        available GPU providers ahead of CPU restores hardware acceleration."""
        import onnxruntime as ort

        available = set(ort.get_available_providers())
        preferred = [
            "CUDAExecutionProvider",
            "TensorrtExecutionProvider",
            "ROCMExecutionProvider",
            "CoreMLExecutionProvider",
            "DmlExecutionProvider",
        ]
        providers = [ provider for provider in preferred if provider in available ]
        providers.append("CPUExecutionProvider")

        return providers

    @staticmethod
    def _flatten_nested_pack(path: str, name: str) -> None:
        """Some InsightFace archives (e.g. antelopev2.zip) wrap the model files
        in a top-level directory that matches the pack name, so extraction into
        `path/` yields `path/name/*.onnx` instead of `path/*.onnx`. Move the
        files up one level so the layout matches what `FaceAnalysis` expects."""
        nested = os.path.join(path, name)

        if not os.path.isdir(nested):
            return

        for entry in os.listdir(nested):
            src = os.path.join(nested, entry)
            dst = os.path.join(path, entry)
            if os.path.exists(dst):
                continue
            shutil.move(src, dst)

        if not os.listdir(nested):
            os.rmdir(nested)

    @staticmethod
    def _ensure_models_dir(root: str) -> None:
        """`FaceAnalysis` resolves models under `root/models/`. If the caller's
        `root` doesn't already end in `models`, plant a symlink so both layouts
        work. Recreate the link if it's dangling or points somewhere unexpected
        so re-runs after a failed provisioning don't get stuck."""
        if os.path.basename(root) == "models":
            return

        link_path = os.path.join(root, "models")
        target = os.path.abspath(root)

        if os.path.islink(link_path):
            if os.path.realpath(link_path) == target:
                return
            os.unlink(link_path)
        elif os.path.exists(link_path):
            return

        os.symlink(target, link_path, target_is_directory=True)

    def _get_device_id(self) -> int:
        return 0

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await InsightfaceFaceTrackingTaskAction(action, self.model, self._get_device_id()).run(context)
