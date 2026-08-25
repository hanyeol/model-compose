from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from mindor.dsl.schema.component import MusicSegmentDetectorComponentConfig
from mindor.dsl.schema.action import MusicSegmentDetectorActionConfig
from mindor.dsl.schema.action.impl.music_segment_detector.impl.native import NativeMusicSegmentDetectorStrategy
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ..base import MusicSegmentDetectorService, MusicSegmentDetectorDriver, register_music_segment_detector_service
from ..base import ComponentActionContext
from .common import MusicSegmentDetectorAction
import os

if TYPE_CHECKING:
    import numpy as np

# Chroma analysis hop length in samples. At the default sample_rate=22050 this
# gives ~23ms frames; boundaries and min_segment_duration snap to this grid.
_CHROMA_HOP_LENGTH = 512

# Deterministic seed so repeated runs over the same audio return identical
# labels. Not user-tunable — reproducibility beats per-run variety here.
_KMEANS_RNG_SEED = 0

# Maximum number of structural roles k-means considers when labeling segments.
# Real songs rarely have more than ~4 distinct sections (verse/chorus/bridge/outro).
_MAX_STRUCTURAL_LABELS = 4

# Agglomerative fallback: target ~one segment per this many seconds of audio,
# clamped to [_MIN_AGG_SEGMENTS, _MAX_AGG_SEGMENTS].
_AGG_TARGET_SECONDS_PER_SEGMENT = 10.0
_MIN_AGG_SEGMENTS = 2
_MAX_AGG_SEGMENTS = 12

# --- Laplacian (McFee-style spectral clustering) --------------------------

# Number of MFCC coefficients used for the timbre stream. 13 is the standard
# choice in music information retrieval — enough to distinguish instrumentation
# (drums, vocals, strings) without overfitting to fine spectral detail.
_MFCC_N_COEFFS = 13

# Weight of the harmonic (chroma) recurrence versus the timbre (MFCC) path
# similarity when combining them into a single affinity matrix. McFee's recipe
# picks μ from the median degrees of the two graphs; this constant is our fixed
# fallback when either graph is degenerate.
_LAPLACIAN_DEFAULT_MU = 0.5

# Search range for the number of structural clusters k. eigengap heuristic
# picks a k with a large jump in the eigenvalue spectrum within this range.
# Upper bound reflects that real songs rarely have more than ~8 distinct
# structural roles.
_LAPLACIAN_K_MIN = 2
_LAPLACIAN_K_MAX = 8

# When multiple k values give nearly-equal eigengaps, plain argmax always
# picks the smallest (coarsest) k and collapses the song into 2 sections. To
# prefer richer structure in ambiguous cases, we accept any k whose gap is at
# least this fraction of the best gap and among those pick the largest k.
# Value close to 1.0 = strict (behaves like argmax); lower = more permissive.
_LAPLACIAN_GAP_TOLERANCE = 0.9

# Recurrence matrix width parameter passed to librosa.segment.recurrence_matrix.
# It suppresses similarity within `±width` frames of the diagonal, so the
# graph highlights *long-range* repetition (verse → chorus recurring later)
# rather than trivial adjacent-frame similarity. width=3 matches McFee's
# reference recipe.
_RECURRENCE_WIDTH = 3

# Odd window (in beats) used to smooth the raw per-beat cluster assignment via
# a majority filter. Suppresses single-beat flickers without erasing real
# section boundaries. Kept small (5 beats ≈ one bar at 4/4) so genuine short
# sections like an 8-beat pre-chorus survive.
_LABEL_SMOOTHING_WINDOW = 5

class NativeMusicSegmentDetectorAction(MusicSegmentDetectorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        strategy = await context.render_variable(self.config.strategy)

        try:
            strategy = NativeMusicSegmentDetectorStrategy(strategy)
        except ValueError:
            raise ValueError(f"Invalid strategy: {strategy}")

        params.update({
            "strategy": strategy,
        })

        return params

    async def _detect_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for audio in audios:
            results.append(await self._detect(audio, params, cancellation_token))

        return results

    async def _detect(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        sample_rate = params["sample_rate"]
        strategy    = params["strategy"]

        samples = await self._load_pcm_samples(source, sample_rate)

        def _detect(samples: np.ndarray) -> Dict[str, Any]:
            segments = self._detect_segments(samples, sample_rate, strategy)
            segments = self._merge_short_segments(segments, params["min_segment_duration"])
            duration = len(samples) / sample_rate if sample_rate else 0.0

            return {
                "segments": segments,
                "duration": duration,
                "sample_rate": sample_rate,
            }

        return await self._run_in_executor(_detect, samples)

    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        if input_path is None:
            raise ValueError("Native audio segment detector requires a file-based audio source.")

        try:
            return await self._run_in_executor(load_pcm_samples, input_path, sample_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    def _detect_segments(self, samples: np.ndarray, sample_rate: int, strategy: str) -> List[Dict[str, Any]]:
        import numpy as np
        import librosa

        if samples.size == 0:
            return []

        duration = float(len(samples) / sample_rate) if sample_rate else 0.0

        # Chroma-CQT captures harmonic structure — better for music than STFT chroma.
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate, hop_length=_CHROMA_HOP_LENGTH)

        if chroma.shape[1] < 2:
            return [ { "start_time": 0.0, "end_time": duration, "label": "A" } ]

        # Some strategies (laplacian) produce boundaries and labels together
        # from a single spectral embedding; others (agglomerative) produce only
        # boundaries and require a separate labeling pass.
        boundary_frames, precomputed_labels = self._compute_boundaries_and_labels(
            samples, chroma, sample_rate, strategy,
        )
        boundary_times = librosa.frames_to_time(boundary_frames, sr=sample_rate, hop_length=_CHROMA_HOP_LENGTH).tolist()

        # Snap the timeline to [0.0, duration]. frames_to_time can produce a
        # tail slightly past `duration` because chroma frames extend to the end
        # of the last full hop; clamp both ends explicitly.
        if not boundary_times or boundary_times[0] > 0.0:
            boundary_times = [ 0.0 ] + boundary_times

        boundary_times[-1] = duration if boundary_times[-1] > duration else boundary_times[-1]

        if boundary_times[-1] < duration:
            boundary_times.append(duration)

        cluster_ids = precomputed_labels if precomputed_labels is not None else self._cluster_segments(chroma, boundary_frames)
        cluster_ids = self._normalize_labels(cluster_ids)

        segments: List[Dict[str, Any]] = []

        for index in range(len(boundary_times) - 1):
            start_time = float(boundary_times[index])
            end_time   = float(boundary_times[index + 1])

            if end_time <= start_time:
                continue

            label = self._format_label(int(cluster_ids[index]))

            # Merge adjacent segments that share a label: label-aware smoothing
            # inside a stable section leaves boundary times that split one real
            # section into fragments carrying identical labels. Downstream
            # merging by min_duration cannot fix this — it only sees short
            # neighbours — so we collapse label-runs here where the labels are
            # still authoritative.
            if segments and segments[-1]["label"] == label:
                segments[-1]["end_time"] = end_time
                continue

            segments.append({ "start_time": start_time, "end_time": end_time, "label": label })

        return segments

    def _compute_boundaries_and_labels(
        self,
        samples: np.ndarray,
        chroma: np.ndarray,
        sample_rate: int,
        strategy: str,
    ) -> "tuple[np.ndarray, Optional[np.ndarray]]":
        """Return (boundary_frames_in_chroma_frames, optional_segment_labels).

        Both entries are aligned so the i-th segment (between boundary[i] and
        boundary[i+1]) has label labels[i] when labels are returned. Strategies
        that don't produce labels return None for the second element and let
        the caller run a separate labeling pass.
        """
        import numpy as np
        import librosa

        if strategy == NativeMusicSegmentDetectorStrategy.AGGLOMERATIVE:
            # Target one segment per _AGG_TARGET_SECONDS_PER_SEGMENT of audio,
            # clamped to a sensible range. librosa's agglomerative segmenter
            # needs k up-front, so we pick k from the audio length rather than
            # from raw frame count (which would drift with hop_length changes).
            frames_per_second = (sample_rate / _CHROMA_HOP_LENGTH) if sample_rate else 0.0
            approx_seconds = chroma.shape[1] / frames_per_second if frames_per_second else 0.0
            k = int(round(approx_seconds / _AGG_TARGET_SECONDS_PER_SEGMENT))
            k = max(_MIN_AGG_SEGMENTS, min(_MAX_AGG_SEGMENTS, k))
            # librosa returns segment *start* frames only (no trailing end);
            # append chroma.shape[1] so _cluster_segments sees N boundaries →
            # (N-1) segments, matching the laplacian path's convention.
            starts = librosa.segment.agglomerative(chroma, k=k)
            boundaries = np.concatenate([ starts, [ chroma.shape[1] ] ]).astype(int)
            return boundaries, None

        # McFee & Ellis (2014) style spectral clustering:
        #   beat-sync chroma + MFCC → combined recurrence graph → symmetric
        #   normalized Laplacian → k eigenvectors as embedding → k-means on the
        #   embedding produces per-beat labels; segment boundaries are the
        #   points where the label sequence changes.
        try:
            beat_frames, sync_chroma, sync_mfcc = self._beat_synchronize_features(
                samples, sample_rate, chroma,
            )
        except Exception:
            # Beat tracking can fail on very short or extreme inputs; fall back
            # to per-frame analysis rather than crashing.
            beat_frames = np.arange(chroma.shape[1], dtype=int)
            sync_chroma = chroma
            sync_mfcc = self._compute_mfcc(samples, sample_rate)

        if sync_chroma.shape[1] < 2:
            return np.array([ 0, chroma.shape[1] ], dtype=int), np.array([ 0 ])

        affinity = self._build_combined_affinity(sync_chroma, sync_mfcc)
        embedding = self._laplacian_embedding(affinity)

        if embedding is None:
            return np.array([ 0, chroma.shape[1] ], dtype=int), np.array([ 0 ])

        beat_labels = self._cluster_embedding(embedding)

        # Convert per-beat labels back to chroma-frame boundaries. Consecutive
        # beats with the same label collapse into one segment; the boundary
        # frame is the chroma frame index at the start of each label run.
        # Force the first boundary to frame 0 so the leading gap before the
        # first detected beat (if any) is absorbed into the opening segment
        # rather than becoming an unlabeled segment downstream.
        boundaries_list: List[int] = [ 0 ]
        segment_labels: List[int] = [ int(beat_labels[0]) ]

        for i in range(1, len(beat_labels)):
            if int(beat_labels[i]) != segment_labels[-1]:
                boundaries_list.append(int(beat_frames[i]))
                segment_labels.append(int(beat_labels[i]))

        boundaries_list.append(chroma.shape[1])
        boundaries = np.array(boundaries_list, dtype=int)
        labels = np.array(segment_labels, dtype=int)

        return boundaries, labels

    def _beat_synchronize_features(
        self,
        samples: np.ndarray,
        sample_rate: int,
        chroma: np.ndarray,
    ) -> "tuple[np.ndarray, np.ndarray, np.ndarray]":
        """Detect beats and aggregate chroma/MFCC by beat. Returns (beat_frames,
        beat_synced_chroma, beat_synced_mfcc). Beat frames are indexed in the
        same hop grid as `chroma` so callers can map back to time.
        """
        import numpy as np
        import librosa

        _, beat_frames = librosa.beat.beat_track(
            y=samples, sr=sample_rate, hop_length=_CHROMA_HOP_LENGTH, trim=False,
        )

        # beat_track can return an empty array on very short or arrhythmic
        # audio; without beats we degenerate to per-frame analysis.
        if beat_frames.size == 0:
            beat_frames = np.arange(chroma.shape[1], dtype=int)

        mfcc = self._compute_mfcc(samples, sample_rate)

        sync_chroma = librosa.util.sync(chroma, beat_frames, aggregate=np.median)
        sync_mfcc   = librosa.util.sync(mfcc,   beat_frames, aggregate=np.mean)

        return beat_frames, sync_chroma, sync_mfcc

    @staticmethod
    def _compute_mfcc(samples: np.ndarray, sample_rate: int) -> np.ndarray:
        import librosa
        return librosa.feature.mfcc(
            y=samples, sr=sample_rate, hop_length=_CHROMA_HOP_LENGTH, n_mfcc=_MFCC_N_COEFFS,
        )

    def _build_combined_affinity(self, chroma: np.ndarray, mfcc: np.ndarray) -> np.ndarray:
        """Combine two views of the beat-sync features into one affinity matrix:
        chroma recurrence (captures repetition of harmonic content across the
        song) and MFCC path similarity (captures local timbre continuity). The
        mix weight balances the two so neither dominates the graph degree.
        """
        import numpy as np
        import librosa

        # Recurrence on chroma: which beats sound harmonically like which other
        # beats anywhere in the song. `width=_RECURRENCE_WIDTH` suppresses
        # trivial similarity to immediately-adjacent beats so the graph is
        # driven by long-range repetition (verse → chorus recurring later).
        recurrence = librosa.segment.recurrence_matrix(chroma, mode="affinity", sym=True, width=_RECURRENCE_WIDTH)

        # Recurrence on MFCC captures per-pair timbre similarity across the
        # song (drums/vocals/instrumentation), giving a second view that
        # separates sections which share a chord progression but differ in
        # arrangement.
        mfcc_affinity = librosa.segment.recurrence_matrix(mfcc, mode="affinity", sym=True, width=_RECURRENCE_WIDTH)

        # μ balances the two graphs by median degree — McFee's trick to avoid
        # one graph dominating simply because it has more nonzero entries.
        rec_degree = np.median(np.sum(recurrence, axis=1))
        mfcc_degree = np.median(np.sum(mfcc_affinity, axis=1))
        total = rec_degree + mfcc_degree
        mu = (mfcc_degree / total) if total > 0 else _LAPLACIAN_DEFAULT_MU

        return mu * recurrence + (1.0 - mu) * mfcc_affinity

    @staticmethod
    def _laplacian_embedding(affinity: np.ndarray) -> Optional[np.ndarray]:
        """Symmetric normalized Laplacian eigendecomposition, returning the
        first k eigenvectors as an embedding. k is chosen by the eigengap
        heuristic within [_LAPLACIAN_K_MIN, _LAPLACIAN_K_MAX].

        The returned matrix has shape (n_nodes, k). Rows are row-normalized so
        k-means on them approximates spherical k-means (Ng, Jordan & Weiss).
        """
        import numpy as np

        n = affinity.shape[0]
        degree = np.sum(affinity, axis=1)
        degree[degree == 0] = 1.0
        d_inv_sqrt = 1.0 / np.sqrt(degree)
        laplacian = np.eye(n) - (affinity * d_inv_sqrt[:, None] * d_inv_sqrt[None, :])

        try:
            eigvals, eigvecs = np.linalg.eigh(laplacian)
        except np.linalg.LinAlgError:
            return None

        # Eigengap heuristic within the allowed k range. Plain argmax always
        # falls back to the smallest k when several candidates are near-equal,
        # which coarsens ambiguous songs into just two sections. Instead we
        # find the best gap, then accept any k whose gap is within
        # _LAPLACIAN_GAP_TOLERANCE of the best, and pick the largest such k —
        # preferring finer structure when the data supports it.
        k_max = min(_LAPLACIAN_K_MAX, n - 1)
        k_min = min(_LAPLACIAN_K_MIN, k_max)

        gaps = { k: float(eigvals[k] - eigvals[k - 1]) for k in range(k_min, k_max + 1) }
        best_gap = max(gaps.values())
        threshold = best_gap * _LAPLACIAN_GAP_TOLERANCE
        best_k = max(k for k, g in gaps.items() if g >= threshold)

        embedding = eigvecs[:, :best_k]

        # Row-normalize (Ng-Jordan-Weiss) so k-means clusters by direction, not
        # magnitude. Zero-length rows fall back to zeros (won't attract points).
        norms = np.linalg.norm(embedding, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embedding / norms

    def _cluster_embedding(self, embedding: np.ndarray) -> np.ndarray:
        k = embedding.shape[1]
        raw_labels = self._cluster_kmeans(embedding, k)
        return self._majority_smooth(raw_labels, _LABEL_SMOOTHING_WINDOW)

    @staticmethod
    def _majority_smooth(labels: np.ndarray, window: int) -> np.ndarray:
        """Replace each label with the majority label in a centered window of
        `window` beats (window must be odd). Edges use whatever window fits.
        This suppresses single-beat flickers while leaving multi-beat runs
        intact — genuine boundaries survive because they are supported by many
        consecutive beats on both sides.
        """
        import numpy as np

        n = len(labels)
        if n <= 1 or window <= 1:
            return labels

        half = window // 2
        smoothed = np.empty_like(labels)

        for i in range(n):
            lo = max(0, i - half)
            hi = min(n, i + half + 1)
            window_slice = labels[lo:hi]
            values, counts = np.unique(window_slice, return_counts=True)
            smoothed[i] = int(values[int(np.argmax(counts))])

        return smoothed

    def _cluster_segments(self, chroma: np.ndarray, boundary_frames: np.ndarray) -> np.ndarray:
        import numpy as np

        boundaries = np.asarray(boundary_frames, dtype=int)

        # Mean chroma per segment as a compact fingerprint for clustering.
        segment_features: List[np.ndarray] = []

        for index in range(len(boundaries) - 1):
            start = boundaries[index]
            end = max(start + 1, boundaries[index + 1])
            segment_features.append(chroma[:, start:end].mean(axis=1))

        features = np.stack(segment_features, axis=0)
        k = max(1, min(len(features), _MAX_STRUCTURAL_LABELS))

        return self._cluster_kmeans(features, k)

    @staticmethod
    def _normalize_labels(cluster_ids: np.ndarray) -> np.ndarray:
        """Relabel clusters so the first segment is always A, the next new
        cluster is B, etc. Makes results interpretable independently of the
        arbitrary order k-means assigned to centroids.
        """
        import numpy as np

        remap: Dict[int, int] = {}
        normalized = np.empty_like(cluster_ids)

        for index, cluster in enumerate(cluster_ids.tolist()):
            if cluster not in remap:
                remap[cluster] = len(remap)
            normalized[index] = remap[cluster]

        return normalized

    @staticmethod
    def _cluster_kmeans(features: np.ndarray, k: int, iterations: int = 20) -> np.ndarray:
        import numpy as np

        if k <= 1 or len(features) <= 1:
            return np.zeros(len(features), dtype=int)

        rng = np.random.default_rng(_KMEANS_RNG_SEED)

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
            distances = np.stack([ np.sum((features - centroid) ** 2, axis=1) for centroid in centroids ], axis=1)
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

@register_music_segment_detector_service(MusicSegmentDetectorDriver.NATIVE)
class NativeMusicSegmentDetectorService(MusicSegmentDetectorService):
    def __init__(self, id: str, config: MusicSegmentDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "librosa", "numpy", "soundfile" ]

    async def _run(
        self,
        action: MusicSegmentDetectorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeMusicSegmentDetectorAction(action).run(context)
