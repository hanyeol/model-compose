from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
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

    def __init__(self, config: InsightfaceFaceTrackingModelActionConfig, model: FaceAnalysis):
        super().__init__(config)

        self.model: FaceAnalysis = model
        self._prepared: bool = False

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_threshold = await context.render_scalar(self.config.params.detection_threshold, float)
        return_gender_age   = await context.render_scalar(self.config.return_gender_age, bool)

        if not 0.0 <= detection_threshold <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {detection_threshold}")

        params["detection_threshold"] = detection_threshold
        params["detection_size"]      = tuple(self.config.params.detection_size)
        params["return_gender_age"]   = return_gender_age

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
        cluster_tracks: Dict[int, Dict[str, Any]] = {}
        centroids_state: Dict[str, Any] = { "centroids": [], "counts": [] }
        frame_count = 0

        def _track_frame(frame: PILImage.Image, timestamp: float) -> None:
            faces = self._detect_frame(frame, params)
            self._cluster_faces(faces, timestamp, centroids_state, cluster_tracks, params)

        async for frame in frames:
            timestamp = offset + frame_count / frame_rate
            await self._run_in_executor(_track_frame, frame, timestamp)
            frame_count += 1

        # Flush any still-open `current` segment so every segment is
        # visible to the result builder.
        for track in cluster_tracks.values():
            if track["current"] is not None:
                track["segments"].append(track["current"])
                track["current"] = None

        logging.debug(f"InsightFace face tracking: {frame_count} frames at offset {offset:.3f}s")

        return self._build_tracking_result(cluster_tracks, centroids_state, frame_count, params)

    def _detect_frame(self, frame: PILImage.Image, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        import numpy as np
        import cv2

        if not self._prepared:
            self.model.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])
            self._prepared = True

        image_cv = cv2.cvtColor(np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR)
        detections = self.model.get(image_cv)

        return self._serialize_faces(detections, image_cv, params["return_image"], params["return_gender_age"])

    def _cluster_faces(
        self,
        faces: List[Dict[str, Any]],
        timestamp: float,
        centroids_state: Dict[str, Any],
        cluster_tracks: Dict[int, Dict[str, Any]],
        params: Dict[str, Any],
    ) -> None:
        import numpy as np

        similarity_threshold     = params["similarity_threshold"] or 0.0
        min_face_size            = params["min_face_size"] or 0
        max_face_count_per_frame = params["max_face_count_per_frame"] or 0
        merge_gap                = params["merge_gap"] or 0.0
        bounding_box_padding     = params["bounding_box_padding"] or 0.0

        candidates = self._filter_faces(faces, min_face_size, max_face_count_per_frame)
        centroids: List[np.ndarray] = centroids_state["centroids"]
        counts: List[int] = centroids_state["counts"]

        # Score every (face, cluster) pair up front, then bind them in descending
        # order so a strong match wins its cluster regardless of detection order.
        # Ties are broken by how much each face overlaps the cluster's last known
        # position, which keeps a moving face from stealing a spatially-distant
        # cluster with a marginally higher embedding score.
        normalized_faces: List[np.ndarray] = []
        for face in candidates:
            embedding = face["embedding"]
            normalized_faces.append(embedding / (np.linalg.norm(embedding) + 1e-12))

        pairs: List[Tuple[float, float, int, int]] = []
        for face_index, normalized in enumerate(normalized_faces):
            face_bbox = candidates[face_index]["bounding_box"]
            for cluster_id, centroid in enumerate(centroids):
                similarity = float(np.dot(normalized, centroid))
                if similarity < similarity_threshold:
                    continue
                last_bbox = cluster_tracks.get(cluster_id, {}).get("last_bbox")
                overlap = self._bbox_overlap(face_bbox, last_bbox) if last_bbox is not None else 0.0
                pairs.append((similarity, overlap, face_index, cluster_id))

        pairs.sort(reverse=True)

        assigned_face: Dict[int, int] = {}
        used_clusters: set = set()
        for similarity, _, face_index, cluster_id in pairs:
            if face_index in assigned_face or cluster_id in used_clusters:
                continue
            assigned_face[face_index] = cluster_id
            used_clusters.add(cluster_id)

        for face_index, face in enumerate(candidates):
            normalized = normalized_faces[face_index]
            cluster_id = assigned_face.get(face_index, -1)

            if cluster_id >= 0:
                count = counts[cluster_id]
                updated = (centroids[cluster_id] * count + normalized) / (count + 1)
                centroids[cluster_id] = updated / (np.linalg.norm(updated) + 1e-12)
                counts[cluster_id] += 1
            else:
                centroids.append(normalized.copy())
                counts.append(1)
                cluster_id = len(centroids) - 1

            self._add_face_to_track(cluster_tracks, cluster_id, timestamp, face, merge_gap, bounding_box_padding)

    def _add_face_to_track(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        cluster_id: int,
        timestamp: float,
        face: Dict[str, Any],
        merge_gap: float,
        bounding_box_padding: float,
    ) -> None:
        """Fold a new detection into its cluster's segment history. The
        cluster's `current` segment is extended if this frame is within
        `merge_gap` of the previous one; otherwise the current segment is
        sealed into `segments` and a fresh one starts. Only the highest-
        scoring frame's image is retained per segment, so memory scales with
        the number of segments rather than the number of frames.

        The face crop is materialized here (lazily) rather than up-front in
        `_serialize_faces`, so frames that never become a segment's best
        never pay the crop / PIL-conversion cost."""
        track = cluster_tracks.setdefault(cluster_id, { "segments": [], "current": None, "last_bbox": None })
        track["last_bbox"] = face["bounding_box"]

        current: Optional[Dict[str, Any]] = track["current"]
        score = face["score"]

        if current is not None and timestamp - current["end"] <= merge_gap:
            current["end"] = timestamp
            current["frame_count"] += 1
            if score > current["best_score"]:
                current["best_score"]  = score
                current["best_image"]  = self._extract_face_image(face, bounding_box_padding)
                current["best_gender"] = face.get("gender")
                current["best_age"]    = face.get("age")
            return

        if current is not None:
            track["segments"].append(current)

        track["current"] = {
            "start":       timestamp,
            "end":         timestamp,
            "frame_count": 1,
            "best_score":  score,
            "best_image":  self._extract_face_image(face, bounding_box_padding),
            "best_gender": face.get("gender"),
            "best_age":    face.get("age"),
        }

    def _serialize_faces(
        self,
        detections: List[Face],
        image_cv: np.ndarray,
        return_image: bool,
        return_gender_age: bool,
    ) -> List[Dict[str, Any]]:
        # Defer cropping to _add_face_to_track: only the frames that actually
        # become a segment's representative are worth converting to PIL, so
        # we pass a reference to the source frame (cheap) instead of eagerly
        # producing an RGB PIL crop for every detection (expensive when a
        # track spans many frames or the input has many candidate faces).
        faces: List[Dict[str, Any]] = []

        for detection in detections:
            x1, y1, x2, y2 = [ int(v) for v in detection.bbox ]
            embedding = getattr(detection, "normed_embedding", None)

            if embedding is None:
                continue

            face: Dict[str, Any] = {
                "embedding":    embedding,
                "bounding_box": { "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1 },
                "score":        float(getattr(detection, "det_score", 0.0)),
            }

            if return_image:
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

    def _build_tracking_result(
        self,
        cluster_tracks: Dict[int, Dict[str, Any]],
        centroids_state: Dict[str, Any],
        frame_count: int,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        min_frame_count = params["min_frame_count"] or 1

        centroids: List[np.ndarray] = centroids_state["centroids"]
        tracks: List[Dict[str, Any]] = []

        for cluster_id in sorted(cluster_tracks.keys()):
            cluster_segments = cluster_tracks[cluster_id]["segments"]
            track_frame_count = sum(segment["frame_count"] for segment in cluster_segments)

            if track_frame_count < min_frame_count:
                continue

            segments: List[Dict[str, Any]] = []

            for cluster_segment in cluster_segments:
                segment = {
                    "start_time": format_timecode(cluster_segment["start"]),
                    "end_time":   format_timecode(cluster_segment["end"]),
                    "duration":   format_timecode(cluster_segment["end"] - cluster_segment["start"]),
                    "score":      cluster_segment["best_score"],
                }

                if params["return_image"]:
                    segment["image"] = cluster_segment["best_image"]

                segments.append(segment)

            best_cluster_segment = max(cluster_segments, key=lambda cluster_segment: cluster_segment["best_score"])

            track: Dict[str, Any] = {
                "segments":    segments,
                "frame_count": track_frame_count,
                "score":       best_cluster_segment["best_score"],
            }

            if params["return_embedding"]:
                track["embedding"] = FaceEmbedding(centroids[cluster_id].tolist())

            if params["return_gender_age"]:
                if best_cluster_segment["best_gender"] is not None:
                    track["gender"] = best_cluster_segment["best_gender"]

                if best_cluster_segment["best_age"] is not None:
                    track["age"] = best_cluster_segment["best_age"]

            tracks.append(track)

        return {
            "tracks":      tracks,
            "frame_count": frame_count,
        }

    @staticmethod
    def _gender_to_label(gender: int) -> str:
        return "male" if gender == 1 else "female"

    def _extract_face_image(self, face: Dict[str, Any], bounding_box_padding: float) -> Optional[PILImage.Image]:
        """Return the face crop for a detection, cropping on demand from the
        source frame when `return_image` was requested. Returns None when the
        crop was not requested (no `image_source` was attached)."""
        image_source = face.get("image_source")

        if image_source is None:
            return None

        return self._crop_face_image(image_source, face["bounding_box"], bounding_box_padding)

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
    def _filter_faces(faces: List[Dict[str, Any]], min_face_size: int, max_face_count_per_frame: int) -> List[Dict[str, Any]]:
        if min_face_size > 0:
            faces = [ face for face in faces if min(face["bounding_box"]["width"], face["bounding_box"]["height"]) >= min_face_size ]

        if max_face_count_per_frame > 0 and len(faces) > max_face_count_per_frame:
            faces = sorted(faces, key=lambda face: face["score"], reverse=True)[:max_face_count_per_frame]

        return faces

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
        return await InsightfaceFaceTrackingTaskAction(action, self.model).run(context)
