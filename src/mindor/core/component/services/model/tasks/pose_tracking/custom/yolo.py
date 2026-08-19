from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Union, Dict, List, Tuple, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, YoloPoseTrackingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import PoseTrackingTaskAction
from ...pose_detection.utils import openpose, coco
from ....base import ComponentActionContext, ModelTaskService
from PIL import Image as PILImage

if TYPE_CHECKING:
    from ultralytics import YOLO
    from ultralytics.engine.results import Results
    import numpy as np

class YoloPoseTrackingTaskAction(PoseTrackingTaskAction):
    config: YoloPoseTrackingModelActionConfig

    def __init__(self, config: YoloPoseTrackingModelActionConfig, model: YOLO):
        super().__init__(config)

        self.model: YOLO = model

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tracker = await context.render_scalar(self.config.params.tracker, str)

        if tracker not in ("bytetrack", "botsort"):
            raise ValueError(f"'tracker' must be 'bytetrack' or 'botsort', got {tracker!r}")

        params["tracker"] = f"{tracker}.yaml"

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
        """Track poses across one video's frames. Streaming mode returns an
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
        track_segments: Dict[int, Dict[str, Any]] = {}
        tracked_frames: List[Dict[str, Any]] = []
        frame_count = 0

        def _track_frame(image: PILImage.Image, timestamp: float) -> Dict[str, Any]:
            poses = self._detect_poses_in_frame(image, params)
            tracked_poses, _ = self._add_poses_to_tracks(
                poses,
                timestamp,
                frame_rate,
                track_segments,
                params
            )

            tracked_frame: Dict[str, Any] = {
                "number":        frame_count + 1,
                "timestamp":     timestamp,
                "tracked_poses": tracked_poses,
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
            self._interpolate_missing_poses(tracked_frames, frame_rate, params["merge_gap"] or 0.0)

        # Flush any still-open `current` segment so every segment is
        # visible to the result builder.
        for track in track_segments.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None

        logging.debug(f"YOLO pose tracking: {frame_count} frames at offset {offset:.3f}s")

        return await self._run_in_executor(self._build_tracking_result, track_segments, frame_count, tracked_frames, params)

    async def _stream_tracks(
        self,
        frames: ImageArrayValue,
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        track_segments: Dict[int, Dict[str, Any]] = {}
        merge_gap = params["merge_gap"] or 0.0
        frame_period = 1.0 / frame_rate
        frame_count = 0

        # Frame chunk emission is delayed by `merge_gap` so that a detection in
        # a later frame can back-fill missing detections in the frames between
        # (linear bounding-box interpolation per track). Segment/track/idle
        # chunks still flow at their original moment — consumers that only care
        # about frames see the interpolated stream, and consumers that mix
        # chunk types accept that segment/track chunks may precede their
        # same-timestamp frame chunk.
        pending_frames: List[Dict[str, Any]] = []
        last_pose_by_track: Dict[int, Tuple[float, Dict[str, Any]]] = {}

        def _track_frame(image: PILImage.Image, timestamp: float) -> Dict[str, Any]:
            poses = self._detect_poses_in_frame(image, params)
            tracked_poses, tracked_segments = self._add_poses_to_tracks(
                poses,
                timestamp,
                frame_rate,
                track_segments,
                params
            )

            tracked_frame: Dict[str, Any] = {
                "number":             frame_count + 1,
                "timestamp":          timestamp,
                "tracked_poses":      tracked_poses,
                "tracked_segments":   tracked_segments,
                "interpolated_poses": [],
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
                pending_frame["tracked_poses"] = pending_frame["tracked_poses"] + pending_frame["interpolated_poses"]
                del pending_frame["interpolated_poses"]
                ready.append(pending_frame)

            return ready

        async for image in frames:
            if cancellation_token is not None and cancellation_token.is_cancelled():
                break

            timestamp = offset + frame_count / frame_rate
            tracked_frame = await self._run_in_executor(_track_frame, image, timestamp)
            frame_count += 1

            # Fill gaps for every track that got a fresh detection this frame
            # and had a prior detection within `merge_gap`. The prior/current
            # pair anchors the linear interpolation across the pending frames
            # in between.
            if params["return_frames"]:
                for pose, track_id in tracked_frame["tracked_poses"]:
                    last_pose = last_pose_by_track.get(track_id)
                    if last_pose is not None:
                        prev_timestamp, prev_pose = last_pose
                        if timestamp - prev_timestamp <= merge_gap + frame_period + 1e-6:
                            self._interpolate_between_poses(
                                pending_frames,
                                0,
                                len(pending_frames),
                                track_id,
                                prev_timestamp,
                                prev_pose,
                                timestamp,
                                pose
                            )
                    last_pose_by_track[track_id] = (timestamp, pose)

                pending_frames.append(tracked_frame)

                for ready_frame in _flush_ready_frames(force=False):
                    yield self._build_frame_chunk(ready_frame, params)

            if params["return_tracks"]:
                for track_id, segment in tracked_frame["tracked_segments"]:
                    yield self._build_segment_chunk(track_id, segment, params)

                # Any track we didn't touch this frame whose gap now exceeds
                # `merge_gap` is idle: seal its still-open segment and emit a
                # track chunk. The `emitted` flag keeps us from re-emitting a
                # long-idle track every frame — a fresh detection resets it
                # in `_add_poses_to_tracks` so the next idle period fires again.
                idle_track_chunks = self._sweep_idle_tracks(track_segments, timestamp, frame_period, merge_gap, params)
                for track_id, segment_chunk, track_chunk in idle_track_chunks:
                    if segment_chunk is not None:
                        yield segment_chunk
                    yield track_chunk

        if params["return_frames"]:
            for ready_frame in _flush_ready_frames(force=True):
                yield self._build_frame_chunk(ready_frame, params)

        # Final flush: seal every still-open segment and emit any track that
        # hasn't been announced yet (including tracks that never went idle).
        if params["return_tracks"]:
            for track_id, segment_chunk, track_chunk in self._flush_remaining_tracks(track_segments, params):
                if segment_chunk is not None:
                    yield segment_chunk
                yield track_chunk
        else:
            for track in track_segments.values():
                if track["current"] is not None:
                    track["segments"].append(track["current"])
                    track["current"] = None

        logging.debug(f"YOLO pose tracking (streaming): {frame_count} frames at offset {offset:.3f}s")

        if params["return_metadata"]:
            yield { "type": "metadata", "frame_count": frame_count }

    def _detect_poses_in_frame(self, image: PILImage.Image, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # `persist=True` keeps the tracker state alive across successive frames
        # of the same video so track ids are stable. `max_pose_count_per_frame`
        # caps detections up front; the tracker consumes what YOLO returns.
        max_det = params["max_pose_count_per_frame"] or 300

        predictions = self.model.track(
            source=image.convert("RGB"),
            conf=params["min_confidence"],
            max_det=max_det,
            tracker=params["tracker"],
            persist=True,
            verbose=False,
        )

        prediction = predictions[0]
        width, height = image.size

        return self._build_detected_poses(prediction, width, height, params)

    def _filter_poses(
        self,
        poses: List[Dict[str, Any]],
        min_pose_size: int,
        max_pose_count_per_frame: int,
    ) -> List[Dict[str, Any]]:
        if min_pose_size > 0:
            poses = [ pose for pose in poses if self._bbox_meets_min_size(pose["bounding_box"], min_pose_size) ]

        if max_pose_count_per_frame > 0 and len(poses) > max_pose_count_per_frame:
            poses = sorted(poses, key=lambda pose: pose["score"], reverse=True)[:max_pose_count_per_frame]

        return poses

    def _add_poses_to_tracks(
        self,
        poses: List[Dict[str, Any]],
        timestamp: float,
        frame_rate: float,
        track_segments: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[List[Tuple[Dict[str, Any], int]], List[Tuple[int, Dict[str, Any]]]]:
        """Fold this frame's detections into their tracks' segment histories.
        Unlike face_tracking, association is already done by YOLO's tracker —
        each pose arrives with a `track_id` — so this step only extends or
        seals segments. A track's `current` segment is extended if this frame
        is within one frame period plus `merge_gap` of the previous one;
        otherwise the current segment is sealed into `segments` and a fresh
        one starts. The frame-period baseline means `merge_gap` measures how
        long a person may go undetected before the segment is split, not how
        far apart two detections may be — consecutive frames always merge, so
        `merge_gap=0` does what a user naïvely expects.

        Returns `(tracked_poses, tracked_segments)`: `tracked_poses` is the
        `(pose, track_id)` pairs bound in this frame so the caller can
        materialize a per-frame view; `tracked_segments` is the
        `(track_id, segment)` pairs that were just sealed by these detections
        so streaming callers can emit segment events."""
        merge_gap = params["merge_gap"] or 0.0
        frame_period = 1.0 / frame_rate
        tracked_poses: List[Tuple[Dict[str, Any], int]] = []
        tracked_segments: List[Tuple[int, Dict[str, Any]]] = []

        for pose in poses:
            track_id = pose["track_id"]
            track = track_segments.setdefault(track_id, {
                "segments":  [],
                "current":   None,
                "last_seen": None,
                "emitted":   False,
            })

            track["last_seen"] = timestamp

            current: Optional[Dict[str, Any]] = track["current"]
            score = pose["score"]

            # Absorb ULP-scale jitter: caller derives `timestamp` as
            # `offset + n/rate` while `frame_period` is `1/rate`, and the two
            # paths can diverge by up to ~1e-13 for long offsets. `merge_gap`
            # is measured in seconds, so a microsecond tolerance can't blur any
            # user-meaningful behavior.
            if current is not None and timestamp - current["end"] <= frame_period + merge_gap + 1e-6:
                current["end"] = timestamp
                current["frame_count"] += 1

                if score > current["best_pose"]["score"]:
                    current["best_pose"] = pose

                tracked_poses.append((pose, track_id))

                continue

            if current is not None:
                track["segments"].append(current)
                tracked_segments.append((int(track_id), current))

            track["current"] = {
                "start":       timestamp,
                "end":         timestamp,
                "frame_count": 1,
                "best_pose":   pose,
            }

            track["emitted"] = False

            tracked_poses.append((pose, track_id))

        return tracked_poses, tracked_segments

    def _sweep_idle_tracks(
        self,
        track_segments: Dict[int, Dict[str, Any]],
        timestamp: float,
        frame_period: float,
        merge_gap: float,
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Sweep tracks that have gone idle past `merge_gap` at `timestamp`.

        For each such track, seal any still-open `current` segment (returning
        a segment chunk to emit) and produce a track chunk with the running
        aggregates. Mutates track state: seals `current` into `segments`, sets
        `emitted=True` so the same idle stretch is not announced twice. A
        later detection on the same track_id resets `emitted` in
        `_add_poses_to_tracks`, so re-emission on the next idle period is
        intentional."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"] or 1

        for track_id in sorted(track_segments.keys()):
            track = track_segments[track_id]
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
                segment_chunk = self._build_segment_chunk(track_id, current, params)

            track_frame_count = sum(segment["frame_count"] for segment in track["segments"])

            if track_frame_count < min_frame_count:
                continue

            chunks.append((track_id, segment_chunk, self._build_track_chunk(track_id, track, params)))

            track["emitted"] = True

        return chunks

    def _flush_remaining_tracks(
        self,
        track_segments: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]]:
        """Emit a track chunk (and any still-open segment) for every track
        that hasn't been announced yet. Called once when the frame stream
        ends: at that point every remaining track is authoritative, so we
        skip the idle-timeout check and treat `emitted=True` as the only
        reason to omit a track."""
        chunks: List[Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]] = []
        min_frame_count = params["min_frame_count"] or 1

        for track_id in sorted(track_segments.keys()):
            track = track_segments[track_id]

            if track["current"] is None and track["emitted"]:
                continue

            segment_chunk: Optional[Dict[str, Any]] = None
            current = track["current"]

            if current is not None:
                track["segments"].append(current)
                track["current"] = None
                segment_chunk = self._build_segment_chunk(track_id, current, params)

            track_frame_count = sum(segment["frame_count"] for segment in track["segments"])

            if track_frame_count < min_frame_count:
                continue

            chunks.append((track_id, segment_chunk, self._build_track_chunk(track_id, track, params)))

            track["emitted"] = True

        return chunks

    def _interpolate_missing_poses(
        self,
        tracked_frames: List[Dict[str, Any]],
        frame_rate: float,
        merge_gap: float,
    ) -> None:
        """Walk every frame in chronological order, and for each track,
        interpolate bounding boxes between consecutive detections whose gap is
        within `merge_gap` + one frame period. Interpolated poses are merged
        into each frame's `tracked_poses` in place; `interpolated_poses` is stripped
        so downstream code sees a single unified list."""
        frame_period = 1.0 / frame_rate
        threshold = merge_gap + frame_period + 1e-6
        # Track each track's most recent detection's frame index too so we
        # can hand the interpolator a bounded [start, end) range instead of
        # re-scanning every frame per anchor pair — otherwise the cost is
        # O(anchor_pairs × total_frames) on long videos.
        last_pose_by_track: Dict[int, Tuple[int, float, Dict[str, Any]]] = {}

        for frame in tracked_frames:
            frame.setdefault("interpolated_poses", [])

        for current_index, frame in enumerate(tracked_frames):
            timestamp = frame["timestamp"]
            for pose, track_id in frame["tracked_poses"]:
                last_pose = last_pose_by_track.get(track_id)
                if last_pose is not None:
                    prev_index, prev_timestamp, prev_pose = last_pose
                    if timestamp - prev_timestamp <= threshold:
                        self._interpolate_between_poses(
                            tracked_frames,
                            prev_index + 1,
                            current_index,
                            track_id,
                            prev_timestamp,
                            prev_pose,
                            timestamp,
                            pose
                        )
                last_pose_by_track[track_id] = (current_index, timestamp, pose)

        for frame in tracked_frames:
            frame["tracked_poses"] = frame["tracked_poses"] + frame["interpolated_poses"]
            del frame["interpolated_poses"]

    def _interpolate_between_poses(
        self,
        frames: List[Dict[str, Any]],
        start_index: int,
        end_index: int,
        track_id: int,
        prev_timestamp: float,
        prev_pose: Dict[str, Any],
        current_timestamp: float,
        current_pose: Dict[str, Any],
    ) -> None:
        """Fill in a track's missing detections between two anchors by linear
        bounding-box interpolation. Frames whose timestamp lies strictly between
        `prev_timestamp` and `current_timestamp` and that have no detection (real or interpolated)
        for `track_id` receive a synthetic pose. The interpolated bboxes are
        appended to `interpolated_poses` so callers can distinguish them from real
        detections and merge later."""
        span = current_timestamp - prev_timestamp

        if span <= 0:
            return

        prev_bbox = prev_pose["bounding_box"]
        current_bbox = current_pose["bounding_box"]

        for index in range(start_index, end_index):
            frame = frames[index]
            frame_timestamp = frame["timestamp"]

            if frame_timestamp <= prev_timestamp or frame_timestamp >= current_timestamp:
                continue

            if any(tid == track_id for _, tid in frame["tracked_poses"]):
                continue

            if any(tid == track_id for _, tid in frame["interpolated_poses"]):
                continue

            ratio = (frame_timestamp - prev_timestamp) / span
            interpolated_bbox = (
                int(round(prev_bbox[0] + (current_bbox[0] - prev_bbox[0]) * ratio)),
                int(round(prev_bbox[1] + (current_bbox[1] - prev_bbox[1]) * ratio)),
                int(round(prev_bbox[2] + (current_bbox[2] - prev_bbox[2]) * ratio)),
                int(round(prev_bbox[3] + (current_bbox[3] - prev_bbox[3]) * ratio)),
            )
            frame["interpolated_poses"].append(({ **prev_pose, "bounding_box": interpolated_bbox, "interpolated": True }, track_id))

    def _build_detected_poses(
        self,
        prediction: Results,
        width: int,
        height: int,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        boxes, keypoints = prediction.boxes, prediction.keypoints

        if boxes is None or boxes.id is None or keypoints is None:
            return []

        track_ids      = boxes.id.cpu().numpy().astype(int)
        boxes_xyxy     = boxes.xyxy.cpu().numpy()
        boxes_conf     = boxes.conf.cpu().numpy()
        keypoints_xy   = keypoints.xy.cpu().numpy()
        keypoints_conf = keypoints.conf.cpu().numpy() if keypoints.conf is not None else None

        needs_openpose_keypoints = (
            params["return_openpose_keypoints"]
            or (params["return_skeleton_image"] and params["skeleton_format"] == "openpose")
        )
        needs_keypoints = (
            params["return_keypoints"] or needs_openpose_keypoints
            or (params["return_skeleton_image"] and params["skeleton_format"] == "natural")
        )
        min_visibility = params["min_presence_confidence"]

        poses: List[Dict[str, Any]] = []

        for index in range(track_ids.shape[0]):
            x1, y1, x2, y2 = boxes_xyxy[index]
            conf_row = keypoints_conf[index] if keypoints_conf is not None else None
            pose_keypoints = self._build_keypoints(keypoints_xy[index], conf_row, min_visibility) if needs_keypoints else None
            openpose_keypoints = coco.to_body_18(pose_keypoints) if needs_openpose_keypoints else None

            pose: Dict[str, Any] = {
                "track_id":     int(track_ids[index]),
                "bounding_box": (int(x1), int(y1), int(x2), int(y2)),
                "score":        float(boxes_conf[index]),
                "width":        width,
                "height":       height,
            }

            if pose_keypoints is not None:
                pose["keypoints"] = pose_keypoints
            if openpose_keypoints is not None:
                pose["openpose_keypoints"] = openpose_keypoints

            poses.append(pose)

        return self._filter_poses(poses, params["min_pose_size"], params["max_pose_count_per_frame"])

    def _build_keypoints(
        self,
        keypoints_xy: np.ndarray,
        keypoints_conf: Optional[np.ndarray],
        min_visibility: float,
    ) -> List[Dict[str, Any]]:
        keypoints: List[Dict[str, Any]] = []

        for keypoint in range(keypoints_xy.shape[0]):
            visibility = float(keypoints_conf[keypoint]) if keypoints_conf is not None else 1.0
            x, y = int(keypoints_xy[keypoint, 0]), int(keypoints_xy[keypoint, 1])

            if visibility < min_visibility or (x == 0 and y == 0):
                keypoints.append({ "x": 0, "y": 0, "visibility": 0.0 })
            else:
                keypoints.append({ "x": x, "y": y, "visibility": visibility })

        return keypoints

    def _render_skeleton(self, pose: Dict[str, Any], params: Dict[str, Any]) -> Optional[PILImage.Image]:
        width, height = pose["width"], pose["height"]

        if params["skeleton_format"] == "openpose":
            return openpose.render_skeleton(pose.get("openpose_keypoints"), width, height)

        return coco.render_skeleton(pose.get("keypoints"), width, height)

    def _crop_pose_image(self, pose: Dict[str, Any], padding: float) -> Optional[PILImage.Image]:
        # No source frame is retained (only the pose metadata carries forward),
        # so `return_track_image` is a no-op today. Wire the source frame
        # through `_add_poses_to_tracks` if callers need real crops.
        return None

    def _build_tracking_result(
        self,
        track_segments: Dict[int, Dict[str, Any]],
        frame_count: int,
        tracked_frames: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if params["return_metadata"]:
            result["frame_count"] = frame_count

        if params["return_tracks"]:
            min_frame_count = params["min_frame_count"] or 1
            tracks: List[Dict[str, Any]] = []

            for track_id in sorted(track_segments.keys()):
                tracked_segments = track_segments[track_id]["segments"]
                track_frame_count = sum(segment["frame_count"] for segment in tracked_segments)

                if track_frame_count < min_frame_count:
                    continue

                segments: List[Dict[str, Any]] = []

                for tracked_segment in tracked_segments:
                    best_pose = tracked_segment["best_pose"]
                    segment: Dict[str, Any] = {
                        "start_time":   format_timecode(tracked_segment["start"]),
                        "end_time":     format_timecode(tracked_segment["end"]),
                        "duration":     format_timecode(tracked_segment["end"] - tracked_segment["start"]),
                        "score":        best_pose["score"],
                        "bounding_box": self._serialize_bounding_box(best_pose["bounding_box"]),
                    }

                    if params["return_keypoints"] and "keypoints" in best_pose:
                        segment["keypoints"] = best_pose["keypoints"]
                    if params["return_openpose_keypoints"] and "openpose_keypoints" in best_pose:
                        segment["openpose_keypoints"] = best_pose["openpose_keypoints"]
                    if params["return_skeleton_image"]:
                        segment["skeleton_image"] = self._render_skeleton(best_pose, params)
                    if params["return_track_image"]:
                        segment["image"] = self._crop_pose_image(best_pose, params["bounding_box_padding"])

                    segments.append(segment)

                best_segment = max(tracked_segments, key=lambda s: s["best_pose"]["score"])
                best_pose = best_segment["best_pose"]

                tracks.append({
                    "track_id":    int(track_id),
                    "segments":    segments,
                    "frame_count": track_frame_count,
                    "score":       best_pose["score"],
                })

            result["tracks"] = tracks

        if params["return_frames"]:
            result["frames"] = [ self._serialize_tracked_frame(tracked_frame, params) for tracked_frame in tracked_frames ]

        return result

    def _build_track_chunk(
        self,
        track_id: int,
        track: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Snapshot of a track's running aggregates. Emitted whenever a
        track goes idle past `merge_gap`; may be emitted multiple times for
        the same `track_id` if YOLO's tracker reuses the id after a gap —
        each emission is authoritative for the state up to that moment, and
        downstream should treat the latest chunk for a given `track_id` as
        canonical."""
        best_segment = max(track["segments"], key=lambda s: s["best_pose"]["score"])
        best_pose = best_segment["best_pose"]

        return {
            "type":          "track",
            "track_id":      int(track_id),
            "segment_count": len(track["segments"]),
            "frame_count":   sum(segment["frame_count"] for segment in track["segments"]),
            "score":         best_pose["score"],
        }

    def _build_segment_chunk(
        self,
        track_id: int,
        tracked_segment: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        best_pose = tracked_segment["best_pose"]
        segment: Dict[str, Any] = {
            "start_time":   format_timecode(tracked_segment["start"]),
            "end_time":     format_timecode(tracked_segment["end"]),
            "duration":     format_timecode(tracked_segment["end"] - tracked_segment["start"]),
            "frame_count":  tracked_segment["frame_count"],
            "score":        best_pose["score"],
            "bounding_box": self._serialize_bounding_box(best_pose["bounding_box"]),
        }

        if params["return_keypoints"] and "keypoints" in best_pose:
            segment["keypoints"] = best_pose["keypoints"]
        if params["return_openpose_keypoints"] and "openpose_keypoints" in best_pose:
            segment["openpose_keypoints"] = best_pose["openpose_keypoints"]
        if params["return_skeleton_image"]:
            segment["skeleton_image"] = self._render_skeleton(best_pose, params)
        if params["return_track_image"]:
            segment["image"] = self._crop_pose_image(best_pose, params["bounding_box_padding"])

        return {
            "type":     "segment",
            "track_id": int(track_id),
            "segment":  segment,
        }

    def _build_frame_chunk(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        chunk: Dict[str, Any] = {
            "type":      "frame",
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "poses":     [ self._serialize_tracked_pose(tracked_pose, track_id) for tracked_pose, track_id in tracked_frame["tracked_poses"] ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            chunk["image"] = tracked_frame["image"]

        return chunk

    def _serialize_tracked_frame(self, tracked_frame: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        frame: Dict[str, Any] = {
            "number":    tracked_frame["number"],
            "timestamp": format_timecode(tracked_frame["timestamp"]),
            "poses":     [ self._serialize_tracked_pose(tracked_pose, track_id) for tracked_pose, track_id in tracked_frame["tracked_poses"] ],
        }

        if params["return_frame_image"] and "image" in tracked_frame:
            frame["image"] = tracked_frame["image"]

        return frame

    def _serialize_tracked_pose(self, tracked_pose: Dict[str, Any], track_id: int) -> Dict[str, Any]:
        pose: Dict[str, Any] = {
            "track_id":     int(track_id),
            "bounding_box": self._serialize_bounding_box(tracked_pose["bounding_box"]),
        }

        if tracked_pose.get("interpolated"):
            pose["interpolated"] = True

        return pose

    @staticmethod
    def _serialize_bounding_box(bounding_box: Tuple[int, int, int, int]) -> Dict[str, int]:
        x1, y1, x2, y2 = bounding_box

        return { "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1 }

    @staticmethod
    def _bbox_meets_min_size(bounding_box: Tuple[int, int, int, int], min_size: int) -> bool:
        """Whether both sides of `bounding_box` are at least `min_size` pixels."""
        x1, y1, x2, y2 = bounding_box

        return min(x2 - x1, y2 - y1) >= min_size

class YoloPoseTrackingTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[YOLO] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "ultralytics", "lap" ]

    async def _load_model(self) -> None:
        from ultralytics import YOLO

        model_path = await self._provision_model(self.config.model, prefetch=True)
        self.model = YOLO(model_path)

    async def _unload_model(self) -> None:
        self.model = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await YoloPoseTrackingTaskAction(action, self.model).run(context)
