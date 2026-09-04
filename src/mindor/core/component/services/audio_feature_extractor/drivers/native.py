from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.dsl.schema.action.impl.audio_feature_extractor.impl.common import AudioFeature
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.soundfile.audio import load_pcm_samples
from ....action.media import MediaInputPathResolver
from ..base import AudioFeatureExtractorService, AudioFeatureExtractorDriver, register_audio_feature_extractor_service
from ..base import ComponentActionContext
from .common import AudioFeatureExtractorAction, AudioSpectrum, AudioWaveform
import os

if TYPE_CHECKING:
    import numpy as np

class NativeAudioFeatureExtractorAction(AudioFeatureExtractorAction):
    async def _extract_batch(
        self,
        audios: List[MediaSource],
        feature: AudioFeature,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for audio in audios:
            results.append(await self._extract(feature, audio, params, cancellation_token))

        return results

    async def _extract(
        self,
        feature: AudioFeature,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples = await self._load_pcm_samples(source, params["sample_rate"])

        if feature == AudioFeature.SPECTRUM:
            return await self._run_in_executor(self._compute_spectrum, samples, params)

        if feature == AudioFeature.WAVEFORM:
            return await self._run_in_executor(self._compute_waveform, samples, params)

        raise ValueError(f"Unsupported audio feature: {feature}")

    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "audio" ])

        if input_path is None:
            raise ValueError("Native audio feature extractor requires a file-based audio source.")

        try:
            return await self._run_in_executor(load_pcm_samples, input_path, sample_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    def _compute_spectrum(self, samples: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np

        sample_rate = params["sample_rate"]
        fps         = params["fps"]
        band_count  = params["band_count"]
        window_size = params["window_size"]

        hop = max(1, sample_rate // fps)
        frame_count = max(0, (len(samples) - window_size) // hop)

        frequencies = np.fft.rfftfreq(window_size, 1.0 / sample_rate)
        band_indices, band_centers = self._compute_band_indices(
            frequencies,
            band_count,
            params["min_frequency"],
            params["max_frequency"],
            params["frequency_scale"]
        )

        window = self._get_fft_window(params["window_type"], window_size)

        bands = np.zeros((frame_count, band_count), dtype=np.float32)
        for frame in range(frame_count):
            start = frame * hop
            segment = samples[start:start + window_size] * window
            magnitude = np.abs(np.fft.rfft(segment, n=window_size))
            for band, band_index in enumerate(band_indices):
                if band_index.size:
                    bands[frame, band] = magnitude[band_index].mean()
                else:
                    # Band is narrower than the FFT bin spacing (typical in the
                    # low-frequency end when band_count is high relative to
                    # window_size). Sample the magnitude at the band center via
                    # linear interpolation so the bar isn't stuck at zero.
                    bands[frame, band] = np.interp(band_centers[band], frequencies, magnitude)

        frames = self._normalize_spectrum(bands, params["normalize_mode"], params["percentile"])

        return AudioSpectrum({
            "frames": frames.tolist(),
            "fps": fps,
            "band_count": band_count,
            "frame_count": frame_count,
            "duration": frame_count / fps if fps else 0.0,
            "sample_rate": sample_rate,
            "window_size": window_size,
        })

    def _compute_waveform(self, samples: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np

        sample_rate  = params["sample_rate"]
        fps          = params["fps"]
        point_count  = params["point_count"]
        summary_mode = params["summary_mode"]
        rectify      = params["rectify"]

        win = max(point_count, int(sample_rate * params["window_duration"]))
        hop = max(1, sample_rate // fps)
        bucket = win // point_count
        usable = point_count * bucket

        frame_count = max(0, (len(samples) - win) // hop)
        frames = np.zeros((frame_count, point_count), dtype=np.float32)

        for frame in range(frame_count):
            start = frame * hop
            segment = samples[start:start + usable].reshape(point_count, bucket)
            if summary_mode == "peak":
                if rectify:
                    frames[frame] = np.abs(segment).max(axis=1)
                else:
                    peak_pos = segment.max(axis=1)
                    peak_neg = segment.min(axis=1)
                    frames[frame] = np.where(np.abs(peak_pos) >= np.abs(peak_neg), peak_pos, peak_neg)
            else:  # rms
                rms = np.sqrt((segment ** 2).mean(axis=1))
                frames[frame] = rms if rectify else rms * np.sign(segment.mean(axis=1))

        return AudioWaveform({
            "frames": frames.tolist(),
            "fps": fps,
            "point_count": point_count,
            "frame_count": frame_count,
            "duration": frame_count / fps if fps else 0.0,
            "sample_rate": sample_rate,
        })

    @staticmethod
    def _compute_band_indices(
        frequencies: np.ndarray,
        band_count: int,
        min_frequency: float,
        max_frequency: float,
        frequency_scale: str
    ) -> Tuple[List[np.ndarray], np.ndarray]:
        import numpy as np

        if frequency_scale == "log":
            min_frequency_safe = max(min_frequency, 1e-3)
            edges = np.logspace(np.log10(min_frequency_safe), np.log10(max_frequency), band_count + 1)
            centers = np.sqrt(edges[:-1] * edges[1:])
        else:
            edges = np.linspace(min_frequency, max_frequency, band_count + 1)
            centers = (edges[:-1] + edges[1:]) * 0.5

        indices = [ np.where((frequencies >= edges[band]) & (frequencies < edges[band + 1]))[0] for band in range(band_count) ]

        return indices, centers

    @staticmethod
    def _get_fft_window(name: str, size: int) -> np.ndarray:
        import numpy as np

        return {
            "hann":     np.hanning,
            "hamming":  np.hamming,
            "blackman": np.blackman,
        }[name](size).astype(np.float32)

    @staticmethod
    def _normalize_spectrum(bands: np.ndarray, mode: str, percentile: float) -> np.ndarray:
        import numpy as np

        if bands.size == 0 or mode == "none":
            return bands

        if mode == "peak-percentile":
            scale = np.percentile(bands, percentile) or 1.0
            return np.clip(np.sqrt(bands / scale), 0.0, 1.0)

        return bands

@register_audio_feature_extractor_service(AudioFeatureExtractorDriver.NATIVE)
class NativeAudioFeatureExtractorService(AudioFeatureExtractorService):
    def __init__(self, id: str, config: AudioFeatureExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy", "soundfile", "librosa" ]

    async def _run(
        self,
        action: AudioFeatureExtractorActionConfig,
        context: ComponentActionContext,
    ) -> Any:
        return await NativeAudioFeatureExtractorAction(action).run(context)
