from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from mindor.dsl.schema.component import AudioSegmentDetectorComponentConfig
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from mindor.dsl.schema.action.impl.audio_segment_detector.impl.common import AudioSegmentDetectorStrategy
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ..base import AudioSegmentDetectorService, AudioSegmentDetectorDriver, register_audio_segment_detector_service
from ..base import ComponentActionContext
from .common import AudioSegmentDetectorAction
import os

if TYPE_CHECKING:
    import numpy as np

class NativeAudioSegmentDetectorAction(AudioSegmentDetectorAction):
    def _detect_segments(self, samples: np.ndarray, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        import numpy as np
        import librosa

        sample_rate   = params["sample_rate"]
        strategy      = params["strategy"]
        return_labels = params["return_labels"]

        if samples.size == 0:
            return []

        hop_length = 512
        # Chroma-CQT captures harmonic structure — better for music than STFT chroma.
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate, hop_length=hop_length)

        if chroma.shape[1] < 2:
            duration = len(samples) / sample_rate if sample_rate else 0.0
            segment: Dict[str, Any] = { "start_time": 0.0, "end_time": float(duration) }
            if return_labels:
                segment["label"] = "A"
            return [ segment ]

        boundary_frames = self._compute_boundaries(chroma, strategy)
        boundary_times = librosa.frames_to_time(boundary_frames, sr=sample_rate, hop_length=hop_length).tolist()

        # Ensure the segmentation spans the full audio.
        duration = float(len(samples) / sample_rate) if sample_rate else 0.0
        if not boundary_times or boundary_times[0] > 0.0:
            boundary_times = [ 0.0 ] + boundary_times
        if boundary_times[-1] < duration:
            boundary_times = boundary_times + [ duration ]

        labels = self._compute_labels(chroma, boundary_frames) if return_labels else None

        segments: List[Dict[str, Any]] = []
        for index in range(len(boundary_times) - 1):
            start_time = float(boundary_times[index])
            end_time = float(boundary_times[index + 1])
            if end_time <= start_time:
                continue
            segment: Dict[str, Any] = { "start_time": start_time, "end_time": end_time }
            if return_labels:
                if labels is not None and index < len(labels):
                    segment["label"] = self._format_label(int(labels[index]))
                else:
                    segment["label"] = self._format_label(index)
            segments.append(segment)

        return segments

    def _compute_boundaries(self, chroma: np.ndarray, strategy: str) -> np.ndarray:
        import numpy as np
        import librosa

        if strategy == AudioSegmentDetectorStrategy.AGGLOMERATIVE:
            # Fixed cluster count fallback (~8) — librosa's agglomerative segmenter needs k up-front.
            k = max(2, min(8, chroma.shape[1] // 8 or 2))
            return librosa.segment.agglomerative(chroma, k=k)

        # Laplacian segmentation via recurrence-matrix eigendecomposition.
        # Follows the librosa "Laplacian segmentation" recipe.
        recurrence = librosa.segment.recurrence_matrix(chroma, mode="affinity", sym=True)
        degree = np.sum(recurrence, axis=1)
        degree[degree == 0] = 1.0
        laplacian = np.eye(recurrence.shape[0]) - (recurrence / degree[:, None])

        try:
            eigvals, eigvecs = np.linalg.eigh(laplacian)
        except np.linalg.LinAlgError:
            return np.array([ 0, chroma.shape[1] ], dtype=int)

        # Use the second eigenvector (Fiedler vector) sign changes as boundary candidates.
        fiedler = eigvecs[:, 1] if eigvecs.shape[1] > 1 else eigvecs[:, 0]
        sign_changes = np.where(np.diff(np.sign(fiedler)) != 0)[0] + 1

        boundaries = np.concatenate(([ 0 ], sign_changes, [ chroma.shape[1] ])).astype(int)
        return np.unique(boundaries)

    def _compute_labels(self, chroma: np.ndarray, boundary_frames: np.ndarray) -> Optional[np.ndarray]:
        import numpy as np

        boundaries = np.asarray(boundary_frames, dtype=int)

        if boundaries.size < 2:
            return None

        # Mean chroma per segment as a compact fingerprint for clustering.
        segment_features: List[np.ndarray] = []

        for index in range(len(boundaries) - 1):
            start = boundaries[index]
            end = max(start + 1, boundaries[index + 1])
            segment_features.append(chroma[:, start:end].mean(axis=1))

        features = np.stack(segment_features, axis=0)
        k = max(1, min(len(features), 4))

        return self._kmeans(features, k)

    @staticmethod
    def _kmeans(features: np.ndarray, k: int, iterations: int = 20) -> np.ndarray:
        import numpy as np

        if k <= 1 or len(features) <= 1:
            return np.zeros(len(features), dtype=int)

        rng = np.random.default_rng(0)

        # k-means++ seeding
        first = int(rng.integers(len(features)))
        centroids = [ features[first] ]
        for _ in range(k - 1):
            distances = np.min(
                np.stack([ np.sum((features - c) ** 2, axis=1) for c in centroids ], axis=0),
                axis=0,
            )
            total = distances.sum()
            if total <= 0:
                index = int(rng.integers(len(features)))
            else:
                index = int(rng.choice(len(features), p=distances / total))
            centroids.append(features[index])
        centroids = np.stack(centroids)

        labels = np.zeros(len(features), dtype=int)
        for _ in range(iterations):
            distances = np.stack([ np.sum((features - c) ** 2, axis=1) for c in centroids ], axis=1)
            new_labels = np.argmin(distances, axis=1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            for cluster in range(k):
                mask = labels == cluster
                if mask.any():
                    centroids[cluster] = features[mask].mean(axis=0)

        return labels

    @staticmethod
    def _format_label(index: int) -> str:
        # A, B, ..., Z, AA, AB, ...
        letters = ""
        value = index
        while True:
            letters = chr(ord("A") + value % 26) + letters
            value = value // 26 - 1
            if value < 0:
                break
        return letters

    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await MediaInputPathResolver.resolve(source)

        try:
            return await self._run_in_executor(load_pcm_samples, input_path, sample_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

@register_audio_segment_detector_service(AudioSegmentDetectorDriver.NATIVE)
class NativeAudioSegmentDetectorService(AudioSegmentDetectorService):
    def __init__(self, id: str, config: AudioSegmentDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "librosa", "numpy", "soundfile" ]

    async def _run(
        self,
        action: AudioSegmentDetectorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeAudioSegmentDetectorAction(action).run(context)
