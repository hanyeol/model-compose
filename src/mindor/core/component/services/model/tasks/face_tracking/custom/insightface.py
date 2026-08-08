from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, ModelConfig
from mindor.dsl.schema.action import ModelActionConfig, InsightfaceFaceTrackingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import FaceTrackingTaskAction
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

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        detection_threshold = await context.render_scalar(self.config.detection_threshold, float)

        if not 0.0 <= detection_threshold <= 1.0:
            raise ValueError(f"'detection_threshold' must be between 0.0 and 1.0, got {detection_threshold}")

        params["detection_threshold"] = detection_threshold
        params["detection_size"]      = tuple(self.config.detection_size)

        return params

    async def _track(
        self,
        segments: List[Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        def _detect_all() -> List[List[List[Dict[str, Any]]]]:
            import numpy as np
            import cv2

            self.model.prepare(ctx_id=0, det_size=params["detection_size"], det_thresh=params["detection_threshold"])

            segment_frame_faces: List[List[List[Dict[str, Any]]]] = []

            for segment in segments:
                frame_faces: List[List[Dict[str, Any]]] = []

                for frame in segment["frames"]:
                    image_cv = cv2.cvtColor(np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR)
                    detections = self.model.get(image_cv)
                    frame_faces.append(self._serialize_faces(detections, params))

                segment_frame_faces.append(frame_faces)

            return segment_frame_faces

        segment_frame_faces = await self._run_in_executor(_detect_all)
        segment_assignments = self._cluster_faces(segment_frame_faces, params)
        people = self._build_appearances(segment_assignments, segments, params)

        logging.debug(f"InsightFace face tracking: {len(segments)} segments -> {len(people)} people")

        return {
            "people":         people,
            "segment_count":  len(segments),
        }

    def _serialize_faces(self, detections: List[Face], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        min_face_size = params["min_face_size"] or 0
        max_faces_per_frame = params["max_faces_per_frame"] or 0

        faces: List[Dict[str, Any]] = []

        for detection in detections:
            x1, y1, x2, y2 = [ int(v) for v in detection.bbox ]
            width, height = x2 - x1, y2 - y1

            if min_face_size > 0 and min(width, height) < min_face_size:
                continue

            embedding = getattr(detection, "normed_embedding", None)

            if embedding is None:
                continue

            faces.append({
                "embedding":    embedding,
                "bounding_box": [ x1, y1, width, height ],
                "score":        float(getattr(detection, "det_score", 0.0)),
            })

        faces.sort(key=lambda face: face["score"], reverse=True)

        if max_faces_per_frame > 0:
            faces = faces[:max_faces_per_frame]

        return faces

    def _cluster_faces(
        self,
        segment_frame_faces: List[List[List[Dict[str, Any]]]],
        params: Dict[str, Any],
    ) -> List[List[int]]:
        """Assign faces from every frame to running cluster centroids by cosine similarity.

        Returns per-segment lists of cluster ids present anywhere in that segment.
        """
        import numpy as np

        similarity_threshold = params["similarity_threshold"] or 0.0

        centroids: List[np.ndarray] = []
        counts: List[int] = []
        segment_assignments: List[List[int]] = []

        for frame_faces in segment_frame_faces:
            clusters_in_segment: set = set()

            for faces in frame_faces:
                used_in_frame: set = set()

                for face in faces:
                    embedding = face["embedding"]
                    normalized = embedding / (np.linalg.norm(embedding) + 1e-12)

                    best_cluster = -1
                    best_similarity = -1.0

                    for cluster_id, centroid in enumerate(centroids):
                        if cluster_id in used_in_frame:
                            continue

                        similarity = float(np.dot(normalized, centroid))

                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_cluster = cluster_id

                    if best_cluster >= 0 and best_similarity >= similarity_threshold:
                        count = counts[best_cluster]
                        updated = (centroids[best_cluster] * count + normalized) / (count + 1)
                        centroids[best_cluster] = updated / (np.linalg.norm(updated) + 1e-12)
                        counts[best_cluster] += 1
                        cluster_id = best_cluster
                    else:
                        centroids.append(normalized.copy())
                        counts.append(1)
                        cluster_id = len(centroids) - 1

                    used_in_frame.add(cluster_id)
                    clusters_in_segment.add(cluster_id)

            segment_assignments.append(sorted(clusters_in_segment))

        return segment_assignments

    def _build_appearances(
        self,
        segment_assignments: List[List[int]],
        segments: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        clusters: Dict[int, List[Tuple[float, float]]] = {}

        for segment_index, cluster_ids in enumerate(segment_assignments):
            segment = segments[segment_index]
            interval = (segment["start_time"], segment["end_time"])

            for cluster_id in cluster_ids:
                clusters.setdefault(cluster_id, []).append(interval)

        min_appearances = params["min_appearances"] or 1
        merge_gap = params["merge_gap"] or 0.0

        people: List[Dict[str, Any]] = []

        for cluster_id in sorted(clusters.keys()):
            intervals = clusters[cluster_id]

            if len(intervals) < min_appearances:
                continue

            merged = self._merge_intervals(intervals, merge_gap)

            people.append({
                "person_id":     f"person_{len(people) + 1}",
                "cluster_id":    cluster_id,
                "appearances":   [
                    {
                        "start_time": format_timecode(start),
                        "end_time":   format_timecode(end),
                        "duration":   format_timecode(end - start),
                    }
                    for start, end in merged
                ],
                "segment_count": len(intervals),
            })

        return people

    def _merge_intervals(self, intervals: List[Tuple[float, float]], gap: float) -> List[Tuple[float, float]]:
        if not intervals:
            return []

        sorted_intervals = sorted(intervals, key=lambda interval: interval[0])
        merged: List[Tuple[float, float]] = [ sorted_intervals[0] ]

        for start, end in sorted_intervals[1:]:
            last_start, last_end = merged[-1]

            if start - last_end <= gap:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        return merged

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
        params = { "name": name, "root": root }

        try:
            model = FaceAnalysis(**params)
        except:
            self._fix_wrong_model_path(root, name)
            model = FaceAnalysis(**params)

        model.prepare(ctx_id=self._get_device_id())

        return model

    async def _provision_model(self, model: ModelConfig, prefetch: bool = False) -> Tuple[str, str]:
        path = await super()._provision_model(model, prefetch=prefetch)
        root = os.path.dirname(path)
        name = os.path.basename(path)

        if os.path.basename(root) != "models":
            models_dir = os.path.join(root, "models")
            if not os.path.exists(models_dir):
                os.symlink(root, models_dir, target_is_directory=True)
        else:
            root = os.path.dirname(root)

        return (root, name)

    def _fix_wrong_model_path(self, root: str, name: str) -> None:
        model_dir = os.path.join(root, "models", name)
        wrong_model_dir = os.path.join(model_dir, name)

        if os.path.isdir(wrong_model_dir):
            for file in os.listdir(wrong_model_dir):
                shutil.move(os.path.join(wrong_model_dir, file), os.path.join(model_dir, file))
            os.rmdir(wrong_model_dir)

    def _get_device_id(self) -> int:
        return 0

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await InsightfaceFaceTrackingTaskAction(action, self.model).run(context)
