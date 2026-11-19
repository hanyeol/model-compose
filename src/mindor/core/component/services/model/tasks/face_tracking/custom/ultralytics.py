from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Callable, Union, Tuple, Optional, Dict, List, Any
from collections.abc import AsyncIterable, AsyncIterator
from functools import partial
from mindor.dsl.schema.component import ModelComponentConfig, ModelPrecision
from mindor.dsl.schema.action import ModelActionConfig, YoloFaceTrackingModelActionConfig
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.utils.iterators import async_zip
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import FaceTrackingTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from PIL import Image as PILImage

if TYPE_CHECKING:
    from ultralytics import YOLO
    from ultralytics.engine.results import Results
    import torch

    # Per-frame image_source extractor passed into tracking. Binds the frame's
    # PIL image and padding into a closure so the tracking path never touches
    # the raw image; the callback is only valid for the duration of its
    # originating `_track_frame` call and must not be stashed on any track state.
    ExtractImageSourceCallable = Callable[[Tuple[int, int, int, int]], Tuple[Optional[PILImage.Image], Tuple[int, int]]]

class YoloFaceTrackingTaskAction(FaceTrackingTaskAction):
    config: YoloFaceTrackingModelActionConfig

    def __init__(
        self,
        config: YoloFaceTrackingModelActionConfig,
        model: YOLO,
        device: Optional[torch.device],
        half_precision: bool = False,
    ):
        super().__init__(config)

        self.model: YOLO = model
        self.device: Optional[torch.device] = device
        self.half_precision: bool = half_precision

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        min_confidence = await context.render_scalar(self.config.params.min_confidence, float)
        detection_size = await context.render_scalar(self.config.params.detection_size, int)
        iou_threshold  = await context.render_scalar(self.config.params.iou_threshold, float)
        tracker        = await context.render_scalar(self.config.params.tracker, str)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        if detection_size <= 0:
            raise ValueError(f"'detection_size' must be > 0, got {detection_size}")

        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError(f"'iou_threshold' must be between 0.0 and 1.0, got {iou_threshold}")

        if tracker not in ("bytetrack", "botsort"):
            raise ValueError(f"'tracker' must be 'bytetrack' or 'botsort', got {tracker!r}")

        params.update({
            "min_confidence": min_confidence,
            "detection_size": detection_size,
            "iou_threshold":  iou_threshold,
            "tracker":        f"{tracker}.yaml",
        })

        return params

    async def _track_batch(
        self,
        frames: List[ImageArrayValue],
        timestamps: Optional[List[ArrayValue]],
        offsets: List[float],
        frame_rate: float,
        streaming: bool,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[Dict[str, Any], AsyncIterable[Dict[str, Any]]]] = []

        for index in range(len(frames)):
            results.append(await self._track(
                frames[index],
                timestamps[index] if timestamps is not None else None,
                offsets[index],
                frame_rate,
                streaming,
                params,
                cancellation_token,
            ))

        return results

    async def _track(
        self,
        frames: ImageArrayValue,
        timestamps: Optional[ArrayValue],
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
            return self._stream_tracks(frames, timestamps, offset, frame_rate, params, cancellation_token)

        return await self._collect_tracks(frames, timestamps, offset, frame_rate, params, cancellation_token)

    async def _collect_tracks(
        self,
        frames: ImageArrayValue,
        timestamps: Optional[ArrayValue],
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        tracked_frames: List[Dict[str, Any]] = []
        merge_gap = params["merge_gap"]
        frame_period = 1.0 / frame_rate if frame_rate else 0.0
        frame_count = 0

        need_image_source = params["return_track_image"] or params["return_detection_image"]

        def _track_frame(image: PILImage.Image, timestamp: float, frame_period: float) -> Dict[str, Any]:
            faces = self._detect_faces_in_frame(image, params)
            extract_image_source = self._image_source_extractor(image, params) if need_image_source else None
            tracked_faces, _ = self._add_faces_to_tracks(
                faces,
                timestamp,
                frame_period,
                cluster_tracks,
                params,
                extract_image_source,
            )

            tracked_frame: Dict[str, Any] = {
                "number":        frame_count + 1,
                "timestamp":     timestamp,
                "tracked_faces": tracked_faces,
            }

            if params["return_frame_image"]:
                tracked_frame["image"] = image

            return tracked_frame

        previous_frame_timestamp: Optional[float] = None

        async for image, timestamp in async_zip(frames, timestamps):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            if timestamp is not None:
                timestamp = float(timestamp)
                if previous_frame_timestamp is not None:
                    frame_period = timestamp - previous_frame_timestamp
            else:
                timestamp = offset + frame_count / frame_rate

            previous_frame_timestamp = timestamp
            tracked_frame = await self._run_in_executor(_track_frame, image, timestamp, frame_period)
            frame_count += 1

            if params["return_detections"]:
                tracked_frames.append(tracked_frame)

        if params["return_detections"]:
            self._interpolate_missing_faces(tracked_frames, merge_gap)

        # Flush any still-open `current` segment so every segment is
        # visible to the result builder.
        for track in cluster_tracks.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None

        logging.debug(f"YOLO face tracking: {frame_count} frames at offset {offset:.3f}s")

        return await self._run_in_executor(self._build_tracking_result, cluster_tracks, frame_count, tracked_frames, params)

    async def _stream_tracks(
        self,
        frames: ImageArrayValue,
        timestamps: Optional[ArrayValue],
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        merge_gap = params["merge_gap"]
        frame_period = 1.0 / frame_rate if frame_rate else 0.0
        frame_count = 0

        # Frame chunk emission is delayed by `merge_gap` so that a detection in
        # a later frame can back-fill missing detections in the frames between
        # (linear bounding-box interpolation per cluster). Segment/track/idle
        # chunks still flow at their original moment — consumers that only care
        # about frames see the interpolated stream, and consumers that mix
        # chunk types accept that segment/track chunks may precede their
        # same-timestamp frame chunk.
        pending_frames: List[Dict[str, Any]] = []
        last_face_by_cluster: Dict[int, Tuple[float, Dict[str, Any]]] = {}

        need_image_source = params["return_track_image"] or params["return_detection_image"]

        def _track_frame(image: PILImage.Image, timestamp: float) -> Dict[str, Any]:
            faces = self._detect_faces_in_frame(image, params)
            extract_image_source = self._image_source_extractor(image, params) if need_image_source else None
            tracked_faces, tracked_segments = self._add_faces_to_tracks(
                faces,
                timestamp,
                frame_period,
                cluster_tracks,
                params,
                extract_image_source,
            )

            tracked_frame: Dict[str, Any] = {
                "number":             frame_count + 1,
                "timestamp":          timestamp,
                "tracked_faces":      tracked_faces,
                "tracked_segments":   tracked_segments,
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
                pending_frame = pending_frames[0]

                if not force and pending_frame["timestamp"] > cutoff:
                    break

                pending_frames.pop(0)
                pending_frame["tracked_faces"] = pending_frame["tracked_faces"] + pending_frame["interpolated_faces"]
                del pending_frame["interpolated_faces"]
                ready.append(pending_frame)

            return ready

        previous_frame_timestamp: Optional[float] = None

        async for image, timestamp in async_zip(frames, timestamps):
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            if timestamp is not None:
                timestamp = float(timestamp)
                if previous_frame_timestamp is not None:
                    frame_period = timestamp - previous_frame_timestamp
            else:
                timestamp = offset + frame_count / frame_rate

            previous_frame_timestamp = timestamp
            tracked_frame = await self._run_in_executor(_track_frame, image, timestamp)
            frame_count += 1

            # Fill gaps for every cluster that got a fresh detection this frame
            # and had a prior detection within `merge_gap`. The prior/current
            # pair anchors the linear interpolation across the pending frames
            # in between.
            if params["return_detections"]:
                for face, cluster_id in tracked_frame["tracked_faces"]:
                    last_face = last_face_by_cluster.get(cluster_id)

                    if last_face is not None:
                        prev_timestamp, prev_face = last_face

                        if timestamp - prev_timestamp <= merge_gap + frame_period + 1e-6:
                            self._interpolate_between_faces(
                                pending_frames,
                                0,
                                len(pending_frames),
                                cluster_id,
                                prev_timestamp,
                                prev_face,
                                timestamp,
                                face,
                            )

                    last_face_by_cluster[cluster_id] = (timestamp, face)

                pending_frames.append(tracked_frame)

                for ready_frame in _flush_ready_frames(force=False):
                    yield self._build_detection_chunk(ready_frame, params)

            if params["return_tracks"]:
                for cluster_id, segment in tracked_frame["tracked_segments"]:
                    yield self._build_segment_chunk(cluster_id, segment, params)

                # Any cluster we didn't touch this frame whose gap now exceeds
                # `merge_gap` is idle: seal its still-open segment and emit a
                # track chunk. The `emitted` flag keeps us from re-emitting a
                # long-idle cluster every frame — a fresh detection resets it
                # in `_add_faces_to_tracks` so the next idle period fires again.
                idle_track_chunks = self._sweep_idle_tracks(cluster_tracks, timestamp, frame_period, merge_gap, params)

                for cluster_id, segment_chunk, track_chunk in idle_track_chunks:
                    if segment_chunk is not None:
                        yield segment_chunk

                    yield track_chunk

        if params["return_detections"]:
            for ready_frame in _flush_ready_frames(force=True):
                yield self._build_detection_chunk(ready_frame, params)

        # Final flush: seal every still-open segment and emit any track that
        # hasn't been announced yet (including clusters that never went idle).
        if params["return_tracks"]:
            for cluster_id, segment_chunk, track_chunk in self._flush_remaining_tracks(cluster_tracks, params):
                if segment_chunk is not None:
                    yield segment_chunk

                yield track_chunk
        else:
            for track in cluster_tracks.values():
                if track["current"] is not None:
                    track["segments"].append(track["current"])
                    track["current"] = None

        logging.debug(f"YOLO face tracking (streaming): {frame_count} frames at offset {offset:.3f}s")

        if params["return_metadata"]:
            yield { "type": "metadata", "frame_count": frame_count }

    def _detect_faces_in_frame(self, image: PILImage.Image, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # `persist=True` keeps the tracker state alive across successive frames
        # of the same video so track ids are stable. `max_detection_count_per_frame`
        # caps detections up front; the tracker consumes what YOLO returns.
        # YOLO treats `max_det=0` as "return 0 boxes", so fall back to its own
        # default cap to keep the 0-means-unbounded contract.
        max_detection_count_per_frame = params["max_detection_count_per_frame"] or 300

        predictions = self.model.track(
            source=image.convert("RGB"),
            imgsz=params["detection_size"],
            conf=params["min_confidence"],
            iou=params["iou_threshold"],
            max_det=max_detection_count_per_frame,
            tracker=params["tracker"],
            persist=True,
            device=self.device,
            half=self.half_precision,
            verbose=False,
        )

        prediction = predictions[0]
        width, height = image.size

        return self._build_detected_faces(prediction, width, height, params)

    def _filter_faces(
        self,
        faces: List[Dict[str, Any]],
        min_face_size: int,
        max_detection_count_per_frame: int,
    ) -> List[Dict[str, Any]]:
        if min_face_size > 0:
            faces = [ face for face in faces if self._bounding_box_meets_min_size(face["bounding_box"], min_face_size) ]

        if max_detection_count_per_frame > 0 and len(faces) > max_detection_count_per_frame:
            faces = sorted(faces, key=lambda face: face["score"], reverse=True)[:max_detection_count_per_frame]

        return faces

    def _add_faces_to_tracks(
        self,
        faces: List[Dict[str, Any]],
        timestamp: float,
        frame_period: float,
        cluster_tracks: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
        extract_image_source: Optional[ExtractImageSourceCallable] = None,
    ) -> Tuple[List[Tuple[Dict[str, Any], int]], List[Tuple[int, Dict[str, Any]]]]:
        """Fold this frame's detections into their tracks' segment histories.
        Association is already done by YOLO's tracker — each face arrives
        with a `track_id` — so this step only extends or seals segments. A
        track's `current` segment is extended if this frame is within
        `frame_period + merge_gap` of the previous one; otherwise the
        current segment is sealed into `segments` and a fresh one starts.
        `frame_period` is the caller-computed gap to the previous frame —
        `1/frame_rate` when the caller extrapolates timestamps, or the
        actual pts delta when `timestamps` is set. Either way `merge_gap=0`
        means "consecutive frames always merge, one missing frame splits".

        Returns `(tracked_faces, tracked_segments)`: `tracked_faces` is the
        `(face, cluster_id)` pairs bound in this frame so the caller can
        materialize a per-frame view; `tracked_segments` is the
        `(cluster_id, segment)` pairs that were just sealed by these detections
        so streaming callers can emit segment events."""
        tracked_faces: List[Tuple[Dict[str, Any], int]] = []
        tracked_segments: List[Tuple[int, Dict[str, Any]]] = []
        merge_gap = params["merge_gap"]

        for face in faces:
            cluster_id = face["track_id"]
            track = cluster_tracks.setdefault(cluster_id, {
                "segments":  [],
                "current":   None,
                "last_seen": None,
                "last_bbox": None,
                "emitted":   False,
            })

            track["last_seen"] = timestamp

            current: Optional[Dict[str, Any]] = track["current"]
            score = face["score"]

            # 1e-6 tolerance absorbs ULP-scale jitter — timestamp arithmetic
            # can diverge from the frame period by up to ~1e-13 for long
            # offsets, and `merge_gap` is in seconds so a microsecond
            # tolerance can't blur any user-meaningful behavior.
            in_same_segment = current is not None and timestamp - current["end"] <= frame_period + merge_gap + 1e-6

            # EMA-blend this frame's bbox with the track's previous bbox to
            # dampen per-frame jitter. Only applied within the same segment —
            # a new segment starts fresh so a re-detected face doesn't drag
            # the box from its previous appearance. `bounding_box_smoothing`
            # is the weight given to the previous frame (0 disables, 1 freezes).
            if in_same_segment and params["bounding_box_smoothing"] and track["last_bbox"] is not None:
                bounding_box = self._blend_bounding_box(track["last_bbox"], face["bounding_box"], params["bounding_box_smoothing"])
                track["last_bbox"] = bounding_box
                face = { **face, "bounding_box": tuple(int(round(value)) for value in bounding_box) }
            else:
                track["last_bbox"] = tuple(float(value) for value in face["bounding_box"])

            if extract_image_source is not None:
                image_source, origin = extract_image_source(face["bounding_box"])

                if image_source is not None:
                    face = { **face, "image_source": image_source, "image_source_origin": origin }

            # `face_with_image` aliases the current face while it still
            # carries the padded sub-crop reference, so `best_face` can crop
            # the representative image later; the per-frame `face` is then
            # rebound to a sub-dict without `image_source` unless the caller
            # asked for per-detection crops, so non-streaming runs don't pin a
            # padded PIL sub-crop per detected face in `tracked_frames`.
            face_with_image = face

            if "image_source" in face and not params["return_detection_image"]:
                face = { key: value for key, value in face.items() if key not in ("image_source", "image_source_origin") }

            if in_same_segment:
                current["end"] = timestamp
                current["frame_count"] += 1

                if score > current["best_face"]["score"]:
                    current["best_face"] = face_with_image
            else:
                if current is not None:
                    track["segments"].append(current)
                    tracked_segments.append((int(cluster_id), current))

                track["current"] = {
                    "start":       timestamp,
                    "end":         timestamp,
                    "frame_count": 1,
                    "best_face":   face_with_image,
                }

                track["emitted"] = False

            tracked_faces.append((face, cluster_id))

        return tracked_faces, tracked_segments

    def _sweep_idle_tracks(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        timestamp: float,
        frame_period: float,
        merge_gap: float,
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Sweep clusters that have gone idle past `merge_gap` at `timestamp`.

        For each such cluster, seal any still-open `current` segment (returning
        a segment chunk to emit) and produce a track chunk with the running
        aggregates. Mutates track state: seals `current` into `segments`, sets
        `emitted=True` so the same idle stretch is not announced twice. A
        later detection on the same track_id resets `emitted` in
        `_add_faces_to_tracks`, so re-emission on the next idle period is
        intentional."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"]

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

            chunks.append((cluster_id, segment_chunk, self._build_track_chunk(cluster_id, track, params)))

            track["emitted"] = True

        return chunks

    def _flush_remaining_tracks(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Emit a track chunk (and any still-open segment) for every cluster
        that hasn't been announced yet. Called once when the frame stream
        ends: at that point every remaining cluster is authoritative, so we
        skip the idle-timeout check and treat `emitted=True` as the only
        reason to omit a cluster."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"]

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

            chunks.append((cluster_id, segment_chunk, self._build_track_chunk(cluster_id, track, params)))

            track["emitted"] = True

        return chunks

    def _interpolate_missing_faces(
        self,
        tracked_frames: List[Dict[str, Any]],
        merge_gap: float,
    ) -> None:
        """Walk every frame in chronological order, and for each cluster,
        interpolate bounding boxes between consecutive detections whose gap is
        within `merge_gap` + the current frame's prior interval. The threshold
        mirrors the streaming path's per-frame `frame_period` so both modes
        reach the same `in_same_segment` verdict on the same data — including
        VFR inputs where no fixed `frame_rate` captures the real cadence.
        Interpolated faces are merged into each frame's `tracked_faces`
        in place; `interpolated_faces` is stripped so downstream code sees
        a single unified list."""
        # Track each cluster's most recent detection's frame index too so we
        # can hand the interpolator a bounded [start, end) range instead of
        # re-scanning every frame per anchor pair — otherwise the cost is
        # O(anchor_pairs × total_frames) on long videos.
        last_face_by_cluster: Dict[int, Tuple[int, float, Dict[str, Any]]] = {}

        for frame in tracked_frames:
            frame.setdefault("interpolated_faces", [])

        for current_index, frame in enumerate(tracked_frames):
            timestamp = frame["timestamp"]
            frame_period = timestamp - tracked_frames[current_index - 1]["timestamp"] if current_index > 0 else 0.0
            threshold = merge_gap + frame_period + 1e-6

            for face, cluster_id in frame["tracked_faces"]:
                last_face = last_face_by_cluster.get(cluster_id)

                if last_face is not None:
                    prev_index, prev_timestamp, prev_face = last_face

                    if timestamp - prev_timestamp <= threshold:
                        self._interpolate_between_faces(
                            tracked_frames,
                            prev_index + 1,
                            current_index,
                            cluster_id,
                            prev_timestamp,
                            prev_face,
                            timestamp,
                            face,
                        )

                last_face_by_cluster[cluster_id] = (current_index, timestamp, face)

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
        prev_face: Dict[str, Any],
        current_timestamp: float,
        current_face: Dict[str, Any],
    ) -> None:
        """Fill in a cluster's missing detections between two anchors by linear
        bounding-box interpolation. Frames whose timestamp lies strictly between
        `prev_timestamp` and `current_timestamp` and that have no detection (real
        or interpolated) for `cluster_id` receive a synthetic face. The
        interpolated bboxes are appended to `interpolated_faces` so callers
        can distinguish them from real detections and merge later."""
        span = current_timestamp - prev_timestamp

        if span <= 0:
            return

        prev_bbox = prev_face["bounding_box"]
        current_bbox = current_face["bounding_box"]

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
            interpolated_bbox = (
                int(round(prev_bbox[0] + (current_bbox[0] - prev_bbox[0]) * ratio)),
                int(round(prev_bbox[1] + (current_bbox[1] - prev_bbox[1]) * ratio)),
                int(round(prev_bbox[2] + (current_bbox[2] - prev_bbox[2]) * ratio)),
                int(round(prev_bbox[3] + (current_bbox[3] - prev_bbox[3]) * ratio)),
            )
            frame["interpolated_faces"].append(({ **prev_face, "bounding_box": interpolated_bbox, "interpolated": True }, cluster_id))

    def _build_detected_faces(
        self,
        prediction: Results,
        width: int,
        height: int,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        boxes = prediction.boxes

        if boxes is None or boxes.id is None:
            return []

        track_ids         = boxes.id.cpu().numpy().astype(int)
        boxes_xyxy        = boxes.xyxy.cpu().numpy()
        boxes_confidences = boxes.conf.cpu().numpy()

        faces: List[Dict[str, Any]] = []

        for index in range(track_ids.shape[0]):
            x1, y1, x2, y2 = boxes_xyxy[index]

            face: Dict[str, Any] = {
                "track_id":     int(track_ids[index]),
                "bounding_box": (int(x1), int(y1), int(x2), int(y2)),
                "score":        float(boxes_confidences[index]),
                "width":        width,
                "height":       height,
            }

            faces.append(face)

        return self._filter_faces(faces, params["min_face_size"], params["max_detection_count_per_frame"])

    def _image_source_extractor(self, image: PILImage.Image, params: Dict[str, Any]) -> ExtractImageSourceCallable:
        """Bind the current frame and padding into an image_source extractor.

        Valid only while the originating `_track_frame` call runs; never store
        the returned callable on track state, or the frame buffer outlives it.
        """
        return partial(self._extract_face_region, image, crop_margin_ratio=params["crop_margin_ratio"])

    @classmethod
    def _extract_face_region(
        cls,
        image: PILImage.Image,
        bounding_box: Tuple[int, int, int, int],
        crop_margin_ratio: float = 0.0,
    ) -> Tuple[Optional[PILImage.Image], Tuple[int, int]]:
        """Crop the region of `image` around `bounding_box` grown by
        `crop_margin_ratio` on each side, returning `(sub_crop, (ox, oy))`.
        Callers invoke this after smoothing is applied so the sub-crop is sized
        to exactly match `_crop_face_image(padding=...)`; margin and crop
        share the same `int(w * padding)` / `int(h * padding)` truncation, so
        pixels line up at the boundary with no "pixel-identical only on paper"
        caveat. PIL `.crop()` returns an independent copy — not a view — so
        dropping the original frame still releases its buffer while retaining
        just the face's neighborhood.
        Returns `(None, (0, 0))` if the padded box has no valid overlap with
        the frame."""
        width, height = image.size
        x1, y1, x2, y2 = bounding_box
        margin = max(0.0, crop_margin_ratio)

        mx1 = max(0, x1 - int((x2 - x1) * margin))
        my1 = max(0, y1 - int((y2 - y1) * margin))
        mx2 = min(width, x2 + int((x2 - x1) * margin))
        my2 = min(height, y2 + int((y2 - y1) * margin))

        if mx2 <= mx1 or my2 <= my1:
            return None, (0, 0)

        return image.crop((mx1, my1, mx2, my2)), (mx1, my1)

    def _crop_face_image(self, face: Dict[str, Any], padding: float) -> Optional[PILImage.Image]:
        """Crop the face at its detected bounding box (as `(x1, y1, x2, y2)`
        in the original frame's coordinate system) at the frame's native
        resolution. `padding` grows the box by that ratio of its own
        width/height on each side before clipping to the stashed sub-crop.
        Interpreted against `image_source_origin`: when `_extract_face_region`
        pre-cropped a sub-region of the frame, the bounding box is translated
        into the sub-crop's local coordinates before clipping, so a sub-crop
        with its top-left offset yields the same pixels as the full frame as
        long as the padded box stays inside the sub-crop.
        Returns None when the source frame wasn't retained on the face or
        the bounding box has no valid overlap with the sub-crop (fully outside
        or zero-area)."""
        image_source: Optional[PILImage.Image] = face.get("image_source")

        if image_source is None:
            return None

        width, height = image_source.size
        ox, oy = face.get("image_source_origin", (0, 0))
        x1, y1, x2, y2 = face["bounding_box"]
        x1 -= ox
        y1 -= oy
        x2 -= ox
        y2 -= oy

        if padding > 0.0:
            w = x2 - x1
            h = y2 - y1
            x1 -= int(w * padding)
            y1 -= int(h * padding)
            x2 += int(w * padding)
            y2 += int(h * padding)

        cx1 = max(0, x1)
        cy1 = max(0, y1)
        cx2 = min(width, x2)
        cy2 = min(height, y2)

        if cx2 <= cx1 or cy2 <= cy1:
            return None

        return image_source.crop((cx1, cy1, cx2, cy2))

    def _build_tracking_result(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        frame_count: int,
        tracked_frames: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_tracks"]:
            min_frame_count = params["min_frame_count"]
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

                    if params["return_track_image"]:
                        segment["image"] = self._crop_face_image(best_face, params["crop_margin_ratio"])

                    segments.append(segment)

                best_segment = max(tracked_segments, key=lambda s: s["best_face"]["score"])
                best_face = best_segment["best_face"]

                tracks.append({
                    "track_id":    int(cluster_id),
                    "segments":    segments,
                    "frame_count": track_frame_count,
                    "score":       best_face["score"],
                })

            result["tracks"] = tracks

        if params["return_detections"]:
            result["detections"] = [ self._serialize_tracked_frame(tracked_frame, params) for tracked_frame in tracked_frames ]

        if params["return_metadata"]:
            result["frame_count"] = frame_count

        return result

    def _build_track_chunk(
        self,
        cluster_id: int,
        track: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Snapshot of a track's running aggregates. Emitted whenever a
        track goes idle past `merge_gap`; may be emitted multiple times for
        the same `track_id` if YOLO's tracker reuses the id after a gap —
        each emission is authoritative for the state up to that moment, and
        downstream should treat the latest chunk for a given `track_id` as
        canonical."""
        best_segment = max(track["segments"], key=lambda s: s["best_face"]["score"])
        best_face = best_segment["best_face"]

        return {
            "type":          "track",
            "track_id":      int(cluster_id),
            "segment_count": len(track["segments"]),
            "frame_count":   sum(segment["frame_count"] for segment in track["segments"]),
            "score":         best_face["score"],
        }

    def _build_segment_chunk(
        self,
        cluster_id: int,
        tracked_segment: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        best_face = tracked_segment["best_face"]
        chunk: Dict[str, Any] = {
            "type":        "segment",
            "track_id":    int(cluster_id),
            "start_time":  format_timecode(tracked_segment["start"]),
            "end_time":    format_timecode(tracked_segment["end"]),
            "duration":    format_timecode(tracked_segment["end"] - tracked_segment["start"]),
            "frame_count": tracked_segment["frame_count"],
            "score":       best_face["score"],
        }

        if params["return_track_image"]:
            chunk["image"] = self._crop_face_image(best_face, params["crop_margin_ratio"])

        return chunk

    def _build_detection_chunk(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        chunk: Dict[str, Any] = {
            "type":      "detection",
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "faces":     [ self._serialize_tracked_face(tracked_face, cluster_id, params) for tracked_face, cluster_id in tracked_frame["tracked_faces"] ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            chunk["image"] = tracked_frame["image"]

        return chunk

    def _serialize_tracked_frame(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        frame: Dict[str, Any] = {
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "faces":     [ self._serialize_tracked_face(tracked_face, cluster_id, params) for tracked_face, cluster_id in tracked_frame["tracked_faces"] ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            frame["image"] = tracked_frame["image"]

        return frame

    def _serialize_tracked_face(self, tracked_face: Dict[str, Any], cluster_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        face: Dict[str, Any] = {
            "track_id":     int(cluster_id),
            "bounding_box": self._serialize_bounding_box(tracked_face["bounding_box"]),
            "score":        tracked_face["score"],
        }

        if params["return_detection_image"]:
            # Interpolated faces carry the anchor frame's `image_source`, so
            # cropping at the interpolated bbox would show the face from the
            # wrong frame; skip the crop for those and rely on the real anchors.
            face["image"] = self._crop_face_image(tracked_face, params["crop_margin_ratio"]) if not tracked_face.get("interpolated") else None

        if tracked_face.get("interpolated"):
            face["interpolated"] = True

        return face

    @staticmethod
    def _serialize_bounding_box(bounding_box: Tuple[int, int, int, int]) -> Dict[str, int]:
        x1, y1, x2, y2 = bounding_box

        return { "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1 }

    @staticmethod
    def _blend_bounding_box(
        prev_bounding_box: Tuple[float, float, float, float],
        new_bounding_box: Tuple[float, float, float, float],
        smoothing: float,
    ) -> Tuple[float, float, float, float]:
        """EMA-blend `new_bounding_box` toward `prev_bounding_box` as floats.

        `smoothing` is the weight given to the previous frame's box, so a
        larger value produces a heavier tail and a slower response to
        movement (0 disables, 1 freezes on `prev_bounding_box`).
        """
        return tuple(smoothing * prev_bounding_box[n] + (1.0 - smoothing) * new_bounding_box[n] for n in range(4))

    @staticmethod
    def _bounding_box_meets_min_size(bounding_box: Tuple[int, int, int, int], min_size: int) -> bool:
        """Whether both sides of `bounding_box` are at least `min_size` pixels."""
        x1, y1, x2, y2 = bounding_box

        return min(x2 - x1, y2 - y1) >= min_size

class YoloFaceTrackingTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[YOLO] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            *torch_requirements("torch>=2.5,<2.13", "torchvision"),
            "ultralytics",
            "lap",
        ]

    async def _load_model(self) -> None:
        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device)

        def _load() -> YOLO:
            from ultralytics import YOLO

            model = YOLO(model_path)
            model.to(device)

            return model

        self.model, self.device = await self._run_in_executor(_load), device

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await YoloFaceTrackingTaskAction(
            action,
            self.model,
            self.device,
            bool(self.config.precision == ModelPrecision.FLOAT16)
        ).run(context)
