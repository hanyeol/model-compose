from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
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
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for frames, offset in zip(frames_batch, offsets_batch):
            result = await self._track(frames, float(offset or 0.0), frame_rate, params)
            results.append(result)

        return results

    async def _track(
        self,
        frames: ImageArrayValue,
        offset: float,
        frame_rate: float,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        # `track_segments[track_id]` holds `{ "segments": [...], "current": {...} }`.
        # `current` is the open segment being extended by contiguous frames;
        # `segments` is the sealed history. Segment shape mirrors face_tracking so
        # only the highest-scoring frame's pose data is retained per segment.
        track_segments: Dict[int, Dict[str, Any]] = {}
        tracked_frames: List[Dict[str, Any]] = []
        frame_period = 1.0 / frame_rate
        frame_count = 0

        def _track_frame(frame: PILImage.Image, timestamp: float) -> None:
            poses = self._detect_frame(frame, params)
            assigned = self._add_poses_to_tracks(poses, timestamp, frame_period, track_segments, params)

            if params["return_frames"]:
                tracked_frames.append({
                    "number":    frame_count + 1,
                    "timestamp": format_timecode(timestamp),
                    "poses":     [
                        { "track_id": int(track_id), "bounding_box": pose["bounding_box"] }
                        for pose, track_id in assigned
                    ],
                })

        async for frame in frames:
            timestamp = offset + frame_count / frame_rate
            await self._run_in_executor(_track_frame, frame, timestamp)
            frame_count += 1

        # Flush any still-open `current` segment so every segment is
        # visible to the result builder.
        for track in track_segments.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None

        logging.debug(f"YOLO pose tracking: {frame_count} frames at offset {offset:.3f}s")

        return await self._run_in_executor(self._build_tracking_result, track_segments, frame_count, tracked_frames, params)

    def _detect_frame(self, frame: PILImage.Image, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        # `persist=True` keeps the tracker state alive across successive frames
        # of the same video so track ids are stable. `max_pose_count_per_frame`
        # caps detections up front; the tracker consumes what YOLO returns.
        max_det = params["max_pose_count_per_frame"] or 300

        predictions = self.model.track(
            source=frame.convert("RGB"),
            conf=params["min_confidence"],
            max_det=max_det,
            tracker=params["tracker"],
            persist=True,
            verbose=False,
        )

        prediction = predictions[0]
        width, height = frame.size

        return self._serialize_poses(prediction, width, height, params)

    def _serialize_poses(
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
            conf_row = keypoints_conf[index] if keypoints_conf is not None else None
            pose_keypoints = self._serialize_keypoints(keypoints_xy[index], conf_row, min_visibility) if needs_keypoints else None
            openpose_keypoints = coco.to_body_18(pose_keypoints) if needs_openpose_keypoints else None

            pose: Dict[str, Any] = {
                "track_id":     int(track_ids[index]),
                "bounding_box": self._serialize_bounding_box(boxes_xyxy[index]),
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

    def _add_poses_to_tracks(
        self,
        poses: List[Dict[str, Any]],
        timestamp: float,
        frame_period: float,
        track_segments: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Tuple[Dict[str, Any], int]]:
        """Fold a new detection into its track's segment history. The track's
        `current` segment is extended if this frame is within one frame period
        plus `merge_gap` of the previous one; otherwise the current segment is
        sealed into `segments` and a fresh one starts. The frame-period
        baseline means `merge_gap` measures how long a person may go undetected
        before the segment is split, not how far apart two detections may be —
        consecutive frames always merge, so `merge_gap=0` does what a user
        naïvely expects. Returns the `(pose, track_id)` pairs bound in this
        frame so the caller can materialize a per-frame view when requested."""
        merge_gap = params["merge_gap"] or 0.0
        assigned: List[Tuple[Dict[str, Any], int]] = []

        for pose in poses:
            track_id = pose["track_id"]
            track = track_segments.setdefault(track_id, { "segments": [], "current": None })
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
                assigned.append((pose, track_id))
                continue

            if current is not None:
                track["segments"].append(current)

            track["current"] = {
                "start":       timestamp,
                "end":         timestamp,
                "frame_count": 1,
                "best_pose":   pose,
            }
            assigned.append((pose, track_id))

        return assigned

    def _build_tracking_result(
        self,
        track_segments: Dict[int, Dict[str, Any]],
        frame_count: int,
        tracked_frames: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "frame_count": frame_count,
        }

        if params["return_tracks"]:
            min_frame_count = params["min_frame_count"] or 1
            tracks: List[Dict[str, Any]] = []

            for track_id in sorted(track_segments.keys()):
                raw_segments = track_segments[track_id]["segments"]
                track_frame_count = sum(segment["frame_count"] for segment in raw_segments)

                if track_frame_count < min_frame_count:
                    continue

                segments: List[Dict[str, Any]] = []

                for raw_segment in raw_segments:
                    best_pose = raw_segment["best_pose"]
                    segment: Dict[str, Any] = {
                        "start_time":   format_timecode(raw_segment["start"]),
                        "end_time":     format_timecode(raw_segment["end"]),
                        "duration":     format_timecode(raw_segment["end"] - raw_segment["start"]),
                        "score":        best_pose["score"],
                        "bounding_box": best_pose["bounding_box"],
                    }

                    if params["return_keypoints"] and "keypoints" in best_pose:
                        segment["keypoints"] = best_pose["keypoints"]
                    if params["return_openpose_keypoints"] and "openpose_keypoints" in best_pose:
                        segment["openpose_keypoints"] = best_pose["openpose_keypoints"]
                    if params["return_skeleton_image"]:
                        segment["skeleton_image"] = self._render_skeleton(best_pose, params)
                    if params["return_image"]:
                        segment["image"] = self._extract_pose_image(best_pose, params["bounding_box_padding"])

                    segments.append(segment)

                best_segment = max(raw_segments, key=lambda s: s["best_pose"]["score"])
                best_pose = best_segment["best_pose"]

                tracks.append({
                    "track_id":    int(track_id),
                    "segments":    segments,
                    "frame_count": track_frame_count,
                    "score":       best_pose["score"],
                })

            result["tracks"] = tracks

        if params["return_frames"]:
            result["frames"] = tracked_frames

        return result

    def _render_skeleton(self, pose: Dict[str, Any], params: Dict[str, Any]) -> Optional[PILImage.Image]:
        width, height = pose["width"], pose["height"]

        if params["skeleton_format"] == "openpose":
            return openpose.render_skeleton(pose.get("openpose_keypoints"), width, height)

        return coco.render_skeleton(pose.get("keypoints"), width, height)

    def _extract_pose_image(self, pose: Dict[str, Any], padding: float) -> Optional[PILImage.Image]:
        # No source frame is retained (only the pose metadata carries forward),
        # so `return_image` is a no-op today. Wire the source frame through
        # `_add_poses_to_tracks` if callers need real crops.
        return None

    def _serialize_keypoints(
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

    @staticmethod
    def _serialize_bounding_box(box_xyxy: np.ndarray) -> Dict[str, int]:
        x1, y1, x2, y2 = box_xyxy

        return { "x": int(x1), "y": int(y1), "width": int(x2 - x1), "height": int(y2 - y1) }

    @staticmethod
    def _filter_poses(
        poses: List[Dict[str, Any]],
        min_pose_size: int,
        max_pose_count_per_frame: int,
    ) -> List[Dict[str, Any]]:
        if min_pose_size > 0:
            poses = [ pose for pose in poses if min(pose["bounding_box"]["width"], pose["bounding_box"]["height"]) >= min_pose_size ]

        if max_pose_count_per_frame > 0 and len(poses) > max_pose_count_per_frame:
            poses = sorted(poses, key=lambda pose: pose["score"], reverse=True)[:max_pose_count_per_frame]

        return poses

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
